# Patch 10.9.1 — Registry and Test Hotfix

## Incident

Patch 10.9 generated the reference outputs, then failed two post-run tests:

1. `parameter_registry.yaml` had five newly appended registry entries indented as
   children of `CTRL-HEAD-001`, rather than as entries of the `parameters` list.
2. The non-interactive-build contract test still expected the superseded
   `run_patch_10_7.bat` string, despite the current reference entry point being
   `run_patch_10_9.bat`.

## Corrective action

- Restored valid YAML list indentation.
- Updated the contract test to verify the current reference-build entry point.
- Added a lightweight hotfix runner that performs no numerical rerun and no
  media rendering.

## Scientific impact

None. This patch changes neither the model nor the generated mission evidence.
It only completes the integrity gate that Patch 10.9 should have completed.
