# Incident — Missing Phase 02 Generator and CLI Entry Point

## Observed condition

The project retained Phase 02 output artifacts and tests but the source file
`src/aquaskim/phase02.py` was absent. `src/aquaskim/cli.py` and the documented
`scripts/bootstrap_and_build.bat` entry point were also absent. As a result,
full pytest stopped during collection even though selected test subsets passed.

## Root cause

Historical patches preserved generated outputs and partial test evidence while
source recovery was incomplete. The remaining reference path also imported a
physical-plant helper from the historical Phase 08 quota-based module.

## Correction in Patch 10.10

- Reconstruct Phase 02 from shared configuration, geometry and mass-property
  source modules.
- Restore a thin CLI and a safe non-release bootstrap script.
- Move shared physical-plant assembly into `mission_plant.py`.
- Add a Legacy Registry and explicit reference-path import audit.
- Block report, ZIP and final release scripts until a later Release Gate.

## Verification

Patch 10.10 requires YAML parse, package import audit, `compileall` and full
pytest before it can be considered PASS. No heavy simulation or media render is
part of this correction.
