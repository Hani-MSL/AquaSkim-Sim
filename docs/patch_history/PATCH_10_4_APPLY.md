# Patch 10.4 — Mission fidelity and advanced visual suite

## Purpose
This patch supersedes the short historical autonomy reels in the active engineering build. It does **not** generate the final Word report or delivery ZIP.

## Apply in Windows CMD

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_4_MissionFidelity_VisualSuite.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_4.bat
```

## Output scope

- multi-target 3-DOF mission with three verified captures and return-to-home
- reverse differential pivot turns for sharp heading changes
- A* route legs, progress watchdog, safety event and energy-return ledgers
- 9 PNG/SVG engineering figures, including 2-D / 3-D mechanical, force, dynamic and control views
- 6 GIF/MP4 replays and contact sheet
- evidence package, hashes, snapshots, commands, handoff

## One-command rebuild from a clean clone

```bat
scripts\bootstrap_and_build.bat
```

The wizard asks for the documented parameter set and stores local answers in `config\user_profile.yaml`. This file and generated outputs are Git-ignored, but snapshots are preserved in timestamped evidence records.
