# Patch 10.17.1 — Offline Bootstrap Hotfix

## Scope

This overlay fixes only the bootstrap command in
`scripts/run_patch_10_17_engineering_release_gate.bat`.

The previous script used `python -m pip install --editable .` with PEP 517 build
isolation. On a host without DNS/Internet access, pip attempted to download the
build requirements (`setuptools>=69`, `wheel`) even though the Conda environment
already provides them. The Engineering Release Gate therefore did not start.

## Change

The editable install is now explicitly local and offline-safe:

```bat
python -m pip install --editable . --no-build-isolation --no-deps
```

The script also disables pip's version-check network lookup for this execution.

## Non-changes

- No mission, dynamic-model, controller, policy, YAML or evidence data changes.
- No GIF/MP4 rendering.
- No Word report, delivery ZIP or Release Build.
- The Engineering Release Gate remains audit-only.

## Apply

Extract the ZIP to `C:\Projects` so it overlays `C:\Projects\AquaSkim-Sim`.
Then run:

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_17_engineering_release_gate.bat
```

A successful result must say `ENGINEERING_RELEASE_CANDIDATE` and retain
`Release: DISABLED`.
