# Apply Patch 03

1. Extract this ZIP in `C:\Projects` and replace same-name files.
2. Run exactly one command from the project root:

```bat
scripts\run_patch_03.bat
```

The script activates `aquaskim-sim`, installs the editable package, runs preflight, regenerates Phase 02 dependency artifacts, builds Phase 03, runs the full tests and preserves an evidence package.

No library installation is expected because Phase 03 uses packages already defined in `environment.yml`.
