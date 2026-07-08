# Patch 10.9 — Mission Fidelity Correction and Visual Evidence Audit

## Scope

This patch responds to visual QA findings. It is a correction of the dynamics
and evidence pipeline, not a cosmetic redraw.

## Changed behaviour

- Replaces moving corner-cutting with conservative stop-turn-go waypoint tracking.
- Adds braking before a pivot and pivot hysteresis.
- Limits forward tracking thrust and records the control regime in every sample.
- Adds a low-speed resistance continuation for legitimate near-zero-speed turns.
- Prevents repeated reactivation of a target that has already been deferred.
- Adds a formal forward-tracking quality gate.
- Replaces first-frame-only contact sheets with 5-frame temporal audit sheets.

## Fixed non-interactive design policy

The run remains entirely non-interactive. The reference values, rationale,
valid ranges and verification artifacts are stored in:

- `config/reference_design.yaml`
- `config/parameter_registry.yaml`

## Current status

The final Word report and release ZIP remain intentionally disabled. This patch
must pass on the target Windows environment before release-quality reporting.
