import math

from aquaskim.config import load_base_configuration
from aquaskim.propulsion import ThrusterSettings, TwinThrusterModel


def _model() -> TwinThrusterModel:
    return TwinThrusterModel(ThrusterSettings.from_config(load_base_configuration().data))


def test_max_rpm_matches_configured_max_thrust_within_design_tolerance() -> None:
    model = _model()
    derived = model.settings.derived_max_thrust_per_side_n
    assert math.isclose(derived, model.settings.max_thrust_per_side_n, abs_tol=0.05)


def test_thrust_and_power_increase_with_rpm() -> None:
    model = _model()
    assert model.total_thrust_at_rpm(3000.0) > model.total_thrust_at_rpm(1500.0)
    assert model.total_electrical_power_at_rpm(3000.0) > model.total_electrical_power_at_rpm(1500.0)


def test_symmetric_operating_point_for_cruise_is_feasible() -> None:
    model = _model()
    point = model.symmetric_operating_point(2.0)
    assert point.feasible
    assert 0.0 < point.throttle_fraction < 1.0
    assert point.total_thruster_power_w > 0.0
