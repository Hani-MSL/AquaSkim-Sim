# Phase 08 — Validation and Acceptance

| Check | Criterion | Evidence |
|---|---|---|
| Planner determinism | Same grid and endpoints produce identical A* route | `test_planner.py` |
| Route safety | Every A* grid cell is unoccupied | `test_planner.py` |
| Closed-loop terminal state | `MISSION_COMPLETE` | `test_autonomy.py` and mission event log |
| Debris collection | At least one confirmed capture | mission metrics and target table |
| Safety | Minimum signed hazard clearance above zero | acceptance CSV |
| Energy | Final SOC above return-to-home floor | mission time series |
| Visual quality | PNG at least 3000 × 1800 px plus SVG | visual-quality manifest test |
| Animation | GIF and MP4 produced | acceptance CSV and manifest |

## Interpretation of success

A successful Phase 08 run does not imply universal navigation success. It
establishes that the configured mission can be reproduced from the project
inputs, follows the documented decision policy and produces a complete trail of
numerical and visual evidence.
