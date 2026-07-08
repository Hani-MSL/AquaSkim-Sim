# Patch 08.1 — Phase 08 Syntax Hotfix

## Incident
Patch 08 failed during import with:

```text
SyntaxError: f-string expression part cannot include a backslash
```

## Root cause
The Markdown summary generator used expressions such as `{"\\n".join(...)}` directly inside an f-string. Python disallows backslashes inside an f-string expression.

## Correction
The summary sections are now assembled into normal variables before the final f-string is created:

- `events`
- `acceptance_rows`
- `artifact_rows`

## Prevention
- `scripts/run_patch_08.bat` now runs `python -m compileall -q src` after editable installation and before importing the CLI.
- `tests/test_phase08_syntax.py` statically compiles `phase08.py` in the test suite.

## Required execution command

```bat
scripts\run_patch_08_hotfix.bat
```

The command runs the corrected official Phase 08 workflow and records its normal evidence, artifact snapshots and handoff.
