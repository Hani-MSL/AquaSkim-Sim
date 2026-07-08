"""Deterministic low-speed marine manoeuvre simulations for AquaSkim-Sim.

The routines in this module run directly on the existing 3-DOF plant.  They do
not invent illustrative paths: every plotted or animated trajectory comes from
logged RK4 state histories and logged twin-thruster / hydrodynamic-force terms.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import degrees, hypot
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from aquaskim.config import ProjectConfiguration
from aquaskim.dynamics_3dof import CraftState, PlanarCatamaranDynamics, ThrusterCommand
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.reference_design import load_reference_configuration, project_root


@dataclass(frozen=True)
class ManeuverResult:
    name: str
    description: str
    rows: list[dict[str, float | str]]
    events: list[dict[str, float | str]]

    @property
    def final(self) -> dict[str, float | str]:
        return self.rows[-1]


def load_protocol() -> dict[str, Any]:
    path = project_root() / "config" / "maneuver_protocol.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "reference_maneuver_protocol" not in data:
        raise ValueError("maneuver_protocol.yaml must contain reference_maneuver_protocol.")
    return data["reference_maneuver_protocol"]


def _record_row(
    model: PlanarCatamaranDynamics,
    state: CraftState,
    command: ThrusterCommand,
    current: tuple[float, float],
    time_s: float,
    name: str,
    command_state: str,
) -> dict[str, float | str]:
    u_rel, v_rel = model.relative_water_velocity_body(state, current)
    x_drag, y_drag, n_drag = model.hydrodynamic_forces(state, current)
    return {
        "maneuver": name,
        "time_s": float(time_s),
        "x_m": state.x_m,
        "y_m": state.y_m,
        "psi_rad": state.psi_rad,
        "psi_deg": degrees(state.psi_rad),
        "u_mps": state.u_mps,
        "v_mps": state.v_mps,
        "r_rps": state.r_rps,
        "speed_over_ground_mps": hypot(state.u_mps, state.v_mps),
        "u_relative_water_mps": u_rel,
        "v_relative_water_mps": v_rel,
        "port_thrust_n": command.port_thrust_n,
        "starboard_thrust_n": command.starboard_thrust_n,
        "total_thrust_n": command.total_thrust_n,
        "yaw_moment_n_m": model.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n),
        "x_drag_n": x_drag,
        "y_drag_n": y_drag,
        "yaw_drag_n_m": n_drag,
        "current_x_mps": current[0],
        "current_y_mps": current[1],
        "command_state": command_state,
    }


def _open_loop(
    model: PlanarCatamaranDynamics,
    *,
    name: str,
    description: str,
    duration_s: float,
    current_earth_mps: tuple[float, float],
    command_at,
) -> ManeuverResult:
    dt = model.settings.integration_time_step_s
    sample_every = max(1, int(round(model.settings.trajectory_sample_interval_s / dt)))
    state = CraftState()
    rows: list[dict[str, float | str]] = []
    steps = int(round(duration_s / dt))
    for step in range(steps + 1):
        time_s = step * dt
        command, command_state = command_at(time_s)
        if step % sample_every == 0 or step == steps:
            rows.append(_record_row(model, state, command, current_earth_mps, time_s, name, command_state))
        if step < steps:
            state = model.rk4_step(state, command, current_earth_mps, dt)
    return ManeuverResult(name=name, description=description, rows=rows, events=[])


def simulate_step_thrust(model: PlanarCatamaranDynamics, protocol: dict[str, Any]) -> ManeuverResult:
    p = protocol["step_thrust"]
    onset, thrust = float(p["onset_s"]), float(p["thrust_per_side_n"])
    return _open_loop(
        model,
        name="symmetric_step_thrust",
        description="Symmetric moderate thrust step for surge response and force balance.",
        duration_s=float(p["duration_s"]),
        current_earth_mps=(0.0, 0.0),
        command_at=lambda t: (
            ThrusterCommand(0.0, 0.0) if t < onset else ThrusterCommand(thrust, thrust),
            "idle" if t < onset else "symmetric step",
        ),
    )


def simulate_turning_circle(model: PlanarCatamaranDynamics, protocol: dict[str, Any]) -> ManeuverResult:
    p = protocol["turning_circle"]
    onset = float(p["onset_s"])
    port, starboard = float(p["port_thrust_n"]), float(p["starboard_thrust_n"])
    return _open_loop(
        model,
        name="differential_turning_circle",
        description="Constant differential thrust turn with positive forward propulsion.",
        duration_s=float(p["duration_s"]),
        current_earth_mps=(0.0, 0.0),
        command_at=lambda t: (
            ThrusterCommand(0.0, 0.0) if t < onset else ThrusterCommand(port, starboard),
            "idle" if t < onset else "starboard-biased turn",
        ),
    )


def simulate_cross_current(model: PlanarCatamaranDynamics, protocol: dict[str, Any]) -> ManeuverResult:
    p = protocol["cross_current"]
    onset, thrust = float(p["onset_s"]), float(p["thrust_per_side_n"])
    current = tuple(float(x) for x in p["current_earth_mps"])
    return _open_loop(
        model,
        name="open_loop_cross_current",
        description="Symmetric open-loop thrust under a low cross-current disturbance.",
        duration_s=float(p["duration_s"]),
        current_earth_mps=(current[0], current[1]),
        command_at=lambda t: (
            ThrusterCommand(0.0, 0.0) if t < onset else ThrusterCommand(thrust, thrust),
            "idle" if t < onset else "symmetric cruise",
        ),
    )


def simulate_zig_zag(model: PlanarCatamaranDynamics, protocol: dict[str, Any]) -> ManeuverResult:
    """State-triggered ±heading zig-zag with fixed documented actuation.

    The test is deliberately feedback-triggered: a switch occurs only after the
    simulated heading crosses the requested ±target.  This avoids a misleading
    time-scripted oscillation that could be disconnected from the plant state.
    """
    p = protocol["zig_zag"]
    onset = float(p["onset_s"])
    target_rad = np.deg2rad(float(p["target_heading_deg"]))
    mean = float(p["mean_thrust_per_side_n"])
    differential = float(p["differential_thrust_n"])
    duration = float(p["duration_s"])
    dt = model.settings.integration_time_step_s
    sample_every = max(1, int(round(model.settings.trajectory_sample_interval_s / dt)))
    state = CraftState()
    direction = 1.0
    active = False
    reversals = 0
    events: list[dict[str, float | str]] = []
    rows: list[dict[str, float | str]] = []
    steps = int(round(duration / dt))
    for step in range(steps + 1):
        time_s = step * dt
        if time_s < onset:
            command, command_state = ThrusterCommand(0.0, 0.0), "idle"
        else:
            if not active:
                active = True
                events.append({"time_s": time_s, "event": "ZIGZAG_START", "reason": "documented step onset"})
            if direction > 0.0 and state.psi_rad >= target_rad:
                direction = -1.0
                reversals += 1
                events.append({"time_s": time_s, "event": "HEADING_REVERSAL", "target_heading_deg": -float(p["target_heading_deg"]), "reason": "positive heading threshold crossed"})
            elif direction < 0.0 and state.psi_rad <= -target_rad:
                direction = 1.0
                reversals += 1
                events.append({"time_s": time_s, "event": "HEADING_REVERSAL", "target_heading_deg": float(p["target_heading_deg"]), "reason": "negative heading threshold crossed"})
            command = ThrusterCommand(mean - direction * differential / 2.0, mean + direction * differential / 2.0)
            command_state = "turn_starboard" if direction > 0.0 else "turn_port"
        if step % sample_every == 0 or step == steps:
            row = _record_row(model, state, command, (0.0, 0.0), time_s, "heading_zig_zag", command_state)
            row["heading_target_deg"] = direction * float(p["target_heading_deg"]) if active else 0.0
            row["reversal_count"] = reversals
            rows.append(row)
        if step < steps:
            state = model.rk4_step(state, command, (0.0, 0.0), dt)
    return ManeuverResult(
        name="heading_zig_zag",
        description="State-triggered small-angle differential-thrust zig-zag for yaw damping observation.",
        rows=rows,
        events=events,
    )


def _unwrapped_heading(rows: list[dict[str, float | str]]) -> np.ndarray:
    return np.unwrap(np.asarray([float(row["psi_rad"]) for row in rows], dtype=float))


def result_metrics(result: ManeuverResult, protocol: dict[str, Any]) -> dict[str, float | str]:
    rows = result.rows
    t = np.asarray([float(row["time_s"]) for row in rows])
    heading = _unwrapped_heading(rows)
    speed = np.asarray([float(row["speed_over_ground_mps"]) for row in rows])
    yaw = np.asarray([float(row["r_rps"]) for row in rows])
    if result.name == "symmetric_step_thrust":
        p = protocol["step_thrust"]
        onset = float(p["onset_s"])
        steady_mask = t >= (t[-1] - float(p["steady_window_s"]))
        steady_speed = float(np.mean(speed[steady_mask]))
        threshold = 0.9 * steady_speed
        candidate = np.where((t >= onset) & (speed >= threshold))[0]
        rise = float(t[candidate[0]] - onset) if candidate.size else float("nan")
        acceleration = np.gradient(np.asarray([float(row["u_mps"]) for row in rows]), t)
        return {
            "maneuver": result.name,
            "steady_speed_mps": steady_speed,
            "rise_time_to_90pct_s": rise,
            "peak_surge_acceleration_mps2": float(np.max(acceleration)),
            "peak_abs_yaw_rate_rps": float(np.max(np.abs(yaw))),
            "final_x_m": float(rows[-1]["x_m"]),
        }
    if result.name == "differential_turning_circle":
        distances = np.hypot(np.diff([float(row["x_m"]) for row in rows]), np.diff([float(row["y_m"]) for row in rows]))
        path_length = float(np.sum(distances))
        heading_change = float(abs(heading[-1] - heading[0]))
        radius = path_length / heading_change if heading_change > 1e-9 else float("nan")
        return {
            "maneuver": result.name,
            "path_length_m": path_length,
            "heading_change_deg": float(np.rad2deg(heading_change)),
            "kinematic_turn_radius_m": radius,
            "kinematic_turn_diameter_m": 2.0 * radius,
            "peak_yaw_rate_rps": float(np.max(np.abs(yaw))),
            "final_speed_mps": float(speed[-1]),
        }
    if result.name == "heading_zig_zag":
        p = protocol["zig_zag"]
        target = float(p["target_heading_deg"])
        headings = np.asarray([float(row["psi_deg"]) for row in rows])
        reversals = sum(1 for e in result.events if e["event"] == "HEADING_REVERSAL")
        overshoot = max(0.0, float(np.max(np.abs(headings))) - target)
        return {
            "maneuver": result.name,
            "heading_target_deg": target,
            "reversal_count": float(reversals),
            "peak_heading_deg": float(np.max(np.abs(headings))),
            "overshoot_deg": overshoot,
            "peak_yaw_rate_rps": float(np.max(np.abs(yaw))),
        }
    if result.name == "open_loop_cross_current":
        return {
            "maneuver": result.name,
            "final_x_m": float(rows[-1]["x_m"]),
            "cross_track_drift_m": float(rows[-1]["y_m"]),
            "final_speed_mps": float(speed[-1]),
            "peak_abs_sway_mps": float(np.max(np.abs([float(row["v_mps"]) for row in rows]))),
            "peak_abs_yaw_rate_rps": float(np.max(np.abs(yaw))),
        }
    raise ValueError(f"No metric extractor for {result.name}")


def time_step_convergence(protocol: dict[str, Any]) -> list[dict[str, float]]:
    """Repeat one smooth turn with successively smaller integration time steps."""
    p = protocol["convergence"]
    base = load_reference_configuration()
    output: list[dict[str, float]] = []
    results: dict[float, ManeuverResult] = {}
    for dt in [float(value) for value in p["time_steps_s"]]:
        data = deepcopy(base.data)
        data["dynamics_3dof"]["integration_time_step_s"] = dt
        data["dynamics_3dof"]["trajectory_sample_interval_s"] = dt
        config = ProjectConfiguration(source_path=base.source_path, data=data)
        model, *_ = build_digital_twin_plant(config)
        turn_p = deepcopy(protocol)
        turn_p["turning_circle"] = deepcopy(protocol["turning_circle"])
        turn_p["turning_circle"]["duration_s"] = float(p["turning_duration_s"])
        results[dt] = simulate_turning_circle(model, turn_p)
    ref_dt = float(p["reference_time_step_s"])
    ref = results[ref_dt]
    ref_final = ref.final
    ref_heading = _unwrapped_heading(ref.rows)[-1]
    for dt, result in results.items():
        final = result.final
        heading = _unwrapped_heading(result.rows)[-1]
        position_error = hypot(float(final["x_m"]) - float(ref_final["x_m"]), float(final["y_m"]) - float(ref_final["y_m"]))
        output.append({
            "time_step_s": dt,
            "final_x_m": float(final["x_m"]),
            "final_y_m": float(final["y_m"]),
            "final_heading_deg": degrees(float(heading)),
            "position_error_to_reference_m": position_error,
            "heading_error_to_reference_deg": abs(degrees(float(heading - ref_heading))),
        })
    return sorted(output, key=lambda row: float(row["time_step_s"]), reverse=True)


def run_reference_maneuvers() -> tuple[dict[str, ManeuverResult], list[dict[str, float]], dict[str, Any]]:
    protocol = load_protocol()
    model, *_ = build_digital_twin_plant(load_reference_configuration())
    results = {
        "step": simulate_step_thrust(model, protocol),
        "turn": simulate_turning_circle(model, protocol),
        "zigzag": simulate_zig_zag(model, protocol),
        "current": simulate_cross_current(model, protocol),
    }
    return results, time_step_convergence(protocol), protocol
