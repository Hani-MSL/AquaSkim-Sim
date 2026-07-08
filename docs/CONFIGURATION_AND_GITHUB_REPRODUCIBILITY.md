# Configuration and GitHub Reproducibility

## Public repository contract
The committed repository contains source code, tests, default engineering inputs, scenario contracts and batch runners. It deliberately excludes generated outputs, Evidence folders and personal metadata.

## One-command interactive build
On Windows with Miniconda installed, a new user runs:

```bat
scripts\bootstrap_and_build.bat
```

The command:

1. checks Conda;
2. creates `aquaskim-sim` if necessary;
3. installs the project in editable mode;
4. performs a syntax gate;
5. asks for project metadata and engineering/missions settings;
6. writes a Git-ignored `config/user_profile.yaml`;
7. rebuilds the engineering phases and their Evidence packages; and
8. stores the execution log under `records/bootstrap/`.

## What the wizard asks
The interactive wizard covers course metadata, basin geometry, water depth, current vector, hull envelope, hull spacing, payload, battery capacity, mission duration, SOC, collection quota, lane spacing, vehicle speeds, safety radius, Monte Carlo count, validation envelope and animation quality.

## Advanced override policy
The profile file is YAML and recursively merged over `config/base_parameters.yaml`. A user may edit it after the first successful run to override any supported parameter while retaining the base file as an auditable default.

## Important boundary
The Word report and final delivery ZIP remain deferred until the final documentation/release phase. The engineering build already creates all numerical results, figures, animations, videos, Evidence manifests and handoffs required by current phases.
