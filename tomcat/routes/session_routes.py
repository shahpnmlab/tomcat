"""
Session Routes for TomCat Application

This module handles all routes related to session management,
including session creation, viewing, editing, and downloading.
"""
import json
import os
import logging
import tarfile
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, \
    session as flask_session, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid

logger = logging.getLogger(__name__)

# Create a Blueprint for session routes
session_bp = Blueprint('session', __name__)


def initialize_routes(config, session_manager_instance, file_locator_instance, media_manager_instance, allowed_file_func, thread_manager_instance):
    """
    Initialize session routes with required dependencies.

    Args:
        config: Application configuration object
        session_manager_instance: Session manager instance
        file_locator_instance: File locator instance
        media_manager_instance: Media manager instance
        allowed_file_func: Function to check if a file is allowed
        thread_manager_instance: Thread manager instance
    """
    # Make dependencies available to route handlers in this blueprint
    # For session_manager, file_locator, media_manager, use the passed instances directly in route functions
    # or assign to module-level variables if they are truly global for the blueprint context.
    # For simplicity here, we'll use the instance names directly in the functions where needed.
    # If run_search_and_add needs them, it will get them from its closure or app context.

    # Store thread_manager for use in start_search
    # Note: Python's closures will allow inner functions to access these.
    # To be explicit for run_search_and_add, ensure it can access session_manager and file_locator.
    # These are already available in its closure from the outer initialize_routes scope.

    # Rename to avoid conflict with module names if any, and to be clear these are instances
    session_manager = session_manager_instance
    file_locator = file_locator_instance
    media_manager = media_manager_instance
    thread_manager = thread_manager_instance


    def run_search_and_add(job_id, app_context, filename, basename):
        """The actual search task that runs in a background thread."""
        with app_context: # app_context provides access to current_app, config, etc.
            try:
                # Access session_manager and file_locator from the closure of initialize_routes
                current_app.search_jobs[job_id]['status'] = 'running'

                session = session_manager.load_session(filename) # Uses session_manager from outer scope
                search_results = file_locator.search_tomograms(basename) # Uses file_locator from outer scope
                if search_results:
                    session.add_tomograms_from_search(search_results)

                current_app.search_jobs[job_id]['status'] = 'complete'
                current_app.search_jobs[job_id]['result_count'] = len(search_results) if search_results else 0
            except Exception as e:
                logger.error(f"Search job {job_id} failed: {e}")
                current_app.search_jobs[job_id]['status'] = 'failed'
                current_app.search_jobs[job_id]['error'] = str(e)

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

    @session_bp.route('/start_search/<filename>', methods=['POST'])
    def start_search(filename):
        """Starts a background search for tomograms."""
        basename = request.form.get('search_basename', '').strip()
        if not basename:
            return jsonify({'error': 'Search basename cannot be empty'}), 400

        job_id = str(uuid.uuid4())
        current_app.search_jobs[job_id] = {'status': 'queued'}

        # Submit the task to the thread manager (now available from initialize_routes closure)
        thread_manager.submit_task(
            f"search_{job_id}",
            run_search_and_add,
            job_id,
            current_app.app_context(), # Pass app context to background thread
            filename,
            basename
        )

        return jsonify({'job_id': job_id})

    @session_bp.route('/search_status/<job_id>')
    def search_status(job_id):
        """Checks the status of a background search job."""
        job = current_app.search_jobs.get(job_id)
        if not job:
            return jsonify({'status': 'not_found'}), 404
        return jsonify(job)

    @session_bp.route('/autosave/<filename>', methods=['POST'])
    def autosave(filename):
        """
        Autosave session data without refreshing the page.
        """
        # Load the session
        session = session_manager.load_session(filename)
        if not session:
            return jsonify({"status": "error", "message": "Session not found"}), 404

        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            updates = data.get('updates', [])
            updated_count = 0

            # Defer saving until all updates are processed
            with session.deferred_save():
                for update in updates:
                    tomo_name = update.get('tomo_name')
                    if not tomo_name:
                        continue

                    # Update row in dataframe without saving immediately
                    success = session.update_tomogram_data(
                        tomo_name,
                        thickness=update.get('thickness'),
                        notes=update.get('notes'),
                        delete=update.get('delete', False),
                        score=update.get('score'),
                        double_confirmed=update.get('double_confirmed', False)
                    )

                    if success:
                        updated_count += 1

            return jsonify({
                "status": "success",
                "message": f"Autosave successful, updated {updated_count} entries",
                "updatedCount": updated_count
            })
        except Exception as e:
            logger.error(f"Error in autosave: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

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
        search_notes = ""

        # Handle form submission for adding entries (before pagination)
        if request.method == 'POST':
            # Synchronous search logic is removed. It's now handled by start_search and background task.
            # The 'search_tomograms' form submission will be caught by frontend JS.
            # If it ever reaches here (e.g. JS disabled), it will fall through or could be handled as an error.
            # For now, we assume JS will prevent default and call start_search.

            # Check if the user is manually adding a new entry
            if 'add_new_entry' in request.form: # This part remains
                new_tomo_name = request.form.get('new_tomo_name', '').strip()
                if new_tomo_name:
                    if session.add_tomogram(new_tomo_name):
                        flash(f"Added new tomogram: {new_tomo_name}")
                        return redirect(url_for('session.process_csv', filename=filename)) # Redirect to refresh
                    else:
                        flash(f"Tomogram '{new_tomo_name}' already exists")

        # Handle notes search
        if 'search_notes' in request.form:
            search_notes = request.form.get('notes_query', '').strip().lower()
            if search_notes:
                df['notes_str'] = df['notes'].fillna('').astype(str)
                df = df[df['notes_str'].str.lower().str.contains(search_notes)].drop(columns=['notes_str'])
                if len(df) == 0:
                    flash(f"No tomograms found with notes containing '{search_notes}'")

        # --- PAGINATION LOGIC ---
        page = request.args.get('page', 1, type=int)
        per_page = 50  # Items per page
        total_rows = len(df)
        total_pages = (total_rows + per_page - 1) // per_page

        start_index = (page - 1) * per_page
        end_index = start_index + per_page

        paginated_df = df.iloc[start_index:end_index]
        # --- END PAGINATION LOGIC ---

        tomo_names = paginated_df['tomo_name'].tolist()
        media_manager.batch_process_tomograms(tomo_names)

        thumbnails = {}
        for tomo_name in tomo_names:
            if tomo_name and media_manager.get_thumbnail_path(tomo_name): # Ensure path exists
                thumbnails[tomo_name] = True # Value is now just a boolean

        return render_template('form.html',
                               df=paginated_df,
                               filename=filename,
                               paths=config.paths,
                               thumbnails=thumbnails,
                               tomo_names_json=json.dumps(tomo_names),
                               search_results=search_results,
                               added_count=added_count,
                               skipped_count=skipped_count,
                               search_notes=search_notes,
                               pagination={
                                   'page': page,
                                   'per_page': per_page,
                                   'total_pages': total_pages,
                                   'total_rows': total_rows
                               })


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

    @session_bp.route('/export_session/<filename>', methods=['GET'])
    def export_session(filename):
        """
        Export session as a tarball including the CSV and all generated media files.
        Creates a compressed archive with the session CSV and all related media.

        Args:
            filename (str): Name of the session file
        """
        # Load the session to get tomogram names
        session = session_manager.load_session(filename)
        if not session:
            flash(f"Session not found: {filename}")
            return redirect(url_for('session.upload_file'))

        # Get tomogram names
        tomo_names = session.get_tomogram_names()

        # Create a temporary file for the tarball
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tarball_filename = f"{os.path.splitext(filename)[0]}_{timestamp}.tar.gz"
        tarball_path = os.path.join(tempfile.gettempdir(), tarball_filename)

        try:
            # Create tarball
            with tarfile.open(tarball_path, "w:gz") as tar:
                # Add session file
                session_path = os.path.join(config.upload_folder, filename)
                if os.path.exists(session_path):
                    tar.add(session_path, arcname=filename)

                for tomo_name in tomo_names:
                    if not tomo_name: continue

                    media_dir = os.path.join(config.media_cache_dir, tomo_name)

                    # Add all files from the media directory for this tomogram
                    if os.path.isdir(media_dir):
                        for file in os.listdir(media_dir):
                            file_path = os.path.join(media_dir, file)
                            arcname = os.path.join("media", tomo_name, file) # Store in media/tomo_name/ structure
                            tar.add(file_path, arcname=arcname)

                if config.config_file and os.path.exists(config.config_file):
                    tar.add(config.config_file, arcname="config.json")

            # Move tarball to upload folder for downloading
            download_path = os.path.join(config.upload_folder, tarball_filename)
            os.rename(tarball_path, download_path)

            flash(f"Session exported successfully as {tarball_filename}")

            # Serve the tarball for download
            return send_from_directory(config.upload_folder, tarball_filename, as_attachment=True)

        except Exception as e:
            logger.error(f"Error exporting session: {str(e)}")
            flash(f"Error exporting session: {str(e)}")
            return redirect(url_for('session.process_csv', filename=filename))

    @session_bp.route('/import_archive', methods=['POST'])
    def import_archive():
        """
        Import a previously exported tarball archive.
        Extracts session file and media contents to the appropriate directories.
        """
        if 'archive_file' not in request.files:
            flash('No archive file selected')
            return redirect(url_for('session.upload_file'))

        archive_file = request.files['archive_file']
        if archive_file.filename == '':
            flash('No selected file')
            return redirect(url_for('session.upload_file'))

        if not archive_file.filename.endswith(('.tar.gz', '.tgz')):
            flash('Only .tar.gz or .tgz files are supported')
            return redirect(url_for('session.upload_file'))

        # Create a temporary directory to extract files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save the uploaded file to the temp directory
            archive_path = os.path.join(temp_dir, secure_filename(archive_file.filename))
            archive_file.save(archive_path)

            try:
                session_filename = None
                extracted_once = False

                # Extract the archive
                with tarfile.open(archive_path, "r:gz") as tar:
                    # Ensure temp_dir exists for extraction
                    os.makedirs(temp_dir, exist_ok=True)

                    # Find and extract session file first
                    for member in tar.getmembers():
                        if member.name.endswith('.csv') and not member.isdir():
                            session_filename = os.path.basename(member.name)
                            tar.extract(member, path=temp_dir) # Extract only the CSV for now
                            # Copy session file to upload folder immediately
                            src_session_path = os.path.join(temp_dir, member.name) # Use member.name for correct path in archive
                            dst_session_path = os.path.join(config.upload_folder, session_filename)
                            import shutil
                            shutil.copy2(src_session_path, dst_session_path)
                            break

                    if not session_filename:
                        flash('No valid session file (.csv) found in the archive.')
                        return redirect(url_for('session.upload_file'))

                    # Extract all other files (media, config)
                    for member in tar.getmembers():
                        if member.name.endswith('.csv') and not member.isdir():
                            continue # Skip already processed CSV

                        # Handle media files, expecting them in "media/tomo_name/file"
                        if member.name.startswith("media/") and not member.isdir():
                            # Path parts: "media", "tomo_name", "filename.ext"
                            parts = member.name.split(os.path.sep)
                            if len(parts) == 3:
                                tomo_name = parts[1]
                                media_filename = parts[2]
                                # Destination: .tomcat/media_cache/tomo_name/filename.ext
                                target_dir = os.path.join(config.media_cache_dir, tomo_name)
                                os.makedirs(target_dir, exist_ok=True)
                                # Extract to the correct nested media cache directory
                                # We need to extract it to temp_dir first with its full path, then move.
                                # Or, more simply, extract member to target_dir but ensure member.name is just the filename part.
                                # For tar.extract, the path is where to extract, and it preserves subdirectories from member.name.
                                # So, we want to extract 'media/tomo_name/file' into 'temp_dir'
                                # then move 'temp_dir/media/tomo_name/file' to 'media_cache_dir/tomo_name/file'

                                # Simpler: extract all to temp_dir, then move individuals.
                                # This requires extracting all members first, which we can do.
                                if not extracted_once: # Extract all members if not done yet
                                    tar.extractall(path=temp_dir)
                                    extracted_once = True

                                src_media_path = os.path.join(temp_dir, member.name)
                                if os.path.exists(src_media_path): # Check if file was extracted
                                    dst_media_path = os.path.join(target_dir, media_filename)
                                    shutil.move(src_media_path, dst_media_path)


                        # Handle config.json
                        elif member.name == "config.json" and not member.isdir():
                            if not extracted_once:
                                tar.extractall(path=temp_dir)
                                extracted_once = True
                            src_config_path = os.path.join(temp_dir, member.name)
                            if os.path.exists(src_config_path):
                                dst_config_path = config.config_file
                                shutil.copy2(src_config_path, dst_config_path)
                                config.load() # Reload config after importing

                if not extracted_once and os.path.exists(archive_path) and tarfile.is_tarfile(archive_path):
                    # if we only found CSV and didn't trigger full extraction for media/config
                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(path=temp_dir)
                    # try to process media/config again if they were missed
                    # This logic is a bit convoluted due to staged extraction attempt.
                    # A cleaner way would be to extract all, then iterate through temp_dir contents.
                    # For now, this attempts to catch cases. A full rework of import might be better.


                flash(f"Successfully imported session from archive: {session_filename}")
                return redirect(url_for('session.process_csv', filename=session_filename))

            except Exception as e:
                logger.error(f"Error importing archive: {str(e)}")
                flash(f"Error importing archive: {str(e)}")
                return redirect(url_for('session.upload_file'))

    # Return the blueprint - not strictly necessary but helps with clarity
    return session_bp