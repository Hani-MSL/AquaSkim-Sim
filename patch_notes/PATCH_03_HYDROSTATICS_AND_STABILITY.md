# Patch 03 — Hydrostatics and Transverse Stability

## Scope

This patch implements Phase 03 as a reproducible engineering package.

## New scientific components

- Fresh-water displacement equilibrium.
- Draft and freeboard calculations.
- Initial transverse stability: `KB`, `BM`, `KG`, `GM`.
- Finite-heel numerical strip integration for the twin hulls.
- Nonlinear GZ and righting-moment curves.
- Partial-emergence and low-freeboard indicators.
- Payload sweep from empty basket to design payload.
- Acceptance matrix and automated tests.

## Visual outputs

Four report-quality PNG/SVG pairs are generated. Long text is moved to information panels; geometry panes use only compact labels and markers.

## One-command execution

```bat
scripts\run_patch_03.bat
```

## Reproducibility

The official runner records command lines, stdout, stderr, config snapshot, source/config hashes, environment metadata, generated-output hashes, copied artifacts and a Phase 03 Handoff.

## Tests

This patch extends the test suite with hydrostatic equilibrium, small-angle consistency, operating-heel restoration, artifact and visual-quality checks.
