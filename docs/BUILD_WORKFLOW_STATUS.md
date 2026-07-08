# Build Workflow Status

## Current state: active engineering development

The project is not yet frozen for final delivery. Therefore the interactive entry point is intentionally protected from launching a long, destructive rebuild.

- `scripts\bootstrap_and_build.bat` → creates/updates a local scientific experiment profile only.
- `scripts\configure_experiment.bat` → same configuration action directly.
- Patch-specific scripts → generate only the artifacts belonging to their patch.

## Final-release state (future)

After mission-capacity logic, coverage mission behaviour, dynamic/force animation suite and visual quality gates are complete, the same `bootstrap_and_build.bat` path will:

1. create or update the local experiment profile;
2. rebuild all supported model stages;
3. run validation and quality gates;
4. create reproducibility evidence and hashes;
5. generate the optional local Word report and delivery ZIP.

Personal cover metadata will be an optional **separate** local step at that time and will never be part of the public GitHub configuration wizard.
