# Summary: Phase 4 Plan 01 (Thread Safety & Security Scaffolds)

## Objectives
Create test scaffolds for thread safety and security features before implementation (Nyquist Rule).
These tests should initially fail, proving that the concurrency and security issues exist.

## Completed Tasks
- [x] **Task 1: Create thread safety stress tests**
  - Created `tests/test_thread_safety.py`
  - Verified that `test_concurrent_processing_queue_mutations` fails with `KeyError` (OrderedDict mutation race).
  - Verified that `test_simultaneous_submit_task` fails (multiple threads successfully submit the same task key).
  - Committed as `f3df939`.
- [x] **Task 2: Create archive security tests**
  - Created `tests/test_import_archive_security.py`
  - Verified that `test_traversal_aborts_no_write` fails (archive with `../` not rejected).
  - Verified that `test_symlink_traversal_rejection` fails (archive with absolute symlink not rejected).
  - Verified that `test_valid_archive_accepted` passes (no regressions for valid archives).
  - Committed as `a975282`.

## Verification Results
- `python -m pytest tests/test_thread_safety.py` -> 2 FAILED, 2 PASSED (as expected for TDD)
- `python -m pytest tests/test_import_archive_security.py` -> 2 FAILED, 1 PASSED (as expected for TDD)

## Decisions & Observations
- The `OrderedDict` in `MediaManager` is definitely not thread-safe for concurrent mutations during iteration.
- `ThreadManager.submit_task` has a clear race condition where multiple threads can pass the "is already running" check simultaneously.
- The `import_archive` route is vulnerable to Zip Slip and symlink traversal as it doesn't validate tar members before extraction.
- Fixed a minor blueprint registration issue in the test fixture to allow multiple app creations for testing.

## Next Steps
- Implement locks in `MediaManager` and `ThreadManager` (Phase 4 Plan 02).
- Implement archive member validation in `import_archive` (Phase 4 Plan 03).
