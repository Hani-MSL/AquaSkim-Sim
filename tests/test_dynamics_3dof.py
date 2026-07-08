from aquaskim.config import load_base_configuration
from aquaskim.dynamics_3dof import CraftState, DynamicsSettings, PlanarCatamaranDynamics, ThrusterCommand
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases


def _model() -> PlanarCatamaranDynamics:
    config = load_base_configuration(); data = config.data
    geometry = CatamaranGeometry.from_config(data)
    hydro = CatamaranHydrostatics(geometry, HydrostaticSettings.from_config(data))
    _, full = build_load_cases(data)["full_design_payload"]
    case = hydro.case_from_mass_properties("full", full)
    resistance = CatamaranResistanceModel(geometry, HydrodynamicSettings.from_config(data), case)
    return PlanarCatamaranDynamics(geometry=geometry, resistance=resistance, hydro_case=case, mass_properties=full, settings=DynamicsSettings.from_config(data))


def test_zero_command_and_zero_current_hold_rest_state() -> None:
    model = _model(); state = CraftState()
    derivative = model.derivatives(state, ThrusterCommand(0.0, 0.0), (0.0, 0.0))
    assert derivative.u_mps == 0.0
    assert derivative.v_mps == 0.0
    assert derivative.r_rps == 0.0


def test_symmetric_thrust_creates_positive_surge_without_yaw() -> None:
    model = _model(); derivative = model.derivatives(CraftState(), ThrusterCommand(1.0, 1.0), (0.0, 0.0))
    assert derivative.u_mps > 0.0
    assert abs(derivative.r_rps) < 1e-12


def test_differential_thrust_creates_yaw_acceleration() -> None:
    model = _model(); derivative = model.derivatives(CraftState(), ThrusterCommand(0.5, 1.5), (0.0, 0.0))
    assert derivative.r_rps > 0.0


def test_current_is_subtracted_from_relative_water_velocity() -> None:
    model = _model(); u_rel, v_rel = model.relative_water_velocity_body(CraftState(u_mps=0.4), (0.1, 0.2))
    assert abs(u_rel - 0.3) < 1e-12
    assert abs(v_rel + 0.2) < 1e-12


def test_low_speed_drag_extension_is_finite_during_stop_turn_go() -> None:
    from aquaskim.config import load_base_configuration
    from aquaskim.phase08 import _build_model
    from aquaskim.dynamics_3dof import CraftState

    model, *_ = _build_model(load_base_configuration())
    x_drag, y_drag, n_drag = model.hydrodynamic_forces(
        CraftState(u_mps=1.0e-4),
        (0.0, 0.0),
    )
    assert all(abs(value) < 1.0 for value in (x_drag, y_drag, n_drag))
