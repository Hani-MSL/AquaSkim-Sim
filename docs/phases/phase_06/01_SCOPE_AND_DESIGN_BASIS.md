# Phase 06 — Scope and Design Basis

## Objective
Create the first time-domain plant model for the fully loaded AquaSkim-Sim catamaran. This connects mechanical mass properties, hydrostatics, Phase 04 resistance and twin-thruster forces into reproducible planar motion.

## State and coordinates

- Earth-fixed state: `x`, `y`, `ψ` in ENU.
- Body-fixed velocity: `u` (surge), `v` (sway), `r` (yaw rate).
- The earth-fixed current is transformed to the body frame at each time step. Drag uses velocity **relative to water**, not only ground speed.

## Engineering rationale

A planar 3-DOF representation is appropriate because the mission is a low-speed surface-cleaning task in sheltered water. Phase 03 already validates hydrostatic margin; Phase 06 therefore focuses on horizontal motion. Roll, pitch and heave are intentionally outside the current plant.

## Scenario set

1. Calm straight-line acceleration and settling.
2. Differential-thrust timed turn.
3. Symmetric thrust with a cross-current disturbance.
