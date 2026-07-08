# Apply Patch 10.9.1

## Scope

This is a lightweight integrity hotfix. It fixes the malformed YAML registry and
updates one outdated test expectation. It does not modify the physical model,
mission dynamics, output figures, GIFs or MP4 files.

## Commands

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_9_1_RegistryAndTestHotfix.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_9_1_hotfix.bat
```
