# Phase 06 — Validation and Acceptance

## Automated checks

- Calm symmetric thrust converges within configured surge-speed tolerance.
- Differential thrust produces a non-zero heading change.
- Peak yaw rate stays within the configured design bound.
- Cross-current generates observable open-loop drift; this establishes the baseline for guidance control.
- All generated PNG files satisfy report-quality pixel dimensions and matching SVG files exist.

## Interpretation discipline

A passing result verifies internal consistency of this transparent model; it does not claim experimental identification or certification. The next phases will introduce environmental geometry, sensor models, mission decisions and closed-loop guidance.
