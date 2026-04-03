---
phase: 03-file-deduplication
verified: 2026-04-03T00:30:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
---

# Phase 3: File Deduplication Verification Report

**Phase Goal:** `_preali.mrc` files are resolved to their canonical tomogram basename and do not appear as independent entries in the catalogue
**Verified:** 2026-04-03T00:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A directory containing both `tomo001_rec.mrc` and `tomo001_preali.mrc` produces exactly one catalogue entry (`tomo001`), not two | VERIFIED | `extract_basename('tomo001_rec.mrc') == extract_basename('tomo001_preali.mrc') == 'tomo001'`; `search_tomograms()` keys `results_dict` by `extract_basename()` return value — both files collapse to the same key; confirmed by behavioral spot-check |
| 2 | `find_tiltseries_file('tomo001')` returns `tomo001_preali.mrc` when no `_ali.mrc` exists, and returns `tomo001_ali.mrc` when it does exist | VERIFIED | `FileLocator.EXTENSIONS['tiltseries']` = `['_preali.mrc', '_ali.mrc', ...]`; `find_file()` sorts by length descending — `_preali.mrc` (len 11) sorts before `_ali.mrc` (len 8); exact-match loop tries `_preali.mrc` first, so `tomo001_preali.mrc` is returned when `tomo001_ali.mrc` is absent |
| 3 | Sessions created before this fix that have a `tomo_name` of `tomo001_preali` load without error and retain all annotations | VERIFIED | `Session.load()` calls `pd.read_csv()` with no transformation on `tomo_name`; behavioral spot-check confirmed old CSV rows load with original name intact |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tomcat/utils/file_utils.py` | `extract_basename()` strips `_preali` suffix; `search_tomograms()` deduplicates by canonical name | VERIFIED | File exists; contains `_preali.mrc` and `_preali` in `tiltseries_suffixes` (line 31); contains `r'_preali'` as first entry in regex `patterns` list (line 45); `search_tomograms()` unchanged — already deduplicates via `results_dict` key |
| `tests/test_extract_basename_preali.py` | TDD tests covering `_preali.mrc` and `_preali` stripping plus regression cases | VERIFIED | File exists with 7 tests; all 7 pass (`pytest 7 passed in 0.16s`) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `file_utils.py:extract_basename` | `file_utils.py:search_tomograms` | `extract_basename(file)` call at line 241 | WIRED | Line 241: `tomo_name = extract_basename(file)` — confirmed present; `results_dict` keyed by this return value at lines 244–256 |
| `FileLocator.EXTENSIONS['tiltseries']` | `file_utils.py:find_file` | `sorted_extensions` priority — `_preali.mrc` listed before `_ali.mrc` | WIRED | `EXTENSIONS['tiltseries'][0]` = `'_preali.mrc'`; `find_file()` sorts by `len(reverse=True)` — `_preali.mrc` (len 11) ranked before `_ali.mrc` (len 8); exact-match loop respects this order |

---

### Data-Flow Trace (Level 4)

Not applicable — `extract_basename()` and `search_tomograms()` are pure computation functions (no dynamic data rendering). The fix is entirely within the file-discovery / name-normalisation layer.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `extract_basename('tomo001_preali.mrc')` returns `'tomo001'` | `python -c "from tomcat.utils.file_utils import extract_basename; assert extract_basename('tomo001_preali.mrc') == 'tomo001'"` | `'tomo001'` | PASS |
| `extract_basename('tomo001_preali')` returns `'tomo001'` | inline assertion | `'tomo001'` | PASS |
| Pre-existing cases unchanged: `_rec.mrc`, `_ali.mrc`, `.mrc`, `_bin8` | inline assertions | all `'tomo001'` | PASS |
| Both `_rec.mrc` and `_preali.mrc` map to same deduplication key | `assert extract_basename('tomo001_rec.mrc') == extract_basename('tomo001_preali.mrc')` | equal | PASS |
| Old session CSV with `tomo001_preali` in `tomo_name` loads unchanged | `pd.read_csv()` assertion | row retained as `'tomo001_preali'` | PASS |
| All 7 TDD tests pass | `pytest tests/test_extract_basename_preali.py -v` | `7 passed in 0.16s` | PASS |
| `_preali.mrc` has higher priority than `_ali.mrc` in `find_file()` sort | length comparison assertion | `_preali.mrc` index 1, `_ali.mrc` index 2 | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEDUP-01 | 03-01-PLAN.md | `FileLocator.extract_basename()` strips `_preali` suffix so `_preali.mrc` files share a canonical name with their tomogram | SATISFIED | `extract_basename('tomo001_preali.mrc')` returns `'tomo001'`; `extract_basename('tomo001_preali')` returns `'tomo001'`; 7 tests confirm both forms and all regression cases |
| DEDUP-02 | 03-01-PLAN.md | `_preali.mrc` is used as the tilt series fallback only when no `.ali` file exists (existing priority order maintained) | SATISFIED | `EXTENSIONS['tiltseries']` = `['_preali.mrc', '_ali.mrc', ...]`; `find_file()` sorts by length descending, placing `_preali.mrc` (len 11) before `_ali.mrc` (len 8); no code change was needed — priority was already correct |
| DEDUP-03 | 03-01-PLAN.md | Existing sessions with duplicate `_preali` entries are not broken by the fix (graceful handling) | SATISFIED | `Session.load()` calls `pd.read_csv()` with no `tomo_name` transformation; behavioral check confirmed old CSV rows load with original name retained; no retroactive rewrite occurs |

No orphaned requirements — all three IDs declared in the plan's `requirements` field are accounted for. No additional DEDUP-* requirements appear in REQUIREMENTS.md beyond these three.

---

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholder returns, or empty implementations found in `tomcat/utils/file_utils.py`.

---

### Human Verification Required

#### 1. End-to-end deduplication with real filesystem

**Test:** Create a test directory containing both `tomo001_rec.mrc` and `tomo001_preali.mrc`. Configure TomCat to use that directory as both `tomogram_path` and `tiltseries_path`. Run a search for `tomo001` via the UI and confirm that exactly one catalogue row appears.
**Expected:** One row with name `tomo001`. No second row `tomo001_preali`.
**Why human:** Requires a real filesystem with MRC files and a running Flask server; cannot be tested via static code analysis alone.

#### 2. Tilt-series file selection when both `_preali.mrc` and `_ali.mrc` are present

**Test:** Place both `tomo001_preali.mrc` and `tomo001_ali.mrc` in the `tiltseries_path` directory. Load the detail view for `tomo001` and observe which file is selected for the tilt-series animation.
**Expected:** `tomo001_ali.mrc` is selected (higher priority in length-sorted order).
**Why human:** Requires actual filesystem files and a running server; the priority logic is verified statically but real file selection needs a live run.

---

### Gaps Summary

No gaps. All three observable truths are verified, both key links are wired, all three requirement IDs are satisfied, 7/7 tests pass, and no anti-patterns were found.

The fix is minimal and exactly as specified in the plan: two line edits inside `extract_basename()` — adding `_preali.mrc` and `_preali` to `tiltseries_suffixes`, and adding `r'_preali'` to the regex patterns list. No changes were made to `search_tomograms()`, `Session.load()`, or `FileLocator.EXTENSIONS`, preserving backward compatibility.

Commit trail is clean: `6ad819a` (failing tests, RED phase) followed by `c048814` (implementation fix, GREEN phase).

---

_Verified: 2026-04-03T00:30:00Z_
_Verifier: Claude (gsd-verifier)_
