# Incident — Patch 10.13 current-compensation API mismatch

## Observed failure

The Patch 10.13 full test gate stopped before media production. The control-robustness module passed the keyword argument `activation_speed_mps` to `current_aware_course_command`, but the shared guidance function did not expose that parameter. In addition, the reference setting was not represented in `QualityMissionSettings`.

## Impact

No Patch 10.13 reports, QA manifests, GIFs, MP4s, contact sheets, evidence snapshots, Word report, delivery ZIP, or release artifact were generated. Prior evidence remains unchanged.

## Corrective action

Patch 10.13.1 adds the versioned activation threshold to the shared mission settings, implements the matching guidance API, wires the setting through the reference mission controller, and adds regression tests for zero-speed activation semantics.

## Acceptance

The repaired source must pass YAML parsing, import audit, syntax compilation, the full pytest suite, and then regenerate all required 10.11, 10.12 and 10.13 evidence from current source.
