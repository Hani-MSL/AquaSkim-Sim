# Phase 05 — Energy, battery SOC and return-home policy

## Objective
Phase 05 transforms Phase 04 electrical operating demand into a mission-energy model. It creates a transparent battery-side power budget, integrates usable SOC over deterministic duty-cycle missions and derives a conservative return-home threshold.

## Design basis
- Full payload remains the governing displacement case.
- Phase 04 propulsion power is the source of thruster electrical demand.
- `P_pack = P_bus / eta_DC` converts DC-bus demand to battery-side demand.
- Usable battery energy is nominal energy multiplied by usable SOC window and capacity derating.
- A mild Peukert-style multiplier is applied at currents above the reference current.

## Scope
- Battery energy budget and current estimate.
- 60-minute mission SOC profiles.
- Endurance to the configured return-home boundary.
- Return-trip energy envelope versus distance and head current.

## Explicit exclusions
Cell thermal dynamics, ageing, charging, BMS cut-off transients and real pack characterization are out of scope.
