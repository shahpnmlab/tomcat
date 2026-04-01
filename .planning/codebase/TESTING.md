# Testing

## Overview

**Status: No tests exist.** The project lists `pytest>=6.0.0` as a dev dependency in `pyproject.toml` but has zero test files in the repository.

## Test Framework

- **Framework:** pytest (declared, not implemented)
- **Test files:** None found
- **Coverage:** 0%

## Configuration

`pyproject.toml` declares dev dependencies:
```
dev = [
    "pytest>=6.0.0",
    "black>=22.0.0",
    "isort>=5.0.0",
    "flake8>=4.0.0",
]
```

No `pytest.ini`, `conftest.py`, or `tox.ini` present.

## What Would Need Testing

Given the architecture, the following areas have highest value for tests:

### Unit Tests
- `tomcat/utils/file_utils.py` — `FileLocator.extract_basename()`, file format priority logic
- `tomcat/models/session.py` — `Session` CSV parsing, metadata validation
- `tomcat/config.py` — Config load/save round-trips
- `tomcat/utils/media_utils.py` — Thumbnail/GIF generation (requires mock MRC data)

### Integration Tests
- Flask routes via `flask.testing.FlaskClient`
- `SessionManager` create/load workflows
- `MediaManager` cache-check and queue behavior
- `FileLocator` directory scanning with fixture directories

### Flask Test Client Pattern
The app factory `create_app()` in `tomcat/app.py` supports testing:
```python
import pytest
from tomcat.app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
```

## Mocking Considerations

- **MRC files:** `mrcfile` library would need real or mock `.mrc` files for media generation tests
- **File system:** Temp directories via `tmp_path` pytest fixture for session/config tests
- **ThreadPoolExecutor:** Should be mocked in unit tests to avoid background thread complications

## CI/CD

No CI configuration found (no `.github/workflows/`, no `Makefile` with test targets).