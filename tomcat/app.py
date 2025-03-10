"""
TomCat - Tomography Catalogue Tool

Main application script that integrates all modules and provides
both web interface and command-line functionality.
"""
import logging
import typer
from flask import Flask

# Import our modules
from tomcat.config import Config
from tomcat.utils.thread_utils import ThreadManager
from tomcat.utils.file_utils import FileLocator
from tomcat.utils.template_utils import register_template_utils
from tomcat.models.session import SessionManager
from tomcat.services.media_service import MediaManager

# Import route blueprints
from tomcat.routes import settings_routes, session_routes, media_routes

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create Typer CLI app
cli = typer.Typer(help="TomCat - Tomography Catalogue Tool")

# Initialize core components
app = None
config = None
thread_manager = None
file_locator = None
session_manager = None
media_manager = None


def create_app():
    """
    Create and configure the Flask application.

    Returns:
        Flask: The configured Flask application
    """
    global app, config, thread_manager, file_locator, session_manager, media_manager

    # Initialize Flask application
    app = Flask(__name__)
    app.secret_key = 'tomcat_secret_key'

    # Initialize configuration
    config = Config()

    # Create thread manager
    thread_manager = ThreadManager(max_workers=4)

    # Initialize services and managers
    file_locator = FileLocator(config)
    session_manager = SessionManager(config)
    media_manager = MediaManager(config, thread_manager)

    # Configure Flask app with our settings
    app.config.update(config.get_flask_config())

    # Helper function to check if a file is allowed
    def allowed_file(filename):
        """Check if a filename has an allowed extension."""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.allowed_extensions

    # Register blueprints
    app.register_blueprint(
        settings_routes.initialize_routes(config),
        url_prefix='/settings'
    )

    app.register_blueprint(
        session_routes.initialize_routes(
            config, session_manager, file_locator, media_manager, allowed_file
        ),
        url_prefix='/session'
    )

    app.register_blueprint(
        media_routes.initialize_routes(config, media_manager),
        url_prefix='/media'
    )

    # Add URL rules for root routes
    app.add_url_rule('/', 'index', lambda: app.redirect('/session/'))

    # Add compatibility routes for AJAX requests that might use old URLs
    @app.route('/browse_directory', methods=['POST'])
    def compat_browse_directory():
        """Compatibility route for old AJAX requests"""
        return app.view_functions['settings.browse_directory']()

    @app.route('/media_status/<media_type>/<tomo_name>')
    def compat_media_status(media_type, tomo_name):
        """Compatibility route for old media status requests"""
        return app.view_functions['media.get_media_status'](media_type, tomo_name)

    @app.route('/thumbnail_status/<tomo_name>')
    def compat_thumbnail_status(tomo_name):
        """Compatibility route for old thumbnail status requests"""
        return app.view_functions['media.get_thumbnail_status'](tomo_name)

    @app.route('/thumbnail_progress')
    def compat_thumbnail_progress():
        """Compatibility route for old thumbnail progress requests"""
        return app.view_functions['media.get_thumbnail_progress']()

    @app.route('/serve_media/<media_type>/<tomo_name>')
    def compat_serve_media(media_type, tomo_name):
        """Compatibility route for old media serving requests"""
        return app.view_functions['media.serve_media'](media_type, tomo_name)

    @app.route('/thumbnails/<filename>')
    def compat_serve_thumbnail(filename):
        """Compatibility route for old thumbnail serving requests"""
        return app.view_functions['media.serve_thumbnail'](filename)

    # Register template utilities
    register_template_utils(app)

    logger.info("Flask application initialized")
    return app


# =============================================================================
# CLI Commands
# =============================================================================

@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(16006, help="Port to bind to"),
    debug: bool = typer.Option(False, help="Enable debug mode")
):
    """Run the TomCat web application."""
    app = create_app()
    logger.info(f"Starting TomCat on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)


@cli.command()
def init():
    """Initialize the TomCat application configuration."""
    global config
    if config is None:
        config = Config()
    config.save()
    logger.info(f"Initialized TomCat configuration in {config.config_file}")
    logger.info(f"Application data directory: {config.app_data_dir}")


@cli.command()
def info():
    """Display information about the TomCat application."""
    global config, session_manager

    if config is None:
        config = Config()

    if session_manager is None:
        session_manager = SessionManager(config)

    print(f"TomCat - Tomography Catalogue Tool")
    print(f"Configuration file: {config.config_file}")
    print(f"App data directory: {config.app_data_dir}")
    print(f"Configured paths:")
    for key, value in config.paths.items():
        print(f"  {key}: {value or 'Not configured'}")

    # Display session information
    sessions = session_manager.get_sessions()
    print(f"\nAvailable sessions ({len(sessions)}):")
    for session in sessions:
        print(f"  {session['filename']} - {session['modified']} ({session['entry_count']} entries)")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    # Run the CLI app if executed directly
    try:
        cli()
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")