# Apply Patch 07 — Environment, Sensors and Debris

## Preconditions
- Apply after Patch 06.
- Run from an activated Windows CMD session that can invoke `conda`.
- Existing environment name: `aquaskim-sim`.

## Apply

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_07_Environment_Sensors_Debris.zip" -C C:\Projects
```

## Official one-command execution

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_07.bat
```

## Outputs
The official command regenerates Phase 02–06 dependencies, executes Phase 07, runs all tests, and creates immutable evidence under:

```text
records/phases/phase_07/runs/phase07_<UTC timestamp>/
```

The stable handoff is written to:

```text
records/handoffs/PHASE07_LATEST_HANDOFF.md
```
