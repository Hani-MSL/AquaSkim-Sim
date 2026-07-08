# Patch 10.15 — System-Level Scenario Validation

## Scope

This patch adds deterministic system-level scenarios that are explicitly
classified as validated, boundary, or controlled failure. It does not build a
Word report, delivery archive, or release package.

## Execution gate

The Windows runner applies this order:

1. editable install;
2. YAML parse audit;
3. import audit;
4. compileall;
5. full pytest suite;
6. one fixed preparation run for all system scenarios;
7. isolated GIF/MP4 rendering from the prepared logged CSV data;
8. media quality checks, evidence snapshot, SHA-256 manifest, and handoff.

## Important policy

- Validated scenarios are the only rows counted as validated operation.
- The diagonal boundary and both controlled failures are retained as limitation evidence.
- The reference path remains noninteractive and quota-independent.
- Word, delivery ZIP, and release build remain disabled.
