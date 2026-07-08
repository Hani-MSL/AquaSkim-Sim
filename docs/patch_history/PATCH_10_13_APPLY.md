# Patch 10.13 — Current-aware Control Robustness and Reference-policy Recovery

## Scope

This patch adds a deterministic current-aware path-holding study and bounded
heading-gain sensitivity analysis. It also repairs the fixed-reference loader
so `reference_mission` policy is merged into the effective non-interactive
configuration instead of silently falling back to generic defaults.

Because the corrected policy is an input to reference execution, the Patch
runner renews existing Reference Mission Fidelity (10.11) and Current-aware
Operating Envelope (10.12) artifacts before generating the new 10.13 evidence.

## Explicit exclusions

- No Word report.
- No delivery ZIP.
- No release build.
- No user-profile input.
- No use of Legacy quota-based autonomy in the reference path.

## Files added or changed

- Current-aware line-hold controller, bounded gain sensitivity, media renderer,
  prepare/finalize workflow and four new GIF/MP4 replay outputs.
- Versioned control protocol and visualisation protocol.
- Reference-policy loader recovery and regression tests.
- Recorded runner with gate order:

```text
YAML parse → import audit → compileall → full pytest
→ renew 10.11 reference evidence → renew 10.12 envelope evidence
→ prepare 10.13 static evidence → four isolated GIF/MP4 renders
→ media QA → SHA-256 evidence snapshot → handoff
```

The isolated renders are deliberate: each high-resolution GIF is produced by a
fresh Python process to avoid persistent Matplotlib/Pillow writer state across
multiple exports.

## Expected results

The exact wall-clock time depends on the workstation because the script first
runs the full test suite, renews upstream evidence and renders 14 media files
(6+4+4 GIF/MP4 pairs). It is normal for this task to take longer than prior
single-phase patches.

After success, inspect:

```text
outputs\reports\reference_current_control_robustness_validation.md
outputs\logs\reference_current_control_visual_quality_manifest.json
outputs\animations\reference_current_control_contact_sheet.png
outputs\figures\reference_current_track_comparison.png
outputs\figures\reference_current_control_response.png
outputs\figures\reference_controller_sensitivity_map.png
records\phases\phase_10_13\runs\...
records\handoffs\PHASE10_13_LATEST_HANDOFF.md
```
