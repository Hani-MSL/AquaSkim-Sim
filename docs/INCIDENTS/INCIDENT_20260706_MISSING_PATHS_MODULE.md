# Incident: missing `aquaskim.paths` module

## Symptom

Running the reference-design mission failed before simulation started:

```text
ModuleNotFoundError: No module named 'aquaskim.paths'
```

## Root cause

The compatibility module that defines project-relative directory locations was
missing from the source tree even though multiple existing numerical phases
imported it. Some previous runs could appear healthy while compiled cache files
remained available, but a clean import correctly exposed the missing source
dependency.

## Corrective action

Patch 10.6.1 restores `src/aquaskim/paths.py`, provides all current and planned
evidence-directory aliases, and adds a pre-run contract check. The reference
mission cannot start until the project root, configuration folder, evidence
folder and `config/base_parameters.yaml` are all confirmed.

## Prevention

Every future recorded run executes:

```text
1. Editable package installation
2. Project path contract check
3. Python syntax gate
4. Numerical execution
5. Tests and evidence capture
```
