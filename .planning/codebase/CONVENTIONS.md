# Coding Conventions

**Analysis Date:** 2026-04-01

## Naming Patterns

**Files:**
- `snake_case` for all Python module files: `file_utils.py`, `media_service.py`, `thread_utils.py`
- Route modules follow the pattern `<domain>_routes.py`: `session_routes.py`, `media_routes.py`, `settings_routes.py`
- Utility modules follow the pattern `<domain>_utils.py`: `file_utils.py`, `media_utils.py`, `thread_utils.py`

**Classes:**
- `PascalCase`: `Config`, `Session`, `SessionManager`, `FileLocator`, `MediaManager`, `ThreadManager`, `MediaProcessingError`
- Manager classes are suffixed with `Manager`: `SessionManager`, `MediaManager`, `ThreadManager`
- Error classes are suffixed with `Error`: `MediaProcessingError`

**Functions and Methods:**
- `snake_case` for all functions and methods: `create_app`, `find_tomogram_file`, `generate_jpeg_thumbnail`
- Private/internal methods prefixed with `_`: `_create_directories`, `_generate_thumbnail`, `_all_media_exists`, `_shutdown`
- Helper functions that back a public function are prefixed with `_`: `_generate_thumbnail_from_mrc`, `_generate_thumbnail_from_image`
- Blueprint factory functions named `initialize_routes`: used in every route module

**Variables:**
- `snake_case` for all variables: `tomo_name`, `file_locator`, `thread_manager`
- Module-level loggers always named `logger`: `logger = logging.getLogger(__name__)`
- Constants use `UPPER_SNAKE_CASE`: `EXTENSIONS`, `TYPE_PRIORITY`, `URL_MAPPING`

**Route endpoints:**
- Blueprint name is the domain: `session`, `media`, `settings`
- Endpoint names within blueprints use `snake_case`: `upload_file`, `process_csv`, `detail_view`

## Code Style

**Formatting:**
- Black is configured with `line-length = 88` (see `pyproject.toml`)
- Target Python versions: 3.7, 3.8, 3.9, 3.10

**Linting:**
- flake8 with `max-line-length = 88` and `extend-ignore = E203`
- isort with `profile = "black"` for import ordering

**Type annotations:**
- Not used in the codebase; all functions use only docstring-based type documentation

## Import Organization

**Order (as seen in source files):**
1. Standard library modules (`os`, `json`, `logging`, `re`, `glob`, `time`, etc.)
2. Third-party packages (`flask`, `pandas`, `numpy`, `mrcfile`, `PIL`, `imageio`, `typer`, `werkzeug`)
3. Internal `tomcat.*` imports

**Pattern:**
```python
import os
import logging
from flask import Blueprint, render_template, request
from tomcat.config import Config
from tomcat.utils.thread_utils import ThreadManager
```

**Path Aliases:**
- None used; all internal imports use full package paths: `from tomcat.utils import generate_jpeg_thumbnail`

**Deferred imports (inside functions):**
- Used sparingly in `media_service.py` to avoid circular imports:
  ```python
  from tomcat.utils import generate_jpeg_thumbnail
  ```

## Module Structure Pattern

Every module follows this structure:
1. Module-level docstring describing the module
2. Standard library imports
3. Third-party imports
4. Internal imports
5. `logger = logging.getLogger(__name__)`
6. Classes or functions

## Blueprint Pattern

All route modules use the same factory pattern:

```python
# Module level: create blueprint
session_bp = Blueprint('session', __name__)

# Factory function: inject dependencies via closure
def initialize_routes(config, session_manager, ...):
    # Inner route functions defined here capture dependencies via closure
    @session_bp.route('/path', methods=['GET', 'POST'])
    def route_handler():
        ...
    return session_bp
```

Dependencies (config, managers) are injected at startup in `tomcat/app.py` and captured by route closures, not accessed via `current_app.config` inside handlers.

## Error Handling

**Strategy:** Exception-based with logging + graceful degradation. Functions return `bool` or `None` to indicate success/failure rather than raising exceptions to callers.

**Patterns:**
- Wrap all I/O operations in `try/except Exception as e` and log with `logger.error(f"...: {str(e)}")`
- Return `False` or `None` on failure, `True` or the result on success
- Custom exception class `MediaProcessingError` in `tomcat/utils/media_utils.py` is raised internally within the media utils layer and caught at the function boundary before returning `False`
- Route handlers use `flash()` for user-visible error messages and redirect
- API (JSON) routes return `jsonify({"status": "error", "message": ...})` with appropriate HTTP status codes

**Example pattern (service layer):**
```python
try:
    result = do_operation()
    logger.info(f"Success: {result}")
    return True
except Exception as e:
    logger.error(f"Error doing operation: {str(e)}")
    return False
```

**Example pattern (route handler):**
```python
try:
    ...
    flash("Success message")
    return redirect(url_for('session.upload_file'))
except Exception as e:
    logger.error(f"Error in route: {str(e)}")
    flash(f"Error: {str(e)}")
    return redirect(url_for('session.upload_file'))
```

**Bare `except` blocks:**
- Used in cleanup code where errors must not propagate: `finally` blocks that remove temp files use bare `except: pass`

## Logging

**Framework:** Python standard library `logging`

**Setup:**
- Root logger configured in `tomcat/app.py`:
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(levelname)s - %(message)s',
      datefmt='%H:%M:%S'
  )
  ```
- Each module creates its own logger: `logger = logging.getLogger(__name__)`

**Levels used:**
- `logger.debug()` — internal tracing, file search steps, frame processing progress
- `logger.info()` — successful operations: "Generated thumbnail for X", "Loaded session from Y"
- `logger.warning()` — non-fatal issues: "Directory not found", "MRC file contains NaN values"
- `logger.error()` — operation failures with `str(e)` included

**F-string formatting:**
- All log messages use f-strings: `logger.info(f"Loaded session from {self.filepath}")`

## Comments

**When to Comment:**
- Section dividers use `# ===` style banners in `app.py`
- Inline comments explain non-obvious logic (file priority ordering, queue recursion prevention)
- `# TODO`/`# FIXME`/`# NOTE` markers not observed in the codebase — inline comments explain intent directly

**Docstrings:**
- Every public class and method has a Google-style docstring with `Args:` and `Returns:` sections
- Private/helper functions (`_generate_thumbnail_from_mrc`) have brief single-line docstrings
- Module-level docstrings present on every file

**Docstring format:**
```python
def find_file(self, tomo_name, directory, extensions):
    """
    Find a file for a specific tomogram in the given directory.

    Args:
        tomo_name (str): Tomogram name to find
        directory (str): Directory to search in
        extensions (list): List of file extensions to look for

    Returns:
        str or None: Path to the file if found, None otherwise
    """
```

## Function Design

**Size:** Functions tend to be medium-length (20-80 lines). Long functions such as `generate_tiltseries_animation` in `tomcat/utils/media_utils.py` (120+ lines) contain multiple fallback strategies.

**Parameters:**
- Required parameters are positional; optional ones use keyword defaults
- `**kwargs` used in `update_tomogram_data` and `update_paths` for flexible field updates
- Long parameter lists in route factories: `initialize_routes(config, session_manager, file_locator, media_manager, allowed_file_func, thread_manager)`

**Return Values:**
- Service/model methods: `bool` for operations, `str/None` for lookup, `dict/None` for data retrieval
- Route handlers: Flask response objects (`render_template`, `redirect`, `jsonify`)
- Background worker functions: `bool`

## Context Managers

Used consistently for resource management and logical grouping:
- `Session.deferred_save()` — context manager to batch CSV writes, defined in `tomcat/models/session.py`
- `safe_file_open()` — context manager for error-wrapped file I/O in `tomcat/utils/media_utils.py`
- `mrcfile.open()` — used with `with` throughout `tomcat/utils/media_utils.py`

## Module Exports

**`__all__` lists** defined in `tomcat/utils/__init__.py` to control public API:
```python
__all__ = [
    'extract_basename',
    'FileLocator',
    'ThreadManager',
    'generate_jpeg_thumbnail',
    'generate_tiltseries_animation',
    'generate_tomogram_animation'
]
```

Other `__init__.py` files are empty or minimal.

---

*Convention analysis: 2026-04-01*
