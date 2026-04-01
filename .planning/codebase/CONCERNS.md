# Concerns

Technical debt, known issues, and areas needing attention.

---

## Security

### Hardcoded Secret Key
- **File:** `tomcat/app.py:53`
- **Issue:** Flask `SECRET_KEY` is hardcoded as a static string
- **Risk:** Session forgery if key is discovered; breaks security across deployments
- **Fix:** Load from environment variable or config file excluded from VCS

### Unrestricted Filesystem Browsing
- **File:** `tomcat/routes/settings_routes.py`
- **Issue:** Settings UI allows configuring arbitrary filesystem paths with no sandboxing
- **Risk:** Could expose sensitive paths if app is accessible beyond localhost
- **Fix:** Acceptable for a local-only tool; document clearly as localhost-only

### Zip Slip Vulnerability
- **File:** `tomcat/routes/session_routes.py` — `import_archive`
- **Issue:** Archive extraction doesn't validate extracted paths against target directory
- **Risk:** Malicious archive could overwrite arbitrary files on the filesystem
- **Fix:** Validate each member path against the target extraction directory before extracting

### No Authentication
- **Issue:** Application has no login or access control
- **Risk:** Any process/user with network access to the port can read/modify data
- **Fix:** Acceptable for local-only use; document scope clearly

---

## Race Conditions

### MediaManager Thread Safety
- **File:** `tomcat/services/media_service.py`
- **Issue:** `processing_queue`, `thumbnail_progress`, and `media_status` dicts are mutated from worker threads without locks
- **Risk:** Corrupted state under concurrent media generation requests
- **Fix:** Use `threading.Lock` around dict mutations, or switch to `concurrent.futures` result polling

### Non-Atomic Task Submission
- **File:** `tomcat/utils/thread_utils.py` — `ThreadManager.submit_task`
- **Issue:** Check-then-set pattern on the in-progress set is not atomic
- **Risk:** Duplicate media generation jobs submitted under race conditions
- **Fix:** Use a `threading.Lock` around the check-and-add operation

---

## Technical Debt

### Global Service Instances
- **File:** `tomcat/app.py`
- **Issue:** `SessionManager`, `MediaManager`, `ThreadManager` instantiated at module level as globals
- **Risk:** Makes testing difficult; services share state across requests
- **Fix:** Use Flask application context (`g`) or proper dependency injection

### Unbounded `search_jobs` Dict (Memory Leak)
- **File:** `tomcat/routes/session_routes.py` (likely)
- **Issue:** Search job results accumulate without expiry or cleanup
- **Risk:** Memory grows unbounded over long-running sessions
- **Fix:** Add TTL-based eviction or bound the dict size

### FileLocator Instantiated Twice
- **File:** `tomcat/app.py`
- **Issue:** `FileLocator` object created redundantly
- **Fix:** Single instantiation, passed via dependency injection

### Stale Developer Comment
- **File:** `tomcat/app.py`
- **Issue:** Comment `# ADD THIS LINE:` left from development — not user-facing but indicates incomplete cleanup

### `_preali.mrc` Basename Not Stripped
- **File:** `tomcat/utils/file_utils.py` — `extract_basename`
- **Issue:** `_preali` suffix not removed when extracting canonical basename
- **Risk:** Mismatched lookups between file types for the same tomogram

### Broken `.tomcat` Import
- **File:** `tomcat/routes/session_routes.py` — `import_archive`
- **Issue:** Import only searches for `.csv` files inside archive, ignores other session artifacts
- **Fix:** Include all `.tomcat/` directory contents in import/export

---

## Performance

### Full MRC Files Loaded into RAM
- **File:** `tomcat/utils/media_utils.py`
- **Issue:** Entire MRC volume loaded into memory for thumbnail/GIF generation
- **Risk:** OOM errors on large tomograms (typical sizes: 1-10 GB)
- **Fix:** Use `mrcfile` memory-mapped mode; only read slices needed for output

### Excessive Polling
- **File:** `tomcat/static/js/media_updater.js`
- **Issue:** Up to 150 simultaneous polling requests per page load (one per tomogram)
- **Risk:** Server overwhelmed on large sessions; wasted bandwidth
- **Fix:** Batch status requests into a single `/media/media_status/batch` endpoint

---

## Fragile Areas

### Non-Atomic CSV Save
- **File:** `tomcat/models/session.py` — `Session.save()`
- **Issue:** CSV written directly to target path; partial write on crash corrupts the session file
- **Fix:** Write to `.tmp` file then `os.replace()` (atomic on same filesystem)

### Unbounded `os.walk` Depth
- **File:** `tomcat/utils/file_utils.py`
- **Issue:** Directory search walks entire subtree with no depth limit
- **Risk:** Hangs on deeply nested or circular symlink structures
- **Fix:** Add `maxdepth` parameter; follow symlinks cautiously

### Cross-Filesystem `os.rename` in Export
- **File:** `tomcat/routes/session_routes.py`
- **Issue:** Export uses `os.rename` which fails across filesystem boundaries
- **Fix:** Use `shutil.move` which falls back to copy+delete when needed

---

## Testing Gap

- **Zero test files exist** despite `pytest` being a declared dev dependency
- All logic — file parsing, media generation, session management — is untested
- No CI configuration
- See `TESTING.md` for recommended test structure

---

## Summary

| Category | Severity | Count |
|----------|----------|-------|
| Security | High | 3 |
| Race conditions | Medium | 2 |
| Tech debt | Low-Medium | 6 |
| Performance | Medium | 2 |
| Fragile areas | Medium | 3 |
| Testing | High | 1 (systemic) |
