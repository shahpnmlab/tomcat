"""
Settings Routes for TomCat Application

This module handles all routes related to application settings,
including configuration, path management, and directory browsing.
"""
import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session as flask_session

logger = logging.getLogger(__name__)

# Create a Blueprint for settings routes
settings_bp = Blueprint('settings', __name__)


def initialize_routes(config):
    """
    Initialize settings routes with config object.

    Args:
        config: Application configuration object
    """

    @settings_bp.route('/settings', methods=['GET', 'POST'])
    def settings():
        """
        View and update application settings, particularly file paths.
        """
        if request.method == 'POST':
            # Update paths from form
            config.update_paths(
                lowmag_path=request.form.get('lowmag_path', ''),
                tiltseries_path=request.form.get('tiltseries_path', ''),
                tomogram_path=request.form.get('tomogram_path', ''),
                notes_path=request.form.get('notes_path', config.base_dir)
            )

            flash('Settings updated successfully')

            # Check if there's a current session to return to
            current_session = flask_session.get('current_session')
            if current_session:
                return redirect(url_for('session.process_csv', filename=current_session))
            else:
                return redirect(url_for('session.upload_file'))

        return render_template('settings.html', paths=config.paths)


    @settings_bp.route('/browse_directory', methods=['POST'])
    def browse_directory():
        """
        API endpoint to browse directories on the local filesystem.
        Returns a list of subdirectories and files in the specified path.
        """
        data = request.get_json()
        current_path = data.get('path', config.base_dir)

        # Validate and normalize the path
        try:
            # Convert to absolute path if relative
            if not os.path.isabs(current_path):
                current_path = os.path.abspath(os.path.join(config.base_dir, current_path))

            # Check if path exists and is a directory
            if not os.path.isdir(current_path):
                return jsonify({'error': 'Not a valid directory'}), 400

            # Get parent directory
            parent_dir = os.path.dirname(current_path)

            # List directories and files
            items = []
            for item in os.listdir(current_path):
                item_path = os.path.join(current_path, item)
                is_dir = os.path.isdir(item_path)
                items.append({
                    'name': item,
                    'path': item_path,
                    'is_directory': is_dir,
                    'size': os.path.getsize(item_path) if not is_dir else 0
                })

            # Sort: directories first, then files
            items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))

            return jsonify({
                'current_path': current_path,
                'parent_path': parent_dir,
                'items': items
            })

        except Exception as e:
            logger.error(f"Error browsing directory: {str(e)}")
            return jsonify({'error': str(e)}), 500


    @settings_bp.route('/reset_session')
    def reset_session():
        """
        Resets the application settings to defaults and creates a new session.
        """
        try:
            # Reset paths to defaults
            config.paths = config.default_paths.copy()

            # Save the default configuration
            config.save()

            # Clear current session reference
            if 'current_session' in flask_session:
                flask_session.pop('current_session')

            # Create a new session
            flash("Settings reset to defaults. Starting new session.")
            return redirect(url_for('session.new_session'))
        except Exception as e:
            logger.error(f"Error resetting session: {str(e)}")
            flash(f"Error resetting session: {str(e)}")
            return redirect(url_for('session.upload_file'))


    # Return the blueprint - not strictly necessary but helps with clarity
    return settings_bp