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
            filename = "lowmag.jpg"
        elif media_type == 'tiltseries':
            filename = "tiltseries.gif"
        elif media_type == 'tomogram':
            filename = "tomogram.gif"
        else:
            return "Invalid media type", 400

        media_dir = os.path.join(config.media_cache_dir, tomo_name)
        file_path = os.path.join(media_dir, filename)

        os.makedirs(media_dir, exist_ok=True)

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            if os.path.exists(file_path): # Remove if empty
                os.remove(file_path)
            media_manager.queue_tomogram_for_processing(tomo_name, priority=True)
            return "", 202

        return send_from_directory(media_dir, filename)

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

    @media_bp.route('/thumbnail/<tomo_name>') # Route changed from /thumbnails/<filename>
    def serve_thumbnail(tomo_name): # Parameter changed from filename to tomo_name
        """
        Serve thumbnail files.

        Args:
            tomo_name (str): Name of the tomogram (used to find thumbnail.jpg)
        """
        thumbnail_dir = os.path.join(config.media_cache_dir, tomo_name)
        return send_from_directory(thumbnail_dir, "thumbnail.jpg")

    @media_bp.route('/thumbnail_status/<tomo_name>')
    def get_thumbnail_status(tomo_name):
        """
        Check if a specific thumbnail is available locally.

        Args:
            tomo_name (str): Name of the tomogram
        """
        thumbnail_path = os.path.join(config.media_cache_dir, tomo_name, "thumbnail.jpg")
        if os.path.exists(thumbnail_path):
            return jsonify({'available': True, 'path': tomo_name}) # 'path' is now tomo_name for URL construction
        else:
            # Ensure media_manager queues if not available
            media_manager.get_thumbnail_path(tomo_name)
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