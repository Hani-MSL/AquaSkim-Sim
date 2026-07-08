# Phase 08 — Output Inventory

## Figures

- `phase08_autonomy_architecture`: data/control architecture.
- `phase08_planning_map`: configuration-space map and recorded A* paths.
- `phase08_closed_loop_mission`: actual dynamic trajectory with state colours.
- `phase08_control_dashboard`: heading, thrust, SOC, load, speed and clearance.
- `phase08_decision_timeline`: state occupancy and human-readable transition reasons.

Every figure is exported as PNG for Word and SVG for lossless reuse.

## Animation

- `outputs/animations/phase08_closed_loop_mission.gif`
- `outputs/videos/phase08_closed_loop_mission.mp4`

## Numeric data

- Mission time series with state, pose, body velocities, SOC, load, commands and safety clearance.
- Planned-route table with each recorded waypoint and cumulative path length.
- State-event table with timestamp, reason, target ID, SOC and position.
- Collected-debris table with mass and capture position.
- Acceptance-check table.

## Evidence

The official runner copies all Phase 02–08 artifacts into a timestamped
snapshot, computes SHA-256 hashes, preserves stdout/stderr and emits a Phase 08
handoff document.
