"""
Media Utility Functions for TomCat Application

This module provides utility functions for media operations including
generating thumbnails, animations, and other visualizations from MRC files.
"""
import os
import sys
import logging
import traceback
import numpy as np
from PIL import Image, UnidentifiedImageError
import mrcfile
import imageio
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MediaProcessingError(Exception):
    """Custom exception for media processing errors with detailed context."""
    pass

@contextmanager
def safe_file_open(file_path, mode='rb'):
    """
    Context manager for safely opening files with proper error handling.

    Args:
        file_path (str): Path to the file to open
        mode (str): File open mode

    Yields:
        file: Opened file handle

    Raises:
        MediaProcessingError: If file cannot be opened or accessed
    """
    file_obj = None
    try:
        file_obj = open(file_path, mode)
        yield file_obj
    except FileNotFoundError:
        raise MediaProcessingError(f"File not found: {file_path}")
    except PermissionError:
        raise MediaProcessingError(f"Permission denied when accessing: {file_path}")
    except IsADirectoryError:
        raise MediaProcessingError(f"Expected a file but got a directory: {file_path}")
    except Exception as e:
        raise MediaProcessingError(f"Error opening file {file_path}: {str(e)}")
    finally:
        if file_obj:
            file_obj.close()

def normalize_tomogram_data(data):
    """
    Normalize tomogram data to values between 0 and 255 for display.
    Uses percentile-based contrast enhancement to improve visibility
    of features in tomogram slices.

    Args:
        data (numpy.ndarray): Input tomogram slice data

    Returns:
        numpy.ndarray: Normalized data with values between 0 and 255
    """
    # Remove NaN values
    data = np.nan_to_num(data)

    # Get min and max values (excluding outliers)
    # For tomograms, use 1st and 99th percentiles to enhance contrast
    p_low, p_high = np.percentile(data, [1, 99])

    # Clip data to the percentile range
    data = np.clip(data, p_low, p_high)

    # Normalize to [0, 255]
    if p_high > p_low:
        data = ((data - p_low) / (p_high - p_low) * 255).astype(np.uint8)
    else:
        # Handle case where p_low equals p_high (flat data)
        data = np.zeros(data.shape, dtype=np.uint8)

    return data

def normalize_tiltseries_data(data):
    """
    Normalize tilt series data to values between 0 and 255 for display.
    Uses a wider percentile range to preserve more of the original
    dynamic range while still removing extreme outliers.

    Args:
        data (numpy.ndarray): Input tilt series slice data

    Returns:
        numpy.ndarray: Normalized data with values between 0 and 255
    """
    # Remove NaN values
    data = np.nan_to_num(data)

    # For tilt series, use wider percentile range (0.5-99.5) to preserve
    # more of the original data range while still removing extreme outliers
    p_low, p_high = np.percentile(data, [0.5, 99.5])

    # Clip data to the percentile range
    data = np.clip(data, p_low, p_high)

    # Normalize to [0, 255]
    if p_high > p_low:
        data = ((data - p_low) / (p_high - p_low) * 255).astype(np.uint8)
    else:
        # Handle case where p_low equals p_high (flat data)
        data = np.zeros(data.shape, dtype=np.uint8)

    return data

def normalize_image_data(data):
    """
    Generic normalize image data to values between 0 and 255 for display.
    Uses percentile-based contrast enhancement suitable for general images.

    Args:
        data (numpy.ndarray): Input image data

    Returns:
        numpy.ndarray: Normalized data with values between 0 and 255
    """
    # Remove NaN values
    data = np.nan_to_num(data)

    # Get min and max values (excluding outliers)
    p_low, p_high = np.percentile(data, [1, 99])

    # Clip data to the percentile range
    data = np.clip(data, p_low, p_high)

    # Normalize to [0, 255]
    if p_high > p_low:
        data = ((data - p_low) / (p_high - p_low) * 255).astype(np.uint8)
    else:
        # Handle case where p_low equals p_high (flat data)
        data = np.zeros(data.shape, dtype=np.uint8)

    return data

def validate_mrc_file(file_path):
    """
    Validates that an MRC file exists, is readable, and contains valid data.

    Args:
        file_path (str): Path to the MRC file

    Returns:
        tuple: (is_valid, message) where is_valid is a boolean and message is a string

    Raises:
        MediaProcessingError: If validation fails
    """
    if not os.path.exists(file_path):
        raise MediaProcessingError(f"MRC file does not exist: {file_path}")

    if not os.path.isfile(file_path):
        raise MediaProcessingError(f"Path is not a file: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise MediaProcessingError(f"MRC file is empty: {file_path}")

    try:
        with mrcfile.open(file_path, permissive=True) as mrc:
            if mrc.data is None:
                raise MediaProcessingError(f"MRC file contains no data: {file_path}")

            if np.all(mrc.data == 0):
                raise MediaProcessingError(f"MRC file contains only zeros: {file_path}")

            # Check for NaN or infinity values
            if np.isnan(mrc.data).any() or np.isinf(mrc.data).any():
                # Don't raise, just log a warning
                logger.warning(f"MRC file contains NaN or infinite values: {file_path}")

            return True, "MRC file is valid"
    except mrcfile.utils.ReadOnlyError:
        raise MediaProcessingError(f"MRC file is not readable: {file_path}")
    except mrcfile.utils.InvalidMRCError as e:
        raise MediaProcessingError(f"Invalid MRC file format: {file_path}, {str(e)}")
    except Exception as e:
        raise MediaProcessingError(f"Error validating MRC file: {file_path}, {str(e)}")

def get_traceback_str():
    """Returns formatted traceback information for logging."""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    return ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))


def generate_jpeg_thumbnail(source_file, output_file, min_side=150):
    """
    Generate a JPEG thumbnail from an MRC file or other image file.

    Args:
        source_file (str): Path to the source file (MRC, JPG, PNG, etc.)
        output_file (str): Path to save the thumbnail to
        min_side (int, optional): Minimum side length for the thumbnail

    Returns:
        bool: True if successful, False otherwise
    """
    # Check input parameters
    if not source_file or not output_file:
        logger.error("Missing required parameters: source_file and output_file must be specified")
        return False

    if not os.path.exists(source_file):
        logger.error(f"Source file does not exist: {source_file}")
        return False

    if min_side <= 0:
        logger.error(f"Invalid minimum side length: {min_side}")
        return False

    # Track file type for better error reporting
    file_type = "unknown"

    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Handle different file types
        if source_file.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
            file_type = "image"
            return _generate_thumbnail_from_image(source_file, output_file, min_side)

        elif source_file.lower().endswith(('.mrc', '.rec', '.rec.mrc')):
            file_type = "mrc"
            # Validate the MRC file first
            validate_mrc_file(source_file)
            return _generate_thumbnail_from_mrc(source_file, output_file, min_side)

        else:
            logger.error(f"Unsupported file format for thumbnail generation: {source_file}")
            return False

    except MediaProcessingError as e:
        logger.error(f"Media processing error for {file_type} file: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error generating thumbnail from {file_type} file: {str(e)}")
        logger.debug(get_traceback_str())
        return False
    finally:
        # Clean up partial output file if generation failed
        if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            try:
                os.remove(output_file)
                logger.debug(f"Removed empty output file: {output_file}")
            except:
                pass

def parse_tilt_angles(tlt_file):
    """Parses a .tlt or .rawtlt file and returns a list of angles."""
    if not tlt_file or not os.path.exists(tlt_file):
        return None
    try:
        angles = []
        with open(tlt_file, 'r') as f:
            for line in f:
                try:
                    # Attempt to convert each line to a float, skipping if it fails
                    angles.append(float(line.strip()))
                except (ValueError, TypeError):
                    continue # Ignore non-numeric lines
        return angles
    except Exception as e:
        logger.error(f"Could not parse tilt file {tlt_file}: {e}")
        return None

def generate_frames_from_mrc(source_file, output_dir, media_type, max_frames=200):
    """
    Generates individual JPEG frames from an MRC file into a directory.
    Returns the number of frames generated.
    """
    try:
        validate_mrc_file(source_file) # Validator is already in this file
        with mrcfile.open(source_file, permissive=True) as mrc:
            data = mrc.data
            if data is None or (hasattr(data, 'size') and data.size == 0):
                logger.error(f"MRC data is None or empty for {source_file}")
                return 0
            if len(data.shape) != 3:
                # If not 3D, perhaps it's a single 2D image. Log and try to process as one frame.
                if len(data.shape) == 2:
                    logger.warning(f"Expected 3D data for frame generation, got 2D. Processing as single frame: {source_file}")
                    num_slices = 1
                    slice_data_is_2d = True
                else:
                    raise MediaProcessingError(f"Expected 3D data for frame generation, got {len(data.shape)}D data. Shape: {data.shape}")
            else:
                num_slices = data.shape[0]
                slice_data_is_2d = False

            if num_slices == 0:
                logger.warning(f"No slices found in MRC file: {source_file}")
                return 0

            step = max(1, num_slices // max_frames if num_slices > 1 else 1) # Ensure step is at least 1

            frame_count = 0
            os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists

            for i in range(0, num_slices, step):
                if slice_data_is_2d: # Handle the 2D as single slice case
                    slice_data = data
                else:
                    slice_data = data[i]

                # Use the correct normalization function based on media type
                if media_type == 'tiltseries':
                    normalized = normalize_tiltseries_data(slice_data)
                else: # Default to tomogram normalization for 'tomogram' or other types
                    normalized = normalize_tomogram_data(slice_data)

                # Convert to an 8-bit grayscale image
                img = Image.fromarray(normalized).convert('L')

                # Save as a high-quality JPEG
                frame_path = os.path.join(output_dir, f"{frame_count}.jpg")
                img.save(frame_path, 'JPEG', quality=90)
                frame_count += 1
                if slice_data_is_2d: # If it was a single 2D image, break after one frame
                    break
            return frame_count
    except MediaProcessingError as e: # Catch specific media processing errors
        logger.error(f"MediaProcessingError while generating frames from {source_file}: {e}")
        # Clean up any partial frames
        if os.path.isdir(output_dir):
            for f_name in os.listdir(output_dir):
                try:
                    os.remove(os.path.join(output_dir, f_name))
                except OSError:
                    pass # Ignore if file is already gone or other issues
        return 0
    except Exception as e:
        logger.error(f"Failed to generate frames from {source_file}: {e}")
        logger.debug(get_traceback_str()) # Log full traceback for unexpected errors
        # Clean up any partial frames
        if os.path.isdir(output_dir):
            for f_name in os.listdir(output_dir):
                try:
                    os.remove(os.path.join(output_dir, f_name))
                except OSError:
                    pass
        return 0

def _generate_thumbnail_from_image(source_file, output_file, min_side):
    """Helper function to generate thumbnail from standard image formats."""
    try:
        # For image files, use PIL directly
        img = Image.open(source_file)

        # Check if image is valid
        if img.width <= 0 or img.height <= 0:
            raise MediaProcessingError(f"Invalid image dimensions: {img.width}x{img.height}")

        # Convert to RGB if it's not already
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize preserving aspect ratio
        width, height = img.size
        ratio = max(min_side / width, min_side / height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        # Save as JPEG
        img.save(output_file, 'JPEG', quality=85)
        logger.info(f"Generated thumbnail from image file: {output_file}")
        return True

    except UnidentifiedImageError:
        raise MediaProcessingError(f"File is not a valid image: {source_file}")
    except OSError as e:
        raise MediaProcessingError(f"OS error handling image file: {str(e)}")
    except Exception as e:
        raise MediaProcessingError(f"Error processing image file: {str(e)}")

def _generate_thumbnail_from_mrc(source_file, output_file, min_side):
    """Helper function to generate thumbnail from MRC files."""
    try:
        # For MRC files, use mrcfile library
        with mrcfile.open(source_file, permissive=True) as mrc:
            # Get the data as a numpy array
            data = mrc.data

            if data is None or data.size == 0:
                raise MediaProcessingError("MRC file contains no data")

            # For multi-slice data (3D), take a projection or middle slice
            if len(data.shape) == 3:
                if data.shape[0] == 0:
                    raise MediaProcessingError("MRC file has 0 slices")

                # Use the middle slice for thumbnail
                middle_slice = data.shape[0] // 2
                slice_data = data[middle_slice]
                logger.debug(f"Using middle slice ({middle_slice}) from 3D volume with {data.shape[0]} slices")
            else:
                # Use the data as is for 2D
                slice_data = data
                logger.debug(f"Using 2D data with shape {slice_data.shape}")

            # Handle NaN or infinite values
            if np.isnan(slice_data).any() or np.isinf(slice_data).any():
                logger.warning(f"Replacing NaN/Inf values in MRC data from {source_file}")
                slice_data = np.nan_to_num(slice_data, nan=0.0, posinf=np.max(slice_data[~np.isinf(slice_data)]),
                                          neginf=np.min(slice_data[~np.isinf(slice_data)]))

            # Normalize using percentile-based approach
            normalized = normalize_image_data(slice_data)

            # Create PIL image
            img = Image.fromarray(normalized)

            # Check image dimensions
            if img.width <= 0 or img.height <= 0:
                raise MediaProcessingError(f"Invalid image dimensions after normalization: {img.width}x{img.height}")

            # Resize preserving aspect ratio
            width, height = img.size
            ratio = max(min_side / width, min_side / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

            # Save as JPEG
            img.save(output_file, 'JPEG', quality=85)
            logger.info(f"Generated thumbnail from MRC file: {output_file}, dimensions: {new_size}")
            return True

    except mrcfile.utils.ReadOnlyError:
        raise MediaProcessingError(f"MRC file is not readable: {source_file}")
    except mrcfile.utils.InvalidMRCError as e:
        raise MediaProcessingError(f"Invalid MRC file format: {str(e)}")
    except Exception as e:
        raise MediaProcessingError(f"Error processing MRC file: {str(e)}")

def generate_tiltseries_animation(source_file, output_file, min_side=384, fps=10, max_frames=100):
    """
    Generate a GIF animation from a tilt series MRC file.
    Uses specialized normalization for tilt series data.

    Args:
        source_file (str): Path to the source tilt series MRC file
        output_file (str): Path to save the GIF animation to
        min_side (int, optional): Minimum side length for the frames
        fps (int, optional): Frames per second for the animation
        max_frames (int, optional): Maximum number of frames to include in animation

    Returns:
        bool: True if successful, False otherwise
    """
    # Validate input parameters
    if not source_file or not output_file:
        logger.error("Missing required parameters: source_file and output_file must be specified")
        return False

    if not os.path.exists(source_file):
        logger.error(f"Source file does not exist: {source_file}")
        return False

    if min_side <= 0 or fps <= 0 or max_frames <= 0:
        logger.error(f"Invalid parameters: min_side={min_side}, fps={fps}, max_frames={max_frames}")
        return False

    try:
        # Validate the MRC file first
        validate_mrc_file(source_file)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Open the MRC file
        with mrcfile.open(source_file, permissive=True) as mrc:
            # Get the data as a numpy array
            data = mrc.data

            # Check if this is a tilt series (should be 3D data)
            if len(data.shape) != 3:
                raise MediaProcessingError(
                    f"Expected 3D data for tilt series, got {len(data.shape)}D data with shape {data.shape}")

            # Check if there are enough slices
            if data.shape[0] < 2:
                raise MediaProcessingError(
                    f"Not enough slices for animation in tilt series: {data.shape[0]} slices")

            # Handle NaN or infinite values
            if np.isnan(data).any() or np.isinf(data).any():
                logger.warning(f"Replacing NaN/Inf values in tilt series data from {source_file}")
                # Get valid min/max for replacement values
                valid_data = data[~np.isnan(data) & ~np.isinf(data)]
                if valid_data.size > 0:
                    valid_min, valid_max = np.min(valid_data), np.max(valid_data)
                else:
                    valid_min, valid_max = 0, 1  # Fallback if all data is invalid

                data = np.nan_to_num(data, nan=valid_min, posinf=valid_max, neginf=valid_min)

            # Log data shape
            logger.info(f"Tilt series shape: {data.shape}")

            # Determine frame sampling based on max_frames
            num_slices = data.shape[0]
            step = max(1, num_slices // max_frames)

            # Prepare frames for the animation
            frames = []
            pil_frames = []  # For PIL fallback
            frame_count = 0

            for i in range(0, num_slices, step):
                # Get the current slice
                slice_data = data[i]

                # Apply specialized normalization for tilt series
                normalized = normalize_tiltseries_data(slice_data)

                # Create PIL image
                img = Image.fromarray(normalized)

                # Resize preserving aspect ratio
                width, height = img.size
                ratio = max(min_side / width, min_side / height)
                new_size = (int(width * ratio), int(height * ratio))

                try:
                    img = img.resize(new_size, Image.LANCZOS)
                except Exception as e:
                    logger.warning(f"Error resizing frame {i}, trying nearest neighbor: {str(e)}")
                    img = img.resize(new_size, Image.NEAREST)

                # Convert to RGB for GIF
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Add to frames (numpy array for imageio)
                frames.append(np.array(img))
                # Also keep PIL image for fallback
                pil_frames.append(img)

                frame_count += 1

                # Progress logging for large datasets
                if frame_count % 20 == 0:
                    logger.debug(f"Processed {frame_count} frames for tilt series animation")

            if not frames:
                raise MediaProcessingError("No frames were generated for the animation")

            # Use a temporary file first to avoid empty file issues
            temp_output = output_file + ".tmp"
            animation_saved = False

            # Method 1: Try imageio with explicit format
            try:
                logger.debug("Trying animation save method 1: imageio with explicit format")
                imageio.mimsave(temp_output, frames, format='GIF', fps=fps, loop=0)

                if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                    os.replace(temp_output, output_file)
                    animation_saved = True
                    logger.info(f"Generated tilt series animation with imageio (method 1): {output_file}")
            except Exception as e:
                logger.warning(f"Failed to save animation with imageio explicit format: {str(e)}")
                # Continue to next method if this fails

            # Method 2: Try PIL directly if imageio failed
            if not animation_saved:
                try:
                    logger.debug("Trying animation save method 2: PIL direct")
                    # Convert fps to duration in ms for PIL
                    duration = int(1000 / fps)

                    # Save with PIL
                    pil_frames[0].save(
                        temp_output,
                        format='GIF',
                        append_images=pil_frames[1:],
                        save_all=True,
                        duration=duration,
                        loop=0,
                        optimize=False
                    )

                    if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                        os.replace(temp_output, output_file)
                        animation_saved = True
                        logger.info(f"Generated tilt series animation with PIL (method 2): {output_file}")
                except Exception as e:
                    logger.warning(f"Failed to save animation with PIL: {str(e)}")

            # Check if any method succeeded
            if animation_saved:
                logger.info(f"Successfully generated tilt series animation: {output_file}, size: {os.path.getsize(output_file)/1024:.1f} KB")
                return True
            else:
                raise MediaProcessingError("All animation saving methods failed")

    except MediaProcessingError as e:
        logger.error(f"Media processing error: {str(e)}")
        return False
    except MemoryError:
        logger.error(f"Not enough memory to process tilt series: {source_file}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error generating tilt series animation: {str(e)}")
        logger.debug(get_traceback_str())
        return False
    finally:
        # Clean up partial output files
        temp_output = output_file + ".tmp"
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
                logger.debug(f"Removed temporary output file: {temp_output}")
            except:
                pass

        if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            try:
                os.remove(output_file)
                logger.debug(f"Removed empty output file: {output_file}")
            except:
                pass

def generate_tomogram_animation(source_file, output_file, min_side=384, fps=10, max_frames=50):
    """
    Generate a GIF animation from a tomogram MRC file.
    Shows slices through the tomogram volume with specialized normalization
    for tomogram data.

    Args:
        source_file (str): Path to the source tomogram MRC file
        output_file (str): Path to save the GIF animation to
        min_side (int, optional): Minimum side length for the frames
        fps (int, optional): Frames per second for the animation
        max_frames (int, optional): Maximum number of frames to include in animation

    Returns:
        bool: True if successful, False otherwise
    """
    # Validate input parameters
    if not source_file or not output_file:
        logger.error("Missing required parameters: source_file and output_file must be specified")
        return False

    if not os.path.exists(source_file):
        logger.error(f"Source file does not exist: {source_file}")
        return False

    if min_side <= 0 or fps <= 0 or max_frames <= 0:
        logger.error(f"Invalid parameters: min_side={min_side}, fps={fps}, max_frames={max_frames}")
        return False

    try:
        # Validate the MRC file first
        validate_mrc_file(source_file)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Open the MRC file
        with mrcfile.open(source_file, permissive=True) as mrc:
            # Get the data as a numpy array
            data = mrc.data

            # Check if this is a 3D volume
            if len(data.shape) != 3:
                raise MediaProcessingError(
                    f"Expected 3D data for tomogram, got {len(data.shape)}D data with shape {data.shape}")

            # Check if there are enough slices
            if data.shape[0] < 2:
                raise MediaProcessingError(
                    f"Not enough slices for animation in tomogram: {data.shape[0]} slices")

            # Handle NaN or infinite values
            if np.isnan(data).any() or np.isinf(data).any():
                logger.warning(f"Replacing NaN/Inf values in tomogram data from {source_file}")
                # Get valid min/max for replacement values
                valid_data = data[~np.isnan(data) & ~np.isinf(data)]
                if valid_data.size > 0:
                    valid_min, valid_max = np.min(valid_data), np.max(valid_data)
                else:
                    valid_min, valid_max = 0, 1  # Fallback if all data is invalid

                data = np.nan_to_num(data, nan=valid_min, posinf=valid_max, neginf=valid_min)

            # We'll slice through the Z axis (first dimension in MRC files)
            num_slices = data.shape[0]

            # Determine step size based on max_frames
            step = max(1, num_slices // max_frames)

            logger.debug(f"Tomogram has {num_slices} slices, using step size {step}")

            # Log data shape
            logger.info(f"Tomogram shape: {data.shape}")

            # Prepare frames for the animation
            frames = []
            pil_frames = []  # For PIL fallback
            frame_count = 0

            for i in range(0, num_slices, step):
                # Get the current slice
                slice_data = data[i]

                # Apply specialized normalization for tomogram slices
                normalized = normalize_tomogram_data(slice_data)

                # Create PIL image
                img = Image.fromarray(normalized)

                # Resize preserving aspect ratio
                width, height = img.size
                ratio = max(min_side / width, min_side / height)
                new_size = (int(width * ratio), int(height * ratio))

                try:
                    img = img.resize(new_size, Image.LANCZOS)
                except Exception as e:
                    logger.warning(f"Error resizing frame {i}, trying nearest neighbor: {str(e)}")
                    img = img.resize(new_size, Image.NEAREST)

                # Convert to RGB for GIF
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Add to frames (numpy array for imageio)
                frames.append(np.array(img))
                # Also keep PIL image for fallback
                pil_frames.append(img)

                frame_count += 1

                # Progress logging for large datasets
                if frame_count % 20 == 0:
                    logger.debug(f"Processed {frame_count} frames for tomogram animation")

            if not frames:
                raise MediaProcessingError("No frames were generated for the animation")

            # Use a temporary file first to avoid empty file issues
            temp_output = output_file + ".tmp"
            animation_saved = False

            # Method 1: Try imageio with explicit format
            try:
                logger.debug("Trying animation save method 1: imageio with explicit format")
                imageio.mimsave(temp_output, frames, format='GIF', fps=fps, loop=0)

                if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                    os.replace(temp_output, output_file)
                    animation_saved = True
                    logger.info(f"Generated tomogram animation with imageio (method 1): {output_file}")
            except Exception as e:
                logger.warning(f"Failed to save animation with imageio explicit format: {str(e)}")
                # Continue to next method if this fails

            # Method 2: Try PIL directly if imageio failed
            if not animation_saved:
                try:
                    logger.debug("Trying animation save method 2: PIL direct")
                    # Convert fps to duration in ms for PIL
                    duration = int(1000 / fps)

                    # Save with PIL
                    pil_frames[0].save(
                        temp_output,
                        format='GIF',
                        append_images=pil_frames[1:],
                        save_all=True,
                        duration=duration,
                        loop=0,
                        optimize=False
                    )

                    if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                        os.replace(temp_output, output_file)
                        animation_saved = True
                        logger.info(f"Generated tomogram animation with PIL (method 2): {output_file}")
                except Exception as e:
                    logger.warning(f"Failed to save animation with PIL: {str(e)}")

            # Check if any method succeeded
            if animation_saved:
                logger.info(f"Successfully generated tomogram animation: {output_file}, size: {os.path.getsize(output_file)/1024:.1f} KB")
                return True
            else:
                raise MediaProcessingError("All animation saving methods failed")

    except MediaProcessingError as e:
        logger.error(f"Media processing error: {str(e)}")
        return False
    except MemoryError:
        logger.error(f"Not enough memory to process tomogram: {source_file}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error generating tomogram animation: {str(e)}")
        logger.debug(get_traceback_str())
        return False
    finally:
        # Clean up partial output files
        temp_output = output_file + ".tmp"
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
                logger.debug(f"Removed temporary output file: {temp_output}")
            except:
                pass

        if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            try:
                os.remove(output_file)
                logger.debug(f"Removed empty output file: {output_file}")
            except:
                pass