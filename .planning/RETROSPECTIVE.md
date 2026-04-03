# Project Retrospective: TomCat Bug Fix Initiative

## Milestone: v1.0 — Bug Fix v1

**Shipped:** 2026-04-03
**Phases:** 4 | **Plans:** 6

### What Was Built
- **Media Cache Fix**: `get_media_status()` now gates on disk existence first, caches "ready" in the status dict, and only queues background jobs when the file is genuinely absent.
- **Thumbnail Pagination**: Bootstrap pagination controls added inside #thumbnail-grid-view using the existing `pagination` context variable.
- **File Deduplication**: `extract_basename()` now strips `_preali` and `_preali.mrc` suffixes to prevent duplicate entries.
- **Thread Safety**: Granular locks in `MediaManager` and `ThreadManager` prevent race conditions and concurrent mutation errors.
- **Security Hardening**: Realpath-based Zip Slip and symlink traversal protection in archive import.

### What Worked
- **Test-Driven Development (TDD)**: Creating failing stress tests and security mocks before implementation proved essential for verifying the concurrency and Zip Slip fixes.
- **Wave-based Planning**: Grouping related fixes into phases and plans allowed for clear tracking and independent verification of each bug.
- **Surgical Edits**: Maintaining a narrow scope for each plan kept the code changes focused and easy to review.

### What Was Inefficient
- **Manual Verification Overhead**: Some UI changes required manual browser checks which were slower than automated tests.
- **Subagent Max Turns**: Several execution plans hit the subagent turn limit, necessitating manual spot-checks for completion.

### Patterns Established
- **Path Normalization**: Consistent use of `os.path.realpath` and `os.path.normpath` for security checks.
- **Lock-per-Resource**: Applying locks directly to the objects being protected (OrderedDicts, status dicts) rather than a global lock.

### Key Lessons
- Concurrency issues in Python's `threading` with `OrderedDict` are subtle but easily reproducible with high-contention stress tests.
- Symlink traversal is a common vector often overlooked in standard Zip Slip protection; both member names and link targets must be validated.

### Cost Observations
- Milestone completed in 3 active days.
- 59 files modified with significant documentation and test coverage.

---
## Cross-Milestone Trends

| Milestone | Duration | Plans | Tasks | Commits | Tests |
|-----------|----------|-------|-------|---------|-------|
| v1.0      | 3 days   | 6     | 7     | ~30     | 25+   |

---
*Last updated: 2026-04-03 after v1.0 milestone completion*
