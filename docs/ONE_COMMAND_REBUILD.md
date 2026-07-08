# One-command rebuild

The public GitHub workflow is designed so generated artifacts are not committed. A user clones the repo and runs one command:

```bat
scripts\run_from_zero_to_delivery.bat
```

The command creates/activates the Conda environment, installs the package, removes stale generated folders, rebuilds all evidence, creates a Word report, and assembles the final delivery ZIP.

Final output:

```text
outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
```

The rebuild is intentionally longer than a unit-test run because it regenerates numerical evidence, figures, GIF/MP4 media, report assets, and manifests.
