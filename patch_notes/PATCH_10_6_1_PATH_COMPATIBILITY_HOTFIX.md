# Patch 10.6.1 — Path Compatibility Hotfix

## Scope
This patch fixes the missing source module `aquaskim.paths`. It does not change
the physical model, mission assumptions, reference design or scientific results.

## Changed files
- `src/aquaskim/paths.py`
- `src/aquaskim/config.py` — reference build ignores local profiles by default
- `scripts/check_project_contract.bat`
- `scripts/run_patch_10_6.bat`
- `scripts/run_patch_10_6_hotfix.bat`
- `tests/test_paths_contract.py`
- incident documentation

## New quality gate
The run now checks that `config/base_parameters.yaml` exists before attempting
the mission. If it does not exist, the script stops with one explicit message
instead of emitting an import traceback midway through execution.
