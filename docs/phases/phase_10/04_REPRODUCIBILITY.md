# Reproducible Build

## Full rebuild from zero

```bat
scripts\bootstrap_and_build.bat
```

This command creates/uses `aquaskim-sim`, installs the project, runs Phases 02--10 in order, executes the test suite, writes evidence packages, builds the final Word report and creates the submission ZIP.

## Rebuild only the final report

```bat
scripts\run_patch_10.bat
```

This runner rebuilds prerequisite Phase outputs before producing Phase 10 artifacts, then creates a timestamped evidence package under `records/phases/phase_10/runs/`.
