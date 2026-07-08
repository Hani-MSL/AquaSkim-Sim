# Visualisation catalogue

## Static engineering figures

| Asset | Purpose |
|---|---|
| `mission_multitarget_map` | Actual 3-DOF trajectory, A* legs, targets, obstacles and home station |
| `mission_tracking_dynamics` | Heading, speed, surge, sway and yaw response |
| `mission_force_energy_history` | Port/starboard thrust, hydrodynamic drag, yaw moment, SOC and bus power |
| `mechanical_force_diagram_2d` | Planar sampled force decomposition from the time-series ledger |
| `mechanical_force_diagram_3d` | Parametric hull, gravity, buoyancy, propulsion and drag vectors |
| `mission_trajectory_time_3d` | Position-time reconstruction of the surface mission |
| `controller_allocation_surfaces_3d` | Bounded mapping from errors to yaw moment and total thrust |
| `mission_scenario_comparison` | Nominal, two operating-current cases and explicit energy-guard case |
| `mission_quality_dashboard` | Clearance, collection progression, state occupancy and scenario outcomes |

## Animation and video assets

Six GIF/MP4 pairs are produced: top-down mission replay, telemetry, planning, 3-D force vectors, state machine and 3-D vehicle replay.  The interactive profile controls replay frames and FPS.  The contact sheet provides a fast visual QA record.

## Visible-title policy

Internal development names and phase identifiers are not rendered inside figures. They remain in evidence folder names, filenames, manifests and handoffs only.
