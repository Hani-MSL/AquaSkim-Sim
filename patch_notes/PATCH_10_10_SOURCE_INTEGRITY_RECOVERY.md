# Patch 10.10 — Source Integrity Recovery and Reference-Path Consolidation

## Why this patch exists

The project contained retained artefacts for Phase 02 but lacked the source
module that generated them. It also lacked `aquaskim.cli` and the documented
`bootstrap_and_build.bat` entry point. Full pytest therefore failed during test
collection, even though selected tests had passed previously.

## Main corrections

- reconstructs `phase02.py` using real shared geometry and mass-properties;
- restores `aquaskim.cli` without enabling final report delivery;
- restores a safe local scientific-profile bootstrap;
- creates a neutral physical-plant assembly used by the reference mission and
  manoeuvre suites;
- isolates the old quota-based branch as legacy-only;
- blocks accidental Word/ZIP/release commands;
- adds the required source-integrity audit order.

## No release claim

A PASS for this patch means only that source and configuration contracts are
internally healthy. It does not mean that the project has passed visual QA,
reference rerendering, release review, report generation or submission
packaging.
