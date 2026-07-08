# Patch 10.11 — Reference Mission Fidelity and Visual Evidence Upgrade

## Scope

- Adds a non-interactive fidelity audit for nominal and high-loading reference missions.
- Adds six long-form GIF/MP4 replays and a six-row contact sheet.
- Adds state-segment, regime-segment and event-ledger CSV evidence.
- Adds a fixed launch/search interval before the first local debris diversion.
- Leaves Word, delivery ZIP and release scripts disabled.

## Validation order

The patch script enforces: YAML parse → import audit → compileall → full pytest →
reference mission/media generation. No media command executes if an earlier gate fails.
