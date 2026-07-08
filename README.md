# AquaSkim-Sim

AquaSkim-Sim is an educational engineering simulation project for an autonomous catamaran surface-cleaning robot. It builds a low-speed 3-DOF sheltered-basin digital-twin workflow, generates reference mission evidence, curates figures and animations, builds a final Word report, and assembles an auditable delivery package.

> **Scope boundary:** this repository contains numerical simulation evidence only. It is **not** sea-trial footage, a certification package, wave-response validation, onboard current-estimator validation, or hardware commissioning proof.

The primary user guide is Persian: see [`README_FA.md`](README_FA.md). This English README is a compact companion.

## What this project produces

A clean rebuild creates a new local `outputs/` folder containing:

- reference mission reports and CSV tables,
- high-quality figures,
- GIF/MP4 visual evidence generated locally,
- presentation evidence contact sheets,
- an engineering release-candidate gate,
- a final Word report in English,
- a final delivery ZIP with SHA-256 manifests.

Generated artifacts are intentionally ignored by Git. They are reproducible outputs, not source files.

## Prerequisites

Install these first:

1. **Git**, for cloning the repository.
2. **Miniconda** or **Mambaforge**, for creating the Python environment.
3. Windows 10/11 is the primary supported path for the `.bat` command.

The project script creates or updates the Conda environment, installs the Python dependencies, installs the package in editable mode, cleans previous local outputs, and regenerates the full output tree. It does not install Git or Miniconda/Mambaforge for you.

## Quick start: one command on Windows

Open a fresh Command Prompt and run:

```bat
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
scripts\run_from_zero_to_delivery.bat
```

The script will:

1. create or activate the `aquaskim-sim` Conda environment,
2. update the existing environment from `environment.yml` when it already exists,
3. install/synchronize dependencies such as `numpy`, `scipy`, `pandas`, `matplotlib`, `python-docx`, `imageio`, and `ffmpeg`,
4. install the package in editable mode,
5. clean old generated `outputs/` and `records/`,
6. regenerate all evidence from source,
7. build the final English Word report,
8. create the final delivery ZIP.

Expected final artifact:

```text
outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
```

The full rebuild may take a while because it generates figures, GIFs, MP4s, CSV tables, QA manifests, the Word report, and the final package.

## Linux/macOS quick start

Windows is the primary supported path, but a shell entry point is also included:

```bash
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
bash scripts/run_from_zero_to_delivery.sh
```

This script also creates or updates the Conda environment before running the full rebuild.

## Manual environment setup

```bat
conda env create -f environment.yml
conda activate aquaskim-sim
python -m pip install --editable . --no-build-isolation --no-deps
```

Then run either:

```bat
python -m aquaskim.rebuild_from_zero
```

or:

```bat
python -m aquaskim rebuild-from-zero
```

## Check the planned pipeline without generating files

```bat
python -m aquaskim.rebuild_from_zero --list-steps
```

## Repository layout

```text
src/aquaskim/      Python package and simulation/reporting modules
config/           Reference model and visualization configuration
tests/            Regression and contract tests
scripts/          Windows and shell entry points
docs/             Method notes, incidents, phase documentation, GitHub guide
outputs/          Generated locally; ignored by Git
records/          Generated locally; ignored by Git
```

## Run tests only

```bat
conda activate aquaskim-sim
python -m pytest -q
```

On a fresh clone, output-dependent tests are skipped until the corresponding generated artifacts exist. After a full rebuild, the delivery-package tests should pass.

## Optional report metadata

The public repository includes only:

```text
config/report_metadata.template.json
```

To put your own name/course metadata in the generated Word report, copy it locally:

```bat
copy config\report_metadata.template.json config\report_metadata.json
```

Then edit `config\report_metadata.json`. This local file is ignored by Git.

## Final delivery package verification

After a successful rebuild, inspect:

```text
outputs\deliverables\FINAL_DELIVERY_PACKAGE_MANIFEST.json
outputs\deliverables\FINAL_DELIVERY_SHA256SUMS.txt
outputs\deliverables\final_delivery_package_audit.md
```

A valid final audit reports:

```text
DELIVERY_PACKAGE_READY
```

## Execution notes

- If `conda` is not recognized, install Miniconda/Mambaforge and open a new terminal.
- The first run needs internet access so Conda can download dependencies.
- Generated outputs are not committed; they are rebuilt locally by the one-command workflow.
- If the `aquaskim-sim` environment already exists, the script updates it from `environment.yml`.

## Non-claims

This repository explicitly does **not** claim:

- No sea-trial certification,
- No wave-response validation,
- No onboard current-estimator validation,
- No hardware commissioning.

## License

MIT License. See `LICENSE`.
