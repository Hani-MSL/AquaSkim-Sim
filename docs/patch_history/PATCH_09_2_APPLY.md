# Patch 09.2 — Comprehensive Validation, Animation Expansion and Reproducible Interactive Build

## Purpose
This patch follows Phase 08.2. It extends the project before final Word-report generation. Do not run `scripts\run_patch_10.bat` after applying this patch; final documentation remains deferred.

## Apply

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_09_2_Comprehensive_Validation_and_Reproducibility.zip" -C C:\Projects
```

## Official Phase 09.2 run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_09_2.bat
```

The command performs syntax checking, executes Phase 09.2, runs the project test suite, and creates an Evidence folder under:

```text
records/phases/phase_09_2/runs/
```

The run is intentionally computation- and rendering-intensive because it creates 8 PNG/SVG figures, 6 GIF files, 6 MP4 files and a 24-trial seeded validation envelope by default.

## Public one-command reproducibility command

```bat
scripts\bootstrap_and_build.bat
```

This command now starts the interactive wizard and asks for engineering, mission, validation and submission metadata. It writes a local Git-ignored profile, then rebuilds the engineering core through Phase 09.2. It intentionally does **not** make the final Word report yet.
