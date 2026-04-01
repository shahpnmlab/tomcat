# Codebase Structure

**Analysis Date:** 2026-04-01

## Directory Layout

```
tomcat/                          # Project root
├── pyproject.toml               # Package metadata, dependencies, entrypoints
├── CLAUDE.md                    # Project guidance for AI assistants
├── README.md                    # User documentation
├── assets/                      # Static project assets (non-served)
├── tomcat/                      # Main Python package
│   ├── __init__.py
│   ├── app.py                   # Flask app factory + Typer CLI entry point
│   ├── config.py                # Config class (loads/saves .tomcat/config.json)
│   ├── models/
│   │   ├── __init__.py
│   │   └── session.py           # Session + SessionManager (CSV-backed data model)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── session_routes.py    # Blueprint: /session/* (catalogue, detail, search, export)
│   │   ├── settings_routes.py   # Blueprint: /settings/* (path config, directory browser)
│   │   └── media_routes.py      # Blueprint: /media/* (serve files, status polling)
│   ├── services/
│   │   ├── __init__.py
│   │   └── media_service.py     # MediaManager (queue, cache-check, background dispatch)
│   ├── utils/
│   │   ├── __init__.py          # Re-exports: FileLocator, ThreadManager, generate_* funcs
│   │   ├── file_utils.py        # FileLocator (MRC file discovery), extract_basename()
│   │   ├── thread_utils.py      # ThreadManager (ThreadPoolExecutor wrapper)
│   │   ├── media_utils.py       # generate_jpeg_thumbnail(), generate_*_animation()
│   │   └── template_utils.py    # Jinja url_for override for blueprint compat
│   ├── templates/
│   │   ├── upload.html          # Session list page (landing page at /session/)
│   │   ├── form.html            # Catalogue table view (/session/process/<filename>)
│   │   ├── detail.html          # Single tomogram detail view (/session/detail/...)
│   │   └── settings.html        # Settings page (/settings/settings)
│   └── static/
│       ├── js/
│       │   └── media_updater.js # Client-side polling + interactive GIF player
│       └── img/
│           ├── 3dmod_active.png
│           └── 3dmod_inactive.png
└── .tomcat/                     # Runtime data dir (auto-created, gitignored)
    ├── config.json              # User path configuration
    ├── uploads/                 # Session files (*.tomcat CSV files)
    ├── thumbnails/              # Generated PNG thumbnails (<name>.png)
    └── media/
        ├── lowmag/              # Generated lowmag JPEGs (<name>.jpg)
        ├── tiltseries/          # Generated tilt series GIFs (<name>.gif)
        └── tomogram/            # Generated tomogram GIFs (<name>.gif)
```

## Directory Purposes

**`tomcat/` (package root):**
- Purpose: Python package; `app.py` is the single wiring point for the entire app
- Key files: `tomcat/app.py` (factory + CLI), `tomcat/config.py` (configuration)

**`tomcat/models/`:**
- Purpose: Data models — encapsulate CSV-backed session state
- Contains: `Session` class (DataFrame + file I/O), `SessionManager` (session lifecycle)
- Key files: `tomcat/models/session.py`

**`tomcat/routes/`:**
- Purpose: Flask blueprints — HTTP layer only; each module defines one blueprint
- Contains: Route handler functions as closures capturing injected service/manager instances
- Key files: `tomcat/routes/session_routes.py`, `tomcat/routes/media_routes.py`, `tomcat/routes/settings_routes.py`

**`tomcat/services/`:**
- Purpose: Business logic that coordinates multiple utilities; currently holds media orchestration
- Contains: `MediaManager` — the only service class; owns the generation queue and status tracking
- Key files: `tomcat/services/media_service.py`

**`tomcat/utils/`:**
- Purpose: Low-level, reusable utilities with no knowledge of Flask or routes
- Contains: File discovery (`file_utils.py`), thread pool (`thread_utils.py`), MRC processing (`media_utils.py`), template helpers (`template_utils.py`)
- Key files: `tomcat/utils/file_utils.py`, `tomcat/utils/thread_utils.py`, `tomcat/utils/media_utils.py`

**`tomcat/templates/`:**
- Purpose: Jinja2 HTML templates; one template per major UI view
- Contains: Bootstrap 5-based responsive HTML; inline JS for autosave and search polling
- Key files: `tomcat/templates/form.html` (main catalogue view), `tomcat/templates/detail.html`

**`tomcat/static/`:**
- Purpose: Served static files (JS, images)
- Contains: `media_updater.js` (polling client), 3dmod launcher button images
- Key files: `tomcat/static/js/media_updater.js`

**`.tomcat/` (runtime, not committed):**
- Purpose: All user data and generated files; created automatically by `Config.__init__()`
- Generated: Yes (at runtime)
- Committed: No

## Key File Locations

**Entry Points:**
- `tomcat/app.py`: CLI entry (`tomcat run`), `create_app()` factory

**Configuration:**
- `tomcat/config.py`: `Config` class definition
- `.tomcat/config.json`: Runtime user config (paths to data directories)
- `pyproject.toml`: Package dependencies and build config

**Core Logic:**
- `tomcat/models/session.py`: Session data model (CSV read/write, tomogram CRUD)
- `tomcat/services/media_service.py`: Media generation orchestration
- `tomcat/utils/file_utils.py`: MRC file discovery (`FileLocator`, `extract_basename`)
- `tomcat/utils/media_utils.py`: MRC→JPEG/GIF conversion functions

**Routes:**
- `tomcat/routes/session_routes.py`: Main catalogue routes, search, autosave, export
- `tomcat/routes/settings_routes.py`: Settings form, directory browser API
- `tomcat/routes/media_routes.py`: Media file serving, status polling endpoints

**Frontend:**
- `tomcat/static/js/media_updater.js`: Polling logic and interactive GIF player
- `tomcat/templates/form.html`: Catalogue table with pagination, search, inline editing
- `tomcat/templates/detail.html`: Per-tomogram media viewer with prev/next navigation

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `media_service.py`, `file_utils.py`)
- Templates: `snake_case.html` (e.g., `upload.html`, `detail.html`)
- JS files: `snake_case.js` (e.g., `media_updater.js`)
- Session files: `<name>.tomcat` (CSV format with `.tomcat` extension)
- Generated thumbnails: `<tomo_name>.png` in `.tomcat/thumbnails/`
- Generated media: `<tomo_name>.jpg` or `<tomo_name>.gif` in respective subdirs

**Directories:**
- Packages: `snake_case/` (`models/`, `routes/`, `services/`, `utils/`)
- Runtime data: `.tomcat/` (hidden dot directory at cwd)

**Classes:**
- PascalCase: `Config`, `Session`, `SessionManager`, `MediaManager`, `FileLocator`, `ThreadManager`

**Functions:**
- snake_case throughout: `create_app()`, `extract_basename()`, `generate_jpeg_thumbnail()`
- Blueprint route functions named after their HTTP action: `upload_file`, `process_csv`, `detail_view`, `serve_media`

## Where to Add New Code

**New Blueprint (new feature area):**
- Implementation: `tomcat/routes/<feature>_routes.py` — define Blueprint, wrap handlers in `initialize_routes(config, ...)` pattern
- Registration: Add `app.register_blueprint(...)` call in `create_app()` in `tomcat/app.py`
- Tests: `tests/test_<feature>_routes.py`

**New Service (business logic):**
- Implementation: `tomcat/services/<feature>_service.py` — instantiate in `create_app()`, inject into relevant blueprints
- No base class required; follow `MediaManager` pattern

**New Utility Function:**
- Shared helpers: `tomcat/utils/media_utils.py` (media processing), `tomcat/utils/file_utils.py` (file ops)
- Export from: `tomcat/utils/__init__.py` — add to `__all__`

**New Template:**
- Location: `tomcat/templates/<name>.html`
- Convention: Extend Bootstrap 5 patterns from existing templates; include `media_updater.js` if media polling is needed

**New Model:**
- Location: `tomcat/models/<name>.py`
- Convention: Accept `config` as first constructor argument; use pandas for tabular data

**New CLI Command:**
- Location: `tomcat/app.py` — add `@cli.command()` decorated function

## Special Directories

**`.tomcat/`:**
- Purpose: All user-generated runtime data — config, sessions, media cache
- Generated: Yes (on first `Config` instantiation)
- Committed: No (in `.gitignore`)
- Note: Location is always relative to `cwd` at the time `tomcat run` is invoked

**`tomcat.egg-info/`:**
- Purpose: Editable install metadata generated by `pip install -e .`
- Generated: Yes
- Committed: No

**`assets/`:**
- Purpose: Project-level static assets (e.g., screenshots, documentation images)
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-04-01*