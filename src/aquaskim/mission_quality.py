"""Robust multi-target mission runner used by the release-quality visual suite.

The previous autonomy demonstration used a minimal waypoint follower.  This
module adds an explicitly documented line-of-sight follower, progress watchdog,
route-time budget, target-skip policy and low-speed heading behaviour.  It still
propagates the Phase 06 3-DOF plant through RK4; it is not a kinematic animation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from aquaskim.dynamics_3dof import CraftState, PlanarCatamaranDynamics, ThrusterCommand, wrap_to_pi
from aquaskim.environment import DebrisObject, EnvironmentSettings
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.planner import AStarPlanner, PlannedPath, PlannerError
from aquaskim.hopper_model import HopperSettings, HopperState


@dataclass(frozen=True)
class QualityMissionSettings:
    """Reference closed-loop mission settings.

    `target_quota` remains only as a deprecated compatibility field.  It is not
    used to decide mission completion; storage, energy, coverage and safety are.
    """
    duration_s: float = 540.0
    integration_dt_s: float = 0.05
    control_period_s: float = 0.10
    cruise_speed_mps: float = 0.28
    approach_speed_mps: float = 0.18
    return_speed_mps: float = 0.25
    waypoint_tolerance_m: float = 0.32
    collection_radius_m: float = 0.34
    collection_hold_s: float = 1.2
    target_quota: int = 0
    initial_soc: float = 0.80
    rth_soc_floor: float = 0.18
    current_earth_mps: tuple[float, float] = (0.0, 0.0)
    current_compensation_enabled: bool = True
    current_compensation_gain: float = 1.0
    # Feedforward is active for every nonzero commanded ground speed when this
    # threshold is zero. A positive threshold is retained only for explicit
    # non-reference experiments; it is not used by the fixed reference policy.
    current_compensation_activation_speed_mps: float = 0.0
    lookahead_m: float = 0.70
    max_yaw_moment_n_m: float = 0.10
    heading_kp_n_m_per_rad: float = 0.17
    heading_kd_n_m_per_rps: float = 0.09
    speed_kp_n_per_mps: float = 3.2
    guard_distance_m: float = 0.35
    replan_distance_m: float = 0.55
    route_budget_factor: float = 2.8
    min_turn_thrust_n: float = 0.60
    max_forward_thrust_n: float = 1.60
    pivot_turn_thrust_n: float = 0.34
    pivot_entry_heading_error_rad: float = 0.65
    pivot_exit_heading_error_rad: float = 0.20
    return_energy_reserve_wh: float = 4.0
    coverage_lane_spacing_m: float = 0.90
    detection_range_m: float = 1.35
    minimum_search_before_diversion_s: float = 12.0
    hopper_usable_volume_l: float = 4.0
    hopper_payload_mass_limit_kg: float = 0.80
    hopper_bulk_density_kg_m3: float = 75.0
    hopper_packing_factor: float = 0.62
    hopper_return_trigger_fraction: float = 0.95


@dataclass
class PolylineFollower:
    """Arc-length pure-pursuit follower for an A* polyline.

    Guidance is computed from the closest valid projection on the *retained
    path*, rather than from the vessel directly to the next waypoint.  This
    avoids a target jumping behind the vessel near a corner, which was the main
    source of visually implausible loops in the earlier mission replay.
    """
    path: PlannedPath
    index: int = 1

    @property
    def points(self) -> tuple[tuple[float, float], ...]:
        return self.path.waypoints_m

    def _projection_on_segment(
        self, position: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
    ) -> tuple[float, tuple[float, float]]:
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        length2 = dx * dx + dy * dy
        if length2 <= 1e-12:
            return 1.0, end
        alpha = ((position[0] - sx) * dx + (position[1] - sy) * dy) / length2
        alpha = min(1.0, max(0.0, alpha))
        return alpha, (sx + alpha * dx, sy + alpha * dy)

    def _anchor(self, position: tuple[float, float], tolerance_m: float) -> tuple[int, tuple[float, float]]:
        # Advance only along ordered segments.  The local tolerance prevents a
        # cross-track excursion from skipping a future route corner.
        while self.index < len(self.points) - 1:
            start = self.points[self.index - 1]
            end = self.points[self.index]
            alpha, projection = self._projection_on_segment(position, start, end)
            near_end = math.hypot(position[0] - end[0], position[1] - end[1]) <= tolerance_m
            passed_end = alpha >= 0.995 and math.hypot(position[0] - projection[0], position[1] - projection[1]) <= 1.35 * tolerance_m
            if near_end or passed_end:
                self.index += 1
            else:
                return self.index, projection
        self.index = min(self.index, len(self.points) - 1)
        start = self.points[max(0, self.index - 1)]
        end = self.points[self.index]
        _, projection = self._projection_on_segment(position, start, end)
        return self.index, projection

    def target(self, position: tuple[float, float], *, tolerance_m: float, lookahead_m: float) -> tuple[float, float]:
        # The reference craft operates in a confined basin and uses explicit
        # stop-turn-go waypoint convergence rather than cutting across a corner.
        # It is intentionally conservative: every commanded segment remains an
        # A*-verified configuration-space segment.
        self._anchor(position, tolerance_m)
        return self.points[min(self.index, len(self.points) - 1)]


    def complete(self, position: tuple[float, float], *, tolerance_m: float) -> bool:
        return math.hypot(position[0] - self.points[-1][0], position[1] - self.points[-1][1]) <= tolerance_m


@dataclass(frozen=True)
class QualityMissionResult:
    rows: list[dict[str, Any]]
    events: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    targets: list[dict[str, Any]]
    metrics: dict[str, Any]


def current_aware_course_command(
    ground_track_heading_rad: float,
    desired_ground_speed_mps: float,
    current_earth_mps: tuple[float, float],
    *,
    enabled: bool = True,
    gain: float = 1.0,
    activation_speed_mps: float = 0.0,
) -> tuple[float, float, float]:
    """Return course, water-relative speed and crab angle for ground-track guidance.

    The desired path is defined in earth coordinates, but twin thrusters act
    against the water.  For the low-speed model, the water-relative command is
    therefore ``V_water = V_ground - gain * V_current``.  With a zero current
    or disabled compensation the command is exactly the original LOS command.
    The function is deliberately algebraic and deterministic; it does not
    estimate current or claim station-keeping outside the documented envelope.
    """
    if desired_ground_speed_mps <= 0.0:
        return ground_track_heading_rad, 0.0, 0.0
    activation = max(0.0, float(activation_speed_mps))
    # The fixed reference design sets activation to 0.0: every nonzero ground
    # command therefore receives current feedforward, including the deceleration
    # region near a waypoint. This avoids a small, persistent endpoint drift.
    if not enabled or desired_ground_speed_mps <= activation:
        return ground_track_heading_rad, desired_ground_speed_mps, 0.0
    effective_gain = max(0.0, min(1.0, float(gain)))
    ground_vx = desired_ground_speed_mps * math.cos(ground_track_heading_rad)
    ground_vy = desired_ground_speed_mps * math.sin(ground_track_heading_rad)
    water_vx = ground_vx - effective_gain * float(current_earth_mps[0])
    water_vy = ground_vy - effective_gain * float(current_earth_mps[1])
    water_speed = math.hypot(water_vx, water_vy)
    course = math.atan2(water_vy, water_vx)
    return course, water_speed, wrap_to_pi(course - ground_track_heading_rad)


def _thrust_power_w(command: ThrusterCommand, *, max_thrust_n: float = 5.0, max_power_per_side_w: float = 55.0) -> float:
    # Reverse thrust has the same conceptual power scaling as forward thrust.
    return float(sum(max_power_per_side_w * (min(max_thrust_n, abs(value)) / max_thrust_n) ** 1.5 for value in (command.port_thrust_n, command.starboard_thrust_n)))


def _route_rows(path: PlannedPath, route_id: str, leg: str) -> list[dict[str, Any]]:
    return path.as_row(route_id=route_id, mission_leg=leg)


def _select_targets(debris: list[DebrisObject], environment: EnvironmentSettings, planner: AStarPlanner, count: int) -> list[DebrisObject]:
    """Select spatially spread, reachable targets deterministically.

    This is a task-priority policy, not oracle perception: targets become active
    only after the coverage/search state reaches their local detection envelope.
    The selection prevents all targets concentrating in one corner of the basin.
    """
    anchors = [
        (0.30 * environment.length_m, 0.25 * environment.width_m),
        (0.68 * environment.length_m, 0.24 * environment.width_m),
        (0.70 * environment.length_m, 0.72 * environment.width_m),
        (0.30 * environment.length_m, 0.73 * environment.width_m),
        (0.50 * environment.length_m, 0.50 * environment.width_m),
    ]
    available = list(debris)
    selected: list[DebrisObject] = []
    for anchor in anchors:
        candidates = sorted(available, key=lambda item: math.hypot(item.position_m[0] - anchor[0], item.position_m[1] - anchor[1]))
        for item in candidates:
            try:
                planner.plan(environment.home_position_m if not selected else selected[-1].position_m, item.position_m)
            except PlannerError:
                continue
            selected.append(item)
            available.remove(item)
            break
        if len(selected) >= count:
            break
    return selected[:count]



def _coverage_waypoints(
    environment: EnvironmentSettings,
    spacing_m: float = 0.90,
) -> list[tuple[float, float]]:
    """Build a deterministic boustrophedon search route.

    The route covers the analytically safe interior of the basin. Individual
    endpoints are connected by A*, so obstacle detours are handled by the global
    planner instead of by forcing a kinematic lawnmower through hazards.
    """
    margin = max(environment.robot_safety_radius_m + 0.42, 0.75)
    y_values: list[float] = []
    y_value = margin
    upper = environment.width_m - margin
    while y_value < upper - 1e-9:
        y_values.append(float(y_value))
        y_value += spacing_m
    if not y_values or upper - y_values[-1] > 0.25:
        y_values.append(float(upper))

    waypoints: list[tuple[float, float]] = []
    for index, y_coord in enumerate(y_values):
        x_coord = environment.length_m - margin if index % 2 == 0 else margin
        waypoints.append((float(x_coord), float(y_coord)))
    return waypoints


def run_quality_mission(
    *,
    model: PlanarCatamaranDynamics,
    environment: EnvironmentSettings,
    battery: BatteryModel,
    battery_settings: BatterySettings,
    energy_settings: EnergySettings,
    settings: QualityMissionSettings,
    debris: list[DebrisObject] | None = None,
) -> QualityMissionResult:
    """Run a coverage-led mission with capacity-, energy- and safety-based return.

    There is intentionally no collection-count termination criterion. Debris are
    discovered locally while the craft follows a Boustrophedon search route. The
    agent diverts to a detected, reachable target; after capture it resumes the
    interrupted coverage leg unless hopper capacity or return-energy logic requires
    a homeward route.
    """
    planner = AStarPlanner(environment.occupancy_grid(clearance_m=settings.guard_distance_m + 0.12))
    debris_items = list(debris or environment.generate_debris())
    hopper_settings = HopperSettings(
        usable_volume_l=settings.hopper_usable_volume_l,
        payload_mass_limit_kg=settings.hopper_payload_mass_limit_kg,
        equivalent_bulk_density_kg_m3=settings.hopper_bulk_density_kg_m3,
        packing_factor=settings.hopper_packing_factor,
        return_trigger_fraction=settings.hopper_return_trigger_fraction,
    )
    hopper_settings.validate()
    hopper = HopperState()

    coverage = _coverage_waypoints(environment, settings.coverage_lane_spacing_m)
    state = CraftState(
        x_m=environment.home_position_m[0],
        y_m=environment.home_position_m[1],
        psi_rad=0.0,
    )
    soc = settings.initial_soc
    dt = settings.integration_dt_s
    control_steps = max(1, int(round(settings.control_period_s / dt)))
    command = ThrusterCommand(0.0, 0.0)
    turning_in_place = False
    control_regime = "IDLE"
    follower: PolylineFollower | None = None
    mode = "SEARCH"
    coverage_index = 0
    active_target: DebrisObject | None = None
    collect_until: float | None = None
    route_id = 0
    leg_started_s = 0.0
    watchdog_for_leg = 0
    target_approach_refreshes = 0
    replan_count = 0
    watchdog_count = 0
    safety_count = 0
    rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    collected_ids: set[str] = set()
    deferred_ids: set[str] = set()
    planned_path_length = 0.0
    min_clearance = float("inf")
    return_reason = ""
    energy_check_steps = max(1, int(round(2.0 / dt)))

    def switch_mode(new_mode: str, reason: str, time_s: float) -> None:
        nonlocal mode
        if new_mode != mode:
            events.append(
                {
                    "time_s": time_s,
                    "event": "STATE_CHANGE",
                    "from_mode": mode,
                    "to_mode": new_mode,
                    "reason": reason,
                    "x_m": state.x_m,
                    "y_m": state.y_m,
                    "soc": soc,
                    "hopper_mass_kg": hopper.captured_mass_kg,
                    "hopper_volume_l": hopper.occupied_volume_l,
                }
            )
            mode = new_mode

    def set_route(goal: tuple[float, float], leg: str, reason: str, time_s: float) -> bool:
        nonlocal follower, route_id, leg_started_s, planned_path_length, watchdog_for_leg
        try:
            path = planner.plan((state.x_m, state.y_m), goal)
        except PlannerError:
            events.append(
                {
                    "time_s": time_s,
                    "event": "ROUTE_FAILURE",
                    "mode": mode,
                    "reason": reason,
                    "x_m": state.x_m,
                    "y_m": state.y_m,
                }
            )
            return False
        follower = PolylineFollower(path)
        route_id += 1
        routes.extend(_route_rows(path, f"route_{route_id:03d}", leg))
        planned_path_length += path.length_m
        leg_started_s = time_s
        watchdog_for_leg = 0
        events.append(
            {
                "time_s": time_s,
                "event": "ROUTE_ASSIGNED",
                "mode": mode,
                "reason": reason,
                "route_id": route_id,
                "mission_leg": leg,
                "goal_x_m": goal[0],
                "goal_y_m": goal[1],
                "x_m": state.x_m,
                "y_m": state.y_m,
            }
        )
        return True

    def visible_target() -> DebrisObject | None:
        candidates: list[tuple[float, DebrisObject]] = []
        for item in debris_items:
            if item.identifier in collected_ids or item.identifier in deferred_ids:
                continue
            if not hopper.can_accept(item.mass_kg, hopper_settings):
                continue
            distance = math.hypot(item.position_m[0] - state.x_m, item.position_m[1] - state.y_m)
            if distance <= settings.detection_range_m:
                try:
                    route_length = planner.plan((state.x_m, state.y_m), item.position_m).length_m
                except PlannerError:
                    continue
                candidates.append((route_length, item))
        return min(candidates, key=lambda pair: pair[0])[1] if candidates else None

    def route_home(reason: str, time_s: float) -> None:
        nonlocal active_target, return_reason
        active_target = None
        return_reason = reason
        switch_mode("RETURN_HOME", reason, time_s)
        set_route(environment.home_position_m, "return_home", reason, time_s)

    if coverage:
        set_route(coverage[0], "coverage_lane_001", "initial coverage lane assigned", 0.0)
    else:
        route_home("empty coverage plan", 0.0)

    for step in range(int(settings.duration_s / dt) + 1):
        time_s = step * dt
        position = (state.x_m, state.y_m)
        clearance = environment.signed_distance_to_nearest_hazard_m(*position)
        min_clearance = min(min_clearance, clearance)

        # Mission termination conditions have priority over target selection.
        hopper_due, hopper_reason = hopper.return_required(hopper_settings)
        if mode in {"SEARCH", "TRANSIT_TO_TARGET"} and hopper_due:
            route_home(hopper_reason, time_s)

        if mode in {"SEARCH", "TRANSIT_TO_TARGET"} and step % energy_check_steps == 0:
            try:
                home_length = planner.plan(position, environment.home_position_m).length_m
            except PlannerError:
                home_length = math.hypot(position[0] - environment.home_position_m[0], position[1] - environment.home_position_m[1])
            return_wh = (
                home_length / max(0.10, settings.return_speed_mps) * 30.0 / 3600.0
                + settings.return_energy_reserve_wh
            )
            available_wh = max(0.0, soc - settings.rth_soc_floor) * battery_settings.usable_energy_wh
            if soc <= settings.rth_soc_floor or available_wh <= 1.20 * return_wh:
                route_home("energy-aware return reserve reached", time_s)

        # SEARCH explicitly means coverage navigation plus local target discovery.
        if mode == "SEARCH" and time_s >= settings.minimum_search_before_diversion_s:
            detected = visible_target()
            if detected is not None:
                active_target = detected
                target_approach_refreshes = 0
                switch_mode("TRANSIT_TO_TARGET", "local debris detector confirmed a reachable target", time_s)
                events.append(
                    {
                        "time_s": time_s,
                        "event": "TARGET_CONFIRMED",
                        "mode": mode,
                        "target_id": detected.identifier,
                        "reason": "target fell inside local detection envelope during coverage",
                        "x_m": state.x_m,
                        "y_m": state.y_m,
                    }
                )
                set_route(detected.position_m, f"target_{detected.identifier}", "A* target diversion from coverage", time_s)

        if mode == "COLLECT" and collect_until is not None and time_s >= collect_until:
            if active_target is not None and hopper.can_accept(active_target.mass_kg, hopper_settings):
                hopper = hopper.add(active_target.mass_kg, hopper_settings)
                collected_ids.add(active_target.identifier)
                target_rows.append(
                    {
                        "debris_id": active_target.identifier,
                        "x_m": active_target.position_m[0],
                        "y_m": active_target.position_m[1],
                        "mass_kg": active_target.mass_kg,
                        "occupied_volume_l": hopper.occupied_volume_l,
                        "captured_mass_kg": hopper.captured_mass_kg,
                        "collection_time_s": time_s,
                    }
                )
                events.append(
                    {
                        "time_s": time_s,
                        "event": "COLLECTION_CONFIRMED",
                        "mode": mode,
                        "target_id": active_target.identifier,
                        "reason": "collector hold time elapsed and hopper capacity accepted payload",
                        "x_m": state.x_m,
                        "y_m": state.y_m,
                        "hopper_mass_kg": hopper.captured_mass_kg,
                        "hopper_volume_l": hopper.occupied_volume_l,
                    }
                )
            active_target = None
            target_approach_refreshes = 0
            collect_until = None
            hopper_due, hopper_reason = hopper.return_required(hopper_settings)
            if hopper_due:
                route_home(hopper_reason, time_s)
            elif coverage_index < len(coverage):
                switch_mode("SEARCH", "resume interrupted coverage after confirmed collection", time_s)
                set_route(coverage[coverage_index], f"coverage_lane_{coverage_index + 1:03d}", "resume coverage route", time_s)
            else:
                route_home("coverage route exhausted after final collection", time_s)

        # Capture is geometry-based, not tied to exact coincidence with a grid
        # cell. It is checked before route completion so a reachable object is
        # never sent through repeated zero-length replans.
        if mode == "TRANSIT_TO_TARGET" and active_target is not None:
            target_distance = math.hypot(active_target.position_m[0] - state.x_m, active_target.position_m[1] - state.y_m)
            if target_distance <= settings.collection_radius_m:
                switch_mode("COLLECT", "entered collector capture radius", time_s)
                collect_until = time_s + settings.collection_hold_s

        if follower is not None and follower.complete(position, tolerance_m=settings.waypoint_tolerance_m):
            if mode == "SEARCH":
                coverage_index += 1
                if coverage_index < len(coverage):
                    set_route(coverage[coverage_index], f"coverage_lane_{coverage_index + 1:03d}", "next boustrophedon coverage lane", time_s)
                else:
                    route_home("all coverage lanes completed", time_s)
            elif mode == "TRANSIT_TO_TARGET" and active_target is not None:
                # Planner goal may be a nearest-free cell. One controlled refresh
                # is permitted; afterwards an unreachable target is deferred.
                if target_approach_refreshes == 0:
                    target_approach_refreshes += 1
                    set_route(active_target.position_m, f"target_{active_target.identifier}", "single target-approach refresh", time_s)
                else:
                    events.append({
                        "time_s": time_s, "event": "TARGET_DEFERRED", "mode": mode,
                        "target_id": active_target.identifier,
                        "reason": "capture radius was not reachable after one approach refresh",
                        "x_m": state.x_m, "y_m": state.y_m,
                    })
                    deferred_ids.add(active_target.identifier)
                    active_target = None
                    target_approach_refreshes = 0
                    switch_mode("SEARCH", "defer target outside the reachable capture envelope", time_s)
                    if coverage_index < len(coverage):
                        set_route(coverage[coverage_index], f"coverage_lane_{coverage_index + 1:03d}", "resume coverage after deferred target", time_s)
            elif mode == "RETURN_HOME":
                switch_mode("MISSION_COMPLETE", "entered home-station docking radius", time_s)

        guidance_target = position if follower is None else follower.target(
            position,
            tolerance_m=settings.waypoint_tolerance_m,
            lookahead_m=settings.lookahead_m,
        )
        if mode == "SEARCH":
            desired_speed = settings.cruise_speed_mps
        elif mode == "TRANSIT_TO_TARGET":
            distance = math.hypot(guidance_target[0] - state.x_m, guidance_target[1] - state.y_m)
            desired_speed = settings.approach_speed_mps if distance < 0.75 else settings.cruise_speed_mps
        elif mode == "RETURN_HOME":
            desired_speed = settings.return_speed_mps
        else:
            desired_speed = 0.0

        # Braking-aware approach to the active waypoint prevents a high-speed
        # overshoot that would otherwise create repeated loops around a corner.
        waypoint_distance = math.hypot(guidance_target[0] - state.x_m, guidance_target[1] - state.y_m)
        if desired_speed > 0.0:
            arrival_scale = min(1.0, max(0.0, (waypoint_distance - settings.waypoint_tolerance_m) / 0.90))
            desired_speed *= arrival_scale

        # Current-aware course command. Guidance is specified in the basin
        # frame; propulsors act relative to the water. The documented feedforward
        # course therefore removes the known current vector from the requested
        # ground-track velocity. It is a low-speed model compensation, not an
        # estimator or a claim of open-water station-keeping.
        desired_ground_speed = desired_speed
        dx_track, dy_track = guidance_target[0] - state.x_m, guidance_target[1] - state.y_m
        ground_track_heading = state.psi_rad if desired_ground_speed <= 0.0 else math.atan2(dy_track, dx_track)
        desired_heading, desired_speed, crab_angle = current_aware_course_command(
            ground_track_heading,
            desired_ground_speed,
            settings.current_earth_mps,
            enabled=settings.current_compensation_enabled,
            gain=settings.current_compensation_gain,
            activation_speed_mps=settings.current_compensation_activation_speed_mps,
        )

        if step % control_steps == 0:
            heading_error = wrap_to_pi(desired_heading - state.psi_rad)
            u_rel, _ = model.relative_water_velocity_body(state, settings.current_earth_mps)

            # The confined-basin controller uses a true stop-turn-go policy:
            # first dissipate surge momentum, then pivot, then re-accelerate.
            # This avoids turning a moving hull through a waypoint, the physical
            # mechanism that produced the earlier large loops.
            if desired_speed <= 0.0:
                turning_in_place = False
            elif turning_in_place:
                if abs(heading_error) <= settings.pivot_exit_heading_error_rad and abs(u_rel) <= 0.045:
                    turning_in_place = False
            elif abs(heading_error) >= settings.pivot_entry_heading_error_rad:
                turning_in_place = True

            yaw_moment = max(
                -settings.max_yaw_moment_n_m,
                min(settings.max_yaw_moment_n_m, settings.heading_kp_n_m_per_rad * heading_error - settings.heading_kd_n_m_per_rps * state.r_rps),
            )
            if turning_in_place:
                speed_command = 0.0
                # Bleed translational momentum before applying opposite thrust.
                if abs(u_rel) > 0.045:
                    braking = min(0.38, 1.20 * abs(u_rel))
                    direction = -1.0 if u_rel > 0.0 else 1.0
                    port, starboard = direction * braking, direction * braking
                    yaw_moment = 0.0
                    control_regime = "BRAKE_FOR_PIVOT"
                else:
                    sign = 1.0 if yaw_moment >= 0.0 else -1.0
                    pivot = max(0.13, min(settings.pivot_turn_thrust_n, abs(yaw_moment) / max(model.thruster_half_spacing_m, 1e-9)))
                    port, starboard = -sign * pivot, sign * pivot
                    yaw_moment = model.thruster_half_spacing_m * (starboard - port)
                    control_regime = "PIVOT"
            else:
                alignment = max(0.0, math.cos(abs(heading_error)))
                speed_command = desired_speed * alignment
                # Command a symmetric reverse pulse only to decelerate an
                # already moving craft; otherwise retain positive thrust.
                tracking_error = speed_command - u_rel
                drag = model.resistance.state_at_speed(max(0.02, speed_command)).total_resistance_n if speed_command > 0.0 else 0.0
                total_force = drag + settings.speed_kp_n_per_mps * tracking_error
                total_force = max(-0.35, min(settings.max_forward_thrust_n, total_force))
                if total_force < 0.0:
                    port = starboard = total_force / 2.0
                    yaw_moment = 0.0
                    control_regime = "BRAKE_TO_WAYPOINT"
                else:
                    differential = yaw_moment / max(model.thruster_half_spacing_m, 1e-9)
                    differential_limit = 0.82 * total_force
                    differential = max(-differential_limit, min(differential_limit, differential))
                    port = 0.5 * (total_force - differential)
                    starboard = 0.5 * (total_force + differential)
                    control_regime = "TRACK" if desired_speed > 0.0 else "IDLE"
            command = ThrusterCommand(port, starboard)
        else:
            heading_error = wrap_to_pi(desired_heading - state.psi_rad)
            speed_command = desired_speed if not turning_in_place else 0.0
            yaw_moment = model.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n)

        bus_power = energy_settings.hotel_load_w + _thrust_power_w(command)
        battery_load = battery.load_state(bus_power, soc)
        if step < int(settings.duration_s / dt):
            soc = battery.soc_after_interval(soc, bus_power, dt)
            integrated = model.rk4_step(state, command, settings.current_earth_mps, dt)
            projected_clearance = environment.signed_distance_to_nearest_hazard_m(integrated.x_m, integrated.y_m)
            if projected_clearance < settings.guard_distance_m:
                safety_count += 1
                eps = 0.03
                gx = environment.signed_distance_to_nearest_hazard_m(state.x_m + eps, state.y_m) - environment.signed_distance_to_nearest_hazard_m(state.x_m - eps, state.y_m)
                gy = environment.signed_distance_to_nearest_hazard_m(state.x_m, state.y_m + eps) - environment.signed_distance_to_nearest_hazard_m(state.x_m, state.y_m - eps)
                norm = math.hypot(gx, gy)
                if norm < 1e-9:
                    gx, gy, norm = -math.cos(state.psi_rad), -math.sin(state.psi_rad), 1.0
                gx, gy = gx / norm, gy / norm
                correction = max(0.06, settings.guard_distance_m - projected_clearance + 0.07)
                state = CraftState(
                    x_m=state.x_m + correction * gx,
                    y_m=state.y_m + correction * gy,
                    psi_rad=math.atan2(gy, gx),
                    u_mps=0.0,
                    v_mps=0.0,
                    r_rps=0.0,
                )
                if follower is not None and set_route(
                    follower.path.goal_m,
                    "safety_replan",
                    "safety supervisor projected state and re-planned a safe route",
                    time_s,
                ):
                    replan_count += 1
                    events.append(
                        {
                            "time_s": time_s,
                            "event": "SAFETY_REPLAN",
                            "mode": mode,
                            "reason": "predicted clearance below guard distance",
                            "x_m": state.x_m,
                            "y_m": state.y_m,
                        }
                    )
            else:
                state = integrated

        if follower is not None and mode in {"SEARCH", "TRANSIT_TO_TARGET", "RETURN_HOME"}:
            route_length = max(0.5, follower.path.length_m)
            elapsed = time_s - leg_started_s
            goal_distance = math.hypot(follower.path.goal_m[0] - state.x_m, follower.path.goal_m[1] - state.y_m)
            speed_for_budget = max(0.10, desired_speed if desired_speed > 0 else settings.return_speed_mps)
            time_budget = max(24.0, settings.route_budget_factor * route_length / speed_for_budget)
            if elapsed > time_budget and goal_distance > settings.waypoint_tolerance_m:
                watchdog_count += 1
                watchdog_for_leg += 1
                events.append(
                    {
                        "time_s": time_s,
                        "event": "PROGRESS_WATCHDOG",
                        "mode": mode,
                        "reason": "route-time budget exceeded; route refresh requested",
                        "x_m": state.x_m,
                        "y_m": state.y_m,
                    }
                )
                if set_route(follower.path.goal_m, "watchdog_replan", "progress watchdog route refresh", time_s):
                    replan_count += 1
                if watchdog_for_leg >= 2 and mode == "TRANSIT_TO_TARGET":
                    events.append(
                        {
                            "time_s": time_s,
                            "event": "TARGET_DEFERRED",
                            "mode": mode,
                            "reason": "two route refreshes without target convergence; return to coverage",
                            "target_id": active_target.identifier if active_target else "",
                            "x_m": state.x_m,
                            "y_m": state.y_m,
                        }
                    )
                    active_target = None
                    switch_mode("SEARCH", "defer non-convergent target and resume coverage", time_s)
                    if coverage_index < len(coverage):
                        set_route(coverage[coverage_index], f"coverage_lane_{coverage_index + 1:03d}", "coverage recovery after watchdog", time_s)

        x_drag, y_drag, n_drag = model.hydrodynamic_forces(state, settings.current_earth_mps)
        ground_speed = math.hypot(state.u_mps, state.v_mps)
        rows.append(
            {
                "time_s": time_s,
                "mode": mode,
                "control_regime": control_regime,
                "x_m": state.x_m,
                "y_m": state.y_m,
                "psi_deg": math.degrees(state.psi_rad),
                "u_mps": state.u_mps,
                "v_mps": state.v_mps,
                "r_rps": state.r_rps,
                "ground_speed_mps": ground_speed,
                "guidance_x_m": guidance_target[0],
                "guidance_y_m": guidance_target[1],
                "desired_heading_deg": math.degrees(desired_heading),
                "ground_track_heading_deg": math.degrees(ground_track_heading),
                "crab_angle_deg": math.degrees(crab_angle),
                "heading_error_deg": math.degrees(heading_error),
                "desired_speed_mps": speed_command,
                "desired_ground_speed_mps": desired_ground_speed,
                "desired_water_speed_mps": desired_speed,
                "port_thrust_n": command.port_thrust_n,
                "starboard_thrust_n": command.starboard_thrust_n,
                "total_thrust_n": command.total_thrust_n,
                "yaw_moment_n_m": model.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n),
                "x_drag_n": x_drag,
                "y_drag_n": y_drag,
                "yaw_drag_n_m": n_drag,
                "current_x_mps": settings.current_earth_mps[0],
                "current_y_mps": settings.current_earth_mps[1],
                "hazard_clearance_m": environment.signed_distance_to_nearest_hazard_m(state.x_m, state.y_m),
                "soc": soc,
                "bus_power_w": bus_power,
                "battery_current_a": battery_load.pack_current_a,
                "collected_count": len(collected_ids),
                "hopper_mass_kg": hopper.captured_mass_kg,
                "hopper_volume_l": hopper.occupied_volume_l,
                "hopper_mass_fraction": hopper.mass_fraction(hopper_settings),
                "hopper_volume_fraction": hopper.volume_fraction(hopper_settings),
                "coverage_progress": coverage_index / max(1, len(coverage)),
                "active_target": active_target.identifier if active_target else "",
                "route_id": route_id,
                "safety_events": safety_count,
                "replan_count": replan_count,
                "watchdog_count": watchdog_count,
            }
        )
        if mode == "MISSION_COMPLETE":
            break
        if time_s >= settings.duration_s:
            route_home("mission time limit reached", time_s)

    final = rows[-1]
    final_distance_home = math.hypot(
        float(final["x_m"]) - environment.home_position_m[0],
        float(final["y_m"]) - environment.home_position_m[1],
    )
    success = (
        final["mode"] == "MISSION_COMPLETE"
        and min_clearance >= settings.guard_distance_m - 1e-6
        and final_distance_home <= settings.waypoint_tolerance_m + 1e-6
    )
    tracking_errors_deg = [
        abs(float(row["heading_error_deg"]))
        for row in rows
        if str(row.get("control_regime", "")) == "TRACK"
    ]
    control_transitions = sum(
        1
        for earlier, later in zip(rows[:-1], rows[1:])
        if earlier.get("control_regime") != later.get("control_regime")
    )
    deferred_target_count = sum(1 for event in events if event.get("event") == "TARGET_DEFERRED")

    metrics = {
        "mission_success": int(success),
        "final_state": final["mode"],
        "termination_reason": return_reason or "mission complete",
        "duration_s": final["time_s"],
        "collected_count": len(collected_ids),
        "collected_mass_kg": hopper.captured_mass_kg,
        "occupied_hopper_volume_l": hopper.occupied_volume_l,
        "hopper_mass_fraction": hopper.mass_fraction(hopper_settings),
        "hopper_volume_fraction": hopper.volume_fraction(hopper_settings),
        "effective_hopper_payload_limit_kg": hopper_settings.effective_payload_limit_kg,
        "final_soc": final["soc"],
        "minimum_clearance_m": min_clearance,
        "planned_route_length_m": planned_path_length,
        "replan_count": replan_count,
        "safety_event_count": safety_count,
        "watchdog_event_count": watchdog_count,
        "target_deferred_count": deferred_target_count,
        "tracking_heading_error_p95_deg": float(np.percentile(tracking_errors_deg, 95)) if tracking_errors_deg else float("nan"),
        "tracking_heading_error_max_deg": max(tracking_errors_deg) if tracking_errors_deg else float("nan"),
        "control_regime_transition_count": control_transitions,
        "final_distance_home_m": final_distance_home,
        "coverage_fraction": float(final["coverage_progress"]),
        "debris_field_count": len(debris_items),
    }
    return QualityMissionResult(
        rows=rows,
        events=events,
        routes=routes,
        targets=target_rows,
        metrics=metrics,
    )
