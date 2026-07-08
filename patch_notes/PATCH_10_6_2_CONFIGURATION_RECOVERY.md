# Patch 10.6.2 — Configuration Recovery

## Repairs
- restores `config/base_parameters.yaml`
- restores source-level `aquaskim.paths`
- adds all evidence-directory aliases required by existing phases
- makes official configuration loading non-interactive by default
- aligns package version labels to `1.6.2`
- adds configuration and path-contract tests

## Deliberate limitation
The patch does not run Phase 10.6 automatically. Recovery must pass first;
mission dynamics and animation quality will be executed only in the next
validated patch.
