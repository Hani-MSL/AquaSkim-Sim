# Patch 10.17 — Engineering Release Gate

## Scope

This overlay adds an audit-only engineering release-candidate gate after the
fixed-reference evidence has been curated. It normalizes the effective
reference configuration by removing the historical `max_collections` key before
the current mission settings are built, aligns the canonical source version,
and verifies evidence integrity by SHA-256.

## What the runner performs

1. YAML parse audit
2. Import audit
3. Syntax compilation
4. Full pytest suite
5. Source/reference Legacy-isolation checks
6. Canonical version-consistency check
7. Required evidence and visual-manifest checks
8. Curated source-to-copy SHA-256 integrity checks
9. Explicit boundary/controlled-failure classification checks
10. Confirmation that Word, delivery ZIP and final release scripts remain disabled
11. Release-gate report, evidence record and handoff

## Outcome contract

A PASS is reported as `ENGINEERING_RELEASE_CANDIDATE`. It authorizes only the
next controlled Word-report construction phase. It does **not** create a Word
file, delivery ZIP, distribution artifact, certification claim or sea-trial
claim, and it does not enable final release scripts.
