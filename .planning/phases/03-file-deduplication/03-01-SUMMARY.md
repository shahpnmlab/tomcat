---
phase: 03-file-deduplication
plan: 01
subsystem: file-utils
tags: [file_utils, extract_basename, deduplication, preali, mrc]

# Dependency graph
requires: []
provides:
  - "extract_basename() strips _preali and _preali.mrc suffixes to produce canonical tomo name"
  - "tomo001_preali.mrc and tomo001_rec.mrc resolve to same deduplication key 'tomo001'"
  - "search_tomograms() naturally deduplicates via extract_basename — no code change needed there"
affects: [04-thread-safety-security]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Suffix-list-first then regex-second: extract_basename tries suffix stripping before regex patterns; more specific suffixes must precede generic ones"

key-files:
  created:
    - tests/test_extract_basename_preali.py
  modified:
    - tomcat/utils/file_utils.py

key-decisions:
  - "Added _preali.mrc and _preali to tiltseries_suffixes before _ali entries so suffix loop matches most-specific form first"
  - "Added r'_preali' regex pattern before r'_rec' as second-pass safety net (handles case where .mrc stripped first, leaving tomo001_preali)"
  - "No changes to FileLocator.EXTENSIONS — _preali.mrc already listed before _ali.mrc (priority already correct)"
  - "No changes to Session.load() or search_tomograms() — backward compat preserved by pd.read_csv with no tomo_name transformation"

patterns-established:
  - "Suffix list ordering matters: more specific entries (_preali.mrc) must precede generic ones (.mrc) to avoid partial stripping"
  - "Regex patterns in extract_basename act as a fallback for names where only extension was stripped"

requirements-completed: [DEDUP-01, DEDUP-02, DEDUP-03]

# Metrics
duration: 5min
completed: 2026-04-03
---

# Phase 03 Plan 01: File Deduplication Summary

**`extract_basename()` now strips `_preali` and `_preali.mrc` suffixes, so directories with both `tomo001_rec.mrc` and `tomo001_preali.mrc` produce a single catalogue entry `tomo001` instead of two.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-03T00:13:11Z
- **Completed:** 2026-04-03T00:18:00Z
- **Tasks:** 2 (Task 1: TDD fix, Task 2: verification-only)
- **Files modified:** 2

## Accomplishments

- Fixed BUG-03: `_preali.mrc` files no longer create duplicate catalogue entries
- `extract_basename('tomo001_preali.mrc')` now returns `'tomo001'` (was `'tomo001_preali'`)
- `search_tomograms()` deduplication via `results_dict` key works automatically — no code change needed
- Backward compatibility preserved: existing session CSV rows with `tomo001_preali` as `tomo_name` load without modification via `pd.read_csv()`
- TDD: wrote failing tests first, then implemented minimal fix, all 7 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1 RED — failing tests** - `6ad819a` (test)
2. **Task 1 GREEN — fix implementation** - `c048814` (fix)

_Task 2 was verification-only; no code changes, no separate commit needed._

## Files Created/Modified

- `tomcat/utils/file_utils.py` - Added `_preali.mrc`, `_preali` to `tiltseries_suffixes`; added `r'_preali'` to regex `patterns` list in `extract_basename()`
- `tests/test_extract_basename_preali.py` - TDD tests covering `_preali.mrc`, `_preali`, and all pre-existing cases as regression tests

## Decisions Made

- Added `_preali.mrc` and `_preali` to `tiltseries_suffixes` before `_ali` entries — preserving specificity-first ordering so the longer suffix is tried before the generic `.mrc` extension
- Added `r'_preali'` regex pattern before `r'_rec'` as a second-pass fallback for filenames where `.mrc` was stripped first (leaving `tomo001_preali`)
- Did not modify `FileLocator.EXTENSIONS` — `_preali.mrc` was already listed before `_ali.mrc` (file-finding priority was already correct)
- Did not modify `Session.load()` or `search_tomograms()` — existing rows in session CSVs keep their original `tomo_name` values unchanged

## Deviations from Plan

None — plan executed exactly as written. Both suffix-list change and regex-pattern change were specified precisely in the plan's `<action>` section.

## Issues Encountered

None. The fix was straightforward: two line edits matching the plan's specified changes, verified by the plan's automated assertions.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- File deduplication fix complete; researchers with `_preali.mrc` files will see correct single-entry catalogues
- Existing sessions with `_preali` entries in `tomo_name` continue to load without error
- Phase 04 (Thread Safety & Security) can proceed independently

---
*Phase: 03-file-deduplication*
*Completed: 2026-04-03*
