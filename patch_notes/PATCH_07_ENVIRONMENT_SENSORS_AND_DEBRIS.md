# Patch 07 — Environment, Sensors and Debris

## Added engineering scope
- Analytic basin, static obstacles and safety-radius configuration-space inflation
- Deterministic floating-debris placement with clearance checks
- Occupancy grid export
- GNSS/UWB, compass, multi-beam range and debris-detector surrogate models
- Sensor demonstration truth/log generation
- Four report-quality PNG/SVG figures, six CSV tables, JSON/Markdown summaries and visual QA

## One-command official runner

```bat
scripts\run_patch_07.bat
```

## Reproducibility
`bootstrap_and_build.bat` now includes Phases 01–07 in the full implemented build.
