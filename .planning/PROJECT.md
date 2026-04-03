# TomCat — Bug Fix Initiative

## What This Is

TomCat is a local Flask + Typer web application for cataloging and annotating electron microscopy tomography data. Researchers configure paths to data directories, create sessions (stored as CSV files), search for tomograms, and annotate them with metadata. Thumbnails and GIF animations are generated in background threads.

## Core Value

Tomograms load from cache reliably, the catalogue is free of duplicates, and the app is structurally sound — so researchers can annotate without friction or data integrity issues.

## Current State

Shipped **v1.0 Bug Fix v1** on 2026-04-03.
- All five priority bugs (Cache, Pagination, Deduplication, Thread Safety, Zip Slip) are resolved.
- Codebase contains ~7,400 LOC Python/HTML/JS.
- New test scaffolds introduced for concurrency and security.

## Requirements

### Validated

- ✓ Flask web app with Typer CLI (`tomcat run`) — existing
- ✓ Session management via CSV files in `.tomcat/uploads/` — existing
- ✓ Background media generation (thumbnails, GIFs) via ThreadPoolExecutor — existing
- ✓ Tabulated catalogue view with pagination — existing
- ✓ File priority resolution for tomogram/tilt/lowmag types — existing
- ✓ Settings UI for configuring data directory paths — existing
- ✓ Session import/export via `.tomcat` archive files — existing
- ✓ **BUG-01**: GIF/thumbnail cache is checked before re-queuing — v1.0
- ✓ **BUG-02**: Thumbnail view has page navigation matching tabulated view — v1.0
- ✓ **BUG-03**: `_preali.mrc` files do not create duplicate catalogue entries — v1.0
- ✓ **BUG-04**: `MediaManager` dict mutations are thread-safe — v1.0
- ✓ **BUG-05**: Archive import validates extracted paths against target directory (Zip Slip protection) — v1.0

### Active

- [ ] (Next milestone goals TBD via `/gsd:new-milestone`)

### Out of Scope

- New features (search improvements, new annotation fields, export formats)
- Authentication — intentionally absent; local-only tool

## Context

- **Tech stack**: Python 3.7+, Flask, Typer, pandas, mrcfile, Pillow, imageio.
- **Verification**: Verified via 25+ automated tests and manual UI checks.
- **Security**: Zip Slip protection implemented in `import_archive` using path normalization.
- **Concurrency**: Fine-grained locking in `MediaManager` protects internal state.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Disk-first gate in get_media_status | Prevent spurious queuing after restart | ✓ Good |
| Persistent pagination in thumbnail view | Parity with tabulated view; UX consistency | ✓ Good |
| Canonical basename suffix stripping | Eliminate duplicate catalogue entries | ✓ Good |
| Granular locks per dictionary | Prevent `RuntimeError` without global bottleneck | ✓ Good |
| Realpath-based Zip Slip validation | Secure archive import across platforms | ✓ Good |

---
*Last updated: 2026-04-03 after v1.0 milestone completion*
