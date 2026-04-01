# Architecture

**Analysis Date:** 2026-04-01

## Pattern Overview

**Overall:** Service-oriented Flask monolith with CLI entry point

**Key Characteristics:**
- Single-process Flask application with Typer CLI wrapping it
- Services and managers are instantiated once in `create_app()` and injected into blueprints via closure
- Background work is delegated to a thread pool (`ThreadPoolExecutor`) — the web thread never blocks on media generation
- All persistent state is either on-disk (CSV files, generated media files) or in-memory dicts on the Flask `app` object (e.g., `app.search_jobs`)

## Layers

**CLI / Entry Point:**
- Purpose: Parse CLI commands (`run`, `init`, `info`) and boot the Flask app
- Location: `tomcat/app.py`
- Contains: Typer CLI definitions, `create_app()` factory
- Depends on: Config, all services/managers, all blueprints
- Used by: `pyproject.toml` entrypoint `tomcat = "tomcat.app:cli"`

**Configuration:**
- Purpose: Load/save user settings (data directory paths) and provide runtime paths to all other components
- Location: `tomcat/config.py`
- Contains: `Config` class — reads/writes `.tomcat/config.json`, exposes all folder paths
- Depends on: Nothing (pure stdlib)
- Used by: Every other layer

**Models:**
- Purpose: Represent and persist session data (the catalogue of tomograms being annotated)
- Location: `tomcat/models/session.py`
- Contains: `Session` (wraps a CSV via pandas), `SessionManager` (lists/creates/loads sessions)
- Depends on: `Config`, `pandas`, `werkzeug.utils.secure_filename`
- Used by: `session_routes`, `app.py` CLI `info` command

**Services:**
- Purpose: Orchestrate media generation — the highest-level coordination layer above utils
- Location: `tomcat/services/media_service.py`
- Contains: `MediaManager` — manages an `OrderedDict` processing queue, delegates to `ThreadManager`, calls `FileLocator` to find source files
- Depends on: `Config`, `ThreadManager`, `FileLocator`, `tomcat.utils` generation functions
- Used by: `session_routes`, `media_routes`

**Routes (Flask Blueprints):**
- Purpose: Handle HTTP requests; thin layer that delegates to services/models
- Location: `tomcat/routes/session_routes.py`, `tomcat/routes/media_routes.py`, `tomcat/routes/settings_routes.py`
- Contains: Blueprint definitions; all route handlers are closures capturing injected dependencies
- Depends on: `Config`, `SessionManager`, `FileLocator`, `MediaManager`, `ThreadManager`
- Used by: `create_app()` registers them with URL prefixes

**Utilities:**
- Purpose: Low-level, reusable functions — file finding, thread pool management, MRC file processing
- Location: `tomcat/utils/`
- Contains: `FileLocator` (`file_utils.py`), `ThreadManager` (`thread_utils.py`), MRC→JPEG/GIF generation (`media_utils.py`), template URL mapping (`template_utils.py`)
- Depends on: `mrcfile`, `Pillow`, `imageio`, `numpy`
- Used by: `MediaManager`, blueprints (FileLocator also used directly in `session_routes`)

**Templates / Frontend:**
- Purpose: Render HTML and handle client-side polling for async media updates
- Location: `tomcat/templates/`, `tomcat/static/js/media_updater.js`
- Contains: `upload.html` (session list), `form.html` (catalogue table view), `detail.html` (single tomogram view), `settings.html`
- Depends on: Bootstrap 5.2, Bootstrap Icons, `omggif` (interactive GIF player)

## Data Flow

**Session Creation and Search:**
1. User visits `/session/` → `session.upload_file` → renders `upload.html` with existing sessions
2. User creates/names a session → `session.new_session` → `SessionManager.create_session()` → writes `.tomcat` CSV file
3. User submits search basename → JS calls `POST /session/start_search/<filename>` → `ThreadManager.submit_task()` kicks off `run_search_and_add` in background
4. JS polls `GET /session/search_status/<job_id>` → on completion, page refreshes

**Catalogue View and Media Generation:**
1. `GET /session/process/<filename>` → loads `Session`, paginates rows, calls `media_manager.batch_process_tomograms(tomo_names)` for the current page
2. `MediaManager` checks `_all_media_exists()` per tomogram; missing media is queued via `ThreadManager.submit_task()`
3. Background threads call `FileLocator` to find source MRC files, then call `generate_jpeg_thumbnail` / `generate_tiltseries_animation` / `generate_tomogram_animation` from `tomcat.utils`
4. Generated files land in `.tomcat/thumbnails/`, `.tomcat/media/lowmag/`, `.tomcat/media/tiltseries/`, `.tomcat/media/tomogram/`
5. `media_updater.js` polls `/thumbnail_status/<name>` and `/media_status/<type>/<name>` at 2-second intervals and swaps placeholder elements with actual images/GIFs when ready

**Detail View:**
1. `GET /session/detail/<filename>/<tomo_name>` → loads session row, triggers `MediaManager.generate_media_for_tomogram(tomo_name)` with priority=True
2. Page renders `detail.html`; JS polls for all three media types and renders an interactive GIF player (canvas + slider) once the GIF is available

**Autosave:**
1. JS in `form.html` collects changed rows and calls `POST /session/autosave/<filename>` with a JSON payload
2. Route loads session, uses `session.deferred_save()` context manager to batch-apply all updates then write CSV once

**Settings:**
1. `GET /settings/settings` → render `settings.html` with current path values
2. `POST` → `Config.update_paths()` → writes `.tomcat/config.json` → redirect back to active session or session list

**State Management:**
- Persistent state: CSV files in `.tomcat/uploads/`, config in `.tomcat/config.json`, media in `.tomcat/media/` and `.tomcat/thumbnails/`
- In-memory state: `MediaManager.media_status` dict, `MediaManager.processing_queue` (`OrderedDict`), `app.search_jobs` dict on the Flask app instance

## Key Abstractions

**Config:**
- Purpose: Single source of truth for all file-system paths used throughout the app
- Examples: `tomcat/config.py`
- Pattern: Instantiated once, passed by reference into every component that needs path resolution

**Session / SessionManager:**
- Purpose: Encapsulates a pandas DataFrame backed by a CSV; provides typed accessors and `deferred_save()` context manager
- Examples: `tomcat/models/session.py`
- Pattern: `SessionManager.load_session(filename)` returns a fresh `Session` instance on each request — no long-lived session objects

**MediaManager:**
- Purpose: Priority queue + cache-check layer for background media generation; decouples route handlers from thread scheduling
- Examples: `tomcat/services/media_service.py`
- Pattern: `queue_tomogram_for_processing(tomo_name, priority=bool)` is the single entry point; internal `_check_and_generate_*` methods decide whether work is needed

**FileLocator:**
- Purpose: Filesystem scanner that resolves canonical tomogram names to actual MRC/image file paths using priority-ordered extension lists
- Examples: `tomcat/utils/file_utils.py`
- Pattern: `find_tomogram_file(name)`, `find_tiltseries_file(name)`, `find_lowmag_file(name)` — each checks extension priority order; falls back to recursive walk with basename extraction

**ThreadManager:**
- Purpose: Thin wrapper around `ThreadPoolExecutor` with deduplication by `task_key`; prevents duplicate background jobs
- Examples: `tomcat/utils/thread_utils.py`
- Pattern: `submit_task(task_key, func, *args)` — silently no-ops if a task with that key is already running

**Blueprint initialization pattern:**
- Purpose: Inject dependencies (config, managers) into route handlers without using Flask globals or app context
- Examples: All `initialize_routes(...)` functions in `tomcat/routes/`
- Pattern: Outer function captures dependencies in closure; inner route handler functions reference them via closure scope

## Entry Points

**CLI (`tomcat run`):**
- Location: `tomcat/app.py` → `cli()` → `run()` command
- Triggers: `python -m tomcat` or `tomcat run` via entrypoint
- Responsibilities: Calls `create_app()`, starts Flask dev server

**`create_app()`:**
- Location: `tomcat/app.py`
- Triggers: Called by `run` CLI command (and can be called directly for testing)
- Responsibilities: Instantiates `Config`, `ThreadManager`, `FileLocator`, `SessionManager`, `MediaManager`; registers all three blueprints with URL prefixes; registers compat routes; registers template utils

**Root URL `/`:**
- Location: Lambda added via `app.add_url_rule('/', 'index', ...)` in `create_app()`
- Triggers: Browser navigation to root
- Responsibilities: Redirects to `/session/`

**Compatibility Routes:**
- Location: `tomcat/app.py` (registered directly on `app`, not a blueprint)
- Purpose: Preserve old URL paths (e.g., `/media_status/`, `/thumbnails/`, `/serve_media/`) by delegating to current blueprint view functions
- Triggers: Requests from `media_updater.js` which still uses old URL patterns (`/thumbnail_status/`, `/media_status/`, `/serve_media/`, `/thumbnails/`)

## Error Handling

**Strategy:** Log-and-return — functions return `bool` or `None` on failure; routes flash messages to the user and redirect

**Patterns:**
- Services/models return `False` or `None` on failure after logging the exception with `logger.error()`
- Route handlers check return values, use `flash()` to surface errors in the UI, and redirect to a safe page
- Background thread exceptions are caught in `ThreadManager.cleanup_completed_tasks()` via `future.result()` and logged
- Media generation functions clean up empty/partial output files on failure to prevent stale cached errors

## Cross-Cutting Concerns

**Logging:** `logging.basicConfig` configured in `tomcat/app.py` at `INFO` level with timestamp; all modules use `logger = logging.getLogger(__name__)`

**Validation:** Minimal — file extension checked via `allowed_file()` (only `.tomcat` allowed for upload); path inputs sanitized with `werkzeug.utils.secure_filename`

**Authentication:** None — single-user local tool, no auth layer

**Template URL resolution:** `tomcat/utils/template_utils.py` overrides Jinja's `url_for` global with a mapping table to support legacy endpoint names during blueprint migration

---

*Architecture analysis: 2026-04-01*