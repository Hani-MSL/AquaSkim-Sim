# Phase 03 | Visual Quality Standard and Review Record

## Mandatory export standard

Every Phase 03 figure is exported as both:

- PNG for insertion into the final Word report; minimum `4500 × 2400 px`.
- SVG for vector-quality archival and future editing.

## Layout rules

1. No paragraph-length text is allowed over geometric drawings or data curves.
2. Long explanations live in a dedicated right-side panel.
3. Values needing comparison are shown in manually drawn fixed-layout metric grids, not renderer-dependent automatic tables.
4. Cross-section markers use compact symbols only: `CG`, `CB`, hull outline and waterline.
5. Information-panel prose is explicitly line-wrapped in code.
6. Every figure has a title, subtitle, units, scope label and an output file path recorded through the evidence runner.

## Manual review checklist used before Patch release

| Figure | Review result |
|---|---|
| Hydrostatic equilibrium dashboard | PASS — cross-sections, metric grid and explanation blocks are separated |
| Transverse stability curves | PASS — legends, shaded linear range, data curves and interpretation blocks are separated |
| Full-load heeling cross-sections | PASS — no text over waterlines; schematic vertical expansion disclosed |
| Payload envelope | PASS — tabular values and explanations are placed outside curve panels |

## Automated quality gate

`tests/test_phase03_quality.py` verifies that all four PNG outputs exceed the raster-resolution threshold and all matching SVG files are present.
