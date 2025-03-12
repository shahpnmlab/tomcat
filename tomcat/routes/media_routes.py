"""
Media Routes for TomCat Application

This module handles all routes related to media serving and processing,
including thumbnails, lowmag images, tilt series and tomogram animations.
"""
import os
import logging
from flask import Blueprint, send_from_directory, jsonify, request

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

    # Return the blueprint - not strictly necessary but helps with clarity
    return media_bp