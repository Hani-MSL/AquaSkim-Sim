# Incident — Patch 10.18.1 stale Word artifact and hard-coded version test

## Summary
Patch 10.18.1 introduced a real eighth Word table, but the pre-generation full pytest suite still evaluated a stale partial DOCX left by the previous failed run. A separate release-gate test also kept a hard-coded version string instead of checking the canonical version contract dynamically.

## Root causes
- `tests/test_phase10_17_release_gate.py` asserted the exact version `1.6.15` instead of comparing the loaded reference configuration to `aquaskim.__version__`.
- `tests/test_phase10_18_final_word.py` ran against an existing DOCX even when the corresponding manifest and QA JSON were absent, so a stale failed report could block the rebuild before the generator had a chance to replace it.
- The 10.18 script did not clean partial Word outputs before the pre-build full pytest gate.

## Corrective action
- Make the canonical version test compare dynamic canonical sources instead of a fixed patch number.
- Skip structural Word tests unless the report, build manifest and QA JSON all exist together.
- Add an explicit stale-report cleanup step before pre-generation pytest, with a clear lock warning if Microsoft Word or another viewer is holding the report open.
- Keep ZIP delivery and final release scripts disabled.

## Status
Fixed in Patch 10.18.2.
