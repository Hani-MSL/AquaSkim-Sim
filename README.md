# AquaSkim-Sim

[![CI](https://github.com/Hani-MSL/AquaSkim-Sim/actions/workflows/ci.yml/badge.svg)](https://github.com/Hani-MSL/AquaSkim-Sim/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**AquaSkim-Sim** is a reproducible engineering simulation project for an autonomous catamaran surface robot that collects floating debris in sheltered water. The repository covers mechanical architecture, hydrostatics, low-speed 3-DOF dynamics, propulsion and energy modelling, mission planning, current-aware control, validation, visualization, report generation, and delivery-package assembly.

> **Scope boundary:** the repository provides numerical simulation evidence only. It does not claim sea-trial certification, wave-response validation, onboard current-estimator validation, hardware commissioning, or safety approval.

<p align="center">
  <img src="assets/aquaskim_system_overview.svg" width="31%" alt="AquaSkim system overview" />
  <img src="assets/aquaskim_mission_evidence.svg" width="31%" alt="Reference mission evidence" />
  <img src="assets/aquaskim_validation_summary.svg" width="31%" alt="Validation summary" />
</p>

Persian guide: [`README_FA.md`](README_FA.md)

## Highlights

- deterministic reference design and versioned scenario configuration,
- low-speed planar 3-DOF vessel dynamics,
- hydrostatic, propulsion, payload, and energy calculations,
- mission planning and differential-thrust control,
- current-aware operating-envelope and robustness studies,
- reproducible figures, CSV tables, GIF/MP4 evidence, and contact sheets,
- automated English Word report generation,
- SHA-256 verified final delivery ZIP,
- automated source-integrity and regression checks.

## Quick start

### Windows

Install **Git** and **Miniconda** or **Mambaforge**, open a new Command Prompt, and run:

```bat
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
scripts\run_from_zero_to_delivery.bat
```

### Linux/macOS

```bash
git clone https://github.com/Hani-MSL/AquaSkim-Sim.git
cd AquaSkim-Sim
bash scripts/run_from_zero_to_delivery.sh
```

The script creates or updates the `aquaskim-sim` Conda environment, installs the project, removes stale generated artifacts, runs the complete simulation and validation pipeline, builds the Word report, and assembles the delivery package.

Expected final artifact:

```text
outputs/deliverables/AquaSkim-Sim_Final_Delivery_v1.6.21.zip
```

The first run requires internet access for dependency installation. A full rebuild can be time-consuming because it generates figures, animations, videos, tables, QA manifests, the report, and the final archive.

## Output structure

```text
outputs/
├── figures/                 engineering plots and mission figures
├── animations/              GIF simulation replays
├── videos/                  MP4 simulation replays
├── tables/                  CSV evidence and summary tables
├── reports/                 generated reports and build manifests
├── logs/                    machine-readable QA and validation records
├── presentation_evidence/   curated presentation media
└── deliverables/            final ZIP, manifest, checksums, and audit report
```

Generated artifacts are intentionally excluded from Git because they are reproducible from source.

## Validation and tests

Run the lightweight checks and test suite with:

```bat
conda activate aquaskim-sim
python -m aquaskim.integrity_audit report
python -m aquaskim.github_readiness
python -m aquaskim.rebuild_from_zero --dry-run
python -m pytest -q
```

On a clean clone, tests that require generated media or the final delivery package are skipped until a complete rebuild has been executed.

## Repository layout

```text
src/aquaskim/   simulation, dynamics, control, reporting, and packaging code
config/         versioned reference-design and scenario configuration
tests/          unit, regression, and contract tests
scripts/        public execution entrypoints
docs/           modelling, assumptions, validation, and reproducibility notes
assets/         lightweight diagrams used by the documentation
outputs/        generated locally and ignored by Git
records/        generated local run records and ignored by Git
```

## Documentation

- [Project overview](docs/PROJECT_OVERVIEW.md)
- [Modelling and validation](docs/MODELING_AND_VALIDATION.md)
- [Reference design and parameter rationale](docs/REFERENCE_DESIGN_AND_PARAMETER_RATIONALE.md)
- [Reference mission calibration](docs/REFERENCE_MISSION_CALIBRATION.md)
- [Maneuver verification protocol](docs/MANEUVER_VERIFICATION_PROTOCOL.md)
- [Configuration and reproducibility](docs/CONFIGURATION_AND_GITHUB_REPRODUCIBILITY.md)
- [Model scope and limitations](docs/MODEL_SCOPE_AND_LIMITATIONS.md)
- [Output previews](docs/OUTPUT_PREVIEWS.md)

## Optional report metadata

To include local name/course metadata in the generated Word report:

```bat
copy config\report_metadata.template.json config\report_metadata.json
```

Edit `config/report_metadata.json`. The local file is ignored by Git.

## Citation

Citation metadata is provided in [`CITATION.cff`](CITATION.cff).

## License

MIT License. See [`LICENSE`](LICENSE).
