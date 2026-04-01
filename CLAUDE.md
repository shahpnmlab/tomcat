# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TomCat** is a Flask + Typer web application for cataloging and annotating electron microscopy tomography data. Users configure paths to their data directories, create sessions (stored as CSV files), search for tomograms, and annotate them with metadata. Thumbnails and animations (GIF) are generated in background threads.

## Commands

### Installation
```bash
conda create -n tomcat python=3.10
conda activate tomcat
pip install -e .
```

### Running
```bash
tomcat run                          # Start web server at http://127.0.0.1:16006
tomcat run --host 0.0.0.0 --port 8080 --debug
tomcat init                         # Initialize config
tomcat info                         # Show config and sessions
```

### Data Flow
```
CLI (Typer) → create_app() → Flask Blueprints → SessionManager / MediaManager
                                                        ↓
Config (.tomcat/config.json) → FileLocator (finds MRC/tilt/lowmag files)
                                                        ↓
                                               ThreadManager (background pool)
                                                        ↓
                                          Media files (.tomcat/media/, thumbnails/)
```

### Core Components

**`tomcat/app.py`** — Flask app factory (`create_app()`) and Typer CLI definition. Wires together all services and registers blueprints.

**`tomcat/config.py`** — Loads/saves `.tomcat/config.json`. Stores user-configured paths to tomography data directories (lowmag, tilt series, tomogram dirs).

**`tomcat/models/session.py`** — `Session` wraps a CSV file storing per-tomogram metadata (name, thickness, score, notes, deletion flag). `SessionManager` handles creating/loading sessions from `.tomcat/uploads/`.

**`tomcat/utils/file_utils.py`** — `FileLocator` searches configured directories for tomography files. Handles multiple file format variants (`.mrc`, `_rec.mrc`, `_preali.mrc`, `.st`, etc.) and extracts canonical basenames.

**`tomcat/services/media_service.py`** — `MediaManager` orchestrates thumbnail and animation generation. Checks the cache first, then queues work via `ThreadManager`.

**`tomcat/utils/thread_utils.py`** — `ThreadManager` wraps `concurrent.futures.ThreadPoolExecutor` (default 4 workers) for background media generation.

**`tomcat/utils/media_utils.py`** — Low-level functions: generate JPEG thumbnails and GIF animations from MRC files using `mrcfile`, `Pillow`, and `imageio`.

### Routes (Flask Blueprints)

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `session_routes` | `/session` | Upload/create sessions, view/edit tomogram details |
| `settings_routes` | `/settings` | Configure data directory paths |
| `media_routes` | `/media` | Serve generated media files, poll generation status |

The main landing page is `/session/`. JavaScript in `static/js/media_updater.js` polls `/media/media_status/<type>/<name>` to display images as they finish generating in the background.

### Runtime Directories (`.tomcat/`)

Created automatically on first run:
- `.tomcat/config.json` — user settings
- `.tomcat/uploads/` — session CSV files
- `.tomcat/media/` — generated GIFs and images
- `.tomcat/thumbnails/` — cached thumbnails

### File Format Priorities

`FileLocator` searches in priority order:
- **Tomogram**: `_rec.mrc` > `_rec` > `.mrc`
- **Tilt series**: `_preali.mrc` > `_ali.mrc` > `.st.mrc` > `.st`
- **Lowmag**: `.mrc` > `.dm4` > `.tif/.tiff` > `.jpg/.jpeg/.png`

<!-- GSD:project-start source:PROJECT.md -->
## Project

**TomCat — Bug Fix Initiative**

TomCat is a local Flask + Typer web application for cataloging and annotating electron microscopy tomography data. Researchers configure paths to data directories, create sessions (stored as CSV files), search for tomograms, and annotate them with metadata. Thumbnails and GIF animations are generated in background threads.

This initiative addresses five identified bugs: incorrect media cache behavior, missing pagination in thumbnail view, duplicate entries from `_preali.mrc` files, race conditions in `MediaManager`, and a Zip Slip vulnerability in archive import.

**Core Value:** Tomograms load from cache reliably, the catalogue is free of duplicates, and the app is structurally sound — so researchers can annotate without friction or data integrity issues.

### Constraints

- **Tech stack**: Python 3.7+, Flask, Typer, pandas, mrcfile, Pillow, imageio — no new dependencies
- **Compatibility**: Existing sessions and media files must continue to work after fixes
- **Scope**: Changes limited to bug fixes; no refactoring of unrelated code
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10 (recommended via conda) - All backend logic, CLI, media processing
- HTML/Jinja2 - Server-rendered templates in `tomcat/templates/`
- JavaScript (vanilla ES6+) - Client-side polling in `tomcat/static/js/media_updater.js`
- CSS (inline in templates + Bootstrap) - UI styling
## Runtime
- Python >=3.7, tested on 3.10
- Recommended: conda environment (`conda create -n tomcat python=3.10`)
- pip (editable install: `pip install -e .`)
- Lockfile: Not present — only `pyproject.toml` with version ranges
## Frameworks
- Flask >=2.0.0 - Web application framework; app factory in `tomcat/app.py`
- Typer >=0.7.0 - CLI framework; defines `run`, `init`, `info` commands in `tomcat/app.py`
- Werkzeug >=2.0.0 - Flask dependency; also used directly via `werkzeug.utils.secure_filename` in `tomcat/models/session.py`
- Jinja2 (bundled with Flask) - Server-side HTML templates; templates at `tomcat/templates/`
- Bootstrap 5.2.3 - UI components; loaded from `cdn.jsdelivr.net`
- Bootstrap Icons 1.10.0 - Icon set; loaded from `cdn.jsdelivr.net`
- setuptools >=61.0 + wheel - Build backend per `pyproject.toml`
- black >=22.0.0 - Code formatter (dev dependency)
- isort >=5.0.0 - Import sorter (dev dependency)
- flake8 >=4.0.0 - Linter (dev dependency)
- pytest >=6.0.0 - Test runner (dev dependency)
## Key Dependencies
- `mrcfile` >=1.3.0 — Reads MRC/REC electron microscopy files; used in `tomcat/utils/media_utils.py` for all image/animation generation
- `numpy` >=1.20.0 — Array operations on MRC data; percentile-based normalization in `tomcat/utils/media_utils.py`
- `Pillow` >=8.0.0 — Image resizing and JPEG/GIF output; used in `tomcat/utils/media_utils.py`
- `imageio` >=2.9.0 — Primary GIF animation writer; used in `tomcat/utils/media_utils.py` with PIL as fallback
- `pandas` >=1.0.0 — Session data storage as DataFrames backed by CSV files; used in `tomcat/models/session.py`
- `concurrent.futures.ThreadPoolExecutor` (stdlib) — Background media generation pool (4 workers default); wrapped in `tomcat/utils/thread_utils.py`
## Configuration
- No environment variables required for operation
- All user configuration stored in `.tomcat/config.json` in the working directory
- Config keys: `lowmag_path`, `tiltseries_path`, `tomogram_path`
- Config class: `tomcat/config.py`
- `pyproject.toml` — Defines dependencies, entry points, tool settings (black, isort, flake8)
- Entry point: `tomcat = "tomcat.app:cli"` — installs `tomcat` CLI command
## Platform Requirements
- Python >=3.7 (3.10 recommended)
- conda or venv for isolation
- No database server, no message queue — all local filesystem
- Flask's built-in dev server via `app.run()` — not production-grade (no WSGI server like gunicorn)
- Default port: 16006 on 127.0.0.1
- All data stored under `.tomcat/` in the working directory
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case` for all Python module files: `file_utils.py`, `media_service.py`, `thread_utils.py`
- Route modules follow the pattern `<domain>_routes.py`: `session_routes.py`, `media_routes.py`, `settings_routes.py`
- Utility modules follow the pattern `<domain>_utils.py`: `file_utils.py`, `media_utils.py`, `thread_utils.py`
- `PascalCase`: `Config`, `Session`, `SessionManager`, `FileLocator`, `MediaManager`, `ThreadManager`, `MediaProcessingError`
- Manager classes are suffixed with `Manager`: `SessionManager`, `MediaManager`, `ThreadManager`
- Error classes are suffixed with `Error`: `MediaProcessingError`
- `snake_case` for all functions and methods: `create_app`, `find_tomogram_file`, `generate_jpeg_thumbnail`
- Private/internal methods prefixed with `_`: `_create_directories`, `_generate_thumbnail`, `_all_media_exists`, `_shutdown`
- Helper functions that back a public function are prefixed with `_`: `_generate_thumbnail_from_mrc`, `_generate_thumbnail_from_image`
- Blueprint factory functions named `initialize_routes`: used in every route module
- `snake_case` for all variables: `tomo_name`, `file_locator`, `thread_manager`
- Module-level loggers always named `logger`: `logger = logging.getLogger(__name__)`
- Constants use `UPPER_SNAKE_CASE`: `EXTENSIONS`, `TYPE_PRIORITY`, `URL_MAPPING`
- Blueprint name is the domain: `session`, `media`, `settings`
- Endpoint names within blueprints use `snake_case`: `upload_file`, `process_csv`, `detail_view`
## Code Style
- Black is configured with `line-length = 88` (see `pyproject.toml`)
- Target Python versions: 3.7, 3.8, 3.9, 3.10
- flake8 with `max-line-length = 88` and `extend-ignore = E203`
- isort with `profile = "black"` for import ordering
- Not used in the codebase; all functions use only docstring-based type documentation
## Import Organization
- None used; all internal imports use full package paths: `from tomcat.utils import generate_jpeg_thumbnail`
- Used sparingly in `media_service.py` to avoid circular imports:
## Module Structure Pattern
## Blueprint Pattern
## Error Handling
- Wrap all I/O operations in `try/except Exception as e` and log with `logger.error(f"...: {str(e)}")`
- Return `False` or `None` on failure, `True` or the result on success
- Custom exception class `MediaProcessingError` in `tomcat/utils/media_utils.py` is raised internally within the media utils layer and caught at the function boundary before returning `False`
- Route handlers use `flash()` for user-visible error messages and redirect
- API (JSON) routes return `jsonify({"status": "error", "message": ...})` with appropriate HTTP status codes
- Used in cleanup code where errors must not propagate: `finally` blocks that remove temp files use bare `except: pass`
## Logging
- Root logger configured in `tomcat/app.py`:
- Each module creates its own logger: `logger = logging.getLogger(__name__)`
- `logger.debug()` — internal tracing, file search steps, frame processing progress
- `logger.info()` — successful operations: "Generated thumbnail for X", "Loaded session from Y"
- `logger.warning()` — non-fatal issues: "Directory not found", "MRC file contains NaN values"
- `logger.error()` — operation failures with `str(e)` included
- All log messages use f-strings: `logger.info(f"Loaded session from {self.filepath}")`
## Comments
- Section dividers use `# ===` style banners in `app.py`
- Inline comments explain non-obvious logic (file priority ordering, queue recursion prevention)
- `# TODO`/`# FIXME`/`# NOTE` markers not observed in the codebase — inline comments explain intent directly
- Every public class and method has a Google-style docstring with `Args:` and `Returns:` sections
- Private/helper functions (`_generate_thumbnail_from_mrc`) have brief single-line docstrings
- Module-level docstrings present on every file
## Function Design
- Required parameters are positional; optional ones use keyword defaults
- `**kwargs` used in `update_tomogram_data` and `update_paths` for flexible field updates
- Long parameter lists in route factories: `initialize_routes(config, session_manager, file_locator, media_manager, allowed_file_func, thread_manager)`
- Service/model methods: `bool` for operations, `str/None` for lookup, `dict/None` for data retrieval
- Route handlers: Flask response objects (`render_template`, `redirect`, `jsonify`)
- Background worker functions: `bool`
## Context Managers
- `Session.deferred_save()` — context manager to batch CSV writes, defined in `tomcat/models/session.py`
- `safe_file_open()` — context manager for error-wrapped file I/O in `tomcat/utils/media_utils.py`
- `mrcfile.open()` — used with `with` throughout `tomcat/utils/media_utils.py`
## Module Exports
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Single-process Flask application with Typer CLI wrapping it
- Services and managers are instantiated once in `create_app()` and injected into blueprints via closure
- Background work is delegated to a thread pool (`ThreadPoolExecutor`) — the web thread never blocks on media generation
- All persistent state is either on-disk (CSV files, generated media files) or in-memory dicts on the Flask `app` object (e.g., `app.search_jobs`)
## Layers
- Purpose: Parse CLI commands (`run`, `init`, `info`) and boot the Flask app
- Location: `tomcat/app.py`
- Contains: Typer CLI definitions, `create_app()` factory
- Depends on: Config, all services/managers, all blueprints
- Used by: `pyproject.toml` entrypoint `tomcat = "tomcat.app:cli"`
- Purpose: Load/save user settings (data directory paths) and provide runtime paths to all other components
- Location: `tomcat/config.py`
- Contains: `Config` class — reads/writes `.tomcat/config.json`, exposes all folder paths
- Depends on: Nothing (pure stdlib)
- Used by: Every other layer
- Purpose: Represent and persist session data (the catalogue of tomograms being annotated)
- Location: `tomcat/models/session.py`
- Contains: `Session` (wraps a CSV via pandas), `SessionManager` (lists/creates/loads sessions)
- Depends on: `Config`, `pandas`, `werkzeug.utils.secure_filename`
- Used by: `session_routes`, `app.py` CLI `info` command
- Purpose: Orchestrate media generation — the highest-level coordination layer above utils
- Location: `tomcat/services/media_service.py`
- Contains: `MediaManager` — manages an `OrderedDict` processing queue, delegates to `ThreadManager`, calls `FileLocator` to find source files
- Depends on: `Config`, `ThreadManager`, `FileLocator`, `tomcat.utils` generation functions
- Used by: `session_routes`, `media_routes`
- Purpose: Handle HTTP requests; thin layer that delegates to services/models
- Location: `tomcat/routes/session_routes.py`, `tomcat/routes/media_routes.py`, `tomcat/routes/settings_routes.py`
- Contains: Blueprint definitions; all route handlers are closures capturing injected dependencies
- Depends on: `Config`, `SessionManager`, `FileLocator`, `MediaManager`, `ThreadManager`
- Used by: `create_app()` registers them with URL prefixes
- Purpose: Low-level, reusable functions — file finding, thread pool management, MRC file processing
- Location: `tomcat/utils/`
- Contains: `FileLocator` (`file_utils.py`), `ThreadManager` (`thread_utils.py`), MRC→JPEG/GIF generation (`media_utils.py`), template URL mapping (`template_utils.py`)
- Depends on: `mrcfile`, `Pillow`, `imageio`, `numpy`
- Used by: `MediaManager`, blueprints (FileLocator also used directly in `session_routes`)
- Purpose: Render HTML and handle client-side polling for async media updates
- Location: `tomcat/templates/`, `tomcat/static/js/media_updater.js`
- Contains: `upload.html` (session list), `form.html` (catalogue table view), `detail.html` (single tomogram view), `settings.html`
- Depends on: Bootstrap 5.2, Bootstrap Icons, `omggif` (interactive GIF player)
## Data Flow
- Persistent state: CSV files in `.tomcat/uploads/`, config in `.tomcat/config.json`, media in `.tomcat/media/` and `.tomcat/thumbnails/`
- In-memory state: `MediaManager.media_status` dict, `MediaManager.processing_queue` (`OrderedDict`), `app.search_jobs` dict on the Flask app instance
## Key Abstractions
- Purpose: Single source of truth for all file-system paths used throughout the app
- Examples: `tomcat/config.py`
- Pattern: Instantiated once, passed by reference into every component that needs path resolution
- Purpose: Encapsulates a pandas DataFrame backed by a CSV; provides typed accessors and `deferred_save()` context manager
- Examples: `tomcat/models/session.py`
- Pattern: `SessionManager.load_session(filename)` returns a fresh `Session` instance on each request — no long-lived session objects
- Purpose: Priority queue + cache-check layer for background media generation; decouples route handlers from thread scheduling
- Examples: `tomcat/services/media_service.py`
- Pattern: `queue_tomogram_for_processing(tomo_name, priority=bool)` is the single entry point; internal `_check_and_generate_*` methods decide whether work is needed
- Purpose: Filesystem scanner that resolves canonical tomogram names to actual MRC/image file paths using priority-ordered extension lists
- Examples: `tomcat/utils/file_utils.py`
- Pattern: `find_tomogram_file(name)`, `find_tiltseries_file(name)`, `find_lowmag_file(name)` — each checks extension priority order; falls back to recursive walk with basename extraction
- Purpose: Thin wrapper around `ThreadPoolExecutor` with deduplication by `task_key`; prevents duplicate background jobs
- Examples: `tomcat/utils/thread_utils.py`
- Pattern: `submit_task(task_key, func, *args)` — silently no-ops if a task with that key is already running
- Purpose: Inject dependencies (config, managers) into route handlers without using Flask globals or app context
- Examples: All `initialize_routes(...)` functions in `tomcat/routes/`
- Pattern: Outer function captures dependencies in closure; inner route handler functions reference them via closure scope
## Entry Points
- Location: `tomcat/app.py` → `cli()` → `run()` command
- Triggers: `python -m tomcat` or `tomcat run` via entrypoint
- Responsibilities: Calls `create_app()`, starts Flask dev server
- Location: `tomcat/app.py`
- Triggers: Called by `run` CLI command (and can be called directly for testing)
- Responsibilities: Instantiates `Config`, `ThreadManager`, `FileLocator`, `SessionManager`, `MediaManager`; registers all three blueprints with URL prefixes; registers compat routes; registers template utils
- Location: Lambda added via `app.add_url_rule('/', 'index', ...)` in `create_app()`
- Triggers: Browser navigation to root
- Responsibilities: Redirects to `/session/`
- Location: `tomcat/app.py` (registered directly on `app`, not a blueprint)
- Purpose: Preserve old URL paths (e.g., `/media_status/`, `/thumbnails/`, `/serve_media/`) by delegating to current blueprint view functions
- Triggers: Requests from `media_updater.js` which still uses old URL patterns (`/thumbnail_status/`, `/media_status/`, `/serve_media/`, `/thumbnails/`)
## Error Handling
- Services/models return `False` or `None` on failure after logging the exception with `logger.error()`
- Route handlers check return values, use `flash()` to surface errors in the UI, and redirect to a safe page
- Background thread exceptions are caught in `ThreadManager.cleanup_completed_tasks()` via `future.result()` and logged
- Media generation functions clean up empty/partial output files on failure to prevent stale cached errors
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
