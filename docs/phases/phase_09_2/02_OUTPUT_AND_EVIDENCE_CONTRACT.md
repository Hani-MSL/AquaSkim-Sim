# Phase 09.2 — Output and Evidence Contract

## Numerical outputs
The phase writes a deterministic catalog, time series, event ledger, Monte Carlo trial table, operating-envelope definition, summary statistics, acceptance checks and animation manifest under `outputs/tables/`.

## Visual outputs
Eight high-resolution PNG/SVG figures are produced. Text-heavy information is kept in panels and tables rather than densely overlaid on mission geometry.

## Motion outputs
Six GIFs and six MP4 files are generated from model traces:

- scenario reel;
- nominal telemetry replay;
- proactive-energy-return replay;
- safety-shield/replan replay;
- Monte Carlo envelope replay; and
- high-current boundary replay.

## Evidence output
The official runner creates a timestamped folder under:

```text
records/phases/phase_09_2/runs/<run-id>/
```

The record contains commands, command stdout/stderr, environment snapshot, input manifest, source/config hashes, output hashes, artifact copies and a handoff note.
