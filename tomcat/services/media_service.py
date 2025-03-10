"""
Media Service for TomCat Application

This module handles all media-related operations including generation of
thumbnails, animations, and other visualizations.
"""
import os
import logging
import glob

# Import from utils package
from tomcat.utils.file_utils import FileLocator

logger = logging.getLogger(__name__)


class MediaManager:
    """
    Manages the generation, tracking, and serving of media files.
    Handles thumbnails, lowmag images, tilt series and tomogram animations.
    """

    def __init__(self, config, thread_manager):
        """
        Initialize the media manager.

        Args:
            config: Application configuration object
            thread_manager: Thread manager for handling background tasks
        """
        self.config = config
        self.thread_manager = thread_manager
        self.file_locator = FileLocator(config)

        # Media status tracking
        self.media_status = {}

        # Thumbnail progress tracking
        self.thumbnail_progress = {
            'total': 0,
            'downloaded': 0,
            'status': 'idle',
            'message': '',
            'completed_names': [],
            'thumbnail_paths': {}  # Dictionary to map tomo_name to its thumbnail path
        }

    def generate_media_for_tomogram(self, tomo_name):
        """
        Trigger generation of all media types for a given tomogram.
        This runs in the background using the thread pool.

        Args:
            tomo_name (str): Name of the tomogram to generate media for
        """
        # Check for each media type and schedule generation if needed
        self._check_and_generate_thumbnail(tomo_name)
        self._check_and_generate_lowmag(tomo_name)
        self._check_and_generate_tiltseries(tomo_name)
        self._check_and_generate_tomogram(tomo_name)

        # Clean up completed tasks
        self.thread_manager.cleanup_completed_tasks()

    def _check_and_generate_thumbnail(self, tomo_name):
        """
        Check if thumbnail exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        # Check if thumbnail already exists
        thumbnail_pattern = os.path.join(self.config.thumbnails_folder, f"{tomo_name}*.png")
        thumbnail_files = glob.glob(thumbnail_pattern)

        if not thumbnail_files:
            # Find source file for thumbnail generation
            tomogram_file = self.file_locator.find_tomogram_file(tomo_name)

            if tomogram_file:
                output_file = os.path.join(self.config.thumbnails_folder, f"{tomo_name}.png")

                # Submit thumbnail generation task
                self.thread_manager.submit_task(
                    f"thumbnail_{tomo_name}",
                    self._generate_thumbnail,
                    tomo_name, tomogram_file, output_file
                )
                logger.info(f"Scheduled thumbnail generation for {tomo_name}")

    def _check_and_generate_lowmag(self, tomo_name):
        """
        Check if lowmag image exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        # Check if lowmag image already exists
        output_file = os.path.join(self.config.lowmag_folder, f"{tomo_name}.jpg")

        if not os.path.exists(output_file) and self.config.paths['lowmag_path']:
            # Set status to generating
            self.media_status[f"lowmag_{tomo_name}"] = "generating"

            # Submit lowmag generation task
            self.thread_manager.submit_task(
                f"lowmag_{tomo_name}",
                self._generate_lowmag_image,
                tomo_name
            )
            logger.info(f"Scheduled lowmag image generation for {tomo_name}")

    def _check_and_generate_tiltseries(self, tomo_name):
        """
        Check if tilt series animation exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        # Check if tilt series animation already exists
        output_file = os.path.join(self.config.tiltseries_folder, f"{tomo_name}.gif")

        if not os.path.exists(output_file) and self.config.paths['tiltseries_path']:
            # Set status to generating
            self.media_status[f"tiltseries_{tomo_name}"] = "generating"

            # Submit tilt series generation task
            self.thread_manager.submit_task(
                f"tiltseries_{tomo_name}",
                self._generate_tiltseries_animation,
                tomo_name
            )
            logger.info(f"Scheduled tilt series animation generation for {tomo_name}")

    def _check_and_generate_tomogram(self, tomo_name):
        """
        Check if tomogram animation exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        # Check if tomogram animation already exists
        output_file = os.path.join(self.config.tomogram_folder, f"{tomo_name}.gif")

        if not os.path.exists(output_file) and self.config.paths['tomogram_path']:
            # Set status to generating
            self.media_status[f"tomogram_{tomo_name}"] = "generating"

            # Submit tomogram generation task
            self.thread_manager.submit_task(
                f"tomogram_{tomo_name}",
                self._generate_tomogram_animation,
                tomo_name
            )
            logger.info(f"Scheduled tomogram animation generation for {tomo_name}")

    def _generate_thumbnail(self, tomo_name, source_file, output_file):
        """
        Generate a thumbnail image for a tomogram.

        Args:
            tomo_name (str): Name of the tomogram
            source_file (str): Path to the source MRC file
            output_file (str): Path to save the thumbnail to

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Verify source file exists
            if not source_file or not os.path.exists(source_file):
                logger.error(f"Source file not found for thumbnail generation: {source_file}")
                self.thumbnail_progress['status'] = 'error'
                self.thumbnail_progress['message'] = f'Source file not found for {tomo_name}'
                return False

            # Update progress tracking
            self.thumbnail_progress['status'] = 'generating'
            self.thumbnail_progress['message'] = f'Generating thumbnail for {tomo_name}'

            # Use utils.py function to generate the thumbnail
            from tomcat.utils import generate_jpeg_thumbnail
            success = generate_jpeg_thumbnail(source_file, output_file, min_side=150)

            if success:
                # Verify the thumbnail was actually created
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    # Update progress tracking
                    self.thumbnail_progress['status'] = 'success'
                    self.thumbnail_progress['message'] = f'Generated thumbnail for {tomo_name}'
                    self.thumbnail_progress['completed_names'].append(tomo_name)
                    self.thumbnail_progress['thumbnail_paths'][tomo_name] = os.path.basename(output_file)
                    return True
                else:
                    # File wasn't created or is empty
                    self.thumbnail_progress['status'] = 'error'
                    self.thumbnail_progress['message'] = f'Generated thumbnail is invalid for {tomo_name}'
                    return False
            else:
                # Function returned failure
                self.thumbnail_progress['status'] = 'error'
                self.thumbnail_progress['message'] = f'Failed to generate thumbnail for {tomo_name}'
                return False

        except Exception as e:
            logger.error(f"Error generating thumbnail for {tomo_name}: {str(e)}")
            self.thumbnail_progress['status'] = 'error'
            self.thumbnail_progress['message'] = f'Error: {str(e)}'
            return False

    def _generate_lowmag_image(self, tomo_name):
        """
        Generate a JPEG image from the lowmag MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the lowmag image for

        Returns:
            bool: True if successful, False otherwise
        """
        output_file = os.path.join(self.config.lowmag_folder, f"{tomo_name}.jpg")

        try:
            # Find the lowmag file
            lowmag_file = self.file_locator.find_lowmag_file(tomo_name)

            if not lowmag_file:
                logger.error(f"No lowmag file found for {tomo_name}")
                self.media_status[f"lowmag_{tomo_name}"] = "error"
                return False

            # Make sure output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Use utils.py functions to generate the JPEG image
            from tomcat.utils import generate_jpeg_thumbnail
            success = generate_jpeg_thumbnail(lowmag_file, output_file, min_side=384)

            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(f"Successfully generated lowmag image for {tomo_name}")
                self.media_status[f"lowmag_{tomo_name}"] = "ready"
                return True
            else:
                logger.error(f"Failed to generate lowmag image for {tomo_name}")
                self.media_status[f"lowmag_{tomo_name}"] = "error"
                # Clean up empty file if it exists
                if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
                    os.remove(output_file)
                return False

        except Exception as e:
            logger.error(f"Error generating lowmag image for {tomo_name}: {str(e)}")
            self.media_status[f"lowmag_{tomo_name}"] = "error"
            # Clean up output file if it exists but generation failed
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

    def _generate_tiltseries_animation(self, tomo_name):
        """
        Generate an animation from the tilt series MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the tilt series animation for

        Returns:
            bool: True if successful, False otherwise
        """
        output_file = os.path.join(self.config.tiltseries_folder, f"{tomo_name}.gif")

        try:
            # Find the tilt series file
            tiltseries_file = self.file_locator.find_tiltseries_file(tomo_name)

            if not tiltseries_file:
                logger.error(f"No tilt series file found for {tomo_name}")
                self.media_status[f"tiltseries_{tomo_name}"] = "error"
                return False

            logger.info(f"Found tilt series file for {tomo_name}: {tiltseries_file}")

            # Make sure output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            logger.info(f"Generating tilt series animation for {tomo_name} to {output_file}")

            # Use utils.py functions to generate the animation
            from tomcat.utils import generate_tiltseries_animation as utils_generate_animation
            success = utils_generate_animation(tiltseries_file, output_file, min_side=384)

            # Check if the file was created and has content
            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(
                    f"Successfully generated tilt series animation for {tomo_name}, size: {os.path.getsize(output_file)} bytes")
                self.media_status[f"tiltseries_{tomo_name}"] = "ready"
                return True
            else:
                if os.path.exists(output_file):
                    logger.error(
                        f"Generated file exists but is empty: {output_file}, size: {os.path.getsize(output_file)} bytes")
                    # Remove empty file
                    os.remove(output_file)
                else:
                    logger.error(f"Failed to generate file: {output_file}")
                self.media_status[f"tiltseries_{tomo_name}"] = "error"
                return False

        except Exception as e:
            logger.error(f"Error generating tilt series animation for {tomo_name}: {str(e)}")
            self.media_status[f"tiltseries_{tomo_name}"] = "error"
            # Clean up output file if it exists but generation failed
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

    def _generate_tomogram_animation(self, tomo_name):
        """
        Generate an animation from the tomogram MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the animation for

        Returns:
            bool: True if successful, False otherwise
        """
        output_file = os.path.join(self.config.tomogram_folder, f"{tomo_name}.gif")

        try:
            # Find the tomogram file
            tomogram_file = self.file_locator.find_tomogram_file(tomo_name)

            if not tomogram_file:
                logger.error(f"No tomogram file found for {tomo_name}")
                self.media_status[f"tomogram_{tomo_name}"] = "error"
                return False

            logger.info(f"Found tomogram file for {tomo_name}: {tomogram_file}")

            # Make sure output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            logger.info(f"Generating tomogram animation for {tomo_name} to {output_file}")

            # Use utils.py functions to generate the animation
            from tomcat.utils import generate_tomogram_animation as utils_generate_animation
            success = utils_generate_animation(tomogram_file, output_file, min_side=384)

            # Check if the file was created and has content
            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(
                    f"Successfully generated tomogram animation for {tomo_name}, size: {os.path.getsize(output_file)} bytes")
                self.media_status[f"tomogram_{tomo_name}"] = "ready"
                return True
            else:
                if os.path.exists(output_file):
                    logger.error(
                        f"Generated file exists but is empty: {output_file}, size: {os.path.getsize(output_file)} bytes")
                    # Remove empty file
                    os.remove(output_file)
                else:
                    logger.error(f"Failed to generate file: {output_file}")
                self.media_status[f"tomogram_{tomo_name}"] = "error"
                return False

        except Exception as e:
            logger.error(f"Error generating tomogram animation for {tomo_name}: {str(e)}")
            self.media_status[f"tomogram_{tomo_name}"] = "error"
            # Clean up output file if it exists but generation failed
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

    def get_media_status(self, media_type, tomo_name):
        """
        Get the status of media generation for a specific tomogram and media type.

        Args:
            media_type (str): Type of media ('lowmag', 'tiltseries', 'tomogram')
            tomo_name (str): Name of the tomogram

        Returns:
            dict: Status information
        """
        status_key = f"{media_type}_{tomo_name}"

        # Determine the appropriate media folder based on type
        if media_type == 'lowmag':
            media_folder = self.config.lowmag_folder
            file_extension = '.jpg'
        elif media_type == 'tiltseries':
            media_folder = self.config.tiltseries_folder
            file_extension = '.gif'
        elif media_type == 'tomogram':
            media_folder = self.config.tomogram_folder
            file_extension = '.gif'
        else:
            return {"status": "error", "message": "Invalid media type"}

        # Check if the media file exists
        media_file = os.path.join(media_folder, f"{tomo_name}{file_extension}")

        if os.path.exists(media_file) and os.path.getsize(media_file) > 0:
            # File exists and has content, it's ready
            logger.debug(f"Media file is ready: {media_file}")
            return {
                "status": "ready",
                "reload": self.media_status.get(status_key) == "generating",  # Reload if we were previously generating
                "size": os.path.getsize(media_file)
            }

        # Check the status
        status = self.media_status.get(status_key, "unknown")

        # If status is unknown but the file should be generating, update status
        if status == "unknown" and not os.path.exists(media_file):
            self.media_status[status_key] = "generating"
            self.generate_media_for_tomogram(tomo_name)
            status = "generating"

        return {
            "status": status,
            "reload": False,
            "file_exists": os.path.exists(media_file),
            "file_size": os.path.getsize(media_file) if os.path.exists(media_file) else 0
        }

    def get_thumbnail_path(self, tomo_name):
        """
        Get the path to a thumbnail for a specific tomogram.

        Args:
            tomo_name (str): Name of the tomogram

        Returns:
            str or None: Path to the thumbnail if found, None otherwise
        """
        # Check cached paths first
        if tomo_name in self.thumbnail_progress['thumbnail_paths']:
            thumbnail_filename = self.thumbnail_progress['thumbnail_paths'][tomo_name]
            return os.path.join(self.config.thumbnails_folder, thumbnail_filename)

        # Use file locator to find thumbnail
        return self.file_locator.find_thumbnail(tomo_name, self.config.thumbnails_folder)

    def get_thumbnail_progress(self):
        """
        Get the current progress of thumbnail generation.

        Returns:
            dict: Thumbnail generation progress information
        """
        return self.thumbnail_progress