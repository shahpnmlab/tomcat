"""
Template Utilities for TomCat Application

This module provides utility functions for Flask templates,
including URL mapping for blueprint route transition.
"""
from flask import Flask, url_for as flask_url_for

# URL mapping from old routes to new blueprint routes
URL_MAPPING = {
    'upload_file': 'session.upload_file',
    'new_session': 'session.new_session',
    'process_csv': 'session.process_csv',
    'detail_view': 'session.detail_view',
    'download_csv': 'session.download_csv',
    'settings': 'settings.settings',
    'reset_session': 'settings.reset_session',
    'browse_directory': 'settings.browse_directory',
    'serve_media': 'media.serve_media',
    'serve_thumbnail': 'media.serve_thumbnail',
    'media_status': 'media.get_media_status',
    'thumbnail_status': 'media.get_thumbnail_status',
    'thumbnail_progress': 'media.get_thumbnail_progress'
}


def register_template_utils(app: Flask):
    """
    Register template utilities with the Flask application.

    Args:
        app: Flask application instance
    """

    @app.template_global()
    def url_for(endpoint, **values):
        """
        Override Flask's url_for to handle blueprint transition.
        Maps old route names to new blueprint routes.

        Args:
            endpoint: Route endpoint
            **values: URL parameters

        Returns:
            str: URL for the endpoint
        """
        # Map old endpoint names to new blueprint routes
        if endpoint in URL_MAPPING:
            endpoint = URL_MAPPING[endpoint]

        # Call Flask's original url_for
        return flask_url_for(endpoint, **values)