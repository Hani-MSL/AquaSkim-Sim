import math

from aquaskim.config import load_base_configuration
from aquaskim.environment import (
    EnvironmentSettings,
    SensorSettings,
    forward_range_measurements,
    raycast_distance_m,
    simulate_sensor_demo,
)


def _models():
    config = load_base_configuration()
    return config, EnvironmentSettings.from_config(config.data), SensorSettings.from_config(config.data)


def test_debris_generation_is_deterministic_and_hazard_aware() -> None:
    _, environment, _ = _models()
    first = environment.generate_debris()
    second = environment.generate_debris()
    assert first == second
    assert len(first) == environment.debris_count
    for item in first:
        assert environment.point_is_navigable(
            *item.position_m,
            clearance_m=item.radius_m + environment.debris_clearance_m,
        )


def test_occupancy_grid_contains_boundaries_and_hazards() -> None:
    _, environment, _ = _models()
    grid = environment.occupancy_grid()
    assert grid.occupied.any()
    assert grid.occupied[0, 0]
    assert grid.occupied[-1, -1]
    assert not grid.occupied_fraction >= 1.0


def test_raycast_stops_at_basin_boundary() -> None:
    _, environment, settings = _models()
    distance = raycast_distance_m(
        environment,
        environment.length_m - 0.10,
        environment.width_m / 2.0,
        0.0,
        max_range_m=settings.range_sensor_max_range_m,
        step_m=settings.range_sensor_step_m,
    )
    assert 0.08 <= distance <= 0.14


def test_forward_range_has_expected_beam_count() -> None:
    _, environment, settings = _models()
    beams = forward_range_measurements(environment, 1.0, 1.0, 0.0, settings)
    assert len(beams) == settings.range_sensor_beam_count
    assert all(0.0 <= distance <= settings.range_sensor_max_range_m for _, distance in beams)


def test_sensor_demo_is_repeatable_and_stays_safe() -> None:
    config, environment, settings = _models()
    debris = environment.generate_debris()
    first, first_detect, _ = simulate_sensor_demo(
        environment,
        settings,
        debris,
        cruise_speed_mps=float(config.data["propulsion"]["limits"]["target_cruise_speed_mps"]),
        random_seed=int(config.data["project"]["random_seed"]) + 700,
    )
    second, second_detect, _ = simulate_sensor_demo(
        environment,
        settings,
        debris,
        cruise_speed_mps=float(config.data["propulsion"]["limits"]["target_cruise_speed_mps"]),
        random_seed=int(config.data["project"]["random_seed"]) + 700,
    )
    assert first == second
    assert first_detect == second_detect
    assert all(environment.point_is_navigable(float(row["truth_x_m"]), float(row["truth_y_m"]), clearance_m=environment.robot_safety_radius_m) for row in first)
