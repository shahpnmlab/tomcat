"""
File Utility Functions for TomCat Application

This module provides utility functions for file operations, including
finding and identifying tomogram files.
"""
import os
import re
import logging
import glob

logger = logging.getLogger(__name__)


def extract_basename(filename):
    """
    Extract the proper basename from a filename based on common patterns.
    Removes common suffixes and pattern elements to identify the true basename.

    Args:
        filename (str): Original filename including extensions

    Returns:
        str: Extracted basename without suffixes
    """
    # Remove path if present
    name = os.path.basename(filename)

    # Define suffixes to remove in order of specificity
    tomogram_suffixes = ['_rec.mrc', '_rec', '.rec.mrc', '.rec', '.mrc']
    tiltseries_suffixes = ['_ali.mrc', '_ali', '.ali.mrc', '.ali', '.st', '.st.mrc']
    lowmag_suffixes = ['.dm4', '.tif', '.tiff', '.jpg', '.jpeg', '.png']

    # Combine all suffixes
    all_suffixes = tomogram_suffixes + tiltseries_suffixes + lowmag_suffixes

    # Try to remove suffixes
    for suffix in all_suffixes:
        if name.lower().endswith(suffix.lower()):
            name = name[:-len(suffix)]
            break

    # Remove common processing parameters using regex
    patterns = [
        r'_rec',
        r'_ali',
        r'_bin\d+$',  # Remove binning info (e.g., _bin8)
        r'_\d+\.\d+Apx$',  # Remove pixel size info (e.g., _10.00Apx)
        r'_\d+k$',  # Remove resolution info (e.g., _8k)
        r'_[a-z]+\d+$'  # Remove generic parameter (e.g., _param123)
    ]

    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            name = name[:match.start()]

    return name


class FileLocator:
    """
    Utility class for finding files related to tomograms.
    Provides methods to locate lowmag, tiltseries, and tomogram files.
    """

    # File extension definitions
    EXTENSIONS = {
        'tomogram': ['.mrc', '_rec.mrc', '.rec', '.rec.mrc', '_rec'],
        'tiltseries': ['_ali.mrc', '.ali', '.st', '.st.mrc'],
        'lowmag': ['.mrc', '.dm4', '.tif', '.tiff', '.jpg', '.jpeg', '.png']
    }

    # Priority order for file types (higher index = higher priority)
    TYPE_PRIORITY = {'lowmag': 1, 'tiltseries': 2, 'tomogram': 3}

    def __init__(self, config):
        """
        Initialize FileLocator with application configuration.

        Args:
            config: Configuration object containing path information
        """
        self.config = config

    def find_tomogram_file(self, tomo_name):
        """
        Find tomogram file for a specific tomogram name.

        Args:
            tomo_name (str): The name of the tomogram to find

        Returns:
            str or None: Path to the tomogram file if found, None otherwise
        """
        return self.find_file(tomo_name, self.config.paths['tomogram_path'],
                              self.EXTENSIONS['tomogram'])

    def find_tiltseries_file(self, tomo_name):
        """
        Find tilt series file for a specific tomogram name.

        Args:
            tomo_name (str): The name of the tomogram to find

        Returns:
            str or None: Path to the tilt series file if found, None otherwise
        """
        return self.find_file(tomo_name, self.config.paths['tiltseries_path'],
                              self.EXTENSIONS['tiltseries'])

    def find_lowmag_file(self, tomo_name):
        """
        Find low-mag overview file for a specific tomogram name.

        Args:
            tomo_name (str): The name of the tomogram to find

        Returns:
            str or None: Path to the low-mag file if found, None otherwise
        """
        return self.find_file(tomo_name, self.config.paths['lowmag_path'],
                              self.EXTENSIONS['lowmag'])

    def find_thumbnail(self, tomo_name, thumbnails_folder):
        """
        Find thumbnail for a specific tomogram name.

        Args:
            tomo_name (str): The name of the tomogram to find thumbnail for
            thumbnails_folder (str): Path to the thumbnails folder

        Returns:
            str or None: Path to the thumbnail file if found, None otherwise
        """
        pattern = os.path.join(thumbnails_folder, f"{tomo_name}*.png")
        matching_files = glob.glob(pattern)
        if matching_files:
            return matching_files[0]
        return None

    def find_file(self, tomo_name, directory, extensions):
        """
        Find a file for a specific tomogram in the given directory with allowed extensions.
        Prioritizes more specific extensions (longer ones) over generic ones.

        Args:
            tomo_name (str): Tomogram name to find
            directory (str): Directory to search in
            extensions (list): List of file extensions to look for

        Returns:
            str or None: Path to the file if found, None otherwise
        """
        if not directory or not os.path.exists(directory):
            logger.warning(f"Directory not found or not configured: {directory}")
            return None

        # Log what we're searching for
        logger.debug(f"Searching for {tomo_name} in {directory} with extensions {extensions}")

        # Sort extensions by length (descending) to prioritize more specific patterns
        # For example, '_rec.mrc' would be checked before '.mrc'
        sorted_extensions = sorted(extensions, key=len, reverse=True)

        # Look for exact match first with prioritized extensions
        for ext in sorted_extensions:
            file_path = os.path.join(directory, f"{tomo_name}{ext}")
            if os.path.exists(file_path) and os.path.isfile(file_path):
                logger.debug(f"Found exact match: {file_path}")
                return file_path

        # Collect all candidate files first
        candidates = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_lower = file.lower()
                # Check if file has one of the allowed extensions AND contains the tomogram name
                if tomo_name.lower() in file_lower:
                    for ext in sorted_extensions:
                        if file_lower.endswith(ext.lower()):
                            candidates.append({
                                'file': file,
                                'path': os.path.join(root, file),
                                'ext': ext,
                                'basename': extract_basename(file)
                            })
                            break  # Once we've matched an extension, don't check others

        # Process candidates in priority order
        if candidates:
            # First, look for exact basename matches
            exact_matches = [c for c in candidates if c['basename'].lower() == tomo_name.lower()]
            if exact_matches:
                # Sort exact matches by extension priority (index in sorted_extensions)
                best_match = sorted(exact_matches,
                                    key=lambda c: sorted_extensions.index(c['ext']))[0]
                logger.debug(f"Found exact basename match: {best_match['path']}")
                return best_match['path']

            # If no exact basename match, take the candidate with highest extension priority
            best_match = sorted(candidates,
                                key=lambda c: sorted_extensions.index(c['ext']))[0]
            logger.debug(f"Found best partial match: {best_match['path']}")
            return best_match['path']

        logger.warning(f"No file found for {tomo_name} with extensions {extensions} in {directory}")
        return None

    def search_tomograms(self, basename):
        """
        Recursively search for tomograms in the configured directories
        based on the provided basename. Excludes lowmag files from search results.

        Args:
            basename (str): Base name to search for

        Returns:
            list: List of dictionaries with tomogram information, consolidated by basename
        """
        # Dictionary to hold results, keyed by basename to avoid duplicates
        results_dict = {}

        # Search in tomogram and tiltseries paths only (exclude lowmag files)
        search_paths = [
            (self.config.paths['tomogram_path'], 'tomogram', self.EXTENSIONS['tomogram']),
            (self.config.paths['tiltseries_path'], 'tiltseries', self.EXTENSIONS['tiltseries']),
            # Lowmag path has been removed from search paths
        ]

        for path, file_type, extensions in search_paths:
            if not path or not os.path.exists(path):
                continue

            for root, dirs, files in os.walk(path):
                for file in files:
                    if basename.lower() in file.lower() and any(
                            file.lower().endswith(ext.lower()) for ext in extensions):
                        # Extract proper basename
                        tomo_name = extract_basename(file)

                        # Check if we should replace an existing entry
                        should_replace = (
                                tomo_name not in results_dict or
                                self.TYPE_PRIORITY.get(file_type, 0) > self.TYPE_PRIORITY.get(
                            results_dict[tomo_name]['type'], 0)
                        )

                        if should_replace:
                            results_dict[tomo_name] = {
                                'name': tomo_name,
                                'path': os.path.join(root, file),
                                'type': file_type,
                                'filename': file
                            }

        # Convert dictionary to list for return
        return list(results_dict.values())