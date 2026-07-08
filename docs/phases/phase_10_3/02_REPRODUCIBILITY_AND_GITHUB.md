# One-command reproducibility and GitHub contract

## Public repository contents
Commit source code, base configuration, documentation, tests, scripts and dependency files. Do **not** commit generated outputs, evidence records, local profile or personal report metadata.

## One-command entry point

```bat
scripts\bootstrap_and_build.bat
```

The command:

1. checks for Conda;
2. creates `aquaskim-sim` from `environment.yml` if missing;
3. installs the local package;
4. runs a syntax gate;
5. asks for the local project profile;
6. writes `config/user_profile.yaml` locally;
7. rebuilds Phase 02 through Phase 10.3;
8. stores phase evidence, input snapshots, SHA-256 manifests and handoffs;
9. writes a build-session manifest under `records/builds/`.

## Scope of interactive inputs
The wizard exposes values supported by the current model: basin dimensions, water depth, current vector, hull dimensions, hull spacing, design payload, battery capacity, initial SOC, collection quota, mission duration, lane spacing, cruise and return speeds, safety radius, Monte Carlo count and rendering controls.

Changing architecture class, hull topology, number of thrusters, or replacing the analytic environment is outside the current validated model family and requires source changes plus renewed validation.
