# Contributing

Thanks for improving AquaSkim-Sim.

## Local checks

```bat
conda env create -f environment.yml
conda activate aquaskim-sim
python -m pip install --editable . --no-build-isolation --no-deps
python -m pytest -q
python -m aquaskim.github_readiness
```

## Generated files

Do not commit generated outputs, records, videos, Word reports, delivery ZIPs, caches, or local metadata. They are intentionally ignored by Git and can be regenerated with:

```bat
scripts\run_from_zero_to_delivery.bat
```

## Model-boundary language

Do not describe the project as certified hardware or sea-trial validated. Keep the documented numerical-model boundary in reports and README changes.
