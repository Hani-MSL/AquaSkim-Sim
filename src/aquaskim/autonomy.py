"""LEGACY quota-based autonomy branch.

This module is retained for historical Phase 08/09 artifacts and source
traceability.  It is intentionally excluded from the fixed reference build,
which uses :mod:`aquaskim.mission_quality` and capacity/energy/coverage-based
termination instead of ``max_collections``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any

import numpy as np

from aquaskim.dynamics_3dof import CraftState, PlanarCatamaranDynamics, ThrusterCommand, wrap_to_pi
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.environment import DebrisObject, EnvironmentSettings, SensorSettings, debris_detection_probability, is_inside_fov, wrap_angle_deg
from aquaskim.planner import AStarPlanner, PlannedPath, PlannerError


class AutonomyError(ValueError):
    """Raised when Phase 08 agent settings or a mission plan are invalid."""


class AgentState(str, Enum):
    INIT = "INIT"
    SEARCH = "SEARCH"
    TRANSIT_TO_DEBRIS = "TRANSIT_TO_DEBRIS"
    COLLECT = "COLLECT"
    RETURN_HOME = "RETURN_HOME"
    DOCK = "DOCK"
    MISSION_COMPLETE = "MISSION_COMPLETE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass(frozen=True)
class AutonomySettings:
    mission_duration_s: float
    integration_time_step_s: float
    control_period_s: float
    current_earth_mps: tuple[float, float]
    cruise_speed_mps: float
    approach_speed_mps: float
    return_speed_mps: float
    waypoint_tolerance_m: float
    collection_radius_m: float
    collection_hold_s: float
    max_collections: int
    initial_soc: float
    rth_soc_floor: float
    soc_reserve_margin: float
    heading_kp_n_m_per_rad: float
    heading_kd_n_m_per_rps: float
    speed_kp_n_per_mps: float
    minimum_hazard_distance_m: float
    replan_distance_m: float
    visual_detection_min_count: int
    random_seed: int
    return_energy_reserve_wh: float
    return_energy_margin: float
    safety_guard_distance_m: float
    safety_recovery_distance_m: float
    replan_cooldown_s: float
    coverage_lane_spacing_m: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "AutonomySettings":
        source = data["autonomy"]
        result = cls(
            mission_duration_s=float(source["mission_duration_s"]),
            integration_time_step_s=float(source["integration_time_step_s"]),
            control_period_s=float(source["control_period_s"]),
            current_earth_mps=(float(source["current_earth_mps"][0]), float(source["current_earth_mps"][1])),
            cruise_speed_mps=float(source["cruise_speed_mps"]),
            approach_speed_mps=float(source["approach_speed_mps"]),
            return_speed_mps=float(source["return_speed_mps"]),
            waypoint_tolerance_m=float(source["waypoint_tolerance_m"]),
            collection_radius_m=float(source["collection_radius_m"]),
            collection_hold_s=float(source["collection_hold_s"]),
            max_collections=int(source["max_collections"]),
            initial_soc=float(source["initial_soc"]),
            rth_soc_floor=float(source["rth_soc_floor"]),
            soc_reserve_margin=float(source["soc_reserve_margin"]),
            heading_kp_n_m_per_rad=float(source["heading_kp_n_m_per_rad"]),
            heading_kd_n_m_per_rps=float(source["heading_kd_n_m_per_rps"]),
            speed_kp_n_per_mps=float(source["speed_kp_n_per_mps"]),
            minimum_hazard_distance_m=float(source["minimum_hazard_distance_m"]),
            replan_distance_m=float(source["replan_distance_m"]),
            visual_detection_min_count=int(source["visual_detection_min_count"]),
            random_seed=int(source["random_seed"]),
            return_energy_reserve_wh=float(source.get("return_energy_reserve_wh", data["energy"]["model"]["safety_reserve_energy_wh"])),
            return_energy_margin=float(source.get("return_energy_margin", 1.35)),
            safety_guard_distance_m=float(source.get("safety_guard_distance_m", source["minimum_hazard_distance_m"])),
            safety_recovery_distance_m=float(source.get("safety_recovery_distance_m", source["replan_distance_m"])),
            replan_cooldown_s=float(source.get("replan_cooldown_s", 1.5)),
            coverage_lane_spacing_m=float(source.get("coverage_lane_spacing_m", 1.0)),
        )
        result.validate()
        return result

    def validate(self) -> None:
        positive = {
            "mission_duration_s": self.mission_duration_s,
            "integration_time_step_s": self.integration_time_step_s,
            "control_period_s": self.control_period_s,
            "cruise_speed_mps": self.cruise_speed_mps,
            "approach_speed_mps": self.approach_speed_mps,
            "return_speed_mps": self.return_speed_mps,
            "waypoint_tolerance_m": self.waypoint_tolerance_m,
            "collection_radius_m": self.collection_radius_m,
            "collection_hold_s": self.collection_hold_s,
            "heading_kp_n_m_per_rad": self.heading_kp_n_m_per_rad,
            "heading_kd_n_m_per_rps": self.heading_kd_n_m_per_rps,
            "speed_kp_n_per_mps": self.speed_kp_n_per_mps,
            "minimum_hazard_distance_m": self.minimum_hazard_distance_m,
            "replan_distance_m": self.replan_distance_m,
            "return_energy_reserve_wh": self.return_energy_reserve_wh,
            "return_energy_margin": self.return_energy_margin,
            "safety_guard_distance_m": self.safety_guard_distance_m,
            "safety_recovery_distance_m": self.safety_recovery_distance_m,
            "replan_cooldown_s": self.replan_cooldown_s,
            "coverage_lane_spacing_m": self.coverage_lane_spacing_m,
        }
        for name, value in positive.items():
            if value <= 0.0:
                raise AutonomyError(f"autonomy.{name} must be positive.")
        if self.control_period_s < self.integration_time_step_s:
            raise AutonomyError("control_period_s must be >= integration_time_step_s.")
        if not 0.0 < self.initial_soc <= 1.0:
            raise AutonomyError("initial_soc must be in (0, 1].")
        if not 0.0 < self.rth_soc_floor < self.initial_soc:
            raise AutonomyError("rth_soc_floor must be in (0, initial_soc).")
        if self.safety_recovery_distance_m < self.safety_guard_distance_m:
            raise AutonomyError("safety_recovery_distance_m must be >= safety_guard_distance_m.")
        if self.max_collections < 1 or self.visual_detection_min_count < 1:
            raise AutonomyError("max_collections and visual_detection_min_count must be at least one.")


@dataclass(frozen=True)
class MissionEvent:
    time_s: float
    from_state: str
    to_state: str
    reason: str
    target_id: str
    soc: float
    x_m: float
    y_m: float


@dataclass
class RouteFollower:
    path: PlannedPath
    waypoint_index: int = 0

    def finished(self) -> bool:
        return self.waypoint_index >= len(self.path.waypoints_m) - 1

    def target_point(self, position_m: tuple[float, float], *, tolerance_m: float) -> tuple[float, float]:
        while self.waypoint_index < len(self.path.waypoints_m) - 1:
            waypoint = self.path.waypoints_m[self.waypoint_index]
            if math.hypot(position_m[0] - waypoint[0], position_m[1] - waypoint[1]) > tolerance_m:
                break
            self.waypoint_index += 1
        return self.path.waypoints_m[self.waypoint_index]


@dataclass(frozen=True)
class MissionResult:
    rows: list[dict[str, object]]
    event_rows: list[dict[str, object]]
    route_rows: list[dict[str, object]]
    target_rows: list[dict[str, object]]
    metrics: dict[str, object]


def _body_speed_through_water(model: PlanarCatamaranDynamics, state: CraftState, current: tuple[float, float]) -> float:
    u_rel, v_rel = model.relative_water_velocity_body(state, current)
    return math.hypot(u_rel, v_rel)


def _thrust_power_w(command: ThrusterCommand, max_thrust_n: float, max_power_per_side_w: float) -> float:
    # Consistent conceptual scaling with Phase 04 thrust~RPM² and power~RPM³.
    values = (command.port_thrust_n, command.starboard_thrust_n)
    return float(sum(max_power_per_side_w * (max(0.0, min(max_thrust_n, force)) / max_thrust_n) ** 1.5 for force in values))


class AutonomousMission:
    """Closed-loop survey-and-collection mission over Phase 07's safe grid.

    The agent receives a fixed, reproducible environment and virtual detector
    interface.  It maintains a state-machine log, assigns only confirmed
    detections, plans each transit with A*, follows routes using feedback
    steering, and closes the mission by returning to the home station.
    """

    def __init__(
        self,
        *,
        model: PlanarCatamaranDynamics,
        environment: EnvironmentSettings,
        sensor_settings: SensorSettings,
        battery: BatteryModel,
        battery_settings: BatterySettings,
        energy_settings: EnergySettings,
        settings: AutonomySettings,
        debris: list[DebrisObject],
    ) -> None:
        self.model = model
        self.environment = environment
        self.sensor_settings = sensor_settings
        self.battery = battery
        self.battery_settings = battery_settings
        self.energy_settings = energy_settings
        self.settings = settings
        self.debris = list(debris)
        self.planner = AStarPlanner(environment.occupancy_grid())
        self.rng = np.random.default_rng(settings.random_seed)
        self.max_thrust_per_side = 5.0
        self.max_power_per_side_w = 55.0

    def _transition(
        self,
        events: list[MissionEvent],
        *,
        time_s: float,
        previous: AgentState,
        current: AgentState,
        reason: str,
        target_id: str | None,
        soc: float,
        state: CraftState,
    ) -> AgentState:
        if previous != current:
            events.append(MissionEvent(
                time_s=float(time_s),
                from_state=previous.value,
                to_state=current.value,
                reason=reason,
                target_id=target_id or "",
                soc=float(soc),
                x_m=float(state.x_m),
                y_m=float(state.y_m),
            ))
        return current

    def _confirmed_visible_targets(
        self,
        state: CraftState,
        collected: set[str],
        detection_counts: dict[str, int],
    ) -> list[DebrisObject]:
        visible: list[DebrisObject] = []
        heading_deg = math.degrees(state.psi_rad)
        for item in self.debris:
            if item.identifier in collected:
                continue
            dx = item.position_m[0] - state.x_m
            dy = item.position_m[1] - state.y_m
            distance = math.hypot(dx, dy)
            bearing = wrap_angle_deg(math.degrees(math.atan2(dy, dx)) - heading_deg)
            if not is_inside_fov(bearing, self.sensor_settings.debris_detection_fov_deg):
                continue
            probability = debris_detection_probability(distance, self.sensor_settings)
            if probability > 0.0 and self.rng.random() < probability:
                detection_counts[item.identifier] = detection_counts.get(item.identifier, 0) + 1
            if detection_counts.get(item.identifier, 0) >= self.settings.visual_detection_min_count:
                visible.append(item)
        return visible

    def _make_search_waypoints(self) -> list[tuple[float, float]]:
        """Return a full, parameterized lawnmower coverage route.

        Earlier versions used only five hard-coded lanes.  This parameterized
        construction makes coverage density explicit and scales with basin size.
        Every waypoint is subsequently connected through A* on the inflated grid.
        """
        margin = max(self.environment.robot_safety_radius_m + 0.42, 0.72)
        y_values: list[float] = []
        y = margin
        upper = self.environment.width_m - margin
        while y < upper - 1e-9:
            y_values.append(round(y, 6))
            y += self.settings.coverage_lane_spacing_m
        if not y_values or abs(y_values[-1] - upper) > 0.20:
            y_values.append(upper)
        waypoints: list[tuple[float, float]] = []
        for index, y_value in enumerate(y_values):
            x_value = self.environment.length_m - margin if index % 2 == 0 else margin
            waypoints.append((x_value, y_value))
        return waypoints

    def _plan(self, position_m: tuple[float, float], goal_m: tuple[float, float]) -> RouteFollower:
        return RouteFollower(self.planner.plan(position_m, goal_m))

    def _hazard_gradient(self, x_m: float, y_m: float, epsilon_m: float = 0.04) -> tuple[float, float]:
        """Numerical outward gradient of signed hazard distance.

        The direction points toward locally safer free space. It is used only by
        the supervisory safety layer; the nominal route still comes from A*.
        """
        xp = self.environment.signed_distance_to_nearest_hazard_m(x_m + epsilon_m, y_m)
        xm = self.environment.signed_distance_to_nearest_hazard_m(x_m - epsilon_m, y_m)
        yp = self.environment.signed_distance_to_nearest_hazard_m(x_m, y_m + epsilon_m)
        ym = self.environment.signed_distance_to_nearest_hazard_m(x_m, y_m - epsilon_m)
        gx, gy = (xp - xm) / (2.0 * epsilon_m), (yp - ym) / (2.0 * epsilon_m)
        magnitude = math.hypot(gx, gy)
        if magnitude <= 1e-12:
            return (0.0, 0.0)
        return gx / magnitude, gy / magnitude

    def _project_to_safe_state(self, state: CraftState) -> CraftState:
        """Apply a documented digital safety shield after numerical integration.

        This is not claimed as physical collision dynamics. It is a supervisory
        barrier: a state that penetrates the analytical configuration-space
        boundary is projected outward to the configured guard distance and its
        body velocities are reset before the next control update.
        """
        distance = self.environment.signed_distance_to_nearest_hazard_m(state.x_m, state.y_m)
        if distance >= self.settings.safety_guard_distance_m:
            return state
        gx, gy = self._hazard_gradient(state.x_m, state.y_m)
        if math.hypot(gx, gy) <= 1e-12:
            gx, gy = math.cos(state.psi_rad + math.pi), math.sin(state.psi_rad + math.pi)
        correction = self.settings.safety_guard_distance_m - distance + 1e-4
        return CraftState(
            x_m=state.x_m + correction * gx,
            y_m=state.y_m + correction * gy,
            psi_rad=math.atan2(gy, gx),
            u_mps=0.0,
            v_mps=0.0,
            r_rps=0.0,
        )

    def _return_energy_estimate_wh(self, position_m: tuple[float, float], soc: float) -> float:
        """Estimate conservative pack energy for an A* route from position to home."""
        try:
            distance_m = self.planner.plan(position_m, self.environment.home_position_m).length_m
        except PlannerError:
            distance_m = math.hypot(position_m[0] - self.environment.home_position_m[0], position_m[1] - self.environment.home_position_m[1])
        current_mag = math.hypot(*self.settings.current_earth_mps)
        through_water_speed = min(self.settings.return_speed_mps + current_mag, self.model.resistance.settings.analysis_speed_max_mps)
        required_thrust = self.model.resistance.state_at_speed(max(0.05, through_water_speed)).total_resistance_n
        per_side = min(self.max_thrust_per_side, 0.5 * required_thrust)
        command = ThrusterCommand(per_side, per_side)
        bus_load = self.energy_settings.hotel_load_w + _thrust_power_w(command, self.max_thrust_per_side, self.max_power_per_side_w)
        duration_s = distance_m / max(0.05, self.settings.return_speed_mps)
        pack_load = self.battery.load_state(bus_load, soc)
        return pack_load.battery_power_w * duration_s / 3600.0 * pack_load.peukert_multiplier

    def _return_energy_required_wh(self, position_m: tuple[float, float], soc: float) -> float:
        return self.settings.return_energy_margin * self._return_energy_estimate_wh(position_m, soc) + self.settings.return_energy_reserve_wh

    def _needs_energy_return(self, position_m: tuple[float, float], soc: float) -> bool:
        available_above_floor = max(0.0, soc - self.settings.rth_soc_floor) * self.battery_settings.usable_energy_wh
        return available_above_floor <= self._return_energy_required_wh(position_m, soc)

    def _control(
        self,
        state: CraftState,
        target_m: tuple[float, float],
        desired_speed: float,
        hazard_distance_m: float,
    ) -> tuple[ThrusterCommand, dict[str, float]]:
        dx = target_m[0] - state.x_m
        dy = target_m[1] - state.y_m
        nominal_x, nominal_y = dx, dy
        desired_heading = math.atan2(nominal_y, nominal_x)
        speed_cmd = desired_speed
        if hazard_distance_m < self.settings.safety_recovery_distance_m:
            gx, gy = self._hazard_gradient(state.x_m, state.y_m)
            proximity = max(0.0, min(1.0, (self.settings.safety_recovery_distance_m - hazard_distance_m) / self.settings.safety_recovery_distance_m))
            norm = max(1e-9, math.hypot(nominal_x, nominal_y))
            blend_x = nominal_x / norm + 2.5 * proximity * gx
            blend_y = nominal_y / norm + 2.5 * proximity * gy
            desired_heading = math.atan2(blend_y, blend_x)
            safe_ratio = max(0.0, min(1.0, (hazard_distance_m - self.settings.safety_guard_distance_m) / max(1e-9, self.settings.safety_recovery_distance_m - self.settings.safety_guard_distance_m)))
            speed_cmd *= max(0.12, safe_ratio)
        heading_error = wrap_to_pi(desired_heading - state.psi_rad)
        u_rel, _ = self.model.relative_water_velocity_body(state, self.settings.current_earth_mps)
        speed_error = speed_cmd - max(0.0, u_rel)
        baseline = self.model.resistance.state_at_speed(max(0.05, speed_cmd)).total_resistance_n if speed_cmd > 0.01 else 0.0
        total_thrust = max(0.0, min(2.0 * self.max_thrust_per_side, baseline + self.settings.speed_kp_n_per_mps * speed_error))
        yaw_moment = self.settings.heading_kp_n_m_per_rad * heading_error - self.settings.heading_kd_n_m_per_rps * state.r_rps
        differential_force = yaw_moment / self.model.thruster_half_spacing_m
        port = max(0.0, min(self.max_thrust_per_side, 0.5 * total_thrust - 0.5 * differential_force))
        starboard = max(0.0, min(self.max_thrust_per_side, 0.5 * total_thrust + 0.5 * differential_force))
        return ThrusterCommand(port, starboard), {
            "desired_heading_rad": desired_heading,
            "heading_error_rad": heading_error,
            "desired_speed_mps": speed_cmd,
            "total_thrust_command_n": port + starboard,
            "yaw_moment_command_n_m": self.model.thruster_half_spacing_m * (starboard - port),
        }

    def run(self) -> MissionResult:
        dt = self.settings.integration_time_step_s
        control_interval_steps = max(1, int(round(self.settings.control_period_s / dt)))
        state = CraftState(x_m=self.environment.home_position_m[0], y_m=self.environment.home_position_m[1], psi_rad=0.0)
        soc = self.settings.initial_soc
        agent_state = AgentState.INIT
        events: list[MissionEvent] = []
        collected: set[str] = set()
        detection_counts: dict[str, int] = {}
        route_rows: list[dict[str, object]] = []
        mission_rows: list[dict[str, object]] = []
        target_rows: list[dict[str, object]] = []
        current_target: DebrisObject | None = None
        follower: RouteFollower | None = None
        search_waypoints = self._make_search_waypoints()
        search_index = 0
        collection_started_at: float | None = None
        command = ThrusterCommand(0.0, 0.0)
        control_info: dict[str, float] = {"desired_heading_rad": 0.0, "heading_error_rad": 0.0, "desired_speed_mps": 0.0, "total_thrust_command_n": 0.0, "yaw_moment_command_n_m": 0.0}
        min_hazard_distance = float("inf")
        last_route_id = 0
        safety_intervention_count = 0
        replan_count = 0
        last_replan_time_s = -float("inf")
        energy_return_triggered = False

        for step in range(int(math.floor(self.settings.mission_duration_s / dt)) + 1):
            time_s = step * dt
            position = (state.x_m, state.y_m)
            hazard = self.environment.signed_distance_to_nearest_hazard_m(*position)
            min_hazard_distance = min(min_hazard_distance, hazard)
            # Sensor update and perception-derived target confirmation.
            confirmed = self._confirmed_visible_targets(state, collected, detection_counts)

            if agent_state == AgentState.INIT:
                agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.SEARCH, reason="initial self-check passed; start coverage search", target_id=None, soc=soc, state=state)
                try:
                    follower = self._plan(position, search_waypoints[search_index])
                    last_route_id += 1
                    route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="search"))
                except PlannerError:
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="no safe A* path to first search waypoint", target_id=None, soc=soc, state=state)

            if agent_state in {AgentState.SEARCH, AgentState.TRANSIT_TO_DEBRIS} and (soc <= self.settings.rth_soc_floor or self._needs_energy_return(position, soc)):
                reason = "SOC below configured return-to-home floor" if soc <= self.settings.rth_soc_floor else "conservative return-energy budget reached"
                energy_return_triggered = energy_return_triggered or (reason != "SOC below configured return-to-home floor")
                agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.RETURN_HOME, reason=reason, target_id=current_target.identifier if current_target else None, soc=soc, state=state)
                current_target = None
                try:
                    follower = self._plan(position, self.environment.home_position_m)
                    last_route_id += 1
                    route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="return_home"))
                except PlannerError:
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="no safe A* return route", target_id=None, soc=soc, state=state)

            if agent_state == AgentState.SEARCH and current_target is None:
                candidates = [item for item in confirmed if item.identifier not in collected]
                if candidates:
                    candidates.sort(key=lambda item: math.hypot(item.position_m[0] - state.x_m, item.position_m[1] - state.y_m))
                    candidate = candidates[0]
                    try:
                        follower = self._plan(position, candidate.position_m)
                        current_target = candidate
                        last_route_id += 1
                        route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg=f"target_{candidate.identifier}"))
                        agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.TRANSIT_TO_DEBRIS, reason="detector confirmation threshold reached; A* route assigned", target_id=candidate.identifier, soc=soc, state=state)
                    except PlannerError:
                        detection_counts[candidate.identifier] = 0

            if agent_state == AgentState.SEARCH and follower is not None and follower.finished():
                search_index += 1
                if search_index >= len(search_waypoints):
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.RETURN_HOME, reason="coverage route completed", target_id=None, soc=soc, state=state)
                    try:
                        follower = self._plan(position, self.environment.home_position_m)
                        last_route_id += 1
                        route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="return_home"))
                    except PlannerError:
                        agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="no safe return route after search", target_id=None, soc=soc, state=state)
                else:
                    follower = self._plan(position, search_waypoints[search_index])
                    last_route_id += 1
                    route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="search"))

            if agent_state == AgentState.TRANSIT_TO_DEBRIS and current_target is not None:
                distance_target = math.hypot(current_target.position_m[0] - state.x_m, current_target.position_m[1] - state.y_m)
                if distance_target <= self.settings.collection_radius_m:
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.COLLECT, reason="entered collection radius", target_id=current_target.identifier, soc=soc, state=state)
                    collection_started_at = time_s
                    command = ThrusterCommand(0.0, 0.0)
                elif follower is not None and follower.finished():
                    # The cell centre can be offset from a debris location. Use direct, slow final approach.
                    follower = None

            if agent_state == AgentState.COLLECT and current_target is not None:
                if collection_started_at is not None and time_s - collection_started_at >= self.settings.collection_hold_s:
                    collected.add(current_target.identifier)
                    target_rows.append({
                        "debris_id": current_target.identifier,
                        "mass_kg": current_target.mass_kg,
                        "x_m": current_target.position_m[0],
                        "y_m": current_target.position_m[1],
                        "collected_time_s": time_s,
                        "collection_distance_m": math.hypot(current_target.position_m[0] - state.x_m, current_target.position_m[1] - state.y_m),
                    })
                    target_label = current_target.identifier
                    current_target = None
                    collection_started_at = None
                    if len(collected) >= self.settings.max_collections:
                        next_state, reason = AgentState.RETURN_HOME, "configured collection quota reached"
                    else:
                        next_state, reason = AgentState.SEARCH, "collection confirmed; resume search"
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=next_state, reason=reason, target_id=target_label, soc=soc, state=state)
                    if agent_state == AgentState.RETURN_HOME:
                        try:
                            follower = self._plan(position, self.environment.home_position_m)
                            last_route_id += 1
                            route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="return_home"))
                        except PlannerError:
                            agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="no safe return route after collection", target_id=None, soc=soc, state=state)
                    else:
                        try:
                            follower = self._plan(position, search_waypoints[min(search_index, len(search_waypoints) - 1)])
                            last_route_id += 1
                            route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg="search"))
                        except PlannerError:
                            agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="no safe search route after collection", target_id=None, soc=soc, state=state)

            if agent_state == AgentState.RETURN_HOME:
                if math.hypot(state.x_m - self.environment.home_position_m[0], state.y_m - self.environment.home_position_m[1]) <= self.settings.waypoint_tolerance_m:
                    agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.DOCK, reason="entered home-station docking radius", target_id=None, soc=soc, state=state)
                    command = ThrusterCommand(0.0, 0.0)

            if agent_state == AgentState.DOCK:
                agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.MISSION_COMPLETE, reason="dock hold complete", target_id=None, soc=soc, state=state)

            # Guidance and control at the specified update interval.
            if step % control_interval_steps == 0:
                if agent_state in {AgentState.EMERGENCY_STOP, AgentState.MISSION_COMPLETE, AgentState.COLLECT, AgentState.DOCK}:
                    command = ThrusterCommand(0.0, 0.0)
                    control_info = {"desired_heading_rad": state.psi_rad, "heading_error_rad": 0.0, "desired_speed_mps": 0.0, "total_thrust_command_n": 0.0, "yaw_moment_command_n_m": 0.0}
                elif agent_state == AgentState.TRANSIT_TO_DEBRIS and current_target is not None:
                    if follower is not None:
                        target_point = follower.target_point(position, tolerance_m=self.settings.waypoint_tolerance_m)
                    else:
                        target_point = current_target.position_m
                    distance = math.hypot(target_point[0] - state.x_m, target_point[1] - state.y_m)
                    desired_speed = self.settings.approach_speed_mps if distance < 0.75 else self.settings.cruise_speed_mps
                    command, control_info = self._control(state, target_point, desired_speed, hazard)
                elif agent_state == AgentState.SEARCH and follower is not None:
                    target_point = follower.target_point(position, tolerance_m=self.settings.waypoint_tolerance_m)
                    command, control_info = self._control(state, target_point, self.settings.cruise_speed_mps, hazard)
                elif agent_state == AgentState.RETURN_HOME and follower is not None:
                    target_point = follower.target_point(position, tolerance_m=self.settings.waypoint_tolerance_m)
                    command, control_info = self._control(state, target_point, self.settings.return_speed_mps, hazard)

            bus_load_w = self.energy_settings.hotel_load_w + _thrust_power_w(command, self.max_thrust_per_side, self.max_power_per_side_w)
            battery_load = self.battery.load_state(bus_load_w, soc)
            if step < int(self.settings.mission_duration_s / dt):
                soc = self.battery.soc_after_interval(soc, bus_load_w, dt)
                integrated_state = self.model.rk4_step(state, command, self.settings.current_earth_mps, dt)
                integrated_hazard = self.environment.signed_distance_to_nearest_hazard_m(integrated_state.x_m, integrated_state.y_m)
                if integrated_hazard < self.settings.safety_guard_distance_m:
                    state = self._project_to_safe_state(integrated_state)
                    safety_intervention_count += 1
                    if time_s - last_replan_time_s >= self.settings.replan_cooldown_s and agent_state in {AgentState.SEARCH, AgentState.TRANSIT_TO_DEBRIS, AgentState.RETURN_HOME}:
                        if agent_state == AgentState.TRANSIT_TO_DEBRIS and current_target is not None:
                            replan_goal = current_target.position_m
                            leg = f"safety_replan_target_{current_target.identifier}"
                        elif agent_state == AgentState.RETURN_HOME:
                            replan_goal = self.environment.home_position_m
                            leg = "safety_replan_return"
                        else:
                            replan_goal = search_waypoints[min(search_index, len(search_waypoints)-1)]
                            leg = "safety_replan_search"
                        try:
                            follower = self._plan((state.x_m, state.y_m), replan_goal)
                            last_route_id += 1
                            route_rows.extend(follower.path.as_row(route_id=f"route_{last_route_id:02d}", mission_leg=leg))
                            replan_count += 1
                            last_replan_time_s = time_s
                            events.append(MissionEvent(time_s=float(time_s), from_state=agent_state.value, to_state=agent_state.value, reason="supervisory safety shield activated; route replanned", target_id=current_target.identifier if current_target else "", soc=float(soc), x_m=float(state.x_m), y_m=float(state.y_m)))
                        except PlannerError:
                            agent_state = self._transition(events, time_s=time_s, previous=agent_state, current=AgentState.EMERGENCY_STOP, reason="safety shield could not find a valid recovery route", target_id=current_target.identifier if current_target else None, soc=soc, state=state)
                else:
                    state = integrated_state

            distance_home = math.hypot(state.x_m - self.environment.home_position_m[0], state.y_m - self.environment.home_position_m[1])
            hazard = self.environment.signed_distance_to_nearest_hazard_m(state.x_m, state.y_m)
            min_hazard_distance = min(min_hazard_distance, hazard)
            mission_rows.append({
                "time_s": time_s,
                "state": agent_state.value,
                "target_id": current_target.identifier if current_target else "",
                "x_m": state.x_m,
                "y_m": state.y_m,
                "psi_deg": math.degrees(state.psi_rad),
                "u_mps": state.u_mps,
                "v_mps": state.v_mps,
                "r_rps": state.r_rps,
                "distance_home_m": distance_home,
                "hazard_distance_m": hazard,
                "soc": soc,
                "bus_load_w": bus_load_w,
                "battery_current_a": battery_load.pack_current_a,
                "port_thrust_n": command.port_thrust_n,
                "starboard_thrust_n": command.starboard_thrust_n,
                **control_info,
                "confirmed_target_count": sum(count >= self.settings.visual_detection_min_count for count in detection_counts.values()),
                "collected_count": len(collected),
            })
            if agent_state in {AgentState.MISSION_COMPLETE, AgentState.EMERGENCY_STOP}:
                break

        final = mission_rows[-1]
        events_rows = [event.__dict__ for event in events]
        success = final["state"] == AgentState.MISSION_COMPLETE.value and final["distance_home_m"] <= self.settings.waypoint_tolerance_m + 0.20
        route_lengths: dict[str, float] = {}
        for row in route_rows:
            route_id = str(row["route_id"])
            route_lengths[route_id] = max(route_lengths.get(route_id, 0.0), float(row["cumulative_length_m"]))

        metrics: dict[str, object] = {
            "mission_success": int(success),
            "final_state": final["state"],
            "duration_s": final["time_s"],
            "collected_count": len(collected),
            "collected_mass_kg": float(sum(row["mass_kg"] for row in target_rows)),
            "final_soc": final["soc"],
            "final_distance_home_m": final["distance_home_m"],
            "minimum_hazard_distance_m": min_hazard_distance,
            "state_transition_count": len(events_rows),
            "planned_route_count": last_route_id,
            "total_planned_length_m": float(sum(route_lengths.values())),
            "safety_intervention_count": safety_intervention_count,
            "replan_count": replan_count,
            "energy_return_triggered": int(energy_return_triggered),
            "return_energy_required_wh": self._return_energy_required_wh((float(final["x_m"]), float(final["y_m"])), float(final["soc"])),
        }
        return MissionResult(rows=mission_rows, event_rows=events_rows, route_rows=route_rows, target_rows=target_rows, metrics=metrics)
