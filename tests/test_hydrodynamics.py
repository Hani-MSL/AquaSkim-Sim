import math

from aquaskim.config import load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases


def _model() -> CatamaranResistanceModel:
    config = load_base_configuration()
    geometry = CatamaranGeometry.from_config(config.data)
    hydro = CatamaranHydrostatics(geometry, HydrostaticSettings.from_config(config.data))
    cases = build_load_cases(config.data)
    full_case = hydro.case_from_mass_properties("full", cases["full_design_payload"][1])
    return CatamaranResistanceModel(geometry, HydrodynamicSettings.from_config(config.data), full_case)


def test_resistance_is_zero_at_zero_speed_and_positive_afterward() -> None:
    model = _model()
    assert model.state_at_speed(0.0).total_resistance_n == 0.0
    assert model.state_at_speed(0.45).total_resistance_n > 0.0


def test_total_resistance_is_monotonic_over_design_range() -> None:
    model = _model()
    values = [model.state_at_speed(speed).total_resistance_n for speed in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)]
    assert values == sorted(values)


def test_reynolds_and_froude_increase_with_speed() -> None:
    model = _model()
    slow, fast = model.state_at_speed(0.25), model.state_at_speed(0.55)
    assert fast.reynolds_number > slow.reynolds_number
    assert fast.froude_number > slow.froude_number
    assert slow.friction_coefficient > 0.0


def test_wetted_area_and_added_mass_are_positive() -> None:
    model = _model()
    assert model.wetted_surface_area_m2 > 0.0
    assert math.isclose(model.surge_added_mass_kg(3.8), 0.456, abs_tol=1e-12)
