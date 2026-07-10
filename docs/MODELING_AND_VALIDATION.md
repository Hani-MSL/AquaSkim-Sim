# Modelling and validation

This document summarizes the public engineering model implemented by AquaSkim-Sim. It replaces development-stage notes with a single, stable description of the equations, assumptions, configuration, and validation workflow used by the final reproducible build.

## 1. System representation

The simulated vehicle is a twin-hull surface robot with differential stern propulsion and a central collection mechanism. The reference design is defined by versioned files under `config/`; generated outputs are never treated as source inputs.

The planar pose and body-fixed velocity vectors are

\[
\eta = [x,\; y,\; \psi]^T,
\qquad
\nu = [u,\; v,\; r]^T,
\]

where `x` and `y` are inertial position, `ψ` is heading, `u` and `v` are surge and sway velocity, and `r` is yaw rate.

The kinematic relation is

\[
\dot{\eta} = R(\psi)\nu,
\]

with the standard planar rotation matrix `R(ψ)`.

## 2. Low-speed dynamics

The reference motion model follows the conventional low-speed 3-DOF form

\[
M\dot{\nu} + C(\nu)\nu + D(\nu)\nu = \tau + \tau_{env},
\]

where:

- `M` contains rigid-body and effective added-mass terms,
- `C(ν)` represents planar Coriolis and centripetal effects,
- `D(ν)` represents linear and nonlinear hydrodynamic damping,
- `τ` is the commanded propulsion force and moment,
- `τ_env` represents bounded environmental loading such as low current.

The model is intentionally limited to low-speed sheltered-water operation. It is not a seakeeping, wave-response, CFD, or high-speed manoeuvring model.

## 3. Hydrostatics and payload

Hydrostatic calculations use the configured hull geometry, total mass, displaced volume, water density, centre-of-gravity estimates, freeboard, and transverse stability metrics. Payload studies evaluate both mass and usable collection volume.

Collection limits are enforced independently:

\[
m_{captured} \le m_{payload,max},
\]

\[
V_{occupied} \le V_{hopper,usable}.
\]

The occupied volume is estimated from captured mass, effective bulk density, and packing efficiency. Parameter definitions, units, rationale, accepted ranges, and verification evidence are recorded in `config/parameter_registry.yaml`.

## 4. Propulsion and energy

The vehicle uses independent port and starboard thrust commands. Total surge force and yaw moment are obtained from the two actuator contributions and their transverse lever arm. The propulsion model includes command limits and the configured thrust/RPM relationships.

Electrical energy is integrated through the mission using the configured propulsion and hotel-load models. Battery state of charge is part of the mission termination and safe-return logic; it is not used as an unconstrained tuning variable.

## 5. Planning and control

The autonomy workflow combines:

1. deterministic scenario generation,
2. obstacle-aware path planning,
3. mission-state management,
4. differential-thrust heading and speed control,
5. collection-capacity and energy supervision,
6. safe-return and controlled-stop conditions.

Reference missions use versioned random seeds and fixed scenario definitions so that repeated runs remain traceable. The final control workflow records full state histories and separates turning, braking, tracking, replanning, and safety events in the generated evidence.

## 6. Configuration contract

The principal configuration sources are:

- `config/reference_design.yaml` — reference vehicle and mission definition,
- `config/parameter_registry.yaml` — parameter rationale and verification mapping,
- `config/scenarios/` — deterministic scenario definitions,
- `config/reference_*` — validation, visualization, control, and reporting settings.

Local report metadata is optional and stored in `config/report_metadata.json`, which is ignored by Git.

## 7. Validation strategy

Validation is layered rather than based on a single pass/fail result:

- **source integrity:** YAML parsing, import checks, reference-path isolation, and public-entrypoint checks,
- **unit and contract tests:** geometry, hydrostatics, dynamics, propulsion, energy, planning, control, reporting, and packaging,
- **scenario validation:** calm-water, current, obstacle, low-energy, payload, and manoeuvre cases,
- **visual QA:** figure, animation, video, and contact-sheet checks,
- **report QA:** document structure, media count, table count, and hash agreement,
- **delivery verification:** archive membership, SHA-256 validation, required manifests, and forbidden-artifact checks.

A clean rebuild runs these stages in a fixed order through `python -m aquaskim.rebuild_from_zero`.

## 8. Reproducibility boundary

The repository tracks source code, configuration, tests, lightweight documentation assets, and public entrypoints. Generated figures, media, reports, logs, records, and archives are recreated locally and excluded from version control.

The final package explicitly records the following non-claims:

- no sea-trial certification,
- no wave-response validation,
- no onboard current-estimator validation,
- no hardware commissioning or safety approval.
