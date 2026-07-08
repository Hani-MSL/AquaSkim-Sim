# Patch 10.7 — Reference Mission Calibration and Verification

## Why this patch exists
The recovery gate restored the baseline, but the earlier reference mission
settings were not yet calibrated as a complete, auditable mission suite.
This patch separates the two scientifically different demonstrations:

- nominal full-basin coverage
- high-debris hopper-volume return

## Key decisions
- no interactive configuration
- no student metadata
- no fixed collection-count quota
- fixed YAML scenario overlays
- calibration assertions based on logged 3-DOF time histories
- figure titles contain no internal phase or patch numbers

## Scope
This is not the final Word-report stage. It validates the reference mission
behaviour before independent manoeuvre testing and final release packaging.

## Renderer reliability
Animation encoders run in isolated Python subprocesses to avoid multi-writer resource leaks observed in some Matplotlib/FFmpeg installations.
