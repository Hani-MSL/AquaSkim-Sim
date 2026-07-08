# Patch 10.10 — Source Integrity Recovery and Reference-Path Consolidation

## Scope

This patch restores missing source entry points and validates source integrity
before any expensive simulation or media render can occur.

## Included

- real reconstruction of `phase02.py` from current geometry, mass-budget,
  mass-property and visual-quality modules;
- restoration of the package CLI and local bootstrap entry point;
- neutral `mission_plant.py` so reference simulations do not import the
  quota-based Phase 08 autonomy branch;
- explicit legacy registry and reference-path isolation policy;
- a lightweight integrity audit for YAML, imports, source policy and release
  disablement;
- regression tests for the recovered contracts.

## Explicitly excluded

- reference mission rerun;
- GIF/MP4 rendering;
- Word report generation;
- submission ZIP generation;
- Release Build.
