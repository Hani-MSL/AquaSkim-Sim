# Patch 10.5 — Scientific Configuration Refactor

## Why this patch exists
The earlier interactive wizard incorrectly asked for personal report metadata and a fixed collection quota. Neither belongs in a public GitHub configuration workflow or a physically meaningful autonomous-cleaning experiment.

## Changes

- removes student/course/institution prompts and profile storage;
- separates public scientific experiment configuration from private report metadata;
- replaces manual debris-count input with debris surface density [items/m²] plus mass distribution;
- introduces physical hopper semantics: usable volume, payload mass limit and packing factor;
- changes `bootstrap_and_build.bat` into a safe development guard so it does not launch a premature full rebuild;
- adds a configuration contract and tests.

## Deliberate limitation
This patch establishes the correct configuration semantics. The next mission-model patch will connect hopper mass/volume limits to the closed-loop mission termination logic and replaces the legacy fixed collection quota inside the simulator.
