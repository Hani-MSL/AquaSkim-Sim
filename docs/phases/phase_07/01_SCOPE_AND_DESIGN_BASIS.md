# Phase 07 — Scope and Design Basis

## Purpose
Phase 07 creates the operational world required before a genuine autonomous mission can be designed: a bounded basin, static obstacles, deterministic debris targets, a configuration-space occupancy grid and synthetic sensor channels.

## Scope
- Basin coordinates use the existing ENU convention.
- Obstacles are analytic circles or axis-aligned rectangles.
- The vessel is represented in planning space by a safety radius; obstacles and the basin boundary are inflated by this radius.
- Debris is generated with a fixed seed and explicit clearance constraints.
- GNSS/UWB, compass, forward range and debris-detection channels are virtual but have explicit noise/probability models.

## Explicit non-goals
- No camera imagery, neural detection model or trained classifier.
- No dynamic obstacles, wind field, waves or image occlusion.
- No autonomy or closed-loop control. The Phase 07 survey route is solely a repeatable sensor-data generator.

## Handoff to Phase 08
Phase 08 will consume `phase07_occupancy_grid.csv`, `phase07_environment_objects.csv`, `phase07_sensor_demo_log.csv` and `phase07_detection_summary.csv` to implement planning, safety logic, guidance, control and a documented autonomy state machine.
