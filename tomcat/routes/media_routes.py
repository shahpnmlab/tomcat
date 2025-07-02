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
            filename, mimetype = "tiltseries.gif", 'image/gif'
        elif media_type == 'tomogram':
            filename, mimetype = "tomogram.gif", 'image/gif'
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
        from tomcat.utils.media_utils import generate_frames_from_mrc, parse_tilt_angles
        frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
        status_key = f"interactive_{media_type}_{tomo_name}"
        if os.path.isdir(frames_dir) and len(os.listdir(frames_dir)) > 0:
            media_manager.media_status[status_key] = "ready"
        status = media_manager.media_status.get(status_key, "unknown")
        if status == 'unknown':
            source_file = None
            if media_type == 'tiltseries':
                source_file = media_manager.file_locator.find_tiltseries_file(tomo_name)
            elif media_type == 'tomogram':
                source_file = media_manager.file_locator.find_tomogram_file(tomo_name)
            if source_file:
                media_manager.media_status[status_key] = "generating"
                os.makedirs(frames_dir, exist_ok=True)
                media_manager.thread_manager.submit_task(
                    status_key, generate_frames_from_mrc,
                    source_file, frames_dir, media_type
                )
                return jsonify({'status': 'generating'})
            else:
                return jsonify({'status': 'error', 'message': 'Source file not found.'})
        if status == 'generating': return jsonify({'status': 'generating'})
        if status == 'ready':
            try:
                frame_files = sorted(os.listdir(frames_dir), key=lambda x: int(os.path.splitext(x)[0]))
                frame_urls = [url_for('media.serve_interactive_frame', media_type=media_type, tomo_name=tomo_name, frame_name=f) for f in frame_files]
                tilt_angles = None
                if media_type == 'tiltseries':
                    tlt_file = media_manager.file_locator.find_tilt_angle_file(tomo_name)
                    if tlt_file:
                        all_angles = parse_tilt_angles(tlt_file)
                        if all_angles:
                            step = max(1, len(all_angles) // len(frame_urls)) if len(frame_urls) > 0 else 1
                            tilt_angles = [round(all_angles[i * step], 2) for i in range(len(frame_urls))]
                return jsonify({'status': 'ready', 'frames': frame_urls, 'metadata': {'tilt_angles': tilt_angles}})
            except Exception as e:
                logger.error(f"Error serving interactive data for {tomo_name}: {e}")
                return jsonify({'status': 'error', 'message': str(e)})
        return jsonify({'status': 'error', 'message': f'Unknown status: {status}'})

    @media_bp.route('/frame/<media_type>/<tomo_name>/<frame_name>')
    def serve_interactive_frame(media_type, tomo_name, frame_name):
        frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
        return send_from_directory(frames_dir, frame_name)
    # --- END NEW ROUTES ---

    return media_bp