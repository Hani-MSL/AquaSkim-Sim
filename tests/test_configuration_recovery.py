from aquaskim.config import load_base_configuration
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories


def test_complete_engineering_baseline_loads_without_local_profile() -> None:
    config = load_base_configuration()
    assert config.project_name == "AquaSkim-Sim"
    assert config.hull_length_m > 0.0
    assert config.data["hydrostatics"]["water_density_kg_m3"] > 0.0
    assert config.data["hydrodynamics"]["kinematic_viscosity_m2ps"] > 0.0
    assert config.data["autonomy"]["mission_duration_s"] > 0.0


def test_paths_contract_includes_existing_and_reference_evidence_locations() -> None:
    ensure_runtime_directories()
    for key in (
        "phase02_records",
        "phase08_records",
        "phase08_2_records",
        "phase09_2_records",
        "phase10_records",
        "phase10_4_records",
        "phase10_6_records",
        "handoffs",
        "build_records",
    ):
        assert key in DIRECTORIES
        assert DIRECTORIES[key].exists()
