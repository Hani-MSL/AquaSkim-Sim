from aquaskim.config import load_base_configuration
from aquaskim.environment import EnvironmentSettings
from aquaskim.planner import AStarPlanner


def test_astar_route_stays_in_free_configuration_space() -> None:
    config = load_base_configuration()
    environment = EnvironmentSettings.from_config(config.data)
    planner = AStarPlanner(environment.occupancy_grid())
    path = planner.plan(environment.home_position_m, (5.66, 1.24))

    assert path.length_m > 0.0
    assert path.expanded_nodes > 0
    assert all(not planner.occupied(cell) for cell in path.grid_indices)


def test_planner_uses_deterministic_route_for_same_map_and_points() -> None:
    config = load_base_configuration()
    environment = EnvironmentSettings.from_config(config.data)
    planner = AStarPlanner(environment.occupancy_grid())
    first = planner.plan(environment.home_position_m, (5.66, 1.24))
    second = planner.plan(environment.home_position_m, (5.66, 1.24))

    assert first.grid_indices == second.grid_indices
    assert first.waypoints_m == second.waypoints_m
