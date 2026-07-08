# Patch 10.14 — Payload Stability and Low-current Manoeuvre Validation

## Scope

This patch adds a fixed, non-interactive engineering-evidence suite for payload hydrostatics and deterministic low-current manoeuvres. It does **not** generate a Word report, delivery ZIP or release artifact.

## Apply on Windows

```bat
cd /d C:\Projects

tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_14_Payload_Stability_and_Maneuver_Validation.zip" -C C:\Projects

cd /d C:\Projects\AquaSkim-Sim

scripts\run_patch_10_14_payload_maneuver_validation.bat
```

## Gate order

```text
YAML parse → import audit → compileall → full pytest → static engineering figures
→ four isolated GIF/MP4 render jobs → contact sheet → media QA → evidence snapshot
```

## Explicitly disabled

- Word report
- delivery ZIP
- release build

## New evidence

- Hydrostatic payload mass, raised-payload and port-offset sensitivity.
- Nonlinear righting-moment and GZ curves.
- Quasi-static offset-load equilibrium heel estimate.
- Dry/full symmetric thrust-step response.
- Dry/full differential turns and low-current turn displacement.
- Dry/full state-triggered zig-zag response.
- Four GIFs, four MP4s and an evenly sampled contact sheet.

## Model boundary

Payload is represented as a point mass. The offset case is a quasi-static heeling-moment sensitivity. The manoeuvres are low-speed planar 3-DOF simulations inside the documented sheltered-basin model. No wave response, roll transient, structural strength, sea-trial, sensor or certification claim is made.
