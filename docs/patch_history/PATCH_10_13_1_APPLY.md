# Patch 10.13.1 — Apply instructions

## Purpose

This hotfix repairs the shared current-compensation API and wires the documented reference-policy activation threshold into the effective mission settings. It is a correction for the Patch 10.13 gate failure; it does not relax acceptance criteria or enable Word, delivery ZIP, or release build generation.

## Files changed

- `src/aquaskim/mission_quality.py`
- `src/aquaskim/phase10_6.py`
- `src/aquaskim/__init__.py`
- `config/reference_design.yaml`
- `tests/test_phase10_13_current_compensation_api.py`
- `scripts/run_patch_10_13_1_control_hotfix.bat`
- `docs/INCIDENTS/INCIDENT_20260707_PATCH10_13_CONTROL_API_MISMATCH.md`
- `patch_notes/PATCH_10_13_1_CONTROL_API_HOTFIX.md`
- `pyproject.toml`

## Execution

Run only:

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_13_1_control_hotfix.bat
```

The script performs YAML parsing, import audit, compileall, full pytest, then renews 10.11 / 10.12 evidence and rebuilds 10.13 media. It leaves Word, delivery ZIP and release build disabled.
