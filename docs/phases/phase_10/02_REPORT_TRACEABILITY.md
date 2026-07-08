# Report Traceability

Every number inserted into the final Word report is loaded from one of the following sources:

- `config/base_parameters.yaml`
- `outputs/logs/phase02_mechanical_summary.json`
- `outputs/logs/phase03_hydrostatic_summary.json`
- `outputs/logs/phase04_propulsion_summary.json`
- `outputs/logs/phase05_energy_summary.json`
- `outputs/logs/phase06_dynamics_summary.json`
- `outputs/logs/phase07_environment_summary.json`
- `outputs/logs/phase08_autonomy_summary.json`
- `outputs/logs/phase09_validation_summary.json`

Every embedded figure is hashed in `outputs/reports/phase10_report_build_manifest.json`. Therefore the report remains traceable to its source figures and numerical summaries.
