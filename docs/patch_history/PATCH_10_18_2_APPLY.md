# Patch 10.18.2 — Final Word stale-artifact and version-test hotfix

## Scope
This hotfix repairs the Patch 10.18 Word build path after a stale partial DOCX and a hard-coded version assertion blocked pre-generation pytest.

## Changes
- Bumped canonical project version to `1.6.17`.
- Updated the release-gate version regression test to check canonical agreement dynamically.
- Updated Word regression tests so stale partial DOCX files are ignored unless the report manifest and QA JSON exist.
- Added a pre-pytest cleanup step in `scripts/run_patch_10_18_final_word_report.bat` for stale Word/QA/manifest files.
- Added an incident record under `docs/INCIDENTS`.

## Explicitly unchanged
- No delivery ZIP is generated.
- No final release build is enabled.
- No mission simulation or GIF/MP4 rendering is added.
