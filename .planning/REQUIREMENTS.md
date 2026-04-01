# Requirements: TomCat Bug Fix Initiative

**Defined:** 2026-04-01
**Core Value:** Tomograms load from cache reliably, the catalogue is free of duplicates, and the app is structurally sound

## v1 Requirements

### Media Cache

- [ ] **CACHE-01**: Detail view (`/session/detail/`) does not re-queue media generation when GIF/thumbnail files already exist on disk
- [ ] **CACHE-02**: `MediaManager._all_media_exists()` correctly checks all three media types (thumbnail, tiltseries, tomogram) before queuing
- [ ] **CACHE-03**: Switching between catalogue entries does not trigger re-generation of already-cached media

### UI Pagination

- [ ] **PAGE-01**: Thumbnail view renders page navigation controls (previous/next page, page number indicator)
- [ ] **PAGE-02**: Thumbnail view page navigation matches the behaviour of the tabulated view (same route parameter handling)
- [ ] **PAGE-03**: Page state is preserved when switching between tabulated and thumbnail views within a session

### File Deduplication

- [ ] **DEDUP-01**: `FileLocator.extract_basename()` strips `_preali` suffix so `_preali.mrc` files share a canonical name with their tomogram
- [ ] **DEDUP-02**: `_preali.mrc` is used as the tilt series fallback only when no `.ali` file exists for a given tomogram (existing priority order maintained)
- [ ] **DEDUP-03**: Existing sessions with duplicate `_preali` entries are not broken by the fix (graceful handling)

### Thread Safety

- [ ] **THREAD-01**: `MediaManager.processing_queue` (OrderedDict) mutations are protected by a `threading.Lock`
- [ ] **THREAD-02**: `MediaManager.thumbnail_progress` dict mutations are protected by a `threading.Lock`
- [ ] **THREAD-03**: `MediaManager.media_status` dict mutations are protected by a `threading.Lock`
- [ ] **THREAD-04**: `ThreadManager.submit_task` check-and-add to the in-progress set is atomic (lock-protected)

### Security

- [ ] **SEC-01**: `import_archive` in session routes validates each extracted member path against the target extraction directory before writing
- [ ] **SEC-02**: Any member path that would resolve outside the target directory causes the import to abort with an error message (no partial extraction)

## v2 Requirements

### Testing

- **TEST-01**: Unit tests for `FileLocator.extract_basename()` covering `_preali`, `_rec`, `_ali` suffix stripping
- **TEST-02**: Unit tests for `MediaManager` cache-check logic
- **TEST-03**: Integration tests for archive import with malicious path members
- **TEST-04**: Thread safety stress tests for `MediaManager`

### Other Hardening

- **HARD-01**: Flask `SECRET_KEY` loaded from environment variable instead of hardcoded
- **HARD-02**: `Session.save()` uses atomic write (temp file + `os.replace()`)
- **HARD-03**: MRC loading uses memory-mapped mode to avoid OOM on large files

## Out of Scope

| Feature | Reason |
|---------|--------|
| New annotation fields | Bug-fix scope only |
| Authentication / access control | Intentionally absent; local-only tool |
| Test suite creation | Separate initiative (v2) |
| Search improvements | Not requested |
| Performance optimizations (polling batching, MRC mmap) | Deferred to v2 |
| Flask SECRET_KEY hardening | Deferred to v2 (no network exposure) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CACHE-01 | Phase 1 | Pending |
| CACHE-02 | Phase 1 | Pending |
| CACHE-03 | Phase 1 | Pending |
| PAGE-01 | Phase 2 | Pending |
| PAGE-02 | Phase 2 | Pending |
| PAGE-03 | Phase 2 | Pending |
| DEDUP-01 | Phase 3 | Pending |
| DEDUP-02 | Phase 3 | Pending |
| DEDUP-03 | Phase 3 | Pending |
| THREAD-01 | Phase 4 | Pending |
| THREAD-02 | Phase 4 | Pending |
| THREAD-03 | Phase 4 | Pending |
| THREAD-04 | Phase 4 | Pending |
| SEC-01 | Phase 4 | Pending |
| SEC-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*
