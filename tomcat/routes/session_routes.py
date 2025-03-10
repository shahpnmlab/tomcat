"""
Session Routes for TomCat Application

This module handles all routes related to session management,
including session creation, viewing, editing, and downloading.
"""
import json
import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, session as flask_session
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Create a Blueprint for session routes
session_bp = Blueprint('session', __name__)


def initialize_routes(config, session_manager, file_locator, media_manager, allowed_file_func):
    """
    Initialize session routes with required dependencies.

    Args:
        config: Application configuration object
        session_manager: Session manager instance
        file_locator: File locator instance
        media_manager: Media manager instance
        allowed_file_func: Function to check if a file is allowed
    """

    @session_bp.route('/', methods=['GET', 'POST'])
    def upload_file():
        """
        Main route that displays the Existing Sessions page at instantiation.
        Handles session upload and creation.
        """
        # If accessed via GET, display existing sessions page
        if request.method == 'GET':
            # Check if config exists
            config_exists = bool(config.config_file and config.paths)

            # Get list of sessions
            sessions = session_manager.get_sessions()
            sessions_exist = len(sessions) > 0

            # If no paths are set, redirect to settings
            if not any(config.paths.values()):
                flash("Please configure data paths before continuing")
                return redirect(url_for('settings.settings'))

            # Display the upload page with sessions
            return render_template('upload.html',
                                paths=config.paths,
                                sessions=sessions,
                                config_exists=config_exists,
                                sessions_exist=sessions_exist)

        # Handle direct upload if POST
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)

            if file and allowed_file_func(file.filename):
                filename = secure_filename(file.filename)
                filepath = config.upload_folder + '/' + filename
                file.save(filepath)
                return redirect(url_for('session.process_csv', filename=filename))

        # Handle session deletion if requested
        if 'delete_session' in request.form:
            filename = request.form.get('delete_session')
            if filename:
                try:
                    filepath = os.path.join(config.upload_folder, filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        flash(f"Session file '{filename}' deleted successfully")
                    else:
                        flash(f"Session file '{filename}' not found")
                except Exception as e:
                    logger.error(f"Error deleting session file: {str(e)}")
                    flash(f"Error deleting session file: {str(e)}")
            return redirect(url_for('session.upload_file'))

        # For any other POST requests, redirect to GET to show the upload page
        return redirect(url_for('session.upload_file'))


    @session_bp.route('/new_session', methods=['GET', 'POST'])
    def new_session():
        """
        Creates a new empty session with a custom filename or a default timestamp-based one.
        """
        try:
            # Check if this is a POST request with a custom filename
            custom_filename = None
            if request.method == 'POST':
                custom_filename = request.form.get('session_name', '').strip()

            # Create a new session
            session = session_manager.create_session(custom_filename)

            if session:
                flash(f"Created new TomCat session: {session.filename}")
                return redirect(url_for('session.process_csv', filename=session.filename))
            else:
                flash("Error creating new session")
                return redirect(url_for('session.upload_file'))

        except Exception as e:
            logger.error(f"Exception in new_session: {str(e)}")
            flash(f"Error creating new session: {str(e)}")
            return redirect(url_for('session.upload_file'))

    @session_bp.route('/process/<filename>', methods=['GET', 'POST'])
    def process_csv(filename):
        """
        Process and display the session data, handle form submissions,
        and manage the addition of new tomogram entries.
        """
        # Load the session
        session = session_manager.load_session(filename)
        if not session:
            flash(f"Session not found: {filename}")
            return redirect(url_for('session.upload_file'))

        df = session.get_data()
        search_results = None
        added_count = 0
        skipped_count = 0

        # Handle POST request - form submission
        if request.method == 'POST':
            # Check if the user is searching for tomograms
            if 'search_tomograms' in request.form:
                search_basename = request.form.get('search_basename', '').strip()
                if search_basename:
                    # Search for tomograms with the basename
                    search_results = file_locator.search_tomograms(search_basename)

                    # Mark tomograms that already exist in the session
                    existing_tomo_names = session.get_tomogram_names()
                    for result in search_results:
                        result['exists'] = result['name'] in existing_tomo_names

                    # Automatically add all non-existing tomograms
                    added_count, skipped_count = session.add_tomograms_from_search(search_results)

                    if added_count > 0:
                        flash(f"Automatically added {added_count} new tomograms matching '{search_basename}'")
                        # Reload data after adding tomograms
                        df = session.get_data()

                    if not search_results:
                        flash(f"No tomograms found with basename '{search_basename}'")

                    # Set search_results to simply the count for the template
                    search_results = {'count': len(search_results)}

            # Check if the user is manually adding a new entry
            elif 'add_new_entry' in request.form:
                # Get the new entry details
                new_tomo_name = request.form.get('new_tomo_name', '').strip()

                if new_tomo_name:
                    # Add the new tomogram
                    if session.add_tomogram(new_tomo_name):
                        flash(f"Added new tomogram: {new_tomo_name}")
                        # Reload data after adding tomogram
                        df = session.get_data()
                    else:
                        flash(f"Tomogram '{new_tomo_name}' already exists")
            else:
                # Update existing entries
                for index, row in df.iterrows():
                    # Get values from form
                    thickness = request.form.get(f"thickness_{index}")
                    notes = request.form.get(f"notes_{index}")
                    delete = request.form.get(f"delete_{index}") == "on"
                    score = request.form.get(f"score_{index}")
                    double_confirmed = request.form.get(f"double_confirmed_{index}") == "on"

                    # Update row in dataframe
                    session.update_tomogram_data(
                        row['tomo_name'],
                        thickness=thickness,
                        notes=notes,
                        delete=delete,
                        score=score,
                        double_confirmed=double_confirmed
                    )

                flash('Data updated successfully')
                # Reload data after updates
                df = session.get_data()

        # Get tomo_names for media processing
        tomo_names = session.get_tomogram_names()

        # Limit the number of tomograms to process in one request to prevent overload
        batch_size = 10  # Adjust based on your server's capabilities
        tomo_batch = tomo_names[:batch_size] if len(tomo_names) > batch_size else tomo_names

        # Trigger media generation for tomogram batch
        for tomo_name in tomo_batch:
            if tomo_name:  # Skip empty names
                try:
                    media_manager.generate_media_for_tomogram(tomo_name)
                except Exception as e:
                    logger.error(f"Error triggering media generation for {tomo_name}: {str(e)}")

        # Get any thumbnails that are already available
        thumbnails = {}
        for tomo_name in tomo_names:
            if tomo_name:  # Skip empty names
                thumbnail_path = media_manager.get_thumbnail_path(tomo_name)
                if thumbnail_path:
                    thumbnails[tomo_name] = thumbnail_path.split('/')[-1]

        return render_template('form.html',
                               df=df,
                               thumbnails=thumbnails,
                               filename=filename,
                               paths=config.paths,
                               tomo_names_json=json.dumps(tomo_names),
                               search_results=search_results,
                               added_count=added_count,
                               skipped_count=skipped_count)


    @session_bp.route('/detail/<filename>/<tomo_name>', methods=['GET', 'POST'])
    def detail_view(filename, tomo_name):
        """
        Detailed view for a specific tomogram showing low mag, tilt series, and tomogram visualizations.
        """
        # Store current filename in Flask session for settings redirect
        flask_session['current_session'] = filename

        # Load the session
        session = session_manager.load_session(filename)
        if not session:
            flash(f"Session not found: {filename}")
            return redirect(url_for('session.upload_file'))

        # Get the tomogram data
        tomo_data = session.get_tomogram_data(tomo_name)
        if not tomo_data:
            flash(f"Tomogram not found in session: {tomo_name}")
            return redirect(url_for('session.process_csv', filename=filename))

        # Handle form submission (POST request)
        if request.method == 'POST':
            # Get updated values
            notes = request.form.get('notes', '')
            delete = 'delete' in request.form
            double_confirmed = 'double_confirmed' in request.form

            # Update the tomogram data
            session.update_tomogram_data(
                tomo_name,
                notes=notes,
                delete=delete,
                double_confirmed=double_confirmed
            )

            flash("Tomogram data updated successfully")

            # Update tomo_data with new values
            tomo_data['notes'] = notes
            tomo_data['delete'] = delete
            tomo_data['double_confirmed'] = double_confirmed

        # Trigger media generation for this tomogram
        media_manager.generate_media_for_tomogram(tomo_name)

        return render_template('detail.html',
                            tomo_name=tomo_name,
                            tomo_data=tomo_data,
                            filename=filename,
                            lowmag_path=config.paths['lowmag_path'],
                            tiltseries_path=config.paths['tiltseries_path'],
                            tomogram_path=config.paths['tomogram_path'])


    @session_bp.route('/download/<filename>')
    def download_csv(filename):
        """Download session file."""
        return send_from_directory(config.upload_folder, filename, as_attachment=True)


    # Return the blueprint - not strictly necessary but helps with clarity
    return session_bp