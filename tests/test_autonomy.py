from aquaskim.autonomy import AgentState, AutonomousMission, AutonomySettings
from aquaskim.config import load_base_configuration
from aquaskim.dynamics_3dof import DynamicsSettings, PlanarCatamaranDynamics
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.environment import EnvironmentSettings, SensorSettings
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases


def _mission() -> AutonomousMission:
    config = load_base_configuration(); data = config.data
    geometry = CatamaranGeometry.from_config(data)
    hydro = CatamaranHydrostatics(geometry, HydrostaticSettings.from_config(data))
    _, full_mass = build_load_cases(data)["full_design_payload"]
    case = hydro.case_from_mass_properties("full_design_payload", full_mass)
    resistance = CatamaranResistanceModel(geometry, HydrodynamicSettings.from_config(data), case)
    model = PlanarCatamaranDynamics(
        geometry=geometry,
        resistance=resistance,
        hydro_case=case,
        mass_properties=full_mass,
        settings=DynamicsSettings.from_config(data),
    )
    battery_settings = BatterySettings.from_config(data)
    environment = EnvironmentSettings.from_config(data)
    return AutonomousMission(
        model=model,
        environment=environment,
        sensor_settings=SensorSettings.from_config(data),
        battery=BatteryModel(battery_settings),
        battery_settings=battery_settings,
        energy_settings=EnergySettings.from_config(data),
        settings=AutonomySettings.from_config(data),
        debris=environment.generate_debris(),
    )


def test_closed_loop_mission_is_deterministic_and_docks_safely() -> None:
    first = _mission().run()
    second = _mission().run()

    assert first.metrics["mission_success"] == 1
    assert first.metrics["final_state"] == AgentState.MISSION_COMPLETE.value
    assert first.metrics["collected_count"] >= 1
    assert first.metrics["minimum_hazard_distance_m"] > 0.0
    assert first.metrics == second.metrics


def test_mission_log_contains_required_state_transitions() -> None:
    result = _mission().run()
    transitions = {(row["from_state"], row["to_state"]) for row in result.event_rows}

    assert (AgentState.INIT.value, AgentState.SEARCH.value) in transitions
    assert (AgentState.SEARCH.value, AgentState.TRANSIT_TO_DEBRIS.value) in transitions
    assert (AgentState.TRANSIT_TO_DEBRIS.value, AgentState.COLLECT.value) in transitions
    assert any(to_state == AgentState.RETURN_HOME.value for _, to_state in transitions)
    assert result.rows[-1]["state"] == AgentState.MISSION_COMPLETE.value
