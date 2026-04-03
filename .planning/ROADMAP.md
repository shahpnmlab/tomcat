# Roadmap: TomCat Bug Fix Initiative

**Milestone:** Bug Fix v1
**Goal:** Eliminate all five identified bugs so media loads from cache reliably, the catalogue is free of duplicates, and the app is structurally sound
**Requirements coverage:** 15/15 v1 requirements

---

## Phases

- [x] **Phase 1: Media Cache Fix** — Correct cache-check logic in MediaManager so already-generated media is never re-queued (completed 2026-04-02)
- [x] **Phase 2: Thumbnail Pagination** — Add page navigation controls to the thumbnail view, matching tabulated view behaviour (completed 2026-04-02)
- [ ] **Phase 3: File Deduplication** — Strip `_preali` suffix in FileLocator so `_preali.mrc` files do not create duplicate catalogue entries
- [ ] **Phase 4: Thread Safety & Security** — Add locks to MediaManager and ThreadManager; fix Zip Slip vulnerability in archive import

---

## Phase Details

### Phase 1: Media Cache Fix
**Goal:** The detail view and catalogue view never re-queue media generation when GIF/thumbnail files already exist on disk
**Depends on:** Nothing (independent)
**Requirements:** CACHE-01, CACHE-02, CACHE-03
**Key files:**
- `tomcat/services/media_service.py` — `MediaManager._all_media_exists()`, `generate_media_for_tomogram()`, `batch_process_tomograms()`
**Success criteria:**
- [ ] Navigating to `/session/detail/<file>/<tomo>` for a tomogram whose media files are already on disk does not submit new background jobs (verified by log output showing no new task submissions)
- [ ] Navigating between multiple catalogue entries in sequence does not re-generate media that was already generated on the first visit
- [ ] `_all_media_exists()` returns `True` only when all three media types (thumbnail, tiltseries, tomogram) are present on disk; returns `False` when any one is missing
**Plans:** 1/1 plans complete

Plans:
- [ ] 01-PLAN-01.md — Fix get_media_status() disk-first gate and status dict population

### Phase 2: Thumbnail Pagination
**Goal:** The thumbnail view renders previous/next page controls and preserves page state when switching between thumbnail and tabulated views
**Depends on:** Nothing (independent)
**Requirements:** PAGE-01, PAGE-02, PAGE-03
**Key files:**
- `tomcat/routes/session_routes.py` — route handler for the thumbnail view
- `tomcat/templates/form.html` — renders both thumbnail grid and tabulated views
**Success criteria:**
- [ ] The thumbnail view renders a visible previous/next page control and a page number indicator when a session has more entries than fit on one page
- [ ] Clicking next/previous in the thumbnail view advances or retreats by one page, matching the page size of the tabulated view
- [ ] Switching from thumbnail view to tabulated view (or vice versa) on page 3 keeps the user on page 3, not page 1
**Plans:** 1/1 plans complete

Plans:
- [x] 02-01-PLAN.md — Add pagination controls inside #thumbnail-grid-view in form.html

### Phase 3: File Deduplication
**Goal:** `_preali.mrc` files are resolved to their canonical tomogram basename and do not appear as independent entries in the catalogue
**Depends on:** Nothing (independent)
**Requirements:** DEDUP-01, DEDUP-02, DEDUP-03
**Key files:**
- `tomcat/utils/file_utils.py` — `FileLocator.extract_basename()`
**Success criteria:**
- [ ] A directory containing both `tomo001_rec.mrc` and `tomo001_preali.mrc` produces exactly one catalogue entry (`tomo001`), not two
- [ ] When no `.ali` file exists for a tomogram, `tomo001_preali.mrc` is selected as the tilt series file; when `tomo001_ali.mrc` exists, the `_preali` file is not used (existing priority order maintained)
- [ ] Sessions created before this fix that contain rows with `_preali` in the name load without error; existing annotations on those rows are not lost
**Plans:** 1 plan

Plans:
- [ ] 03-01-PLAN.md — Strip _preali suffix in extract_basename() to eliminate duplicate catalogue entries

### Phase 4: Thread Safety & Security
**Goal:** MediaManager state is never corrupted under concurrent requests, and archive import cannot write files outside the target directory
**Depends on:** Nothing (independent)
**Requirements:** THREAD-01, THREAD-02, THREAD-03, THREAD-04, SEC-01, SEC-02
**Key files:**
- `tomcat/services/media_service.py` — `MediaManager` (processing_queue, thumbnail_progress, media_status dicts)
- `tomcat/utils/thread_utils.py` — `ThreadManager.submit_task()`
- `tomcat/routes/session_routes.py` — `import_archive`
**Success criteria:**
- [ ] Running concurrent media generation requests (e.g., rapidly loading the catalogue page multiple times) does not produce a `RuntimeError: dictionary changed size during iteration` or silent key clobber (verified by log inspection or manual stress test)
- [ ] `ThreadManager.submit_task()` never submits a duplicate job for the same `task_key` even when called from two threads simultaneously
- [ ] Importing a `.tomcat` archive containing a member path such as `../../etc/passwd` causes the import to abort with a visible error message and writes no files outside `.tomcat/uploads/`
- [ ] A valid `.tomcat` archive imports successfully after the security check is in place (no regression)
**Plans:** TBD

---

## Dependency Map

All four phases are independent of each other — they touch different parts of the codebase with no shared edit surface.

| Phase | Depends on | Can run in parallel with |
|-------|------------|--------------------------|
| 1 — Media Cache Fix | — | 2, 3, 4 |
| 2 — Thumbnail Pagination | — | 1, 3, 4 |
| 3 — File Deduplication | — | 1, 2, 4 |
| 4 — Thread Safety & Security | — | 1, 2, 3 |

Recommended execution order: 1 → 2 → 3 → 4 (sequential for reviewer clarity, not because of technical dependency). Phase 3 before Phase 4 is slightly preferable because the deduplication fix touches `file_utils.py` while thread-safety touches `media_service.py` and `thread_utils.py` — no conflict either way.

---

## Risk Register

| Risk | Phase | Mitigation |
|------|-------|------------|
| `_all_media_exists()` check relies on exact file-naming convention; a mismatch in expected vs. actual filenames causes media to always be re-queued | 1 | Read the actual output paths used by `generate_jpeg_thumbnail` and the animation generators before rewriting the cache check; confirm filenames match |
| Thumbnail view template may share a base template with the tabulated view; pagination controls may need to be threaded through a shared macro rather than duplicated | 2 | Inspect template inheritance chain before writing new HTML; prefer a shared Jinja macro |
| Stripping `_preali` from existing session rows at load time could silently rename rows that users manually named with that suffix | 3 | Apply the strip only in `extract_basename()` during file discovery; do not retroactively rewrite existing CSV rows |
| Adding a `threading.Lock` to `MediaManager` methods called from the main Flask request thread risks a deadlock if a lock is held and a route calls back into a locked method | 4 | Use a single non-reentrant lock per dict; map all call sites before adding lock calls to ensure no re-entrant paths |
| Zip Slip fix that aborts on any absolute path could reject valid platform paths on Windows if the app is ever run there | 4 | Use `os.path.realpath` + `startswith` check (standard pattern); works correctly on all platforms |

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Media Cache Fix | 0/1 | Not started | - |
| 2. Thumbnail Pagination | 0/1 | Not started | - |
| 3. File Deduplication | 0/1 | Not started | - |
| 4. Thread Safety & Security | 0/0 | Not started | - |

---

*Created: 2026-04-01*
