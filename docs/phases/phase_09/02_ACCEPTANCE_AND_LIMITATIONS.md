# Phase 09 — Acceptance Criteria and Modelling Limits

## Acceptance checks

| Check | Criterion |
|---|---|
| Deterministic nominal mission | Passes complete closed-loop mission criteria. |
| Deterministic safety | Minimum signed clearance remains non-negative in every named scenario. |
| Monte Carlo reliability | Success rate is at least 0.95 across the seeded trial set. |
| Mission completion | At least one deterministic mission reaches `MISSION_COMPLETE`. |
| Visual exports | Every Phase 09 figure has a high-resolution PNG and SVG counterpart. |
| Evidence | The recorded runner saves command logs, environment snapshot, artifact hashes, snapshot copies and a handoff. |

## Important limitations

- Monte Carlo results quantify robustness only **within the mild-current controller-calibration envelope: 0 to 0.02 m/s**. The wider thrust envelope analyzed in Phase 04 does not by itself establish closed-loop navigation robustness at larger currents.
- Random debris locations are generated from seeded pseudo-random sequences; they are not observed field data.
- Water current is spatially uniform and constant within one run.
- Obstacles are static, and debris has no independent drift model.
- The result is a transparent educational engineering model, not an operational safety certification.
