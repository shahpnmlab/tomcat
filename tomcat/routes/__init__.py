"""
Route modules for TomCat application.

This package contains route modules that define the web application endpoints.
Each module provides a blueprint that can be registered with the Flask application.
"""

# Import route modules - these are imported explicitly to avoid circular imports
from tomcat.routes import settings_routes, session_routes, media_routes

__all__ = ['settings_routes', 'session_routes', 'media_routes']