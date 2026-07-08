# Phase 08 — Autonomy, Planning, Guidance and Control

## Purpose

Phase 08 closes a reproducible, short mission loop using the previously
implemented mechanical, hydrostatic, hydrodynamic, energy, dynamic and
perception layers. The purpose is not to demonstrate artificial intelligence
for its own sake. It is to show an auditable sequence from sensor evidence to
safe route planning, actuator commands, collection, return-to-home and docking.

## Inputs inherited from prior phases

- Phase 02: hull geometry, mass budget, centre of gravity and inertia estimate.
- Phase 03: full-load displacement and hydrostatic design envelope.
- Phase 04: speed-dependent resistance and twin-thruster sizing.
- Phase 05: battery SOC integration and return-to-home threshold.
- Phase 06: RK4-integrated planar surge–sway–yaw plant.
- Phase 07: analytic basin, inflated occupancy grid, debris population and virtual sensor parameters.

## Mission configuration

The default mission starts at the home station with a conservative SOC of 42%.
The agent must complete two confirmed debris captures and then return to the
home station. The intentionally short quota verifies the whole closed-loop
chain while keeping Phase 08 focused on control and traceability. Phase 09
will expand the mission duration and execute scenario sweeps.

## Explicit exclusions

- No trained vision model, SLAM, EKF or machine-learning policy.
- No moving obstacles, wind, wave force or current uncertainty sweep.
- No fluid–debris interaction or mesh-level collection-funnel CFD.
- No claim of marine safety certification.
