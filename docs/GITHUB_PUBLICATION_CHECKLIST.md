# GitHub publication checklist

Before publishing or merging to the default branch, verify:

- `python -m aquaskim.github_readiness` passes.
- `python -m pytest -q` passes on a clean clone.
- No generated `outputs/` or `records/` artifacts are committed.
- No local `config/report_metadata.json` or `config/user_profile.yaml` is committed.
- The README still includes the model-boundary and non-claim language.
- The one-command rebuild entry point remains `scripts\run_from_zero_to_delivery.bat`.
