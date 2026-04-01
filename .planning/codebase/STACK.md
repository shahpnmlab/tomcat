# Technology Stack

**Analysis Date:** 2026-04-01

## Languages

**Primary:**
- Python 3.10 (recommended via conda) - All backend logic, CLI, media processing
- HTML/Jinja2 - Server-rendered templates in `tomcat/templates/`
- JavaScript (vanilla ES6+) - Client-side polling in `tomcat/static/js/media_updater.js`

**Secondary:**
- CSS (inline in templates + Bootstrap) - UI styling

## Runtime

**Environment:**
- Python >=3.7, tested on 3.10
- Recommended: conda environment (`conda create -n tomcat python=3.10`)

**Package Manager:**
- pip (editable install: `pip install -e .`)
- Lockfile: Not present — only `pyproject.toml` with version ranges

## Frameworks

**Core:**
- Flask >=2.0.0 - Web application framework; app factory in `tomcat/app.py`
- Typer >=0.7.0 - CLI framework; defines `run`, `init`, `info` commands in `tomcat/app.py`
- Werkzeug >=2.0.0 - Flask dependency; also used directly via `werkzeug.utils.secure_filename` in `tomcat/models/session.py`

**Templating:**
- Jinja2 (bundled with Flask) - Server-side HTML templates; templates at `tomcat/templates/`

**Frontend (CDN-loaded, not bundled):**
- Bootstrap 5.2.3 - UI components; loaded from `cdn.jsdelivr.net`
- Bootstrap Icons 1.10.0 - Icon set; loaded from `cdn.jsdelivr.net`

**Build/Dev:**
- setuptools >=61.0 + wheel - Build backend per `pyproject.toml`
- black >=22.0.0 - Code formatter (dev dependency)
- isort >=5.0.0 - Import sorter (dev dependency)
- flake8 >=4.0.0 - Linter (dev dependency)
- pytest >=6.0.0 - Test runner (dev dependency)

## Key Dependencies

**Critical:**
- `mrcfile` >=1.3.0 — Reads MRC/REC electron microscopy files; used in `tomcat/utils/media_utils.py` for all image/animation generation
- `numpy` >=1.20.0 — Array operations on MRC data; percentile-based normalization in `tomcat/utils/media_utils.py`
- `Pillow` >=8.0.0 — Image resizing and JPEG/GIF output; used in `tomcat/utils/media_utils.py`
- `imageio` >=2.9.0 — Primary GIF animation writer; used in `tomcat/utils/media_utils.py` with PIL as fallback
- `pandas` >=1.0.0 — Session data storage as DataFrames backed by CSV files; used in `tomcat/models/session.py`

**Infrastructure:**
- `concurrent.futures.ThreadPoolExecutor` (stdlib) — Background media generation pool (4 workers default); wrapped in `tomcat/utils/thread_utils.py`

## Configuration

**Environment:**
- No environment variables required for operation
- All user configuration stored in `.tomcat/config.json` in the working directory
- Config keys: `lowmag_path`, `tiltseries_path`, `tomogram_path`
- Config class: `tomcat/config.py`

**Build:**
- `pyproject.toml` — Defines dependencies, entry points, tool settings (black, isort, flake8)
- Entry point: `tomcat = "tomcat.app:cli"` — installs `tomcat` CLI command

## Platform Requirements

**Development:**
- Python >=3.7 (3.10 recommended)
- conda or venv for isolation
- No database server, no message queue — all local filesystem

**Production:**
- Flask's built-in dev server via `app.run()` — not production-grade (no WSGI server like gunicorn)
- Default port: 16006 on 127.0.0.1
- All data stored under `.tomcat/` in the working directory

---

*Stack analysis: 2026-04-01*
