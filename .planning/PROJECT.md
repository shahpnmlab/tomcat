# TomCat — Bug Fix Initiative

## What This Is

TomCat is a local Flask + Typer web application for cataloging and annotating electron microscopy tomography data. Researchers configure paths to data directories, create sessions (stored as CSV files), search for tomograms, and annotate them with metadata. Thumbnails and GIF animations are generated in background threads.

This initiative addresses five identified bugs: incorrect media cache behavior, missing pagination in thumbnail view, duplicate entries from `_preali.mrc` files, race conditions in `MediaManager`, and a Zip Slip vulnerability in archive import.

## Core Value

Tomograms load from cache reliably, the catalogue is free of duplicates, and the app is structurally sound — so researchers can annotate without friction or data integrity issues.

## Requirements

### Validated

- ✓ Flask web app with Typer CLI (`tomcat run`) — existing
- ✓ Session management via CSV files in `.tomcat/uploads/` — existing
- ✓ Background media generation (thumbnails, GIFs) via ThreadPoolExecutor — existing
- ✓ Tabulated catalogue view with pagination — existing
- ✓ File priority resolution for tomogram/tilt/lowmag types — existing
- ✓ Settings UI for configuring data directory paths — existing
- ✓ Session import/export via `.tomcat` archive files — existing

### Active

- [ ] **BUG-01**: GIF/thumbnail cache is checked before re-queuing — media not regenerated when files already exist on disk
- [ ] **BUG-02**: Thumbnail view has page navigation matching tabulated view
- [ ] **BUG-03**: `_preali.mrc` files do not create duplicate catalogue entries; used as fallback when `.ali` file absent
- [ ] **BUG-04**: `MediaManager` dict mutations are thread-safe (locks around `processing_queue`, `thumbnail_progress`, `media_status`)
- [ ] **BUG-05**: Archive import validates extracted paths against target directory (no Zip Slip)

### Out of Scope

- New features (search improvements, new annotation fields, export formats) — bug-fix scope only
- Authentication — intentionally absent; local-only tool
- Test suite creation — valuable but separate initiative

## Context

- **Entry point for media generation:** `MediaManager.generate_media_for_tomogram()` and `batch_process_tomograms()` in `tomcat/services/media_service.py`. Cache check is `_all_media_exists()`.
- **BUG-01 root cause:** Cache check is not correctly detecting existing files before queuing background work; detail view (`/session/detail/`) triggers re-generation on every access.
- **BUG-02 root cause:** Thumbnail view template/route does not pass or render page number controls; tabulated view (`form.html`) does.
- **BUG-03 root cause:** `FileLocator.extract_basename()` in `tomcat/utils/file_utils.py` does not strip `_preali` suffix; `_preali.mrc` files surface as independent entries.
- **BUG-04 root cause:** `processing_queue` (OrderedDict), `thumbnail_progress`, and `media_status` dicts in `MediaManager` mutated from worker threads with no `threading.Lock`.
- **BUG-05 root cause:** `import_archive` in `tomcat/routes/session_routes.py` extracts archive without validating member paths against the target directory.

## Constraints

- **Tech stack**: Python 3.7+, Flask, Typer, pandas, mrcfile, Pillow, imageio — no new dependencies
- **Compatibility**: Existing sessions and media files must continue to work after fixes
- **Scope**: Changes limited to bug fixes; no refactoring of unrelated code

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix all 5 bugs in one initiative | Small, related changes; lower overhead as one pass | — Pending |
| No new test suite in this initiative | Separate concern; fixes are verifiable by manual testing | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after initialization*