# Milestones

## v1.0 Bug Fix v1 (Shipped: 2026-04-03)

**Phases completed:** 4 phases, 6 plans, 7 tasks

**Key accomplishments:**

- `get_media_status()` now gates on disk existence first, caches "ready" in the status dict, and only queues background jobs when the file is genuinely absent — eliminating spurious re-generation on every detail-view poll after server restart.
- Bootstrap pagination controls added inside #thumbnail-grid-view using the existing `pagination` context variable, with view mode persisted via localStorage across page reloads
- `extract_basename()` now strips `_preali` and `_preali.mrc` suffixes, so directories with both `tomo001_rec.mrc` and `tomo001_preali.mrc` produce a single catalogue entry `tomo001` instead of two.
- Thread-safe MediaManager and ThreadManager using granular locks to prevent race conditions and concurrent mutation errors.

---
