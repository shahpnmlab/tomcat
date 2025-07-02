"""
Media Service for TomCat Application

This module handles all media-related operations including generation of
thumbnails, animations, and other visualizations.
"""
import os
import logging
import glob
from collections import OrderedDict

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

        # Ordered list of tomograms to process (maintains processing order)
        self.processing_queue = OrderedDict()

        # Thumbnail progress tracking
        self.thumbnail_progress = {
            'total': 0,
            'downloaded': 0,
            'status': 'idle',
            'message': '',
            'completed_names': [],
            'thumbnail_paths': {}  # Dictionary to map tomo_name to its thumbnail path
        }

    def queue_tomogram_for_processing(self, tomo_name, priority=False):
        """
        Add a tomogram to the processing queue.

        Args:
            tomo_name (str): Name of the tomogram to queue for processing
            priority (bool): If True, add to the front of the queue

        Returns:
            bool: True if queued, False if already in queue
        """
        if tomo_name in self.processing_queue:
            return False

        # If priority, add to front, otherwise add to end
        if priority:
            # Create a new OrderedDict with this item first, then add all others
            new_queue = OrderedDict([(tomo_name, True)])
            new_queue.update(self.processing_queue)
            self.processing_queue = new_queue
        else:
            self.processing_queue[tomo_name] = True

        # Only process the queue immediately if we haven't been called from within process_queue
        # This avoids potential recursion issues
        if not getattr(self, '_processing_queue_active', False):
            try:
                self._processing_queue_active = True
                self.process_queue()
            finally:
                self._processing_queue_active = False

        return True

    def process_queue(self):
        """
        Process tomograms in the queue, starting media generation for each.
        This is non-blocking as it schedules background tasks.
        """
        # Maximum number of active tasks to start at once
        max_to_start = max(1, self.thread_manager.max_workers - self.thread_manager.get_active_task_count())
        started = 0

        # Process items in the queue order
        queue_keys = list(self.processing_queue.keys())

        for tomo_name in queue_keys:
            # Start media generation
            if started < max_to_start:
                # Use internal method to avoid recursion
                self._generate_media_for_tomogram_internal(tomo_name)
                started += 1
                # Remove from queue once processed
                del self.processing_queue[tomo_name]
            else:
                # Leave the rest in the queue for next time
                break

        # Clean up completed tasks
        self.thread_manager.cleanup_completed_tasks()

    def batch_process_tomograms(self, tomo_list):
        """
        Queue a batch of tomograms for processing.
        Maintains the order provided in tomo_list.

        Args:
            tomo_list (list): List of tomogram names to process
        """
        # Update total count for tracking
        self.thumbnail_progress['total'] = len(tomo_list)

        # Queue each tomogram in order
        for tomo_name in tomo_list:
            self.queue_tomogram_for_processing(tomo_name)

        logger.info(f"Queued {len(tomo_list)} tomograms for processing")

    def _generate_media_for_tomogram_internal(self, tomo_name):
        """
        Internal method to trigger generation of all media types for a given tomogram.
        This version does not call process_queue to avoid recursion.

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

    def generate_media_for_tomogram(self, tomo_name):
        """
        Trigger generation of all media types for a given tomogram.
        This runs in the background using the thread pool.

        Args:
            tomo_name (str): Name of the tomogram to generate media for
        """
        # Add to queue and process
        self.queue_tomogram_for_processing(tomo_name, priority=True)

    def _check_and_generate_thumbnail(self, tomo_name):
        """
        Check if thumbnail exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        output_dir = os.path.join(self.config.media_cache_dir, tomo_name)
        output_file = os.path.join(output_dir, "thumbnail.jpg") # Changed to jpg as per instructions

        if not os.path.exists(output_file):
            tomogram_file = self.file_locator.find_tomogram_file(tomo_name)
            if tomogram_file:
                os.makedirs(output_dir, exist_ok=True)
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
        output_dir = os.path.join(self.config.media_cache_dir, tomo_name)
        output_file = os.path.join(output_dir, "lowmag.jpg")

        if not os.path.exists(output_file) and self.config.paths['lowmag_path']:
            os.makedirs(output_dir, exist_ok=True)
            self.media_status[f"lowmag_{tomo_name}"] = "generating"
            self.thread_manager.submit_task(
                f"lowmag_{tomo_name}",
                self._generate_lowmag_image,
                tomo_name, output_file
            )
            logger.info(f"Scheduled lowmag image generation for {tomo_name}")

    def _check_and_generate_tiltseries(self, tomo_name):
        """
        Check if tilt series animation exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        output_dir = os.path.join(self.config.media_cache_dir, tomo_name)
        output_file = os.path.join(output_dir, "tiltseries.gif")

        if not os.path.exists(output_file) and self.config.paths['tiltseries_path']:
            os.makedirs(output_dir, exist_ok=True)
            self.media_status[f"tiltseries_{tomo_name}"] = "generating"
            self.thread_manager.submit_task(
                f"tiltseries_{tomo_name}",
                self._generate_tiltseries_animation,
                tomo_name, output_file
            )
            logger.info(f"Scheduled tilt series animation generation for {tomo_name}")

    def _check_and_generate_tomogram(self, tomo_name):
        """
        Check if tomogram animation exists and generate if needed.

        Args:
            tomo_name (str): Name of the tomogram
        """
        output_dir = os.path.join(self.config.media_cache_dir, tomo_name)
        output_file = os.path.join(output_dir, "tomogram.gif")

        if not os.path.exists(output_file) and self.config.paths['tomogram_path']:
            os.makedirs(output_dir, exist_ok=True)
            self.media_status[f"tomogram_{tomo_name}"] = "generating"
            self.thread_manager.submit_task(
                f"tomogram_{tomo_name}",
                self._generate_tomogram_animation,
                tomo_name, output_file
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
                    # Update downloaded count
                    self.thumbnail_progress['downloaded'] += 1
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

    def _generate_lowmag_image(self, tomo_name, output_file):
        """
        Generate a JPEG image from the lowmag MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the lowmag image for

        Returns:
            bool: True if successful, False otherwise
        """
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

    def _generate_tiltseries_animation(self, tomo_name, output_file):
        """
        Generate an animation from the tilt series MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the tilt series animation for

        Returns:
            bool: True if successful, False otherwise
        """
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

    def _generate_tomogram_animation(self, tomo_name, output_file):
        """
        Generate an animation from the tomogram MRC file for the given tomogram.

        Args:
            tomo_name (str): Name of the tomogram to generate the animation for

        Returns:
            bool: True if successful, False otherwise
        """
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
        media_dir = os.path.join(self.config.media_cache_dir, tomo_name)

        if media_type == 'lowmag':
            filename = 'lowmag.jpg'
        elif media_type == 'tiltseries':
            filename = 'tiltseries.gif'
        elif media_type == 'tomogram':
            filename = 'tomogram.gif'
        else:
            return {"status": "error", "message": "Invalid media type"}

        media_file = os.path.join(media_dir, filename)

        if os.path.exists(media_file) and os.path.getsize(media_file) > 0:
            return {
                "status": "ready",
                "reload": self.media_status.get(status_key) == "generating",
                "size": os.path.getsize(media_file)
            }

        status = self.media_status.get(status_key, "unknown")

        # If status is unknown, it's not being generated yet. Queue it.
        # This ensures that if a file is requested and doesn't exist, its generation is (re)attempted.
        if status == "unknown":
            logger.info(f"Media {media_type} for {tomo_name} not found and status unknown. Queuing for generation.")
            self.queue_tomogram_for_processing(tomo_name, priority=True)
            # Update status immediately to prevent re-queueing in very short succession by multiple requests
            self.media_status[status_key] = "generating"
            status = "generating" # Reflect that it's now being generated

        return {"status": status, "reload": False} # No need for file_exists/file_size here, handled by "ready"

    def get_thumbnail_path(self, tomo_name):
        """
        Get the path to a thumbnail for a specific tomogram.

        Args:
            tomo_name (str): Name of the tomogram

        Returns:
            str or None: Path to the thumbnail if found, None otherwise
        """
        thumbnail_path = os.path.join(self.config.media_cache_dir, tomo_name, "thumbnail.jpg") # Changed to jpg
        if os.path.exists(thumbnail_path):
            return thumbnail_path

        self.queue_tomogram_for_processing(tomo_name)
        return None

    def get_thumbnail_progress(self):
        """
        Get the current progress of thumbnail generation.

        Returns:
            dict: Thumbnail generation progress information
        """
        return self.thumbnail_progress

    def _generate_frames_worker(self, media_type, tomo_name):
        """Worker task to generate interactive frames and update status."""
        from tomcat.utils.media_utils import generate_frames_from_mrc

        status_key = f"interactive_{media_type}_{tomo_name}"
        frames_dir = os.path.join(self.config.media_cache_dir, tomo_name, f"frames_{media_type}")

        try:
            source_file = None
            if media_type == 'tiltseries':
                source_file = self.file_locator.find_tiltseries_file(tomo_name)
            elif media_type == 'tomogram':
                source_file = self.file_locator.find_tomogram_file(tomo_name)

            if not source_file:
                # Ensure the frames directory exists for os.listdir checks by the API, even if source is missing
                os.makedirs(frames_dir, exist_ok=True)
                raise FileNotFoundError(f"Source file not found for {media_type} {tomo_name}")

            # Ensure output directory exists before generating frames
            os.makedirs(frames_dir, exist_ok=True)

            # The utility function does the heavy lifting
            frame_count = generate_frames_from_mrc(source_file, frames_dir, media_type)

            if frame_count > 0:
                self.media_status[status_key] = "ready"
                logger.info(f"Successfully generated {frame_count} frames for {media_type} {tomo_name}")
            else:
                # This case handles when the MRC file might be empty or invalid, or if generate_frames_from_mrc returns 0 for other reasons
                logger.warning(f"Frame generation resulted in 0 frames for {media_type} {tomo_name} from {source_file}.")
                raise ValueError(f"Frame generation resulted in 0 frames for {media_type} {tomo_name}.")

        except Exception as e:
            # If anything goes wrong, update the status to 'error'
            self.media_status[status_key] = "error"
            logger.error(f"Error in frame generation worker for {media_type} {tomo_name}: {e}", exc_info=True)
            # Attempt to clean up frames_dir if it was created by this worker instance and is empty or partially filled due to error
            try:
                if os.path.isdir(frames_dir) and not os.listdir(frames_dir): # Only remove if empty
                    logger.info(f"Cleaning up empty frames directory due to error: {frames_dir}")
                    os.rmdir(frames_dir) # Use rmdir for empty directory
                elif os.path.isdir(frames_dir): # If not empty, but error occurred, log it. Manual cleanup might be needed.
                    logger.warning(f"Frames directory {frames_dir} is not empty after error, manual cleanup may be required.")
            except Exception as cleanup_e:
                logger.error(f"Error during cleanup of frames directory {frames_dir}: {cleanup_e}")