# Patch 08.1 Apply Guide

## Purpose
Fix the Phase 08 Python syntax error and add a compiler gate before all official Phase 08 runs.

## Apply
Extract this ZIP into `C:\Projects` and permit replacement of existing files.

```bat
cd /d C:\Projects
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_08_1_SyntaxHotfix.zip" -C C:\Projects
```

## Run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_08_hotfix.bat
```

## Expected final status

```text
AquaSkim-Sim | Official Phase 08 Recorded Run
Status       : PASS
```
