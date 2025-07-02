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


def initialize_routes(config, media_manager):
    """
    Initialize media routes with required dependencies.

    Args:
        config: Application configuration object
        media_manager: Media manager instance
    """

    @media_bp.route('/serve_media/<media_type>/<tomo_name>')
    def serve_media(media_type, tomo_name):
        """
        Serve media files (images or GIFs) for a specific tomogram.

        Args:
            media_type (str): Type of media ('lowmag', 'tiltseries', 'tomogram')
            tomo_name (str): Name of the tomogram
        """
        if media_type == 'lowmag':
            media_folder = config.lowmag_folder
            filename = f"{tomo_name}.jpg"
        elif media_type == 'tiltseries':
            media_folder = config.tiltseries_folder
            filename = f"{tomo_name}.gif"
        elif media_type == 'tomogram':
            media_folder = config.tomogram_folder
            filename = f"{tomo_name}.gif"
        else:
            return "Invalid media type", 400

        # Make sure directory exists
        os.makedirs(media_folder, exist_ok=True)

        # Log the file path for debugging
        file_path = os.path.join(media_folder, filename)
        logger.info(f"Serving media from: {file_path}")

        # Check if file exists and has content
        if not os.path.exists(file_path):
            logger.info(f"File does not exist: {file_path}")
            # Set as priority since user is explicitly requesting it
            media_manager.queue_tomogram_for_processing(tomo_name, priority=True)
            # Return a 202 Accepted response to indicate processing
            return "", 202

        if os.path.getsize(file_path) == 0:
            logger.warning(f"File exists but is empty: {file_path}")
            # Try to regenerate if the file is empty
            os.remove(file_path)
            media_manager.queue_tomogram_for_processing(tomo_name, priority=True)
            return "", 202

        logger.info(f"Serving file: {file_path}, size: {os.path.getsize(file_path)} bytes")

        # Set appropriate content type for the response
        if filename.endswith('.gif'):
            return send_from_directory(media_folder, filename, mimetype='image/gif')
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            return send_from_directory(media_folder, filename, mimetype='image/jpeg')
        else:
            return send_from_directory(media_folder, filename)

    @media_bp.route('/media_status/<media_type>/<tomo_name>')
    def get_media_status(media_type, tomo_name):
        """
        Check the status of media generation for a specific tomogram and media type.

        Args:
            media_type (str): Type of media ('lowmag', 'tiltseries', 'tomogram')
            tomo_name (str): Name of the tomogram
        """
        status = media_manager.get_media_status(media_type, tomo_name)
        return jsonify(status)

    @media_bp.route('/thumbnails/<filename>')
    def serve_thumbnail(filename):
        """
        Serve thumbnail files.

        Args:
            filename (str): Name of the thumbnail file
        """
        return send_from_directory(config.thumbnails_folder, filename)

    @media_bp.route('/thumbnail_status/<tomo_name>')
    def get_thumbnail_status(tomo_name):
        """
        Check if a specific thumbnail is available locally.

        Args:
            tomo_name (str): Name of the tomogram
        """
        thumbnail_path = media_manager.get_thumbnail_path(tomo_name)

        if thumbnail_path:
            return jsonify({
                'available': True,
                'path': os.path.basename(thumbnail_path)
            })
        else:
            # Thumbnail not available yet, but has been queued for generation
            return jsonify({'available': False})

    @media_bp.route('/thumbnail_progress')
    def get_thumbnail_progress():
        """
        Return the current progress of thumbnail downloads.
        """
        return jsonify(media_manager.get_thumbnail_progress())

    @media_bp.route('/process_tomograms', methods=['POST'])
    def process_tomograms():
        """
        Endpoint to explicitly request processing of a list of tomograms.
        This can be called from the frontend when tomograms are first loaded.
        """
        data = request.get_json()
        if not data or 'tomograms' not in data:
            return jsonify({'error': 'Missing tomogram list'}), 400

        tomograms = data['tomograms']
        if not isinstance(tomograms, list):
            return jsonify({'error': 'Tomograms must be a list'}), 400

        # Queue all tomograms for processing in the order provided
        media_manager.batch_process_tomograms(tomograms)

        return jsonify({
            'status': 'processing',
            'message': f'Processing {len(tomograms)} tomograms',
            'count': len(tomograms)
        })

    @media_bp.route('/interactive_data/<media_type>/<tomo_name>')
    def get_interactive_data(media_type, tomo_name):
        """Provides the data needed for the interactive frame viewer."""
        from tomcat.utils.media_utils import generate_frames_from_mrc, parse_tilt_angles

        frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
        status_key = f"interactive_{media_type}_{tomo_name}"

        # If frames exist and directory is not empty, we are ready
        if os.path.isdir(frames_dir) and len(os.listdir(frames_dir)) > 0:
            media_manager.media_status[status_key] = "ready"

        status = media_manager.media_status.get(status_key, "unknown")

        # If status is unknown and no frames, start generating them
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
                logger.info(f"Submitted frame generation task for {status_key}")
                return jsonify({'status': 'generating'})
            else:
                logger.error(f"Source file not found for {media_type} / {tomo_name} for interactive viewer.")
                media_manager.media_status[status_key] = "error"
                return jsonify({'status': 'error', 'message': 'Source file not found.'})

        if status == 'generating':
            return jsonify({'status': 'generating'})

        # If we are ready, prepare the JSON payload
        if status == 'ready':
            try:
                if not os.path.isdir(frames_dir) or not os.listdir(frames_dir):
                    logger.warning(f"Frames directory {frames_dir} missing or empty despite status 'ready'. Resetting.")
                    media_manager.media_status[status_key] = "unknown"
                    if os.path.isdir(frames_dir):
                        import shutil
                        shutil.rmtree(frames_dir, ignore_errors=True)
                    return jsonify({'status': 'error', 'message': 'Frames not found, please try again.'})

                frame_files = sorted(os.listdir(frames_dir), key=lambda x: int(os.path.splitext(x)[0]))
                frame_urls = [url_for('media.serve_interactive_frame', media_type=media_type, tomo_name=tomo_name, frame_name=f) for f in frame_files]

                tilt_angles = None
                if media_type == 'tiltseries':
                    tlt_file = media_manager.file_locator.find_tilt_angle_file(tomo_name)
                    if tlt_file:
                        all_angles = parse_tilt_angles(tlt_file)
                        if all_angles:
                            num_target_frames = len(frame_urls)
                            if len(all_angles) < num_target_frames :
                                logger.warning(f"Number of angles ({len(all_angles)}) is less than frames ({num_target_frames}) for {tomo_name}. Using available angles and padding with None.")
                                tilt_angles = []
                                # Map available angles to frames, proportionally or directly
                                # This simplified logic takes the first 'num_target_frames' angles if available, or all angles if fewer
                                for i in range(num_target_frames):
                                    if i < len(all_angles):
                                        tilt_angles.append(round(all_angles[i], 2))
                                    else:
                                        tilt_angles.append(None) # Pad with None if not enough angles
                            else: # Enough or more angles than frames
                                # Select angles corresponding to the frames (e.g. if frames were skipped)
                                step = max(1, len(all_angles) // num_target_frames if num_target_frames > 0 else 1)
                                tilt_angles = [round(all_angles[i * step], 2) for i in range(num_target_frames)]
                                # Ensure tilt_angles list matches frame_urls length
                                if len(tilt_angles) < num_target_frames:
                                    tilt_angles.extend([None] * (num_target_frames - len(tilt_angles)))
                                elif len(tilt_angles) > num_target_frames:
                                    tilt_angles = tilt_angles[:num_target_frames]


                return jsonify({
                    'status': 'ready',
                    'frames': frame_urls,
                    'metadata': { 'tilt_angles': tilt_angles }
                })
            except Exception as e:
                logger.error(f"Error serving interactive data for {media_type} / {tomo_name}: {e}")
                return jsonify({'status': 'error', 'message': str(e)})

        logger.error(f"Unhandled status '{status}' for interactive data: {media_type}/{tomo_name}")
        return jsonify({'status': 'error', 'message': f'Unknown or unhandled status: {status}'})

    @media_bp.route('/frame/<media_type>/<tomo_name>/<frame_name>')
    def serve_interactive_frame(media_type, tomo_name, frame_name):
        """Serves a single frame for the interactive viewer."""
        frames_dir = os.path.join(config.media_cache_dir, tomo_name, f"frames_{media_type}")
        return send_from_directory(frames_dir, frame_name)

    # Return the blueprint - not strictly necessary but helps with clarity
    return media_bp