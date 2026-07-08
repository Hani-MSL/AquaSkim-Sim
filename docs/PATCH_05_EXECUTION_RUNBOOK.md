# Patch 05 execution runbook

## Single official command

```bat
scripts\run_patch_05.bat
```

## What the command does
1. Activates `aquaskim-sim`.
2. Reinstalls the local package in editable mode.
3. Runs preflight.
4. Regenerates the Phase 02, Phase 03 and Phase 04 dependencies.
5. Builds Phase 05 energy, battery, SOC and return-home artifacts.
6. Runs all automated tests.
7. Stores stdout, stderr, configuration snapshots, source hashes, artifact hashes, artifact copies and a phase handoff in a timestamped evidence folder.

## Evidence location

```text
records/phases/phase_05/runs/phase05_YYYYMMDDTHHMMSSZ/
```

The stable latest handoff is copied to:

```text
records/handoffs/PHASE05_LATEST_HANDOFF.md
```
