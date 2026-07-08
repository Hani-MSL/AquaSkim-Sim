"""Deterministic current-aware path-holding and controller sensitivity tools.

This module uses the fixed reference 3-DOF plant directly.  It does not create
illustrative trajectories: all plots and replays are based on logged RK4 states,
logged thruster commands and the same relative-water hydrodynamic model used by
the reference mission.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from aquaskim.config import ProjectConfiguration, validate_base_configuration
from aquaskim.dynamics_3dof import CraftState, PlanarCatamaranDynamics, ThrusterCommand, wrap_to_pi
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.mission_quality import current_aware_course_command
from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration, project_root


class ControlRobustnessError(ValueError):
    """Raised when the versioned control-robustness protocol is invalid."""


@dataclass(frozen=True)
class TrackHoldCase:
    identifier: str
    title: str
    classification: str
    control_mode: str
    current_compensation_gain: float
    heading_kp_scale: float
    heading_kd_scale: float
    description: str


@dataclass(frozen=True)
class TrackHoldResult:
    case: TrackHoldCase
    rows: list[dict[str, Any]]
    events: list[dict[str, Any]]
    metrics: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ControlRobustnessError(f"Protocol file must be a mapping: {path}")
    return data


def load_control_robustness(path: Path | None = None) -> dict[str, Any]:
    source = path or project_root() / "config" / "reference_control_robustness.yaml"
    root = _read_yaml(source)
    protocol = root.get("reference_control_robustness")
    if not isinstance(protocol, dict):
        raise ControlRobustnessError("Protocol requires a reference_control_robustness mapping.")
    required = ("identifier", "validated_current_magnitude_mps", "track_hold", "cases", "sensitivity", "acceptance")
    missing = [key for key in required if key not in protocol]
    if missing:
        raise ControlRobustnessError(f"Protocol missing keys: {missing}")
    limit = float(protocol["validated_current_magnitude_mps"])
    if limit <= 0:
        raise ControlRobustnessError("validated_current_magnitude_mps must be positive.")
    track = protocol["track_hold"]
    if not isinstance(track, dict):
        raise ControlRobustnessError("track_hold must be a mapping.")
    for key in ("duration_s", "onset_s", "target_ground_speed_mps", "current_earth_mps"):
        if key not in track:
            raise ControlRobustnessError(f"track_hold missing {key}.")
    current = track["current_earth_mps"]
    if not isinstance(current, list) or len(current) != 2:
        raise ControlRobustnessError("track_hold.current_earth_mps must have exactly two components.")
    if math.hypot(float(current[0]), float(current[1])) > limit + 1e-12:
        raise ControlRobustnessError("Track-hold current exceeds validated magnitude limit.")
    cases = control_cases(protocol)
    if len(cases) < 3 or not any(case.control_mode == "open_loop" for case in cases) or not any(case.classification == "validated" for case in cases):
        raise ControlRobustnessError("Protocol requires comparison open-loop and validated current-aware cases.")
    sensitivity = protocol["sensitivity"]
    kp = sensitivity.get("heading_kp_scales", []) if isinstance(sensitivity, dict) else []
    kd = sensitivity.get("heading_kd_scales", []) if isinstance(sensitivity, dict) else []
    if not isinstance(kp, list) or not isinstance(kd, list) or len(kp) < 3 or len(kd) < 3:
        raise ControlRobustnessError("Sensitivity requires at least three Kp and three Kd scales.")
    return protocol


def _case_from_mapping(item: Any) -> TrackHoldCase:
    if not isinstance(item, dict):
        raise ControlRobustnessError("Each control case must be a mapping.")
    required = ("id", "title", "classification", "control_mode", "current_compensation_gain", "heading_kp_scale", "heading_kd_scale", "description")
    missing = [key for key in required if key not in item]
    if missing:
        raise ControlRobustnessError(f"Control case missing keys: {missing}")
    mode = str(item["control_mode"])
    if mode not in {"open_loop", "current_aware"}:
        raise ControlRobustnessError(f"Unsupported control mode: {mode}")
    return TrackHoldCase(
        identifier=str(item["id"]), title=str(item["title"]), classification=str(item["classification"]),
        control_mode=mode, current_compensation_gain=float(item["current_compensation_gain"]),
        heading_kp_scale=float(item["heading_kp_scale"]), heading_kd_scale=float(item["heading_kd_scale"]),
        description=str(item["description"]),
    )


def control_cases(protocol: dict[str, Any] | None = None) -> list[TrackHoldCase]:
    active = protocol if protocol is not None else load_control_robustness()
    return [_case_from_mapping(item) for item in active["cases"]]


def sensitivity_cases(protocol: dict[str, Any] | None = None) -> list[TrackHoldCase]:
    active = protocol if protocol is not None else load_control_robustness()
    sensitivity = active["sensitivity"]
    output: list[TrackHoldCase] = []
    for kp in [float(value) for value in sensitivity["heading_kp_scales"]]:
        for kd in [float(value) for value in sensitivity["heading_kd_scales"]]:
            output.append(TrackHoldCase(
                identifier=f"sensitivity_kp_{kp:.2f}_kd_{kd:.2f}".replace(".", "p"),
                title=f"Gain sensitivity Kp×{kp:.2f}, Kd×{kd:.2f}",
                classification="sensitivity", control_mode=str(sensitivity.get("control_mode", "current_aware")),
                current_compensation_gain=float(sensitivity.get("current_compensation_gain", 1.0)),
                heading_kp_scale=kp, heading_kd_scale=kd,
                description=str(sensitivity.get("description", "Bounded heading gain sensitivity.")),
            ))
    return output


def _case_configuration(base: ProjectConfiguration, protocol: dict[str, Any]) -> ProjectConfiguration:
    """Copy fixed reference data without reading any local profile or legacy module."""
    data = deepcopy(base.data)
    track = protocol["track_hold"]
    data.setdefault("autonomy", {})["current_earth_mps"] = list(track["current_earth_mps"])
    data["autonomy"]["control_period_s"] = float(track["control_period_s"])
    validate_base_configuration(data)
    return ProjectConfiguration(source_path=base.source_path, data=data)


def _array(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, 0.0)) for row in rows], dtype=float)


def simulate_track_hold(case: TrackHoldCase, protocol: dict[str, Any] | None = None, base: ProjectConfiguration | None = None) -> TrackHoldResult:
    """Simulate one fixed earth-track hold under the documented imposed current."""
    active = protocol if protocol is not None else load_control_robustness()
    config = _case_configuration(base or load_reference_configuration(), active)
    model, _, _, _, _, _ = build_digital_twin_plant(config)
    settings = _settings(config.data)
    track = active["track_hold"]
    duration = float(track["duration_s"])
    onset = float(track["onset_s"])
    desired_ground_speed = float(track["target_ground_speed_mps"])
    base_heading = math.radians(float(track.get("target_ground_heading_deg", 0.0)))
    current = tuple(float(value) for value in track["current_earth_mps"])
    lookahead = max(0.10, float(track["cross_track_lookahead_m"]))
    control_period = float(track["control_period_s"])
    max_yaw = float(track["max_yaw_moment_n_m"])
    max_forward = float(track["max_forward_thrust_n"])
    pivot_entry = math.radians(float(track["pivot_entry_heading_error_deg"]))
    pivot_exit = math.radians(float(track["pivot_exit_heading_error_deg"]))
    pivot_limit = float(track["pivot_turn_thrust_n"])
    open_loop_side = float(track["open_loop_thrust_per_side_n"])
    dt = model.settings.integration_time_step_s
    control_steps = max(1, int(round(control_period / dt)))
    steps = int(round(duration / dt))
    state = CraftState()
    command = ThrusterCommand(0.0, 0.0)
    regime = "IDLE"
    turning_in_place = False
    previous_regime = regime
    events: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for step in range(steps + 1):
        time_s = step * dt
        cross_track = state.y_m * math.cos(base_heading) - state.x_m * math.sin(base_heading)
        along_track = state.x_m * math.cos(base_heading) + state.y_m * math.sin(base_heading)
        if time_s < onset:
            ground_heading = base_heading
            desired_heading = base_heading
            desired_water_speed = 0.0
            crab = 0.0
            heading_error = wrap_to_pi(desired_heading - state.psi_rad)
            command = ThrusterCommand(0.0, 0.0)
            regime = "IDLE"
        elif case.control_mode == "open_loop":
            ground_heading = base_heading
            desired_heading = base_heading
            desired_water_speed = desired_ground_speed
            crab = 0.0
            heading_error = wrap_to_pi(desired_heading - state.psi_rad)
            command = ThrusterCommand(open_loop_side, open_loop_side)
            regime = "OPEN_LOOP_CRUISE"
        else:
            # A finite lookahead transforms cross-track error to a stable
            # earth-fixed path-heading correction. Current feedforward then
            # converts that requested ground vector into a water-relative course.
            ground_heading = wrap_to_pi(base_heading - math.atan2(cross_track, lookahead))
            desired_heading, desired_water_speed, crab = current_aware_course_command(
                ground_heading, desired_ground_speed, current, enabled=True,
                gain=case.current_compensation_gain,
                activation_speed_mps=0.0,
            )
            heading_error = wrap_to_pi(desired_heading - state.psi_rad)
            if step % control_steps == 0:
                u_rel, _ = model.relative_water_velocity_body(state, current)
                if turning_in_place:
                    if abs(heading_error) <= pivot_exit and abs(u_rel) <= 0.045:
                        turning_in_place = False
                elif abs(heading_error) >= pivot_entry:
                    turning_in_place = True
                kp = float(settings.heading_kp_n_m_per_rad) * case.heading_kp_scale
                kd = float(settings.heading_kd_n_m_per_rps) * case.heading_kd_scale
                yaw_moment = max(-max_yaw, min(max_yaw, kp * heading_error - kd * state.r_rps))
                if turning_in_place:
                    if abs(u_rel) > 0.045:
                        braking = min(0.38, 1.20 * abs(u_rel))
                        direction = -1.0 if u_rel > 0.0 else 1.0
                        command = ThrusterCommand(direction * braking, direction * braking)
                        regime = "BRAKE_FOR_PIVOT"
                    else:
                        sign = 1.0 if yaw_moment >= 0.0 else -1.0
                        pivot = max(0.13, min(pivot_limit, abs(yaw_moment) / max(model.thruster_half_spacing_m, 1e-9)))
                        command = ThrusterCommand(-sign * pivot, sign * pivot)
                        regime = "PIVOT"
                else:
                    alignment = max(0.0, math.cos(abs(heading_error)))
                    speed_command = desired_water_speed * alignment
                    drag = model.resistance.state_at_speed(max(0.02, speed_command)).total_resistance_n if speed_command > 0.0 else 0.0
                    total_force = max(-0.35, min(max_forward, drag + float(settings.speed_kp_n_per_mps) * (speed_command - u_rel)))
                    if total_force < 0.0:
                        command = ThrusterCommand(total_force / 2.0, total_force / 2.0)
                        regime = "BRAKE_TO_TRACK"
                    else:
                        differential = yaw_moment / max(model.thruster_half_spacing_m, 1e-9)
                        differential = max(-0.82 * total_force, min(0.82 * total_force, differential))
                        command = ThrusterCommand(0.5 * (total_force - differential), 0.5 * (total_force + differential))
                        regime = "CURRENT_AWARE_TRACK"
            else:
                heading_error = wrap_to_pi(desired_heading - state.psi_rad)

        if regime != previous_regime:
            events.append({"time_s": time_s, "event": "CONTROL_REGIME_CHANGE", "from_regime": previous_regime, "to_regime": regime, "case": case.identifier})
            previous_regime = regime
        u_rel, v_rel = model.relative_water_velocity_body(state, current)
        x_drag, y_drag, yaw_drag = model.hydrodynamic_forces(state, current)
        ground_speed = math.hypot(state.u_mps, state.v_mps)
        ground_track_heading = math.atan2(state.v_mps, state.u_mps) if ground_speed > 1e-9 else base_heading
        rows.append({
            "case": case.identifier, "case_title": case.title, "classification": case.classification,
            "time_s": time_s, "x_m": state.x_m, "y_m": state.y_m, "psi_deg": math.degrees(state.psi_rad),
            "u_mps": state.u_mps, "v_mps": state.v_mps, "r_rps": state.r_rps,
            "speed_over_ground_mps": ground_speed, "u_relative_water_mps": u_rel, "v_relative_water_mps": v_rel,
            "current_x_mps": current[0], "current_y_mps": current[1],
            "cross_track_error_m": cross_track, "along_track_m": along_track,
            "ground_track_heading_deg": math.degrees(ground_heading), "desired_heading_deg": math.degrees(desired_heading),
            "actual_ground_velocity_heading_deg": math.degrees(ground_track_heading),
            "heading_error_deg": math.degrees(heading_error), "desired_ground_speed_mps": desired_ground_speed if time_s >= onset else 0.0,
            "desired_water_speed_mps": desired_water_speed, "crab_angle_deg": math.degrees(crab),
            "port_thrust_n": command.port_thrust_n, "starboard_thrust_n": command.starboard_thrust_n,
            "total_thrust_n": command.total_thrust_n, "yaw_moment_n_m": model.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n),
            "x_drag_n": x_drag, "y_drag_n": y_drag, "yaw_drag_n_m": yaw_drag,
            "control_regime": regime, "current_compensation_gain": case.current_compensation_gain,
            "heading_kp_scale": case.heading_kp_scale, "heading_kd_scale": case.heading_kd_scale,
        })
        if step < steps:
            state = model.rk4_step(state, command, current, dt)

    t = _array(rows, "time_s")
    post = t >= max(onset + 8.0, duration * 0.25)
    if not np.any(post):
        post = t >= onset
    cross = _array(rows, "cross_track_error_m")
    heading = _array(rows, "heading_error_deg")
    speed = _array(rows, "speed_over_ground_mps")
    yaw = _array(rows, "r_rps")
    thrust = _array(rows, "total_thrust_n")
    metrics = {
        "case": case.identifier, "title": case.title, "classification": case.classification, "control_mode": case.control_mode,
        "current_magnitude_mps": math.hypot(*current), "current_compensation_gain": case.current_compensation_gain,
        "heading_kp_scale": case.heading_kp_scale, "heading_kd_scale": case.heading_kd_scale,
        "duration_s": duration, "final_cross_track_error_m": float(cross[-1]), "final_abs_cross_track_error_m": float(abs(cross[-1])),
        "p95_abs_cross_track_error_m": float(np.percentile(np.abs(cross[post]), 95)),
        "rms_cross_track_error_m": float(np.sqrt(np.mean(cross[post] ** 2))),
        "p95_abs_heading_error_deg": float(np.percentile(np.abs(heading[post]), 95)),
        "peak_abs_heading_error_deg": float(np.max(np.abs(heading))),
        "mean_ground_speed_mps": float(np.mean(speed[post])), "p05_ground_speed_mps": float(np.percentile(speed[post], 5)),
        "peak_abs_yaw_rate_rps": float(np.max(np.abs(yaw))), "peak_abs_total_thrust_n": float(np.max(np.abs(thrust))),
        "integrated_abs_thrust_n_s": float(np.trapezoid(np.abs(thrust), t)),
        "mean_abs_crab_angle_deg": float(np.mean(np.abs(_array(rows, "crab_angle_deg")[post]))),
        "pivot_or_brake_sample_count": int(sum(str(row["control_regime"]) in {"PIVOT", "BRAKE_FOR_PIVOT", "BRAKE_TO_TRACK"} for row in rows)),
        "control_regime_transition_count": int(len(events)),
    }
    events.append({"time_s": duration, "event": "TRACK_HOLD_COMPLETE", "case": case.identifier, "reason": "fixed deterministic manoeuvre duration elapsed"})
    return TrackHoldResult(case=case, rows=rows, events=events, metrics=metrics)


def run_control_suite(protocol: dict[str, Any] | None = None) -> tuple[list[TrackHoldResult], list[TrackHoldResult], dict[str, Any]]:
    active = protocol if protocol is not None else load_control_robustness()
    base = load_reference_configuration()
    cases = [simulate_track_hold(case, active, base) for case in control_cases(active)]
    sensitivity = [simulate_track_hold(case, active, base) for case in sensitivity_cases(active)]
    return cases, sensitivity, active


def assess_control_suite(cases: list[TrackHoldResult], sensitivity: list[TrackHoldResult], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    acceptance = protocol["acceptance"]
    by_id = {item.case.identifier: item for item in cases}
    open_loop = by_id["open_loop_cross_current"].metrics
    nominal = by_id["compensated_nominal"].metrics
    rows: list[dict[str, Any]] = []
    def check(name: str, observed: Any, criterion: str, passed: bool) -> None:
        rows.append({"check": name, "observed": observed, "criterion": criterion, "status": "PASS" if passed else "FAIL"})
    check("compensated p95 cross-track error", nominal["p95_abs_cross_track_error_m"], f"<= {acceptance['compensated_max_p95_abs_cross_track_m']} m", nominal["p95_abs_cross_track_error_m"] <= float(acceptance["compensated_max_p95_abs_cross_track_m"]) + 1e-12)
    check("compensated final cross-track error", nominal["final_abs_cross_track_error_m"], f"<= {acceptance['compensated_max_final_abs_cross_track_m']} m", nominal["final_abs_cross_track_error_m"] <= float(acceptance["compensated_max_final_abs_cross_track_m"]) + 1e-12)
    check("compensated p95 heading error", nominal["p95_abs_heading_error_deg"], f"<= {acceptance['compensated_max_p95_heading_error_deg']} deg", nominal["p95_abs_heading_error_deg"] <= float(acceptance["compensated_max_p95_heading_error_deg"]) + 1e-12)
    check("open-loop current drift is observable", open_loop["final_abs_cross_track_error_m"], f">= {acceptance['open_loop_min_final_abs_cross_track_m']} m", open_loop["final_abs_cross_track_error_m"] + 1e-12 >= float(acceptance["open_loop_min_final_abs_cross_track_m"]))
    check("sensitivity p95 cross-track bound", max(item.metrics["p95_abs_cross_track_error_m"] for item in sensitivity), f"<= {acceptance['sensitivity_max_p95_abs_cross_track_m']} m", max(item.metrics["p95_abs_cross_track_error_m"] for item in sensitivity) <= float(acceptance["sensitivity_max_p95_abs_cross_track_m"]) + 1e-12)
    check("sensitivity p95 heading bound", max(item.metrics["p95_abs_heading_error_deg"] for item in sensitivity), f"<= {acceptance['sensitivity_max_p95_heading_error_deg']} deg", max(item.metrics["p95_abs_heading_error_deg"] for item in sensitivity) <= float(acceptance["sensitivity_max_p95_heading_error_deg"]) + 1e-12)
    check("sensitivity maintains translation", min(item.metrics["mean_ground_speed_mps"] for item in sensitivity), f">= {acceptance['sensitivity_min_mean_ground_speed_mps']} m/s", min(item.metrics["mean_ground_speed_mps"] for item in sensitivity) + 1e-12 >= float(acceptance["sensitivity_min_mean_ground_speed_mps"]))
    limit = float(protocol["validated_current_magnitude_mps"])
    check("current remains inside declared validation limit", max(item.metrics["current_magnitude_mps"] for item in cases + sensitivity), f"<= {limit:.3f} m/s", max(item.metrics["current_magnitude_mps"] for item in cases + sensitivity) <= limit + 1e-12)
    return rows
