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
