# Phase 03 | Scope and Design Basis

## Objective
Replace the Phase 02 conceptual draft preview with an auditable calm-water hydrostatic calculation for the AquaSkim-Sim catamaran.

## Design questions answered

1. What draft and freeboard occur at dry and full-payload mass?
2. Is initial transverse stability positive?
3. What are `KB`, `BM`, `KG`, and `GM`?
4. What righting arm and righting moment are available at finite heel?
5. At what angle does a local strip of the lifted hull become nearly dry?
6. Does the payload envelope satisfy the selected freeboard and GM rules?

## Water and units

- Fresh water density: `ρ = 1000 kg/m³`
- Gravitational acceleration: `g = 9.80665 m/s²`
- All calculations: SI units
- Positive heel: port side (`+y`) down

## Scope boundary

Included: static equilibrium in calm water, small-angle hydrostatics, finite-heel strip integration, payload sweep, output quality gate and evidence capture.

Excluded: wave excitation, speed-dependent lift, wind heel, CFD, viscosity, added mass, roll damping, transient roll dynamics, slamming and flooding.
