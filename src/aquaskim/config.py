from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aquaskim.paths import DIRECTORIES
from aquaskim.project_profile import deep_merge, load_user_profile


class ConfigurationError(ValueError):
    """Raised when a project configuration file is incomplete or invalid."""


@dataclass(frozen=True)
class ProjectConfiguration:
    source_path: Path
    data: dict[str, Any]

    @property
    def project_name(self) -> str:
        return str(self.data["project"]["name"])

    @property
    def project_version(self) -> str:
        return str(self.data["project"]["version"])

    @property
    def hull_length_m(self) -> float:
        return float(self.data["mechanical"]["geometry"]["hull_length_m"])

    @property
    def hull_width_m(self) -> float:
        return float(self.data["mechanical"]["geometry"]["hull_width_m"])

    @property
    def hull_height_m(self) -> float:
        return float(self.data["mechanical"]["geometry"]["hull_height_m"])

    @property
    def mass_components(self) -> list[dict[str, Any]]:
        return list(self.data["mass_budget"]["components"])


REQUIRED_PATHS: tuple[tuple[str, ...], ...] = (
    ("project", "name"), ("project", "version"),
    ("mission", "environment", "length_m"), ("mission", "environment", "width_m"),
    ("mechanical", "architecture"),
    ("mechanical", "geometry", "hull_length_m"),
    ("mechanical", "geometry", "hull_width_m"),
    ("mechanical", "geometry", "hull_height_m"),
    ("mass_budget", "components"),
    ("hydrostatics", "water_density_kg_m3"),
    ("hydrodynamics", "kinematic_viscosity_m2ps"),
    ("propulsion", "thruster", "max_thrust_per_side_n"),
    ("propulsion", "thruster", "max_power_per_side_w"),
    ("energy", "battery", "capacity_ah"),
    ("energy", "battery", "dc_bus_efficiency"),
    ("energy", "model", "integration_time_step_s"),
    ("simulation", "time_step_s"),
    ("dynamics_3dof", "added_mass_fraction_sway"),
    ("dynamics_3dof", "integration_time_step_s"),
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)
    if not isinstance(parsed, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return parsed


def _require_path(data: dict[str, Any], path_parts: tuple[str, ...]) -> None:
    node: Any = data
    for part in path_parts:
        if not isinstance(node, dict) or part not in node:
            raise ConfigurationError(f"Missing required configuration key: {'.'.join(path_parts)}")
        node = node[part]


def _positive(mapping: dict[str, Any], keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        if float(mapping[key]) <= 0.0:
            raise ConfigurationError(f"{prefix}.{key} must be positive.")


def validate_base_configuration(data: dict[str, Any]) -> None:
    """Validate project-wide invariants before a numerical phase starts."""
    for path_parts in REQUIRED_PATHS:
        _require_path(data, path_parts)

    geometry = data["mechanical"]["geometry"]
    _positive(geometry, ("hull_length_m", "hull_width_m", "hull_height_m", "hull_spacing_center_m"), "mechanical.geometry")

    environment = data["mission"]["environment"]
    _positive(environment, ("length_m", "width_m"), "mission.environment")

    components = data["mass_budget"]["components"]
    if not isinstance(components, list) or not components:
        raise ConfigurationError("mass_budget.components must be a non-empty list.")
    for component in components:
        if not isinstance(component, dict):
            raise ConfigurationError("Every mass component must be a mapping.")
        if float(component.get("mass_kg", 0.0)) <= 0.0:
            raise ConfigurationError(f"Component {component.get('name', '<unnamed>')} must have positive mass_kg.")
        position = component.get("position_m")
        if not isinstance(position, list) or len(position) != 3:
            raise ConfigurationError(f"Component {component.get('name', '<unnamed>')} needs a 3-element position_m.")

    hydro = data["hydrodynamics"]
    _positive(hydro, (
        "water_density_kg_m3", "kinematic_viscosity_m2ps", "wetted_surface_shape_factor",
        "form_factor", "residual_resistance_coefficient", "appendage_drag_area_m2",
        "appendage_drag_coefficient", "collector_immersed_depth_m", "collector_drag_coefficient",
        "added_mass_fraction_surge", "analysis_speed_max_mps", "analysis_speed_points",
        "head_current_max_mps", "head_current_points", "minimum_thrust_reserve_ratio",
        "max_recommended_rpm_fraction",
    ), "hydrodynamics")
    if float(hydro["max_recommended_rpm_fraction"]) > 1.0:
        raise ConfigurationError("hydrodynamics.max_recommended_rpm_fraction must not exceed 1.")

    thruster = data["propulsion"]["thruster"]
    _positive(thruster, ("count", "max_thrust_per_side_n", "max_power_per_side_w", "max_rpm", "thrust_coefficient_n_per_rpm2"), "propulsion.thruster")
    if int(thruster["count"]) != 2:
        raise ConfigurationError("This conceptual twin-thruster architecture requires propulsion.thruster.count = 2.")

    battery = data["energy"]["battery"]
    _positive(battery, ("nominal_voltage_v", "capacity_ah", "usable_fraction", "nominal_energy_wh", "capacity_derating_factor", "dc_bus_efficiency", "peukert_exponent", "reference_current_a", "max_continuous_discharge_current_a", "min_pack_voltage_v", "max_pack_voltage_v"), "energy.battery")
    if float(battery["usable_fraction"]) > 1.0 or float(battery["capacity_derating_factor"]) > 1.0 or float(battery["dc_bus_efficiency"]) > 1.0:
        raise ConfigurationError("Energy fractions and efficiencies must not exceed 1.")
    if float(battery["max_pack_voltage_v"]) <= float(battery["min_pack_voltage_v"]):
        raise ConfigurationError("energy.battery.max_pack_voltage_v must exceed min_pack_voltage_v.")
    energy_model = data["energy"]["model"]
    _positive(energy_model, ("integration_time_step_s", "analysis_duration_s", "safety_reserve_energy_wh", "return_speed_mps", "return_distance_max_m", "return_distance_points", "minimum_endurance_at_cruise_min", "minimum_soc_after_nominal_mission"), "energy.model")
    if not 0.0 < float(energy_model["minimum_soc_after_nominal_mission"]) <= 1.0:
        raise ConfigurationError("energy.model.minimum_soc_after_nominal_mission must be in (0, 1].")

    if float(data["simulation"]["time_step_s"]) <= 0.0:
        raise ConfigurationError("simulation.time_step_s must be positive.")

    dynamics = data["dynamics_3dof"]
    _positive(dynamics, (
        "added_mass_fraction_sway", "added_yaw_inertia_fraction",
        "sway_linear_damping_n_per_mps", "sway_quadratic_damping_n_per_mps2",
        "yaw_linear_damping_n_m_per_rps", "yaw_quadratic_damping_n_m_per_rps2",
        "max_simulation_time_s", "integration_time_step_s", "trajectory_sample_interval_s",
        "current_crossflow_mps", "cruise_thrust_multiplier",
        "turn_left_thrust_multiplier", "turn_right_thrust_multiplier",
        "turn_start_s", "turn_end_s", "scenario_start_delay_s",
        "straight_line_cross_track_limit_m", "maximum_expected_yaw_rate_rps",
        "steady_speed_tolerance_mps",
    ), "dynamics_3dof")
    if float(dynamics["turn_end_s"]) <= float(dynamics["turn_start_s"]):
        raise ConfigurationError("dynamics_3dof.turn_end_s must exceed turn_start_s.")
    if float(dynamics["trajectory_sample_interval_s"]) < float(dynamics["integration_time_step_s"]):
        raise ConfigurationError("dynamics_3dof.trajectory_sample_interval_s must be >= integration_time_step_s.")


def load_base_configuration(path: Path | None = None, *, apply_local_profile: bool = False) -> ProjectConfiguration:
    # Official builds are deterministic: local user profiles are ignored unless
    # a research caller explicitly asks for apply_local_profile=True.
    source_path = path or (DIRECTORIES["config"] / "base_parameters.yaml")
    data = _read_yaml(source_path)
    if apply_local_profile and path is None:
        profile = load_user_profile()
        if profile is not None:
            data = deep_merge(data, profile["overrides"])
    validate_base_configuration(data)
    return ProjectConfiguration(source_path=source_path, data=data)


def load_scenario(scenario_name: str) -> dict[str, Any]:
    path = DIRECTORIES["config"] / "scenarios" / f"{scenario_name}.yaml"
    scenario = _read_yaml(path)
    if "scenario" not in scenario or "environment" not in scenario or "mission" not in scenario:
        raise ConfigurationError(f"Scenario is incomplete: {path}")
    return scenario
