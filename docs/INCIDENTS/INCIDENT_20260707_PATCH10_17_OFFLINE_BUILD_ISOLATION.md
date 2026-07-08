# Incident: Patch 10.17 PEP 517 build-isolation network dependency

## Observation

The Patch 10.17 runner stopped before YAML/import/test/release-gate checks while
`pip install --editable .` attempted to resolve `setuptools>=69` from PyPI.
DNS lookup for `pypi.org` failed.

## Root cause

PEP 517 build isolation creates a temporary build environment and may request
build requirements from an index. The `aquaskim-sim` Conda environment already
contains the required build tools, so network acquisition is unnecessary for the
local editable install used by this audit-only gate.

## Corrective action

Patch 10.17.1 uses:

```bat
python -m pip install --editable . --no-build-isolation --no-deps
```

and disables pip's version-check lookup during this command.

## Verification

The revised local editable-install command completed successfully in a staged
copy. Targeted Release Gate tests passed (`4 passed`), and the audit-only gate
reported `PASS` / `ENGINEERING_RELEASE_CANDIDATE` with final release disabled.
