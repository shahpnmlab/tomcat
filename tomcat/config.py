"""
Configuration Management for TomCat Application

This module handles loading, saving, and managing application configuration
including all file paths and application settings.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration manager for the TomCat application.
    Handles loading, saving, and accessing configuration settings.
    """

    def __init__(self, base_dir=None):
        """
        Initialize configuration with default values.

        Args:
            base_dir (str, optional): Base directory for the application.
                                     If None, uses the current working directory.
        """
        # Set base directory
        self.base_dir = base_dir or os.getcwd()

        # App directories
        self.app_data_dir = os.path.join(self.base_dir, '.tomcat')
        self.upload_folder = os.path.join(self.app_data_dir, 'uploads')
        self.thumbnails_folder = os.path.join(self.app_data_dir, 'thumbnails')
        self.media_folder = os.path.join(self.app_data_dir, 'media')
        self.lowmag_folder = os.path.join(self.media_folder, 'lowmag')
        self.tiltseries_folder = os.path.join(self.media_folder, 'tiltseries')
        self.tomogram_folder = os.path.join(self.media_folder, 'tomogram')

        # Config file path
        self.config_file = os.path.join(self.app_data_dir, 'config.json')

        # Default paths for data sources
        self.default_paths = {
            'lowmag_path': '',
            'tiltseries_path': '',
            'tomogram_path': '',
            'notes_path': self.base_dir  # Default to base directory
        }

        # Actual paths (initialized with defaults, will be updated from config file)
        self.paths = self.default_paths.copy()

        # App name and other settings
        self.app_name = 'TomCat'
        self.allowed_extensions = {'tomcat'}

        # Create necessary directories
        self._create_directories()

        # Load configuration from file if exists
        self.load()

    def _create_directories(self):
        """Create all necessary application directories if they don't exist."""
        directories = [
            self.app_data_dir,
            self.upload_folder,
            self.thumbnails_folder,
            self.media_folder,
            self.lowmag_folder,
            self.tiltseries_folder,
            self.tomogram_folder
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")

    def load(self):
        """
        Load configuration from the config file.
        If the file doesn't exist or has errors, use default values.
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)

                # Update paths with loaded values, keeping defaults for missing keys
                for key, default_value in self.default_paths.items():
                    self.paths[key] = loaded_config.get(key, default_value)

                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading config: {str(e)}")
                # If there's an error, reset to defaults
                self.paths = self.default_paths.copy()
        else:
            # Create default config file
            logger.info("No config file found, creating with defaults")
            self.save()

    def save(self):
        """Save current configuration to the config file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.paths, f, indent=4)
            logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}")
            return False

    def update_paths(self, **kwargs):
        """
        Update path configuration with provided values.

        Args:
            **kwargs: Key-value pairs where key is the path name and value is the new path

        Returns:
            bool: True if successful, False otherwise
        """
        # Update only valid path keys
        for key, value in kwargs.items():
            if key in self.paths:
                self.paths[key] = value

        # Save the updated configuration
        return self.save()

    def get_flask_config(self):
        """
        Get configuration dictionary for Flask app.config.

        Returns:
            dict: Configuration dictionary for Flask
        """
        config_dict = {
            'APP_NAME': self.app_name,
            'APP_DATA_DIR': self.app_data_dir,
            'LOCAL_UPLOAD_FOLDER': self.upload_folder,
            'LOCAL_THUMBNAILS_FOLDER': self.thumbnails_folder,
            'LOCAL_MEDIA_FOLDER': self.media_folder,
            'LOWMAG_MEDIA_FOLDER': self.lowmag_folder,
            'TILTSERIES_MEDIA_FOLDER': self.tiltseries_folder,
            'TOMOGRAM_MEDIA_FOLDER': self.tomogram_folder,
            'CONFIG_FILE': self.config_file,
            'PATHS': self.paths,
            'ALLOWED_EXTENSIONS': self.allowed_extensions
        }
        return config_dict