# Phase 07 — Output Inventory

## Figures
- `phase07_environment_map`: basin, hazards, safety inflation, debris and sensor-demo route
- `phase07_occupancy_grid`: derived configuration-space map
- `phase07_sensor_model`: sensor field-of-view and beam geometry
- `phase07_perception_dashboard`: truth/measurement diagnostics and detection outcomes

## Tables
- environment object inventory
- complete occupancy-grid cells
- sensor specifications
- time-stamped sensor demonstration log
- per-debris detection summary
- acceptance checks

## Evidence
The official runner snapshots every output, creates SHA-256 manifests, stores command stdout/stderr, freezes package versions and writes an explicit handoff.
