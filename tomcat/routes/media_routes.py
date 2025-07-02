"""
Media Routes for TomCat Application

This module handles all routes related to media serving and processing,
including thumbnails, lowmag images, tilt series and tomogram animations.
"""
import os
import logging
from flask import Blueprint, send_from_directory, jsonify, request, url_for

logger = logging.getLogger(__name__)

# Create a Blueprint for media routes
media_bp = Blueprint('media', __name__)


# tomcat/routes/media_routes.py

def initialize_routes(config, media_manager):
    """
    Initialize media routes with required dependencies.
    """

    @media_bp.route('/serve_media/<media_type>/<tomo_name>')
    def serve_media(media_type, tomo_name):
        media_dir = os.path.join(config.media_cache_dir, tomo_name)
        if media_type == 'lowmag':
            filename, mimetype = "lowmag.jpg", 'image/jpeg'
        elif media_type == 'tiltseries':
            filename, mimetype = "tiltseries.jpg", 'image/jpeg'
        elif media_type == 'tomogram':
            filename, mimetype = "tomogram.jpg", 'image/jpeg'
        else:
            return "Invalid media type", 400
        file_path = os.path.join(media_dir, filename)
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            media_manager.queue_tomogram_for_processing(tomo_name, priority=True)
            return "", 404
        return send_from_directory(media_dir, filename, mimetype=mimetype)

    @media_bp.route('/thumbnail/<tomo_name>')
    def serve_thumbnail(tomo_name):
        thumbnail_dir = os.path.join(config.media_cache_dir, tomo_name)
        if not os.path.exists(os.path.join(thumbnail_dir, "thumbnail.jpg")):
            return "", 404
        return send_from_directory(thumbnail_dir, "thumbnail.jpg")

    # --- RESTORED AND UPDATED FUNCTIONS ---
    @media_bp.route('/media_status/<media_type>/<tomo_name>')
    def get_media_status(media_type, tomo_name):
        return jsonify(media_manager.get_media_status(media_type, tomo_name))

    @media_bp.route('/thumbnail_status/<tomo_name>')
    def get_thumbnail_status(tomo_name):
        thumbnail_path = os.path.join(config.media_cache_dir, tomo_name, "thumbnail.jpg")
        if os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0:
            return jsonify({'available': True, 'path': tomo_name})
        else:
            # Ensure it's queued if not available, consistent with previous logic
            media_manager.get_thumbnail_path(tomo_name)
            return jsonify({'available': False})

    @media_bp.route('/thumbnail_progress')
    def get_thumbnail_progress():
        return jsonify(media_manager.get_thumbnail_progress())

    @media_bp.route('/process_tomograms', methods=['POST'])
    def process_tomograms():
        data = request.get_json()
        if not data or 'tomograms' not in data:
            return jsonify({'error': 'Missing tomogram list'}), 400
        tomograms = data['tomograms']
        if not isinstance(tomograms, list): # Added type check for safety
             return jsonify({'error': 'Tomograms must be a list'}), 400
        media_manager.batch_process_tomograms(tomograms)
        return jsonify({'status': 'processing', 'message': f'Processing {len(tomograms)} tomograms'})
    # --- END RESTORED FUNCTIONS ---

    # --- NEW INTERACTIVE VIEWER ROUTES ---
    @media_bp.route('/interactive_data/<media_type>/<tomo_name>')
    def get_interactive_data(media_type, tomo_name):
        try:
            from tomcat.utils.media_utils import parse_tilt_angles # generate_frames_from_mrc is now called by worker

            frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
            status_key = f"interactive_{media_type}_{tomo_name}"

            # Check if frames already exist first, as it's the cheapest check
            # Ensure directory exists and is not empty before declaring "ready"
            if os.path.isdir(frames_dir) and len(os.listdir(frames_dir)) > 0:
                media_manager.media_status[status_key] = "ready"

            status = media_manager.media_status.get(status_key, "unknown")

            if status == "unknown":
                # Use the new worker method which handles its own status updates
                media_manager.media_status[status_key] = "generating" # Set initial status before worker might change it
                os.makedirs(frames_dir, exist_ok=True) # Ensure frames_dir exists for worker and subsequent checks
                media_manager.thread_manager.submit_task(
                    status_key, # Unique ID for the task
                    media_manager._generate_frames_worker, # The new worker method
                    media_type, tomo_name # Arguments for the worker
                )
                logger.info(f"Submitted frame generation task via worker for {status_key}")
                return jsonify({'status': 'generating'})

            if status == "generating":
                return jsonify({'status': 'generating'})

            if status == "ready":
                # Double check directory and contents in case status is stale or files were removed
                if not os.path.isdir(frames_dir) or not os.listdir(frames_dir):
                    logger.warning(f"Status for {status_key} is 'ready' but frames_dir is missing or empty. Resetting.")
                    media_manager.media_status[status_key] = "unknown" # Reset to allow re-generation
                    # It might be good to trigger generation again here, or let client retry
                    return jsonify({'status': 'error', 'message': 'Frames were not found. Please try again.'})

                frame_files = sorted(os.listdir(frames_dir), key=lambda x: int(os.path.splitext(x)[0]))
                frame_urls = [url_for('media.serve_interactive_frame', media_type=media_type, tomo_name=tomo_name, frame_name=f) for f in frame_files]

                tilt_angles = None
                if media_type == 'tiltseries':
                    tlt_file = media_manager.file_locator.find_tilt_angle_file(tomo_name)
                    if tlt_file:
                        all_angles = parse_tilt_angles(tlt_file)
                        if all_angles:
                            # Ensure frame_urls is not empty to avoid division by zero
                            step = max(1, len(all_angles) // len(frame_urls)) if len(frame_urls) > 0 else 1
                            # Ensure that we do not try to access an index out of bounds for all_angles
                            tilt_angles = []
                            for i in range(len(frame_urls)):
                                angle_idx = i * step
                                if angle_idx < len(all_angles):
                                    tilt_angles.append(round(all_angles[angle_idx], 2))
                                else:
                                    # If not enough angles, append None or last known angle. Here, None.
                                    tilt_angles.append(None)


                return jsonify({
                    'status': 'ready',
                    'frames': frame_urls,
                    'metadata': { 'tilt_angles': tilt_angles }
                })

            if status == "error":
                 logger.warning(f"Frame generation previously failed for {status_key}. Client notified.")
                 return jsonify({'status': 'error', 'message': f'Frame generation failed. Please check server logs for details.'})

            # Fallback for any other unexpected status
            logger.error(f"Unexpected status '{status}' for {status_key}.")
            return jsonify({'status': 'error', 'message': f'Unknown media status: {status}'})

        except Exception as e:
            logger.error(f"UNHANDLED EXCEPTION in get_interactive_data for {media_type}/{tomo_name}: {e}", exc_info=True)
            # Ensure status_key reflects error if an unhandled exception occurs before worker sets it
            status_key_check = f"interactive_{media_type}_{tomo_name}"
            media_manager.media_status[status_key_check] = "error"
            return jsonify({'status': 'error', 'message': 'An unexpected server error occurred.'}), 500

    @media_bp.route('/frame/<media_type>/<tomo_name>/<frame_name>')
    def serve_interactive_frame(media_type, tomo_name, frame_name):
        frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
        return send_from_directory(frames_dir, frame_name)
    # --- END NEW ROUTES ---

    return media_bp