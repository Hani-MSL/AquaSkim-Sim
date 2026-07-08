# Patch 10.1 — CMD launcher and metadata hotfix

## Fixed

- `scripts/run_patch_10.bat` no longer contains an unescaped `|` in its banner.
- `semester` is now optional in `config/report_metadata.json`.
- The cover page omits the semester row when no value is supplied.
- Student, course and institution metadata are valid JSON.

## Required command after applying this patch

```bat
scripts\run_patch_10.bat
```
