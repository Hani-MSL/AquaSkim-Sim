# AquaSkim-Sim — Patch 08 Apply Guide

## Purpose
Patch 08 adds the first closed-loop autonomous mission to the digital twin:
- deterministic A* planning on the Phase 07 occupancy grid,
- a traceable autonomy state machine,
- feedback steering and differential-thrust control on the Phase 06 3-DOF plant,
- SOC-aware return-home logic from Phase 05,
- report-quality figures, CSV tables, an animated GIF and MP4,
- complete evidence, input/output snapshots, SHA-256 manifests and a Phase 08 handoff.

## Apply the patch
Extract this ZIP over the parent folder `C:\Projects`.

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_08_Autonomy_Planning_and_Control.zip" -C C:\Projects
```

## Run the entire official Phase 08 workflow

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_08.bat
```

The batch file installs the editable package, runs all upstream dependency phases needed for evidence, generates Phase 08 outputs, runs the full test suite, snapshots artifacts, records command stdout/stderr, writes SHA-256 manifests, and publishes the formal Phase 08 handoff.

## Expected end-state

```text
AquaSkim-Sim | Official Phase 08 Recorded Run
Status       : PASS
Evidence     : records/phases/phase_08/runs/phase08_...
Handoff      : records/handoffs/PHASE08_LATEST_HANDOFF.md
```

## Main artifacts
- `outputs/figures/phase08_*.png` and `.svg`
- `outputs/animations/phase08_closed_loop_mission.gif`
- `outputs/videos/phase08_closed_loop_mission.mp4`
- `outputs/tables/phase08_*.csv`
- `outputs/logs/phase08_*.json`
- `outputs/reports/phase08_autonomy_planning_and_control_summary.md`
