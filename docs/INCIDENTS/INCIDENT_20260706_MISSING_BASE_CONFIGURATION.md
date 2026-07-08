# Incident: missing `config/base_parameters.yaml`

## Symptom

The path contract succeeded, but the project stopped before numerical execution:

```text
[ERROR] Missing required file: config\base_parameters.yaml
```

## Root cause

The project folder contained phase-specific YAML files and local experiment
profiles, but the complete shared engineering baseline was absent. Every
numerical module relies on this baseline because it holds the geometry, mass,
hydrostatics, resistance, propulsion, energy, dynamics, sensing and autonomy
parameters.

## Corrective action

Patch 10.6.2 restores the complete versioned baseline from the last compatible
configuration revision. It also restores a comprehensive source-level path
module and adds direct recovery tests.

## Scope

This patch repairs project integrity only. It does not claim to validate the
new hopper-governed mission behaviour. That behaviour will be tested separately
after the recovered baseline has passed this gate.
