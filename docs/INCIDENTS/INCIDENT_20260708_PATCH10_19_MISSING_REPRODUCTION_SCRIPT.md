# Incident — Patch 10.19 missing reproduction script before final delivery

## Symptom
Patch 10.19 passed the full pre-delivery pytest suite, then stopped during delivery assembly with:

```text
Missing required source_and_reproducibility: scripts/run_patch_10_15_system_scenario_validation.bat
```

## Interpretation
The failure happened before a delivery ZIP, delivery manifest, SHA256SUMS file or final handoff was written. This is the correct fail-closed behavior for the final packaging stage.

## Root cause
A required historical reproduction script was absent or empty in the local working tree, while the delivery package expected it as part of the source-and-reproducibility set.

## Fix
Patch 10.19.1 restores the required reproduction scripts and adds two guards:

1. A fast BAT preflight before the long test suite.
2. A Python delivery preflight that reports all missing or empty scripts together.

## Boundary
This fix only affects packaging reproducibility and diagnostics. It does not modify the model, Word report, curated evidence, release gate, mission simulations or certification claims.
