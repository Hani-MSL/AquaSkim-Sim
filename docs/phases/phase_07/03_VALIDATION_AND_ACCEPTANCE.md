# Phase 07 — Validation and Acceptance

## Required numeric checks

| Check | Acceptance criterion |
|---|---|
| Home location | navigable after safety inflation |
| Debris placement | all objects outside inflated hazards and boundary buffer |
| Sensor demonstration route | all truth samples navigable for the vessel safety radius |
| Occupancy map | contains prohibited cells |
| GNSS/UWB surrogate RMS error | less than 0.20 m |
| Compass surrogate RMS error | less than 8 degrees |
| Debris detector | detects at least one eligible object in the demo |

## Test policy
Unit tests cover deterministic debris generation, hazard-aware placement, occupancy existence, ray-cast boundary response, sensor-demo repeatability and production of all report-quality artifacts.

## Visual policy
Every Phase 07 figure is produced as both PNG and SVG. Technical diagrams isolate long explanations in side panels; text is never placed on top of the robot/environment geometry where it can obscure interpretation.
