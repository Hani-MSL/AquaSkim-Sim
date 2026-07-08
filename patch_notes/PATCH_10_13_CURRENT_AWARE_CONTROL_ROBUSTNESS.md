# Patch 10.13 — Current-aware control robustness

## Purpose

Add a bounded dynamic-control verification layer after the source-integrity,
reference-fidelity and operating-envelope work.

## Adds

- fixed earth-track cross-current comparison;
- open-loop versus current-aware replay;
- logged heading, crab, yaw, thrust and cross-track metrics;
- a 3 × 3 bounded heading-gain sensitivity grid;
- engineering figures, GIFs, MP4s and a multi-frame contact sheet;
- acceptance checks derived only from logged state histories;
- evidence snapshot, input copy, SHA-256 manifest and handoff.

## Reference-policy loader recovery

The audit found that `reference_mission` was stored beside the physical override
block in `reference_design.yaml`, but the loader previously merged only
`overrides`. Patch 10.13 now merges the versioned reference policy explicitly
into the effective non-interactive configuration. This activates the documented
stop-turn-go, guidance and low-speed current-compensation policy rather than
silently falling back to generic defaults.

Because this affects reference execution, the Patch runner renews the 10.11 and
10.12 reference evidence before creating the new control-robustness artifacts.

## Explicit exclusions

- Word report;
- delivery ZIP;
- final release build;
- user-profile input;
- historical quota-based autonomy modules.
