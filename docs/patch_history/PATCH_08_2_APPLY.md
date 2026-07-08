# Patch 08.2 — Mission Quality, Safety Supervision and Interactive Reproducibility

## Purpose
This patch supersedes the original short two-object Phase 08 visual demo as the active engineering baseline. It does **not** produce the final Word report. Final report generation remains deferred until expanded scenario validation is complete.

## Apply
Extract the Patch ZIP in `C:\Projects` and allow replacements.

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_08_2_Mission_Quality_and_Reproducibility.zip" -C C:\Projects
```

## Official run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_08_2.bat
```

The recorded run creates:
- 6 high-resolution PNG/SVG figures;
- 4 GIF and 4 MP4 animations;
- numerical CSV tables and Markdown/JSON summary;
- a timestamped Evidence folder with commands, snapshots and SHA-256 hashes.

## Interactive reproducibility command

```bat
scripts\configure_and_build.bat
```

This is the stable engineering-build entrypoint. It creates/activates the Conda environment, asks for mission and submission-critical values, writes a local Git-ignored profile, and rebuilds implemented engineering phases. It intentionally does not create the final Word report yet.
