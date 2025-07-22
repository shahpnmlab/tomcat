"""
Session Models for TomCat Application

This module provides classes for handling session data operations,
including loading, saving, and manipulating tomogram session data.
"""
import os
import time
import logging
import pandas as pd
from werkzeug.utils import secure_filename
from contextlib import contextmanager # Add this import

logger = logging.getLogger(__name__)


class Session:
    """
    Represents a TomCat session with tomogram data.
    Provides methods to load, save, and manipulate session data.
    """

    def __init__(self, config, filename=None):
        """
        Initialize a session.

        Args:
            config: Application configuration object
            filename (str, optional): Name of the session file. If None, a new session is created.
        """
        self.config = config
        self.filename = filename
        self.filepath = None

        # Default empty dataframe with the required schema
        self._df = pd.DataFrame({
            'tomo_name': [],
            'thickness': [],
            'notes': [],
            'delete': [],
            'score': [],
            'double_confirmed': []
        })
        self._defer_save = False # Add this line

        # Load existing session if filename is provided
        if filename:
            self.filepath = os.path.join(config.upload_folder, filename)
            self.load()

    def load(self):
        """
        Load session data from file.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.filepath or not os.path.exists(self.filepath):
            logger.warning(f"Session file not found: {self.filepath}")
            return False

        try:
            # Load the CSV file
            self._df = pd.read_csv(self.filepath)

            # Ensure all required columns exist
            for col in ['tomo_name', 'thickness', 'notes', 'delete', 'score', 'double_confirmed']:
                if col not in self._df.columns:
                    if col == 'double_confirmed':
                        self._df[col] = False
                    elif col == 'thickness' or col == 'score':
                        self._df[col] = 0.0
                    elif col == 'delete':
                        self._df[col] = False
                    else:
                        self._df[col] = ''

            logger.info(f"Loaded session from {self.filepath}")
            return True

        except Exception as e:
            logger.error(f"Error loading session: {str(e)}")
            return False

    def save(self):
        """
        Save session data to file.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.filepath:
            logger.error("Cannot save session: no filepath specified")
            return False

        try:
            # Save the session dataframe to its designated filepath
            self._df.to_csv(self.filepath, index=False)
            logger.info(f"Saved session to {self.filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving session: {str(e)}")
            return False

    def create_new_session(self, custom_name=None):
        """
        Create a new session with a custom filename or a default timestamp-based one.

        Args:
            custom_name (str, optional): Custom name for the session.
                                        If None, a timestamp-based name is used.

        Returns:
            str: New session filename if successful, None otherwise
        """
        try:
            # Create a timestamp-based filename or use the custom one
            if custom_name:
                # Make sure filename ends with .tomcat and is safe
                if not custom_name.lower().endswith('.tomcat'):
                    custom_name += '.tomcat'
                new_filename = secure_filename(custom_name)
            else:
                # Default timestamp-based name with .tomcat extension
                timestamp = int(time.time())
                new_filename = f"tomcat_session_{timestamp}.tomcat"

            # Set the filepath for the new session
            self.filename = new_filename
            self.filepath = os.path.join(self.config.upload_folder, new_filename)

            # Reset dataframe to empty with required schema
            self._df = pd.DataFrame({
                'tomo_name': [],
                'thickness': [],
                'notes': [],
                'delete': [],
                'score': [],
                'double_confirmed': []
            })

            # Save the new session
            if self.save():
                return new_filename
            else:
                return None

        except Exception as e:
            logger.error(f"Error creating new session: {str(e)}")
            return None

    def get_data(self):
        """
        Get the session data as a pandas DataFrame, sorted alphabetically by tomogram name.

        Returns:
            pandas.DataFrame: Session data sorted by tomo_name
        """
        # Return a copy of the dataframe sorted by tomo_name in ascending order
        return self._df.sort_values('tomo_name', ascending=True).reset_index(drop=True)

    @contextmanager
    def deferred_save(self):
        """Context manager to defer saving until the block is exited."""
        self._defer_save = True
        try:
            yield
        finally:
            self._defer_save = False
            self.save()

    def get_tomogram_data(self, tomo_name):
        """
        Get data for a specific tomogram.

        Args:
            tomo_name (str): Name of the tomogram

        Returns:
            dict or None: Tomogram data as a dictionary, or None if not found
        """
        tomo_row = self._df[self._df['tomo_name'] == tomo_name]
        if tomo_row.empty:
            return None

        return tomo_row.iloc[0].to_dict()

    def update_tomogram_data(self, tomo_name, **kwargs):
        """
        Update data for a specific tomogram.

        Args:
            tomo_name (str): Name of the tomogram
            **kwargs: Key-value pairs to update

        Returns:
            bool: True if successful, False otherwise
        """
        if tomo_name not in self._df['tomo_name'].values:
            logger.error(f"Tomogram not found in session: {tomo_name}")
            return False

        try:
            # Update each provided field
            for key, value in kwargs.items():
                if key in self._df.columns:
                    self._df.loc[self._df['tomo_name'] == tomo_name, key] = value

            # Save the updated session unless deferred
            if not self._defer_save:
                return self.save()
            return True

        except Exception as e:
            logger.error(f"Error updating tomogram data: {str(e)}")
            return False

    def add_tomogram(self, tomo_name, thickness=0.0, notes='', delete=False, score=0.0, double_confirmed=False):
        """
        Add a new tomogram to the session.

        Args:
            tomo_name (str): Name of the tomogram
            thickness (float, optional): Thickness value
            notes (str, optional): Notes about the tomogram
            delete (bool, optional): Whether the tomogram is marked for deletion
            score (float, optional): Score value
            double_confirmed (bool, optional): Whether the tomogram is double confirmed

        Returns:
            bool: True if successful, False otherwise
        """
        if tomo_name in self._df['tomo_name'].values:
            logger.warning(f"Tomogram already exists in session: {tomo_name}")
            return False

        try:
            # Create a new row for this tomogram
            new_row = pd.DataFrame({
                'tomo_name': [tomo_name],
                'thickness': [thickness],
                'notes': [notes],
                'delete': [delete],
                'score': [score],
                'double_confirmed': [double_confirmed]
            })

            # Add the new row to the dataframe
            self._df = pd.concat([self._df, new_row], ignore_index=True)

            # Save the updated session
            return self.save()

        except Exception as e:
            logger.error(f"Error adding tomogram: {str(e)}")
            return False

    def add_tomograms_from_search(self, search_results):
        """
        Add multiple tomograms from search results.

        Args:
            search_results (list): List of dictionaries with tomogram information

        Returns:
            tuple: (count_added, count_skipped)
        """
        added_count = 0
        skipped_count = 0

        try:
            # Get existing tomogram names
            existing_tomo_names = self._df['tomo_name'].values

            # Prepare new rows
            new_rows = []

            for result in search_results:
                tomo_name = result['name']

                # Skip if already exists
                if tomo_name in existing_tomo_names:
                    skipped_count += 1
                    continue

                # Create a new row for this tomogram
                new_rows.append({
                    'tomo_name': tomo_name,
                    'thickness': 0.0,
                    'notes': '',
                    'delete': False,
                    'score': 0.0,
                    'double_confirmed': False
                })

                added_count += 1

            if new_rows:
                # Add all new rows at once
                self._df = pd.concat([self._df, pd.DataFrame(new_rows)], ignore_index=True)

                # Save the updated session
                self.save()

            return (added_count, skipped_count)

        except Exception as e:
            logger.error(f"Error adding tomograms from search: {str(e)}")
            return (added_count, skipped_count)

    def get_tomogram_names(self):
        """
        Get a list of all tomogram names in the session.

        Returns:
            list: List of tomogram names
        """
        return self._df['tomo_name'].tolist()


class SessionManager:
    """
    Manages multiple sessions, provides methods to list, create, and load sessions.
    """

    def __init__(self, config):
        """
        Initialize the session manager.

        Args:
            config: Application configuration object
        """
        self.config = config

    def get_sessions(self):
        """
        Get a list of all available sessions.

        Returns:
            list: List of session information dictionaries
        """
        # Check for existing session files (both .csv and .tomcat)
        csv_files = [f for f in os.listdir(self.config.upload_folder)
                     if f.endswith('.csv')]
        tomcat_files = [f for f in os.listdir(self.config.upload_folder)
                        if f.endswith('.tomcat')]

        session_files = csv_files + tomcat_files

        # Sort by modification time (most recent first)
        session_files.sort(
            key=lambda f: os.path.getmtime(os.path.join(self.config.upload_folder, f)),
            reverse=True
        )

        # Get list of existing sessions for display
        sessions = []
        for filename in session_files:
            file_path = os.path.join(self.config.upload_folder, filename)
            mtime = os.path.getmtime(file_path)

            # Try to get the count of entries
            try:
                df = pd.read_csv(file_path)
                entry_count = len(df)
            except:
                entry_count = 0

            sessions.append({
                'filename': filename,
                'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime)),
                'entry_count': entry_count
            })

        return sessions

    def create_session(self, custom_name=None):
        """
        Create a new session.

        Args:
            custom_name (str, optional): Custom name for the session.

        Returns:
            Session: New session object
        """
        session = Session(self.config)
        filename = session.create_new_session(custom_name)

        if filename:
            logger.info(f"Created new session: {filename}")
            return session
        else:
            logger.error("Failed to create new session")
            return None

    def load_session(self, filename):
        """
        Load an existing session.

        Args:
            filename (str): Name of the session file

        Returns:
            Session: Loaded session object or None if not found
        """
        filepath = os.path.join(self.config.upload_folder, filename)

        if not os.path.exists(filepath):
            logger.error(f"Session file not found: {filepath}")
            return None

        return Session(self.config, filename)