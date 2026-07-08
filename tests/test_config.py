from aquaskim.config import load_base_configuration, load_scenario


def test_base_configuration_loads_and_is_valid() -> None:
    config = load_base_configuration()
    assert config.project_name == "AquaSkim-Sim"
    assert config.hull_length_m > 0.0
    assert len(config.mass_components) >= 10


def test_all_phase_01_scenarios_load() -> None:
    for scenario_name in ("calm_water", "lateral_current", "obstacles", "low_battery"):
        scenario = load_scenario(scenario_name)
        assert scenario["scenario"]["id"] == scenario_name
        assert scenario["scenario"]["duration_s"] > 0.0
