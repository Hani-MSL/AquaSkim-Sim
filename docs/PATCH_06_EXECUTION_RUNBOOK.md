# Patch 06 — Runbook

## One-command official execution

```bat
scripts\run_patch_06.bat
```

The script activates `aquaskim-sim`, performs editable installation, rebuilds the dependencies needed by the dynamics model, generates Phase 06 outputs, runs tests, captures all command output and creates a timestamped evidence package.

## Main output folders

- `outputs/figures/`: PNG and SVG figures
- `outputs/tables/`: dynamic parameters, scenario metrics and time series
- `outputs/logs/`: numerical and visual-QA manifests
- `outputs/reports/`: narrative phase summary
- `records/phases/phase_06/runs/`: immutable official run evidence
- `records/handoffs/PHASE06_LATEST_HANDOFF.md`: input contract for the next phase

## Full rebuild entry point

```bat
scripts\bootstrap_and_build.bat
```

After Patch 06 this rebuilds Phases 01–06. It is the stable single-command project entry point and will be extended rather than renamed in later patches.
