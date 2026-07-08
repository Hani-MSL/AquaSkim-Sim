# Patch 10.19.1 — Delivery Reproduction Script Hotfix

This hotfix repairs the final delivery packaging precondition that failed when the required Patch 10.15 reproduction script was missing or empty in the local working tree.

## Scope
- Restores required reproduction scripts used by the delivery package manifest.
- Adds an explicit reproduction-script preflight before the long pre-delivery test suite.
- Adds a delivery-module preflight that reports all missing or empty reproduction scripts together.
- Updates the canonical project version to `1.6.19`.
- Keeps the final package as a course-project delivery package only.

## Not changed
- No mission simulation is added.
- No GIF/MP4 rendering is added.
- No Word regeneration is required.
- No certification, sea-trial or hardware-commissioning claim is created.

## Run

```bat
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_19_independent_rebuild_and_delivery.bat
```
