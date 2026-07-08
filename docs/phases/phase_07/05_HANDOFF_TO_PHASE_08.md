# Phase 07 → Phase 08 Handoff

## Stable inputs for autonomy
1. `outputs/tables/phase07_occupancy_grid.csv`
2. `outputs/tables/phase07_environment_objects.csv`
3. `outputs/tables/phase07_sensor_demo_log.csv`
4. `outputs/tables/phase07_detection_summary.csv`
5. `outputs/logs/phase07_environment_summary.json`

## Phase 08 design obligations
- Build a mission state machine with explicit state transitions.
- Plan safe routes on the Phase 07 occupancy grid.
- Use the Phase 06 plant model in feedback simulation.
- Use Phase 05 SOC and return threshold in mission decision logic.
- Emit logs explaining every autonomy decision.

## Known limitations inherited by Phase 08
- Obstacles are static in Phase 07.
- Range sensor and debris detector use transparent surrogate models.
- Phase 06 contains planar dynamics only; roll/pitch/heave are excluded.
