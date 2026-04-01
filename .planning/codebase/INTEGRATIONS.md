# External Integrations

**Analysis Date:** 2026-04-01

## APIs & External Services

**None** — TomCat is a fully local application. It does not call any external APIs or web services at runtime.

**CDN resources (frontend only, loaded in browser):**
- Bootstrap 5.2.3 CSS — `https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css`
- Bootstrap Icons 1.10.0 — `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css`

These are HTML `<link>` tags in templates (`tomcat/templates/upload.html`, `tomcat/templates/form.html`, `tomcat/templates/detail.html`, `tomcat/templates/settings.html`). No server-side network calls are made.

## Data Storage

**Databases:**
- None — no database server used

**File-based storage (local filesystem only):**
- Session data: CSV files stored in `.tomcat/uploads/` (`.tomcat` extension, CSV format)
  - Read/written via `pandas.read_csv` / `DataFrame.to_csv` in `tomcat/models/session.py`
- App configuration: `.tomcat/config.json` (JSON)
  - Read/written via `json.load` / `json.dump` in `tomcat/config.py`
- Generated thumbnails: `.tomcat/thumbnails/*.png` (JPEG encoded as PNG filename)
- Generated media: `.tomcat/media/lowmag/*.jpg`, `.tomcat/media/tiltseries/*.gif`, `.tomcat/media/tomogram/*.gif`
- Source data: User-configured directories on local filesystem (MRC, REC, ST, DM4, TIF, JPG formats)

**File Storage:**
- Local filesystem only — all paths managed by `tomcat/config.py`

**Caching:**
- File-system cache only — generated media files serve as cache; checked via `os.path.exists` before regeneration in `tomcat/services/media_service.py`

## Authentication & Identity

**Auth Provider:**
- None — no authentication or user management
- Flask secret key is hardcoded: `app.secret_key = 'tomcat_secret_key'` in `tomcat/app.py`
  - Used only for Flask session flash messages

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service

**Logs:**
- Python stdlib `logging` module
- Format: `%(asctime)s - %(levelname)s - %(message)s` with `%H:%M:%S` time format
- Configured at INFO level in `tomcat/app.py`
- All modules use `logger = logging.getLogger(__name__)`
- Output: stdout only (no log files, no log rotation)

## CI/CD & Deployment

**Hosting:**
- Local machine only — Flask dev server (`app.run()` in `tomcat/app.py`)
- Default binding: `127.0.0.1:16006`

**CI Pipeline:**
- None detected — no CI configuration files present

## Environment Configuration

**Required env vars:**
- None — application requires no environment variables

**Config file:**
- `.tomcat/config.json` in working directory (auto-created on first run)
- Keys: `lowmag_path`, `tiltseries_path`, `tomogram_path` (all strings, default empty)

**Secrets location:**
- No secrets — the Flask secret key is a hardcoded string in `tomcat/app.py`

## Webhooks & Callbacks

**Incoming:**
- None — no webhook endpoints

**Outgoing:**
- None — no outgoing HTTP requests from the server

## Internal Polling (Browser to Server)

**Mechanism:**
- JavaScript in `tomcat/static/js/media_updater.js` polls Flask routes every 2000ms
- Endpoints polled:
  - `/media/media_status/<type>/<name>` — returns JSON status (`generating`, `ready`, `error`)
  - `/media/thumbnail_status/<name>` — thumbnail-specific status
  - `/media/thumbnail_progress` — overall batch progress
- Max 30 retry attempts per media item before giving up
- This is browser-to-server polling only, not a push/WebSocket mechanism

## Scientific File Format Dependencies

**MRC/REC format:**
- `mrcfile` >=1.3.0 library reads binary MRC format files (electron microscopy standard)
- Files located on local filesystem via user-configured paths
- Supported source formats: `.mrc`, `_rec.mrc`, `.rec`, `_preali.mrc`, `_ali.mrc`, `.st`, `.st.mrc`, `.dm4`, `.tif`, `.tiff`, `.jpg`, `.jpeg`, `.png`
- Format priority logic in `tomcat/utils/file_utils.py`

---

*Integration audit: 2026-04-01*
