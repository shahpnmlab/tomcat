# Phase 4: Thread Safety & Security - Research

**Researched:** 2026-04-03
**Domain:** Python threading primitives, dict mutation safety, Zip Slip path traversal
**Confidence:** HIGH

---

## Summary

Phase 4 addresses two independent problem classes. The first is thread safety: `MediaManager` holds three plain Python dicts (`media_status`, `processing_queue` as `OrderedDict`, and `thumbnail_progress`) that are read and mutated from both the Flask request thread and background `ThreadPoolExecutor` worker threads with no synchronisation. `ThreadManager.submit_task()` contains a TOCTOU race — the `if task_key in self.active_futures` check and the subsequent `self.active_futures[task_key] = future` assignment are two separate operations; two threads can both pass the check before either writes, resulting in a duplicate job submission. The second problem class is a Zip Slip vulnerability in `import_archive`: the code calls `tar.extractall(path=temp_dir)` without verifying that each member's resolved path stays within `temp_dir`, so a crafted archive with a member named `../../../../etc/cron.d/backdoor` can write arbitrary files to the filesystem.

Both problems are well-understood with standard Python stdlib solutions. Thread safety is solved with `threading.Lock` (one lock per dict that is accessed from multiple threads). The Zip Slip fix follows the canonical pattern used in Python security advisories: resolve the member's final path with `os.path.realpath()` and assert it starts with the expected extraction root before any write operation, aborting the entire import on the first violation.

**Primary recommendation:** Add three per-dict `threading.Lock` instances to `MediaManager.__init__`, wrap every mutation and read-under-mutation in those locks; add one lock to `ThreadManager.__init__` and make `submit_task()` atomic; replace the bare `tar.extractall()` in `import_archive` with a member-by-member extraction loop that validates each path.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THREAD-01 | `MediaManager.processing_queue` mutations protected by `threading.Lock` | `threading.Lock` is stdlib; `with self._queue_lock:` pattern wraps all read-modify-write ops on `processing_queue` |
| THREAD-02 | `MediaManager.thumbnail_progress` mutations protected by `threading.Lock` | Same lock pattern; `_generate_thumbnail` writes four sub-keys; needs one lock covering the entire update block |
| THREAD-03 | `MediaManager.media_status` mutations protected by `threading.Lock` | Dict is written from worker threads (`_generate_lowmag_image`, etc.) and read from request thread; `with self._status_lock:` covers all sites |
| THREAD-04 | `ThreadManager.submit_task` check-and-add is atomic | Replace the two-step `if/assign` with a single `with self._submit_lock:` block covering both the check and the assignment |
| SEC-01 | `import_archive` validates each extracted member path against target directory | `os.path.realpath(os.path.join(dest, member.name))` + `startswith(real_dest + os.sep)` before extraction |
| SEC-02 | Malicious member path aborts import with error message, writes no files | Pre-scan loop before any extraction; `flash()` + `return redirect()` on violation |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `threading.Lock` | stdlib (all Python >=3.7) | Mutex for dict mutations | Zero-dependency; reentrant-safe when used as a context manager; GIL does not make dict ops atomic under concurrent iteration |
| `threading.RLock` | stdlib | Reentrant lock | Not needed here — no re-entrant call paths exist (see pitfall section); use plain `Lock` |
| `tarfile` (existing) | stdlib | Already imported in session_routes | No new import needed for the Zip Slip fix |
| `os.path.realpath` | stdlib | Resolve symlinks + `..` in paths | Canonical Zip Slip defence; handles symlinks unlike `os.path.abspath` |

### No New Dependencies

The project constraint is explicit: no new dependencies. All required tools are in Python's stdlib or already imported. This is confirmed by inspecting the existing imports in `session_routes.py` (`tarfile`, `os`, `tempfile`) and the constraint in `CLAUDE.md`.

---

## Architecture Patterns

### Pattern 1: Per-dict Lock in MediaManager

**What:** Add one `threading.Lock` for each shared mutable dict in `MediaManager.__init__`. Wrap every site that reads-then-writes (or iterates-then-modifies) with `with self._<name>_lock:`.

**When to use:** Any time a plain dict or `OrderedDict` is accessed from both a request thread and one or more background worker threads.

**Identified mutation sites (full inventory):**

`media_status` (lock: `_status_lock`):
- `_check_and_generate_lowmag` — line 227: `self.media_status[...] = "generating"`
- `_check_and_generate_tiltseries` — line 249: `self.media_status[...] = "generating"`
- `_check_and_generate_tomogram` — line 271: `self.media_status[...] = "generating"`
- `_generate_lowmag_image` — lines 355, 367, 373: `self.media_status[...] = "error"/"ready"`
- `_generate_tiltseries_animation` — lines 404, 421, 431: `self.media_status[...] = "error"/"ready"`
- `_generate_tomogram_animation` — lines 459, 476, 486: `self.media_status[...] = "error"/"ready"`
- `get_media_status` — lines 531, 540, 551: read + write on the request thread

`processing_queue` (lock: `_queue_lock`):
- `queue_tomogram_for_processing` — lines 90 (read), 100–104 (write): entire method body is a read-modify-write; must be locked
- `process_queue` — line 127 (`list(self.processing_queue.keys())`) and line 136 (`del self.processing_queue[tomo_name]`): iteration + deletion

`thumbnail_progress` (lock: `_progress_lock`):
- `batch_process_tomograms` — line 153: write to `['total']`
- `_generate_thumbnail` — lines 298, 303, 311–316, 320, 323: writes to multiple sub-keys in sequence; the entire success-path block must be atomic

**Example (media_status):**
```python
# Source: Python stdlib threading docs — standard lock pattern
import threading

# In __init__:
self._status_lock = threading.Lock()

# In _check_and_generate_lowmag:
with self._status_lock:
    self.media_status[f"lowmag_{tomo_name}"] = "generating"

# In get_media_status (read + conditional write):
with self._status_lock:
    status = self.media_status.get(status_key, "unknown")
    if status in ("generating", "error"):
        return {...}
    # Set before releasing so next poll sees "generating"
    self.media_status[status_key] = "generating"
```

### Pattern 2: Atomic Check-and-Submit in ThreadManager

**What:** Wrap the `if task_key in self.active_futures` check **and** the `self.active_futures[task_key] = future` assignment inside a single `with self._submit_lock:` block.

**Why the current code is racy:** Thread A reads `task_key not in active_futures` → True. Before Thread A writes, Thread B also reads → True. Both threads call `thread_pool.submit()` and both write the future. Result: two workers run the same job; the second future overwrites the first in `active_futures`, making the first future untracked (its exception is silently dropped).

**Example:**
```python
# Source: Python stdlib threading docs
import threading

# In __init__:
self._submit_lock = threading.Lock()

# In submit_task:
def submit_task(self, task_key, func, *args, **kwargs):
    with self._submit_lock:
        if task_key in self.active_futures and not self.active_futures[task_key].done():
            return False
        future = self.thread_pool.submit(func, *args, **kwargs)
        self.active_futures[task_key] = future
    return True
```

Note: `thread_pool.submit()` is called inside the lock. This is acceptable because `ThreadPoolExecutor.submit()` acquires its own internal lock briefly and returns immediately — the submitted function does not run under this lock. The call is non-blocking in terms of actual work.

### Pattern 3: Zip Slip Defence in import_archive

**What:** Before calling any extraction, iterate all archive members and verify each resolved output path stays within the target directory.

**Standard pattern (Python security docs, OWASP):**
```python
# Source: Python tarfile security documentation / OWASP Zip Slip
import os

def _safe_extract(tar, dest):
    """
    Raise ValueError if any member path resolves outside dest.
    dest must be an absolute, realpath-resolved directory.
    """
    real_dest = os.path.realpath(dest)
    for member in tar.getmembers():
        member_path = os.path.realpath(os.path.join(real_dest, member.name))
        if not member_path.startswith(real_dest + os.sep):
            raise ValueError(f"Attempted path traversal in archive: {member.name}")

# Usage in import_archive:
with tarfile.open(archive_path, "r:gz") as tar:
    try:
        _safe_extract(tar, temp_dir)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for('session.upload_file'))
    tar.extractall(path=temp_dir)
```

**Key details:**
- `os.path.realpath` resolves both `..` sequences and symlinks (unlike `os.path.abspath` which only resolves `..`).
- The `real_dest + os.sep` suffix check (e.g. `/tmp/xyz123/`) prevents a path like `/tmp/xyz123evil` from passing the check.
- The validation loop runs **before** `extractall`, so either all members are safe or nothing is extracted (SEC-02: no partial extraction).
- The existing logic that copies files out of `temp_dir` into the app folders is unchanged — this fix only gates what gets extracted into `temp_dir`.

### Anti-Patterns to Avoid

- **Using `RLock` as a precaution:** There are no reentrant call paths in this codebase (no locked method calls another locked method on the same instance). Using `RLock` adds unnecessary complexity and slightly higher overhead. Use `threading.Lock`.
- **One global lock for all three dicts:** Would work for correctness but creates unnecessary contention — `thumbnail_progress` updates (from background workers) would block `media_status` reads (from request threads). Keep locks per-dict.
- **Locking inside background worker methods only:** The request thread also reads and writes `media_status` in `get_media_status()`. All sites for a given dict must use the same lock.
- **Calling `thread_pool.submit()` before checking the existing future:** The current pre-lock code path is safe in the single-thread case but not under concurrent calls. The fix must move the submit call inside the lock.
- **Validating member paths with `os.path.abspath` instead of `os.path.realpath`:** `abspath` does not resolve symlinks; a crafted archive can include a symlink pointing outside `temp_dir`, and subsequent member extractions following that symlink would escape the directory.
- **Aborting only on the first bad member while continuing extraction of others:** SEC-02 requires the import to abort with no files written outside the target directory. Validate all members before extracting any.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe dict | Custom `ConcurrentDict` wrapper class | `threading.Lock` + plain dict | stdlib lock is lower overhead, fully tested, and the codebase already uses plain dicts everywhere |
| Path traversal validation | Regex on member name | `os.path.realpath` + `startswith` | Regex cannot account for symlinks or platform path variations; realpath is the canonical approach |
| Atomic flag for TOCTOU | Boolean attribute + two-step check | Lock + check-and-set inside `with` | Boolean attributes are not atomic under CPython's threading model when the sequence is read-then-write |

---

## Common Pitfalls

### Pitfall 1: Deadlock from Nested Lock Acquisition

**What goes wrong:** If a method that holds `_queue_lock` calls another method that also tries to acquire `_queue_lock`, the thread deadlocks forever.

**Why it happens:** `queue_tomogram_for_processing` calls `process_queue`. If both methods hold the same lock, the inner call blocks waiting for the lock the outer call is holding.

**How to avoid:** Map all call chains before adding locks. In this codebase:
- `queue_tomogram_for_processing` calls `self.process_queue()` via `_processing_queue_active` guard
- `batch_process_tomograms` calls `queue_tomogram_for_processing` in a loop
- Neither `process_queue` nor `_generate_media_for_tomogram_internal` calls back into locked methods

**Verified call chain (no re-entrant paths found):**
- `queue_tomogram_for_processing` → `process_queue` → `_generate_media_for_tomogram_internal` → `_check_and_generate_*` → `thread_manager.submit_task` (no lock held at this point)
- The `_generate_*` worker methods run in background threads and do not call `queue_tomogram_for_processing`

**Conclusion:** Plain `Lock` is safe. Lock `processing_queue` for the duration of `queue_tomogram_for_processing` (including the call to `process_queue` only if `process_queue` reads the same dict) OR restructure so `process_queue` captures `list(keys)` before any other thread can modify them. The safest approach for the queue lock is to take a snapshot of keys with the lock held, then release before submitting tasks:

```python
with self._queue_lock:
    queue_keys = list(self.processing_queue.keys())
    # calculate max_to_start ...
# Lock released; now submit tasks and delete from queue under lock per deletion
for tomo_name in queue_keys[:max_to_start]:
    self._generate_media_for_tomogram_internal(tomo_name)
    with self._queue_lock:
        self.processing_queue.pop(tomo_name, None)
```

### Pitfall 2: `thumbnail_progress` Multi-Key Update Is Not Atomic Without a Lock

**What goes wrong:** `_generate_thumbnail` updates `status`, `message`, `completed_names`, `thumbnail_paths`, and `downloaded` in five separate statements. A concurrent read of `thumbnail_progress` from the request thread (via `get_thumbnail_progress`) can observe a half-updated state.

**How to avoid:** Wrap the entire success-path block (all five mutations) in a single `with self._progress_lock:` block.

### Pitfall 3: os.sep Suffix Required in Zip Slip Check

**What goes wrong:** Checking `member_path.startswith(real_dest)` without the trailing separator allows a path like `/tmp/abc123evil/passwd` to pass when `real_dest` is `/tmp/abc123`.

**How to avoid:** Always use `real_dest + os.sep` as the prefix: `member_path.startswith(real_dest + os.sep)`. Also allow the directory itself (`member_path == real_dest`) for directory-type members.

### Pitfall 4: tarfile filter= Parameter (Python 3.12+)

**What goes wrong:** Python 3.12 emits a `DeprecationWarning` when `tar.extractall()` is called without a `filter=` parameter, and future Python versions may change the default filter.

**How to avoid:** After the path-traversal pre-scan, pass `filter='data'` if running Python >=3.12, or simply rely on the pre-scan (which is the approach this codebase takes since it targets Python >=3.7 where `filter=` is not available in older versions). The pre-scan approach is compatible across all supported versions.

**Confidence:** MEDIUM — This is a forward-compatibility note, not a current blocker for Python 3.10 as recommended.

### Pitfall 5: Zip Slip via Symlink in Archive

**What goes wrong:** An archive member can be a symlink pointing outside `temp_dir`. Subsequent members extracted through that symlink land outside the sandbox even if their names look safe.

**How to avoid:** `os.path.realpath` resolves symlinks in the _current filesystem state_ but cannot predict where a symlink inside the archive will point after extraction. The safe response is to reject any archive member that is a symlink (`member.issym()` or `member.islnk()`) OR to use the validation approach described above which fully resolves after-extraction paths. For this app's use case (exporting/importing its own archives), symlinks are never present in valid archives, so rejecting symlinks outright is both safe and simple.

---

## Code Examples

### threading.Lock for dict protection (stdlib pattern)

```python
# Source: Python 3.10 threading documentation
import threading

class MediaManager:
    def __init__(self, config, thread_manager):
        # ... existing code ...
        self.media_status = {}
        self.processing_queue = OrderedDict()
        self.thumbnail_progress = { ... }

        # One lock per shared mutable dict
        self._status_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._progress_lock = threading.Lock()
```

### Atomic submit_task (stdlib pattern)

```python
# Source: Python 3.10 threading documentation
def submit_task(self, task_key, func, *args, **kwargs):
    with self._submit_lock:
        if task_key in self.active_futures and not self.active_futures[task_key].done():
            logger.debug(f"Task {task_key} is already running")
            return False
        future = self.thread_pool.submit(func, *args, **kwargs)
        self.active_futures[task_key] = future
    logger.debug(f"Submitted task: {task_key}")
    return True
```

### Zip Slip safe extraction (OWASP / Python tarfile docs pattern)

```python
# Source: OWASP Path Traversal cheat sheet; Python tarfile security notes
import os, tarfile

def _safe_extract(tar, dest):
    """Validate all members resolve within dest. Raises ValueError on violation."""
    real_dest = os.path.realpath(dest)
    for member in tar.getmembers():
        member_resolved = os.path.realpath(os.path.join(real_dest, member.name))
        if not (member_resolved == real_dest or
                member_resolved.startswith(real_dest + os.sep)):
            raise ValueError(
                f"Path traversal detected in archive member: {member.name!r}"
            )

# In import_archive, replace bare tar.extractall():
with tarfile.open(archive_path, "r:gz") as tar:
    try:
        _safe_extract(tar, temp_dir)
    except ValueError as e:
        flash(f"Archive rejected: {e}")
        return redirect(url_for('session.upload_file'))
    tar.extractall(path=temp_dir)
```

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all fixes use Python stdlib only; no new packages or services required).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=6.0.0 |
| Config file | none (uses pyproject.toml project root discovery) |
| Quick run command | `python -m pytest tests/ -q` |
| Full suite command | `python -m pytest tests/ -v` |

**Baseline:** 18 tests passing across `test_get_media_status.py` (13 tests) and `test_extract_basename_preali.py` (7 tests).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| THREAD-01 | `processing_queue` mutations under concurrent access do not raise `RuntimeError` | unit (concurrent) | `pytest tests/test_thread_safety.py::TestProcessingQueueLock -x` | Wave 0 |
| THREAD-02 | `thumbnail_progress` multi-key update is atomic (no torn reads) | unit (concurrent) | `pytest tests/test_thread_safety.py::TestThumbnailProgressLock -x` | Wave 0 |
| THREAD-03 | `media_status` concurrent read/write produces no torn state | unit (concurrent) | `pytest tests/test_thread_safety.py::TestMediaStatusLock -x` | Wave 0 |
| THREAD-04 | `submit_task` called from two threads simultaneously submits exactly one job | unit (concurrent) | `pytest tests/test_thread_safety.py::TestSubmitTaskAtomicity -x` | Wave 0 |
| SEC-01 | Valid archive member paths pass validation | unit | `pytest tests/test_import_archive_security.py::TestZipSlipValidation::test_valid_paths_pass -x` | Wave 0 |
| SEC-02 | Archive with traversal member path aborts import, no files written | unit | `pytest tests/test_import_archive_security.py::TestZipSlipValidation::test_traversal_aborts_no_write -x` | Wave 0 |

### Testing Approach for Concurrency

Python's GIL does not make dict operations atomic when multiple Python statements are involved. The standard way to exercise TOCTOU races in unit tests without relying on timing is to use `threading.Barrier` to synchronize threads at the race point:

```python
# Example structure for THREAD-04 test
import threading

def test_submit_task_no_duplicate(thread_manager_instance):
    barrier = threading.Barrier(2)
    results = []

    def try_submit():
        barrier.wait()  # Both threads reach race point simultaneously
        result = thread_manager_instance.submit_task("key", lambda: None)
        results.append(result)

    t1 = threading.Thread(target=try_submit)
    t2 = threading.Thread(target=try_submit)
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Exactly one submit must succeed
    assert results.count(True) == 1
    assert results.count(False) == 1
```

For dict mutation tests (THREAD-01 through THREAD-03), a simpler approach is to verify the lock exists and is used (structural test) combined with a stress test that fires many threads and checks for no exceptions:

```python
def test_media_status_no_runtime_error_under_concurrent_access(manager):
    """RuntimeError: dict changed size during iteration must never occur."""
    errors = []
    def reader():
        for _ in range(100):
            try:
                _ = manager.media_status.get("some_key", "unknown")
            except Exception as e:
                errors.append(e)
    def writer():
        for i in range(100):
            try:
                manager.media_status[f"key_{i}"] = "generating"
            except Exception as e:
                errors.append(e)
    threads = [threading.Thread(target=reader) for _ in range(5)] + \
              [threading.Thread(target=writer) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []
```

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green (18 existing + new tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_thread_safety.py` — covers THREAD-01, THREAD-02, THREAD-03, THREAD-04
- [ ] `tests/test_import_archive_security.py` — covers SEC-01, SEC-02

*(No new framework install needed — pytest already in dev dependencies.)*

---

## Open Questions

1. **Lock granularity for `process_queue` and `queue_tomogram_for_processing`**
   - What we know: Both methods read and write `processing_queue`; `queue_tomogram_for_processing` conditionally calls `process_queue`.
   - What's unclear: Whether locking the full `queue_tomogram_for_processing` body (including the `process_queue` call) introduces meaningful latency if many tomograms are queued at once.
   - Recommendation: Lock only the dict read/write operations, not the `submit_task` calls. Capture a snapshot of keys under the lock, then release before submitting. See Pattern 1 example above.

2. **Python 3.12 tarfile filter deprecation warning**
   - What we know: `filter=` parameter was added in Python 3.12; the project targets Python >=3.7 with 3.10 as recommended.
   - What's unclear: Whether CI will run under 3.12 and produce warnings that fail tests.
   - Recommendation: Suppress or ignore for this phase; the pre-scan approach is the substantive fix. Add a comment noting the forward-compatibility concern.

---

## Sources

### Primary (HIGH confidence)
- Python 3.10 stdlib `threading` module documentation — `Lock`, `RLock`, context manager usage
- Python 3.10 stdlib `tarfile` module documentation — `getmembers()`, `extractall()`, member attributes
- Python 3.10 stdlib `os.path` documentation — `realpath()`, `abspath()` distinction

### Secondary (MEDIUM confidence)
- OWASP Path Traversal / Zip Slip cheat sheet — canonical `realpath + startswith` pattern
- CPython source for `dict` — confirms dict iteration raises `RuntimeError` on size change even under GIL (iteration state is separate from mutation)

### Tertiary (LOW confidence)
- None required — all findings are verifiable directly in the source files and Python stdlib docs.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, no new dependencies
- Architecture: HIGH — lock patterns and Zip Slip fix are directly verified against the actual source code
- Pitfalls: HIGH — deadlock risk verified by manual call-chain analysis of the actual code; lock pitfalls are well-known stdlib properties

**Research date:** 2026-04-03
**Valid until:** Stable indefinitely — stdlib threading primitives and path traversal defences do not change between minor Python versions
