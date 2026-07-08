# Patch 09.2 — Comprehensive Validation, Visual Evidence and Interactive Reproducibility

## Purpose
This patch supersedes the earlier short Phase 09 validation demonstration. It deliberately delays final Word report generation until broader validation and final documentation checks are completed.

## New capabilities
- six deterministic validated/protective/boundary scenarios;
- 24 seeded stratified current/SOC envelope trials by default;
- explicit classification of boundary limitations;
- eight high-resolution PNG/SVG figures;
- six GIFs and six MP4 files;
- numerical scenario/time-series/event/Monte-Carlo outputs;
- Phase 09.2 Evidence, hashes and handoff;
- expanded interactive GitHub-oriented configuration wizard;
- a safe one-command build that asks for user inputs and deliberately excludes final Word generation.

## Active command

```bat
scripts\run_patch_09_2.bat
```

## Long-term public entry point

```bat
scripts\bootstrap_and_build.bat
```

## Important limitation
The high-current and extended-quota cases are intentionally retained as boundary evidence. They are not performance-success claims.
