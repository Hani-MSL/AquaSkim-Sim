"""Payload-sensitive hydrostatics and deterministic manoeuvre evidence.

This module joins two existing project models without changing either model's
scope: calm-water transverse hydrostatics and the low-speed planar 3-DOF plant.
Payload placement is treated as a point-mass sensitivity.  The port-offset case
uses a quasi-static heeling-moment comparison against the nonlinear righting
curve; it is not a roll-dynamics or wave-response simulation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import degrees, hypot
from typing import Any

import numpy as np
import yaml

from aquaskim.config import ProjectConfiguration
from aquaskim.dynamics_3dof import CraftState, DynamicsSettings, PlanarCatamaranDynamics, ThrusterCommand
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticCase, HydrostaticSettings, HeelState
from aquaskim.mass_properties import MassProperties, PointMass, components_from_config, compute_mass_properties
from aquaskim.reference_design import load_reference_configuration, project_root


@dataclass(frozen=True)
class PayloadCase:
    identifier: str
    title: str
    payload_mass_kg: float
    payload_position_m: tuple[float, float, float]
    classification: str
    description: str


@dataclass(frozen=True)
class PayloadStaticResult:
    payload_case: PayloadCase
    mass_properties: MassProperties
    hydro_case: HydrostaticCase
    heel_curve: list[HeelState]
    operating_state: HeelState
    first_emergence_angle_deg: float | None
    first_freeboard_limit_angle_deg: float | None
    payload_heeling_moment_n_m: float
    offset_equilibrium_heel_deg: float
    offset_righting_margin_ratio: float

    def as_row(self) -> dict[str, float | str]:
        return {
            "payload_case": self.payload_case.identifier,
            "title": self.payload_case.title,
            "classification": self.payload_case.classification,
            "payload_mass_kg": self.payload_case.payload_mass_kg,
            "payload_x_m": self.payload_case.payload_position_m[0],
            "payload_y_m": self.payload_case.payload_position_m[1],
            "payload_z_m": self.payload_case.payload_position_m[2],
            "total_mass_kg": self.mass_properties.total_mass_kg,
            "cg_x_m": self.mass_properties.cg_m[0],
            "cg_y_m": self.mass_properties.cg_m[1],
            "cg_z_m": self.mass_properties.cg_m[2],
            "draft_m": self.hydro_case.draft_m,
            "freeboard_m": self.hydro_case.freeboard_m,
            "gm_m": self.hydro_case.gm_m,
            "righting_moment_at_operational_heel_n_m": self.operating_state.righting_moment_n_m,
            "minimum_freeboard_at_operational_heel_m": self.operating_state.min_freeboard_m,
            "first_emergence_angle_deg": "" if self.first_emergence_angle_deg is None else self.first_emergence_angle_deg,
            "first_freeboard_limit_angle_deg": "" if self.first_freeboard_limit_angle_deg is None else self.first_freeboard_limit_angle_deg,
            "payload_heeling_moment_n_m": self.payload_heeling_moment_n_m,
            "offset_equilibrium_heel_deg": self.offset_equilibrium_heel_deg,
            "offset_righting_margin_ratio": self.offset_righting_margin_ratio,
        }


@dataclass(frozen=True)
class ManeuverResult:
    name: str
    payload_case: PayloadCase
    current_earth_mps: tuple[float, float]
    rows: list[dict[str, float | str]]
    events: list[dict[str, float | str]]
    metrics: dict[str, float | str]


def load_payload_maneuver_protocol() -> dict[str, Any]:
    path = project_root() / "config" / "reference_payload_maneuver_validation.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    protocol = data.get("reference_payload_maneuver_validation") if isinstance(data, dict) else None
    if not isinstance(protocol, dict):
        raise ValueError("reference_payload_maneuver_validation.yaml requires reference_payload_maneuver_validation.")
    return protocol


def load_visual_protocol() -> dict[str, Any]:
    path = project_root() / "config" / "reference_payload_maneuver_visualisation.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    protocol = data.get("reference_payload_maneuver_visualisation") if isinstance(data, dict) else None
    if not isinstance(protocol, dict) or not isinstance(protocol.get("render"), dict):
        raise ValueError("reference_payload_maneuver_visualisation.yaml requires reference_payload_maneuver_visualisation.render.")
    return protocol


def payload_cases(protocol: dict[str, Any] | None = None) -> list[PayloadCase]:
    active = protocol or load_payload_maneuver_protocol()
    result: list[PayloadCase] = []
    for raw in active["payload_cases"]:
        position = raw["payload_position_m"]
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError(f"payload case {raw.get('identifier')} requires payload_position_m with three entries.")
        result.append(PayloadCase(
            identifier=str(raw["identifier"]), title=str(raw["title"]),
            payload_mass_kg=float(raw["payload_mass_kg"]),
            payload_position_m=tuple(float(value) for value in position),
            classification=str(raw["classification"]), description=str(raw["description"]),
        ))
    if len({case.identifier for case in result}) != len(result):
        raise ValueError("Payload case identifiers must be unique.")
    return result


def _payload_mass_properties(data: dict[str, Any], payload_case: PayloadCase) -> MassProperties:
    components = components_from_config(data)
    if payload_case.payload_mass_kg > 0.0:
        components.append(PointMass(
            name=f"payload_{payload_case.identifier}",
            mass_kg=payload_case.payload_mass_kg,
            position_m=payload_case.payload_position_m,
        ))
    return compute_mass_properties(components)


def _plant_from_mass_properties(config: ProjectConfiguration, mass_properties: MassProperties, identifier: str) -> tuple[PlanarCatamaranDynamics, CatamaranHydrostatics, HydrostaticCase]:
    data = config.data
    geometry = CatamaranGeometry.from_config(data)
    hydro = CatamaranHydrostatics(geometry, HydrostaticSettings.from_config(data))
    hydro_case = hydro.case_from_mass_properties(identifier, mass_properties)
    resistance = CatamaranResistanceModel(geometry, HydrodynamicSettings.from_config(data), hydro_case)
    model = PlanarCatamaranDynamics(
        geometry=geometry,
        resistance=resistance,
        hydro_case=hydro_case,
        mass_properties=mass_properties,
        settings=DynamicsSettings.from_config(data),
    )
    return model, hydro, hydro_case


def _interpolate_equilibrium_heel(curve: list[HeelState], moment_n_m: float) -> tuple[float, float]:
    if moment_n_m <= 0.0:
        return 0.0, float("inf")
    previous = curve[0]
    for state in curve[1:]:
        if state.righting_moment_n_m >= moment_n_m:
            denominator = state.righting_moment_n_m - previous.righting_moment_n_m
            fraction = 0.0 if abs(denominator) < 1e-12 else (moment_n_m - previous.righting_moment_n_m) / denominator
            heel = previous.heel_deg + fraction * (state.heel_deg - previous.heel_deg)
            return float(heel), float(state.righting_moment_n_m / moment_n_m)
        previous = state
    return float(curve[-1].heel_deg), float(curve[-1].righting_moment_n_m / moment_n_m)


def build_static_results(protocol: dict[str, Any] | None = None, base: ProjectConfiguration | None = None) -> list[PayloadStaticResult]:
    active = protocol or load_payload_maneuver_protocol()
    config = base or load_reference_configuration()
    data = config.data
    hydro_settings = HydrostaticSettings.from_config(data)
    static = active["static_analysis"]
    max_heel = float(static["heel_plot_max_deg"])
    gravity = hydro_settings.gravity_mps2
    results: list[PayloadStaticResult] = []
    for case in payload_cases(active):
        mass = _payload_mass_properties(data, case)
        _, hydro, hydro_case = _plant_from_mass_properties(config, mass, case.identifier)
        full_curve = hydro.heel_curve(hydro_case)
        curve = [state for state in full_curve if state.heel_deg <= max_heel + 1e-9]
        operating = hydro.operating_state(hydro_case)
        offset_moment = case.payload_mass_kg * gravity * abs(case.payload_position_m[1])
        equilibrium_heel, _ = _interpolate_equilibrium_heel(curve, offset_moment)
        margin = float("inf") if offset_moment <= 0.0 else operating.righting_moment_n_m / offset_moment
        results.append(PayloadStaticResult(
            payload_case=case,
            mass_properties=mass,
            hydro_case=hydro_case,
            heel_curve=curve,
            operating_state=operating,
            first_emergence_angle_deg=hydro.first_emergence_angle_deg(full_curve),
            first_freeboard_limit_angle_deg=hydro.first_freeboard_limit_angle_deg(full_curve),
            payload_heeling_moment_n_m=offset_moment,
            offset_equilibrium_heel_deg=equilibrium_heel,
            offset_righting_margin_ratio=margin,
        ))
    return results


def _record_row(model: PlanarCatamaranDynamics, state: CraftState, command: ThrusterCommand, current: tuple[float, float], time_s: float, name: str, payload_case: PayloadCase, command_state: str) -> dict[str, float | str]:
    u_rel, v_rel = model.relative_water_velocity_body(state, current)
    x_drag, y_drag, n_drag = model.hydrodynamic_forces(state, current)
    return {
        "maneuver": name, "payload_case": payload_case.identifier, "time_s": float(time_s),
        "x_m": state.x_m, "y_m": state.y_m, "psi_rad": state.psi_rad, "psi_deg": degrees(state.psi_rad),
        "u_mps": state.u_mps, "v_mps": state.v_mps, "r_rps": state.r_rps,
        "speed_over_ground_mps": hypot(state.u_mps, state.v_mps),
        "u_relative_water_mps": u_rel, "v_relative_water_mps": v_rel,
        "port_thrust_n": command.port_thrust_n, "starboard_thrust_n": command.starboard_thrust_n,
        "total_thrust_n": command.total_thrust_n,
        "yaw_moment_n_m": model.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n),
        "x_drag_n": x_drag, "y_drag_n": y_drag, "yaw_drag_n_m": n_drag,
        "current_x_mps": current[0], "current_y_mps": current[1], "command_state": command_state,
    }


def _simulate_open_loop(model: PlanarCatamaranDynamics, *, name: str, payload_case: PayloadCase, current: tuple[float, float], duration_s: float, command_at) -> tuple[list[dict[str, float | str]], list[dict[str, float | str]]]:
    dt = model.settings.integration_time_step_s
    sample_every = max(1, int(round(model.settings.trajectory_sample_interval_s / dt)))
    state = CraftState()
    rows: list[dict[str, float | str]] = []
    events: list[dict[str, float | str]] = []
    steps = int(round(duration_s / dt))
    for step in range(steps + 1):
        time_s = step * dt
        command, state_name, event = command_at(time_s, state)
        if event:
            events.append({"time_s": time_s, "maneuver": name, "payload_case": payload_case.identifier, **event})
        if step % sample_every == 0 or step == steps:
            rows.append(_record_row(model, state, command, current, time_s, name, payload_case, state_name))
        if step < steps:
            state = model.rk4_step(state, command, current, dt)
    return rows, events


def _metrics_step(rows: list[dict[str, float | str]], onset_s: float, steady_window_s: float) -> dict[str, float | str]:
    t = np.asarray([float(row["time_s"]) for row in rows]); speed = np.asarray([float(row["speed_over_ground_mps"]) for row in rows]); yaw = np.asarray([float(row["r_rps"]) for row in rows])
    steady = float(np.mean(speed[t >= t[-1] - steady_window_s])); candidates = np.where((t >= onset_s) & (speed >= 0.9 * steady))[0]
    rise = float(t[candidates[0]] - onset_s) if candidates.size else float("nan")
    return {"steady_speed_mps": steady, "rise_time_90pct_s": rise, "peak_yaw_rate_rps": float(np.max(np.abs(yaw))), "final_x_m": float(rows[-1]["x_m"])}


def _metrics_turn(rows: list[dict[str, float | str]]) -> dict[str, float | str]:
    x = np.asarray([float(row["x_m"]) for row in rows]); y = np.asarray([float(row["y_m"]) for row in rows]); heading = np.unwrap(np.asarray([float(row["psi_rad"]) for row in rows])); yaw = np.asarray([float(row["r_rps"]) for row in rows]); speed = np.asarray([float(row["speed_over_ground_mps"]) for row in rows])
    path = float(np.sum(np.hypot(np.diff(x), np.diff(y)))); change = float(abs(heading[-1] - heading[0])); radius = path / change if change > 1e-9 else float("nan")
    return {"path_length_m": path, "heading_change_deg": float(np.degrees(change)), "turn_radius_m": radius, "peak_yaw_rate_rps": float(np.max(np.abs(yaw))), "final_speed_mps": float(speed[-1]), "final_y_m": float(y[-1])}


def _metrics_zigzag(rows: list[dict[str, float | str]], events: list[dict[str, float | str]], target_deg: float) -> dict[str, float | str]:
    heading = np.asarray([float(row["psi_deg"]) for row in rows]); yaw = np.asarray([float(row["r_rps"]) for row in rows]); reversals = sum(1 for event in events if event.get("event") == "HEADING_REVERSAL")
    return {"reversal_count": float(reversals), "peak_heading_deg": float(np.max(np.abs(heading))), "overshoot_deg": max(0.0, float(np.max(np.abs(heading))) - target_deg), "peak_yaw_rate_rps": float(np.max(np.abs(yaw)))}


def _step_result(config: ProjectConfiguration, payload_case: PayloadCase, protocol: dict[str, Any]) -> ManeuverResult:
    mass = _payload_mass_properties(config.data, payload_case); model, _, _ = _plant_from_mass_properties(config, mass, payload_case.identifier)
    item = protocol["manoeuvres"]["step_thrust"]; onset = float(item["onset_s"]); thrust = float(item["thrust_per_side_n"])
    rows, events = _simulate_open_loop(model, name="symmetric_step", payload_case=payload_case, current=(0.0, 0.0), duration_s=float(item["duration_s"]), command_at=lambda t, _: (ThrusterCommand(0.0, 0.0), "IDLE", {"event": "STEP_ONSET"}) if abs(t-onset)<1e-9 else ((ThrusterCommand(0.0,0.0),"IDLE",None) if t<onset else (ThrusterCommand(thrust,thrust),"SYMMETRIC_CRUISE",None)))
    return ManeuverResult("symmetric_step", payload_case, (0.0,0.0), rows, events, _metrics_step(rows,onset,float(item["steady_window_s"])))


def _turn_result(config: ProjectConfiguration, payload_case: PayloadCase, protocol: dict[str, Any], current: tuple[float, float]) -> ManeuverResult:
    mass = _payload_mass_properties(config.data, payload_case); model, _, _ = _plant_from_mass_properties(config, mass, payload_case.identifier)
    item = protocol["manoeuvres"]["turning_circle"]; onset=float(item["onset_s"]); port=float(item["port_thrust_n"]); star=float(item["starboard_thrust_n"])
    rows, events = _simulate_open_loop(model, name="differential_turn", payload_case=payload_case, current=current, duration_s=float(item["duration_s"]), command_at=lambda t,_: (ThrusterCommand(0.0,0.0),"IDLE", {"event":"TURN_ONSET"}) if abs(t-onset)<1e-9 else ((ThrusterCommand(0.0,0.0),"IDLE",None) if t<onset else (ThrusterCommand(port,star),"STARBOARD_BIASED_TURN",None)))
    return ManeuverResult("differential_turn",payload_case,current,rows,events,_metrics_turn(rows))


def _zigzag_result(config: ProjectConfiguration, payload_case: PayloadCase, protocol: dict[str, Any]) -> ManeuverResult:
    mass = _payload_mass_properties(config.data, payload_case); model, _, _ = _plant_from_mass_properties(config, mass, payload_case.identifier)
    item=protocol["manoeuvres"]["zig_zag"]; onset=float(item["onset_s"]); target=float(item["target_heading_deg"]); mean=float(item["mean_thrust_per_side_n"]); diff=float(item["differential_thrust_n"])
    direction=1.0; started=False
    def command_at(t:float,state:CraftState):
        nonlocal direction, started
        event=None
        if t < onset:
            return ThrusterCommand(0.0,0.0),"IDLE",None
        if not started:
            started=True; event={"event":"ZIGZAG_START"}
        if direction>0.0 and degrees(state.psi_rad)>=target:
            direction=-1.0; event={"event":"HEADING_REVERSAL","target_heading_deg":-target}
        elif direction<0.0 and degrees(state.psi_rad)<=-target:
            direction=1.0; event={"event":"HEADING_REVERSAL","target_heading_deg":target}
        return ThrusterCommand(mean-direction*diff/2,mean+direction*diff/2), ("TURN_STARBOARD" if direction>0 else "TURN_PORT"), event
    rows, events=_simulate_open_loop(model,name="heading_zigzag",payload_case=payload_case,current=(0.0,0.0),duration_s=float(item["duration_s"]),command_at=command_at)
    return ManeuverResult("heading_zigzag",payload_case,(0.0,0.0),rows,events,_metrics_zigzag(rows,events,target))


def run_payload_maneuver_suite(protocol: dict[str, Any] | None = None, base: ProjectConfiguration | None = None) -> tuple[list[PayloadStaticResult], dict[str, ManeuverResult], dict[str, Any]]:
    active=protocol or load_payload_maneuver_protocol(); config=base or load_reference_configuration(); cases={case.identifier:case for case in payload_cases(active)}
    static=build_static_results(active,config)
    low=cases["full_low_central"]; dry=cases["dry_empty"]
    current=tuple(float(value) for value in active["manoeuvres"]["low_current_turn"]["current_earth_mps"])
    results={
        "step_dry":_step_result(config,dry,active), "step_full":_step_result(config,low,active),
        "turn_dry_calm":_turn_result(config,dry,active,(0.0,0.0)), "turn_full_calm":_turn_result(config,low,active,(0.0,0.0)),
        "turn_full_current":_turn_result(config,low,active,current),
        "zigzag_dry":_zigzag_result(config,dry,active), "zigzag_full":_zigzag_result(config,low,active),
    }
    return static, results, active


def assess_suite(static: list[PayloadStaticResult], maneuvers: dict[str, ManeuverResult], protocol: dict[str, Any]) -> list[dict[str, float | str | bool]]:
    check=protocol["static_analysis"]; acceptance=protocol["acceptance"]; rows=[]
    for result in static:
        rows.extend([
            {"check":"minimum_gm", "case":result.payload_case.identifier, "observed":result.hydro_case.gm_m, "threshold":float(check["required_minimum_gm_m"]), "passed":result.hydro_case.gm_m>=float(check["required_minimum_gm_m"])},
            {"check":"minimum_freeboard", "case":result.payload_case.identifier, "observed":result.hydro_case.freeboard_m, "threshold":float(check["required_minimum_freeboard_m"]), "passed":result.hydro_case.freeboard_m>=float(check["required_minimum_freeboard_m"])},
        ])
    offset=next(item for item in static if item.payload_case.identifier=="full_port_offset")
    rows.append({"check":"offset_equilibrium_heel", "case":offset.payload_case.identifier, "observed":offset.offset_equilibrium_heel_deg, "threshold":float(check["offset_equilibrium_limit_deg"]), "passed":offset.offset_equilibrium_heel_deg<=float(check["offset_equilibrium_limit_deg"])})
    rows.append({"check":"offset_righting_margin", "case":offset.payload_case.identifier, "observed":offset.offset_righting_margin_ratio, "threshold":float(check["required_righting_margin_ratio"]), "passed":offset.offset_righting_margin_ratio>=float(check["required_righting_margin_ratio"])})
    full_step=maneuvers["step_full"].metrics
    rows.append({"check":"full_payload_steady_speed", "case":"full_low_central", "observed":float(full_step["steady_speed_mps"]), "threshold":float(acceptance["minimum_full_payload_steady_speed_mps"]), "passed":float(full_step["steady_speed_mps"])>=float(acceptance["minimum_full_payload_steady_speed_mps"])})
    for name in ("turn_dry_calm","turn_full_calm","turn_full_current","zigzag_dry","zigzag_full"):
        metric=maneuvers[name].metrics
        rows.append({"check":"peak_yaw_rate", "case":name, "observed":float(metric["peak_yaw_rate_rps"]), "threshold":float(acceptance["maximum_peak_yaw_rate_rps"]), "passed":float(metric["peak_yaw_rate_rps"])<=float(acceptance["maximum_peak_yaw_rate_rps"])})
    for name in ("zigzag_dry","zigzag_full"):
        metric=maneuvers[name].metrics
        rows.append({"check":"zigzag_reversals", "case":name, "observed":float(metric["reversal_count"]), "threshold":float(acceptance["minimum_zigzag_heading_crossings"]), "passed":float(metric["reversal_count"])>=float(acceptance["minimum_zigzag_heading_crossings"])})
    return rows
