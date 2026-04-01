# Phase 1: Media Cache Fix - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix `MediaManager` so that media files (thumbnails, GIFs) already on disk are never re-queued for regeneration. The detail view and catalogue view must detect existing files before scheduling background work.

</domain>

<decisions>
## Implementation Decisions

### Root Cause
- **D-01:** The primary re-generation trigger is `get_media_status()` — when `media_status[key]` is `"unknown"` (after server restart, since the dict is in-memory) and the file doesn't exist yet in the dict, it sets status to `"generating"` then calls `queue_tomogram_for_processing()`. Even though `queue_tomogram_for_processing()` correctly calls `_all_media_exists()`, the status is already set to `"generating"` for this session.
- **D-02:** `_all_media_exists()` logic is structurally correct — it checks disk existence. The fix must ensure this check is the authoritative gate, not bypassed by status-dict state.

### Fix Strategy
- **D-03:** In `get_media_status()`, check if the file exists on disk BEFORE checking `media_status`. If the file exists and has size > 0, return `"ready"` immediately — do NOT queue or change status. This removes the re-queuing path entirely for already-generated media.
- **D-04:** Do not remove or alter `_all_media_exists()` — it is correct and should remain as the gate inside `queue_tomogram_for_processing()`.
- **D-05:** On status `"unknown"`: only queue if the file does NOT exist on disk. Set status to `"generating"` only after successfully enqueuing (i.e., after `queue_tomogram_for_processing()` returns True).

### Status Dict Initialisation
- **D-06:** When media is confirmed ready from disk (file exists, size > 0), update `media_status[key] = "ready"` so subsequent polls return from the dict without disk I/O.
- **D-07:** No persistent storage for `media_status` across restarts — in-memory cache populated lazily on first poll is acceptable. The disk check is the truth source.

### Scope
- **D-08:** Fix is confined to `tomcat/services/media_service.py`. No changes to routes, templates, thread_utils, or config.
- **D-09:** Do not change the polling frequency or JS behaviour — that is out of scope.

### Claude's Discretion
- Exact ordering of disk-check vs dict-check within `get_media_status()`
- Whether to extract the disk-check logic into a per-type helper or inline it

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source files
- `tomcat/services/media_service.py` — Full MediaManager implementation; `_all_media_exists()`, `get_media_status()`, `queue_tomogram_for_processing()`, `_check_and_generate_*` methods
- `tomcat/config.py` — `config.thumbnails_folder`, `config.lowmag_folder`, `config.tiltseries_folder`, `config.tomogram_folder` path attributes used in existence checks
- `tomcat/utils/thread_utils.py` — `ThreadManager.submit_task()` deduplication behaviour

### Planning artifacts
- `.planning/REQUIREMENTS.md` — CACHE-01, CACHE-02, CACHE-03
- `.planning/ROADMAP.md` — Phase 1 success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_all_media_exists()` — already correct; reuse its per-type file-path construction logic in `get_media_status()`
- `config.*_folder` attributes — exact folder paths already available on the config object

### Established Patterns
- All media generation methods follow: check file exists → submit task → return
- Status dict keys follow pattern `f"{media_type}_{tomo_name}"` (e.g., `"tiltseries_tomo001"`)
- File naming: thumbnail `{tomo_name}*.png` (glob), lowmag `{tomo_name}.jpg`, tiltseries `{tomo_name}.gif`, tomogram `{tomo_name}.gif`

### Integration Points
- `get_media_status()` is called by `media_routes.py` to serve `/media/media_status/<type>/<name>` — polled by `media_updater.js` every 2 seconds per tomogram
- `generate_media_for_tomogram()` called from `session_routes.py` detail_view (line ~390)
- `batch_process_tomograms()` called from `session_routes.py` process_csv (line ~310)

</code_context>

<specifics>
## Specific Ideas

- The fix is a targeted change to `get_media_status()`: move the file-existence check to the top of the function, before any status-dict lookup or queue call
- No structural refactoring needed — single method change

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-media-cache-fix*
*Context gathered: 2026-04-01*
