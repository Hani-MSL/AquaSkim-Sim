# Patch 06 — 3-DOF Dynamics

## Scope
Adds the first time-domain plant model: body-fixed surge, sway and yaw with earth-fixed ENU position, current-relative drag, added-mass approximations and differential twin-thruster yaw moment.

## One command

```bat
scripts\run_patch_06.bat
```

## Included evidence
The official runner logs each command, stdout/stderr, environment, configuration/code hashes, artifacts and handoff.

## Boundary
This is an open-loop plant. No map, sensor, obstacle avoidance, autonomy or feedback guidance has been added yet.
