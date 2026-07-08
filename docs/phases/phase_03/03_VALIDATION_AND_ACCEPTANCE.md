# Phase 03 | Validation and Acceptance Matrix

| Check | Acceptance criterion | Verification mechanism |
|---|---|---|
| Equilibrium volume | Integrated volume equals `m / ρ` | Bisection residual test in `hydrostatics.py` |
| Dry draft | Positive and less than hull height | Unit test and summary table |
| Full-load draft | Positive and less than hull height | Unit test and summary table |
| Initial stability | `GM >= 0.20 m` for both main load cases | Acceptance CSV |
| Freeboard at zero heel | `>= 0.05 m` for both main load cases | Acceptance CSV |
| Freeboard at 5° | `>= 0.05 m` for both main load cases | Acceptance CSV |
| Restoring tendency | Righting moment at 5° must be positive | Acceptance CSV |
| Curve consistency | Nonlinear GZ must be close to GM reference near 1° | Unit test |
| Visual quality | PNG >= 4500×2400 px and SVG exists | Visual manifest and unit test |
| Traceability | Commands, hashes, inputs and snapshots retained | Recorded Phase 03 runner |

## Interpretation rule

A numerical PASS in this phase proves consistency with the defined conceptual model. It does **not** prove ocean-sea-worthiness or replace CFD, classification rules, tank testing or physical prototype validation.
