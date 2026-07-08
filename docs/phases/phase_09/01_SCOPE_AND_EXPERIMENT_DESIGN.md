# Phase 09 — Scenario Validation, Robustness and Presentation Rehearsal

## Objective
Phase 08 proves that one deterministic closed-loop mission can complete. Phase 09 answers a different engineering question:

> Does the same digital-twin architecture remain safe and useful when current direction, initial battery state and random debris placement vary?

The phase therefore combines four named deterministic scenarios with a seeded Monte Carlo campaign. It does **not** claim formal probabilistic certification, real-water field validation, wave modelling or moving-obstacle prediction.

## Deterministic scenarios

| ID | Disturbance / condition | Primary validation objective |
|---|---|---|
| `nominal_calm` | No current, normal SOC | Establish baseline performance. |
| `cross_current` | 0.02 m/s lateral current | Test heading feedback and cross-track robustness. |
| `low_energy_return` | 0.31 initial SOC, one-object quota | Test conservative collection and return-to-home logic. |
| `diagonal_current` | [0.12, -0.10] m/s current | Test combined longitudinal/lateral disturbance. |

## Monte Carlo protocol

Twenty seeded trials vary:

- current magnitude uniformly in `[0, 0.02] m/s`,
- current direction uniformly in `[0, 360) deg`,
- initial SOC uniformly in `[0.31, 0.48]`,
- current direction and initial SOC; the perception/debris seeds are retained to isolate the navigation-control envelope.

A trial is considered successful only if all of the following are true:

1. The final agent state is `MISSION_COMPLETE`.
2. At least one debris item is collected.
3. Minimum signed hazard distance is non-negative.
4. Final home-station error is no more than `0.30 m`.

## Traceability
Every deterministic scenario, every Monte Carlo trial, the scenario configuration and the aggregate metrics are written to CSV/JSON and are included in the official evidence snapshot.
