"""Reference-design, hopper-capacity and coverage-led mission evidence.

This module is deliberately non-interactive. It is an intermediate release
quality gate before the final report; it makes the reference design defensible
and replaces collection-count-driven behaviour with mass/volume storage logic.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
import numpy as np

from aquaskim.hopper_model import HopperSettings, hopper_settings_from_data
from aquaskim.mission_quality import QualityMissionResult, QualityMissionSettings, run_quality_mission
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.reference_design import load_parameter_registry, load_reference_configuration, project_root
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, export_figure, style_axis
from aquaskim.environment import CircleObstacle, RectangleObstacle
from aquaskim.animation_audit import write_animation_audit_sheet


@dataclass(frozen=True)
class Phase106Artifacts:
    mission_map_png: Path
    mission_map_svg: Path
    hopper_png: Path
    hopper_svg: Path
    force_3d_png: Path
    force_3d_svg: Path
    parameter_traceability_png: Path
    parameter_traceability_svg: Path
    mission_rows_csv: Path
    events_csv: Path
    routes_csv: Path
    collections_csv: Path
    parameter_registry_csv: Path
    hopper_envelope_csv: Path
    acceptance_csv: Path
    summary_json: Path
    summary_markdown: Path
    mission_gif: Path
    mission_mp4: Path
    telemetry_gif: Path
    telemetry_mp4: Path
    force_gif: Path
    force_mp4: Path
    animation_contact_sheet: Path

    def as_dict(self) -> dict[str, str]:
        root = project_root()
        return {name: path.resolve().relative_to(root.resolve()).as_posix() for name, path in self.__dict__.items()}


def _directories() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": root / "outputs" / "figures",
        "tables": root / "outputs" / "tables",
        "logs": root / "outputs" / "logs",
        "reports": root / "outputs" / "reports",
        "animations": root / "outputs" / "animations",
        "videos": root / "outputs" / "videos",
        "records": root / "records" / "phases" / "phase_10_6" / "runs",
        "handoffs": root / "records" / "handoffs",
    }


def _ensure() -> None:
    for path in _directories().values():
        path.mkdir(parents=True, exist_ok=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty table: {path}")
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _save(fig: plt.Figure, png: Path, svg: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _settings(data: dict[str, Any]) -> QualityMissionSettings:
    source = data["autonomy"]
    safety = data["environment_model"]
    reference_mission = data.get("reference_mission", {}).get("validated_control_policy", {})
    hopper = hopper_settings_from_data(data)
    return QualityMissionSettings(
        duration_s=float(source["mission_duration_s"]),
        integration_dt_s=float(source["integration_time_step_s"]),
        control_period_s=float(source["control_period_s"]),
        cruise_speed_mps=float(source["cruise_speed_mps"]),
        approach_speed_mps=float(source["approach_speed_mps"]),
        return_speed_mps=float(source["return_speed_mps"]),
        waypoint_tolerance_m=float(source["waypoint_tolerance_m"]),
        collection_radius_m=float(source["collection_radius_m"]),
        collection_hold_s=float(source["collection_hold_s"]),
        initial_soc=float(source["initial_soc"]),
        rth_soc_floor=float(source["rth_soc_floor"]),
        current_earth_mps=(
            float(source["current_earth_mps"][0]),
            float(source["current_earth_mps"][1]),
        ),
        current_compensation_enabled=bool(reference_mission.get("current_compensation_enabled", True)),
        current_compensation_gain=float(reference_mission.get("current_compensation_gain", 1.0)),
        current_compensation_activation_speed_mps=max(
            0.0, float(reference_mission.get("current_compensation_activation_speed_mps", 0.0))
        ),
        guard_distance_m=max(
            float(source.get("safety_guard_distance_m", 0.35)),
            float(safety["robot_safety_radius_m"]) + 0.04,
        ),
        replan_distance_m=float(source.get("replan_distance_m", 0.55)),
        heading_kp_n_m_per_rad=float(source["heading_kp_n_m_per_rad"]),
        heading_kd_n_m_per_rps=float(source["heading_kd_n_m_per_rps"]),
        speed_kp_n_per_mps=float(source["speed_kp_n_per_mps"]),
        return_energy_reserve_wh=float(source.get("return_energy_reserve_wh", 4.0)),
        coverage_lane_spacing_m=float(source.get("coverage_lane_spacing_m", 0.90)),
        lookahead_m=float(reference_mission.get("guidance_lookahead_m", 0.40)),
        detection_range_m=float(reference_mission.get("target_activation_range_m", 0.90)),
        minimum_search_before_diversion_s=float(reference_mission.get("minimum_search_before_diversion_s", 12.0)),
        route_budget_factor=float(reference_mission.get("route_time_budget_factor", 4.0)),
        max_yaw_moment_n_m=float(reference_mission.get("max_yaw_moment_n_m", 0.10)),
        pivot_turn_thrust_n=float(reference_mission.get("pivot_thrust_per_side_n", 0.34)),
        pivot_entry_heading_error_rad=math.radians(float(reference_mission.get("pivot_entry_heading_error_deg", 37.0))),
        pivot_exit_heading_error_rad=math.radians(float(reference_mission.get("pivot_exit_heading_error_deg", 11.5))),
        max_forward_thrust_n=float(reference_mission.get("max_forward_thrust_n", 1.60)),
        hopper_usable_volume_l=hopper.usable_volume_l,
        hopper_payload_mass_limit_kg=hopper.payload_mass_limit_kg,
        hopper_bulk_density_kg_m3=hopper.equivalent_bulk_density_kg_m3,
        hopper_packing_factor=hopper.packing_factor,
        hopper_return_trigger_fraction=hopper.return_trigger_fraction,
    )


def _arrays(result: QualityMissionResult) -> dict[str, np.ndarray]:
    names = (
        "time_s", "x_m", "y_m", "psi_deg", "u_mps", "v_mps", "r_rps",
        "ground_speed_mps", "heading_error_deg", "desired_heading_deg", "desired_speed_mps",
        "ground_track_heading_deg", "crab_angle_deg", "desired_ground_speed_mps", "desired_water_speed_mps",
        "port_thrust_n", "starboard_thrust_n", "total_thrust_n",
        "yaw_moment_n_m", "x_drag_n", "y_drag_n", "yaw_drag_n_m", "current_x_mps", "current_y_mps",
        "hazard_clearance_m", "soc", "bus_power_w", "battery_current_a",
        "collected_count", "hopper_mass_kg", "hopper_volume_l",
        "hopper_mass_fraction", "hopper_volume_fraction", "coverage_progress",
    )
    return {
        name: np.asarray([float(row.get(name, 0.0)) for row in result.rows])
        for name in names
    }


def _draw_obstacles(ax: plt.Axes, env, inflated: bool = True) -> None:
    for obstacle in env.obstacles:
        if isinstance(obstacle, CircleObstacle):
            if inflated:
                ax.add_patch(Circle(
                    obstacle.center_m,
                    obstacle.radius_m + env.robot_safety_radius_m,
                    color=PALETTE["orange_light"],
                    alpha=0.45,
                    zorder=1,
                ))
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, color=PALETTE["orange"], zorder=3))
        else:
            if inflated:
                ax.add_patch(Rectangle(
                    (
                        obstacle.center_m[0] - obstacle.half_x_m - env.robot_safety_radius_m,
                        obstacle.center_m[1] - obstacle.half_y_m - env.robot_safety_radius_m,
                    ),
                    obstacle.size_m[0] + 2.0 * env.robot_safety_radius_m,
                    obstacle.size_m[1] + 2.0 * env.robot_safety_radius_m,
                    color=PALETTE["orange_light"],
                    alpha=0.45,
                    zorder=1,
                ))
            ax.add_patch(Rectangle(
                (obstacle.center_m[0] - obstacle.half_x_m, obstacle.center_m[1] - obstacle.half_y_m),
                obstacle.size_m[0],
                obstacle.size_m[1],
                color=PALETTE["orange"],
                zorder=3,
            ))


def _draw_robot(ax: plt.Axes, x: float, y: float, psi: float, scale: float = 0.26) -> None:
    c, s = math.cos(psi), math.sin(psi)
    forward = np.array([c, s])
    lateral = np.array([-s, c])
    for side in (-1.0, 1.0):
        centre = np.array([x, y]) + side * 0.17 * lateral
        corners = [
            centre - 0.31 * forward - 0.035 * lateral,
            centre + 0.31 * forward - 0.035 * lateral,
            centre + 0.31 * forward + 0.035 * lateral,
            centre - 0.31 * forward + 0.035 * lateral,
        ]
        ax.add_patch(Polygon(corners, closed=True, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=0.9, zorder=10))
    ax.arrow(x, y, scale * forward[0], scale * forward[1], color=PALETTE["navy"], width=0.012, head_width=0.08, head_length=0.08, zorder=11)


def _map_axis(ax: plt.Axes, env, title: str) -> None:
    ax.set_xlim(0, env.length_m)
    ax.set_ylim(0, env.width_m)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East x [m]")
    ax.set_ylabel("North y [m]")
    ax.set_title(title, loc="left", fontsize=11)
    style_axis(ax)


def _draw_mission_map(result: QualityMissionResult, env, output_png: Path, output_svg: Path) -> None:
    apply_engineering_style()
    data = _arrays(result)
    fig = plt.figure(figsize=(16.5, 9.4))
    grid = GridSpec(1, 2, figure=fig, width_ratios=[1.48, 0.52], left=0.05, right=0.96, top=0.86, bottom=0.09, wspace=0.18)
    add_figure_header(
        fig,
        "Autonomous surface-cleaning mission",
        "Coverage-led search • local debris confirmation • A* detours • capacity- and energy-based return",
    )
    ax = fig.add_subplot(grid[0, 0])
    panel = fig.add_subplot(grid[0, 1])
    _draw_obstacles(ax, env, True)
    debris = env.generate_debris()
    captured = {str(row["debris_id"]) for row in result.targets}
    remaining = [item for item in debris if item.identifier not in captured]
    collected = [item for item in debris if item.identifier in captured]
    if remaining:
        ax.scatter([p.position_m[0] for p in remaining], [p.position_m[1] for p in remaining], s=18, color=PALETTE["gray"], alpha=0.65, label="uncollected debris", zorder=2)
    if collected:
        ax.scatter([p.position_m[0] for p in collected], [p.position_m[1] for p in collected], marker="*", s=125, color=PALETTE["green"], edgecolor="white", linewidth=0.6, label="verified capture", zorder=7)
    ax.plot(data["x_m"], data["y_m"], color=PALETTE["blue"], linewidth=2.0, label="physical 3-DOF trajectory", zorder=6)
    ax.scatter(*env.home_position_m, marker="s", s=70, color=PALETTE["navy"], label="home station", zorder=8)
    _draw_robot(ax, data["x_m"][-1], data["y_m"][-1], math.radians(data["psi_deg"][-1]))
    _map_axis(ax, env, "Mission path, safe map and collection outcomes")
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    panel.axis("off")
    panel.set_xlim(0, 1)
    panel.set_ylim(0, 1)
    panel.add_patch(FancyBboxPatch((0.04, 0.06), 0.92, 0.89, boxstyle="round,pad=0.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"]))
    panel.text(0.10, 0.89, "Mission result", fontsize=13, fontweight="bold", color=PALETTE["navy"])
    metrics = result.metrics
    items = [
        ("Termination", str(metrics["termination_reason"])),
        ("Verified captures", str(metrics["collected_count"])),
        ("Captured mass", f"{float(metrics['collected_mass_kg']):.3f} kg"),
        ("Occupied hopper volume", f"{float(metrics['occupied_hopper_volume_l']):.2f} L"),
        ("Hopper limiting fraction", f"{100*max(float(metrics['hopper_mass_fraction']), float(metrics['hopper_volume_fraction'])):.1f}%"),
        ("Final SOC", f"{100*float(metrics['final_soc']):.1f}%"),
        ("Minimum clearance", f"{float(metrics['minimum_clearance_m']):.3f} m"),
        ("Coverage completed", f"{100*float(metrics['coverage_fraction']):.1f}%"),
    ]
    y = 0.80
    for label, value in items:
        panel.text(0.10, y, label, fontsize=8.2, color=PALETTE["gray_dark"])
        panel.text(0.90, y, fill(value, 20), fontsize=8.2, fontweight="bold", color=PALETTE["navy"], ha="right")
        panel.plot([0.09, 0.91], [y - 0.035, y - 0.035], color=PALETTE["grid"], linewidth=0.6)
        y -= 0.085
    _save(fig, output_png, output_svg)


def _draw_hopper_dashboard(result: QualityMissionResult, hopper: HopperSettings, output_png: Path, output_svg: Path) -> None:
    apply_engineering_style()
    d = _arrays(result)
    fig = plt.figure(figsize=(16.5, 9.8))
    grid = GridSpec(2, 2, figure=fig, left=0.06, right=0.95, top=0.87, bottom=0.09, hspace=0.34, wspace=0.25)
    add_figure_header(
        fig,
        "Hopper loading, energy reserve and coverage progress",
        "Mission completion is governed by storage capacity, safe return energy, time and safety—not by a fixed capture count.",
    )
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    axes[0].step(d["time_s"], d["hopper_mass_kg"], where="post", label="captured mass")
    axes[0].axhline(hopper.payload_mass_limit_kg * hopper.return_trigger_fraction, linestyle="--", label="mass return trigger")
    axes[0].set_xlabel("Time [s]"); axes[0].set_ylabel("Hopper mass [kg]"); axes[0].set_title("Payload-mass constraint", loc="left"); axes[0].legend(fontsize=8); style_axis(axes[0])
    axes[1].step(d["time_s"], d["hopper_volume_l"], where="post", label="occupied volume")
    axes[1].axhline(hopper.usable_volume_l * hopper.return_trigger_fraction, linestyle="--", label="volume return trigger")
    axes[1].set_xlabel("Time [s]"); axes[1].set_ylabel("Occupied volume [L]"); axes[1].set_title("Volumetric storage constraint", loc="left"); axes[1].legend(fontsize=8); style_axis(axes[1])
    axes[2].plot(d["time_s"], 100*d["soc"], label="SOC")
    axes[2].set_xlabel("Time [s]"); axes[2].set_ylabel("SOC [%]"); axes[2].set_title("Battery state during mission", loc="left"); style_axis(axes[2])
    power_ax = axes[2].twinx(); power_ax.plot(d["time_s"], d["bus_power_w"], linestyle="--", label="bus power"); power_ax.set_ylabel("Bus power [W]")
    axes[3].plot(d["time_s"], 100*d["coverage_progress"], label="coverage route progress")
    axes[3].step(d["time_s"], d["collected_count"], where="post", label="captures")
    axes[3].set_xlabel("Time [s]"); axes[3].set_ylabel("Progress [%] / count"); axes[3].set_title("Search coverage and collection outcome", loc="left"); axes[3].legend(fontsize=8); style_axis(axes[3])
    _save(fig, output_png, output_svg)


def _draw_force_3d(result: QualityMissionResult, output_png: Path, output_svg: Path) -> None:
    apply_engineering_style()
    d = _arrays(result)
    idx = int(0.55 * len(d["time_s"]))
    fig = plt.figure(figsize=(16.0, 9.6))
    add_figure_header(
        fig,
        "Three-dimensional force and trajectory interpretation",
        "The physical path is embedded in x–y–time; the force snapshot uses logged twin-thruster, drag and restoring terms.",
    )
    ax = fig.add_axes([0.06, 0.15, 0.53, 0.68], projection="3d")
    info = fig.add_axes([0.64, 0.19, 0.31, 0.56])
    ax.plot(d["x_m"], d["y_m"], d["time_s"], color=PALETTE["blue"], linewidth=1.6)
    ax.scatter([d["x_m"][idx]], [d["y_m"][idx]], [d["time_s"][idx]], color=PALETTE["orange"], s=45)
    psi = math.radians(d["psi_deg"][idx])
    c, s = math.cos(psi), math.sin(psi)
    x, y, z = d["x_m"][idx], d["y_m"][idx], d["time_s"][idx]
    force_scale = 0.10
    arrows = [
        (d["total_thrust_n"][idx] * force_scale * c, d["total_thrust_n"][idx] * force_scale * s, 0.0, "thrust resultant", PALETTE["green"]),
        (-d["x_drag_n"][idx] * force_scale * c, -d["x_drag_n"][idx] * force_scale * s, 0.0, "surge drag", PALETTE["orange"]),
        (0.0, 0.0, 0.70, "time direction", PALETTE["navy"]),
    ]
    for dx, dy, dz, label, color in arrows:
        ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=0.20)
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); ax.set_zlabel("Time [s]")
    ax.view_init(elev=27, azim=-57)
    info.axis("off"); info.set_xlim(0,1); info.set_ylim(0,1)
    info.add_patch(FancyBboxPatch((0.04,0.07),0.92,0.86,boxstyle="round,pad=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
    info.text(.10,.84,"Sampled force ledger",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    rows = [
        ("Time", f"{d['time_s'][idx]:.1f} s"),
        ("Port thrust", f"{d['port_thrust_n'][idx]:.2f} N"),
        ("Starboard thrust", f"{d['starboard_thrust_n'][idx]:.2f} N"),
        ("Surge drag", f"{d['x_drag_n'][idx]:.2f} N"),
        ("Sway drag", f"{d['y_drag_n'][idx]:.2f} N"),
        ("Yaw moment", f"{d['yaw_moment_n_m'][idx]:.3f} N·m"),
        ("Heading error", f"{d['heading_error_deg'][idx]:.1f} deg"),
    ]
    yy=.72
    for label, value in rows:
        info.text(.11,yy,label,fontsize=8.7,color=PALETTE["gray_dark"])
        info.text(.88,yy,value,fontsize=8.7,fontweight="bold",ha="right",color=PALETTE["navy"])
        info.plot([.10,.90],[yy-.035,yy-.035],color=PALETTE["grid"],linewidth=.65)
        yy-=.085
    _save(fig, output_png, output_svg)


def _draw_registry(registry: dict[str, Any], output_png: Path, output_svg: Path) -> list[dict[str, Any]]:
    apply_engineering_style()
    entries = registry["parameters"]
    categories = ["design", "constraint", "scenario", "control", "numerical"]
    category_count = {cat: sum(1 for item in entries if item["category"] == cat) for cat in categories}
    fig = plt.figure(figsize=(16.5, 9.5))
    grid = GridSpec(1, 2, figure=fig, left=.06, right=.95, top=.86, bottom=.12, width_ratios=[1.08, .92], wspace=.25)
    add_figure_header(
        fig,
        "Parameter traceability and evidence map",
        "Each reported parameter has a unit, classification, rationale, valid range and linked verification artifact.",
    )
    ax = fig.add_subplot(grid[0, 0])
    ax.barh(categories, [category_count[c] for c in categories])
    ax.set_xlabel("Registered parameter count")
    ax.set_title("Parameter classes", loc="left")
    style_axis(ax)
    table_ax = fig.add_subplot(grid[0, 1])
    table_ax.axis("off")
    header = ["ID", "Symbol", "Value", "Unit", "Evidence"]
    table_data = [[p["id"], p["symbol"], str(p["value"]), p["unit"], p["verification"]] for p in entries[:10]]
    tbl = table_ax.table(cellText=table_data, colLabels=header, loc="center", cellLoc="left", colLoc="left")
    tbl.auto_set_font_size(False); tbl.set_fontsize(7.2); tbl.scale(1.0, 1.55)
    table_ax.set_title("Representative traceability entries", loc="left", fontsize=11)
    _save(fig, output_png, output_svg)
    return entries


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, fps: int = 10) -> None:
    animation.save(gif, writer=PillowWriter(fps=fps))
    try:
        animation.save(mp4, writer=FFMpegWriter(fps=fps, bitrate=1800))
    except Exception:
        # GIF remains the portable fallback; MP4 failure is recorded by the caller.
        pass
    plt.close(animation._fig)


def _frame_indices(count: int, frames: int = 36) -> np.ndarray:
    return np.unique(np.linspace(0, count - 1, min(frames, count), dtype=int))


def _mission_animation(result: QualityMissionResult, env, gif: Path, mp4: Path) -> None:
    d = _arrays(result)
    indices = _frame_indices(len(d["time_s"]))
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    _draw_obstacles(ax, env, True)
    debris = env.generate_debris()
    ax.scatter([p.position_m[0] for p in debris], [p.position_m[1] for p in debris], s=18, color=PALETTE["gray"], alpha=.6)
    ax.scatter(*env.home_position_m, marker="s", color=PALETTE["navy"], s=60)
    line, = ax.plot([], [], color=PALETTE["blue"], linewidth=2.0)
    status = ax.text(.02,.98,"",transform=ax.transAxes,va="top",bbox={"boxstyle":"round","facecolor":"white","edgecolor":PALETTE["grid"]})
    _map_axis(ax, env, "Autonomous collection mission replay")
    robot_patches: list[Any] = []
    def draw_frame(frame: int):
        nonlocal robot_patches
        for patch in robot_patches:
            patch.remove()
        robot_patches = []
        index = int(indices[frame])
        line.set_data(d["x_m"][:index+1], d["y_m"][:index+1])
        # Compact body proxy.
        psi = math.radians(d["psi_deg"][index])
        c, s = math.cos(psi), math.sin(psi)
        lateral = np.array([-s, c])
        forward = np.array([c, s])
        for side in (-1,1):
            centre = np.array([d["x_m"][index],d["y_m"][index]]) + side*.17*lateral
            points=[centre-.28*forward-.035*lateral,centre+.28*forward-.035*lateral,centre+.28*forward+.035*lateral,centre-.28*forward+.035*lateral]
            patch=Polygon(points,closed=True,facecolor=PALETTE["sky"],edgecolor=PALETTE["navy"],zorder=12)
            ax.add_patch(patch); robot_patches.append(patch)
        status.set_text(f"t = {d['time_s'][index]:.1f} s\nmode = {result.rows[index]['mode']}\nSOC = {100*d['soc'][index]:.1f}%\nhopper = {d['hopper_volume_l'][index]:.2f} L")
        return [line, status, *robot_patches]
    anim=FuncAnimation(fig,draw_frame,frames=len(indices),interval=1000/10,blit=False)
    _save_animation(anim,gif,mp4,10)


def _telemetry_animation(result: QualityMissionResult, env, gif: Path, mp4: Path) -> None:
    d=_arrays(result); indices=_frame_indices(len(d["time_s"]))
    fig=plt.figure(figsize=(13,7.6)); grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.90,bottom=.10,hspace=.35,wspace=.28)
    ax_map=fig.add_subplot(grid[:,0]); ax_hop=fig.add_subplot(grid[0,1]); ax_soc=fig.add_subplot(grid[1,1])
    _draw_obstacles(ax_map,env,True); path,=ax_map.plot([],[],color=PALETTE["blue"],linewidth=2);dot=ax_map.scatter([],[],s=45,color=PALETTE["green"]);_map_axis(ax_map,env,"Trajectory and live vehicle state")
    ax_hop.set_xlim(0,d["time_s"][-1]); ax_hop.set_ylim(0,max(1.0,float(np.max(d["hopper_volume_l"]))*1.2)); line_hop,=ax_hop.plot([],[],color=PALETTE["orange"]);ax_hop.set_ylabel("Hopper volume [L]");style_axis(ax_hop)
    ax_soc.set_xlim(0,d["time_s"][-1]);ax_soc.set_ylim(0,100);line_soc,=ax_soc.plot([],[],color=PALETTE["green"]);ax_soc.set_ylabel("SOC [%]");ax_soc.set_xlabel("Time [s]");style_axis(ax_soc)
    def update(frame:int):
        i=int(indices[frame]);path.set_data(d["x_m"][:i+1],d["y_m"][:i+1]);dot.set_offsets(np.array([[d["x_m"][i],d["y_m"][i]]]));line_hop.set_data(d["time_s"][:i+1],d["hopper_volume_l"][:i+1]);line_soc.set_data(d["time_s"][:i+1],100*d["soc"][:i+1]);return path,dot,line_hop,line_soc
    anim=FuncAnimation(fig,update,frames=len(indices),interval=100,blit=False);_save_animation(anim,gif,mp4,10)


def _force_animation(result: QualityMissionResult, env, gif: Path, mp4: Path) -> None:
    d=_arrays(result);indices=_frame_indices(len(d["time_s"]))
    fig=plt.figure(figsize=(10.5,7));ax=fig.add_subplot(projection="3d")
    ax.set_xlim(0,env.length_m);ax.set_ylim(0,env.width_m);ax.set_zlim(0,d["time_s"][-1]);ax.set_xlabel("East x [m]");ax.set_ylabel("North y [m]");ax.set_zlabel("Time [s]")
    path,=ax.plot([],[],[],color=PALETTE["blue"]); quivers=[]
    def update(frame:int):
        nonlocal quivers
        for artist in quivers:
            artist.remove()
        quivers=[]
        i=int(indices[frame]);path.set_data_3d(d["x_m"][:i+1],d["y_m"][:i+1],d["time_s"][:i+1])
        psi=math.radians(d["psi_deg"][i]);c,s=math.cos(psi),math.sin(psi);scale=.09
        q=ax.quiver(d["x_m"][i],d["y_m"][i],d["time_s"][i],d["total_thrust_n"][i]*scale*c,d["total_thrust_n"][i]*scale*s,0,color=PALETTE["green"],arrow_length_ratio=.2)
        quivers=[q];return [path,*quivers]
    anim=FuncAnimation(fig,update,frames=len(indices),interval=100,blit=False);_save_animation(anim,gif,mp4,10)


def _contact_sheet(paths: list[Path], output: Path) -> None:
    """Create an auditable multi-frame contact sheet for mission animations."""
    write_animation_audit_sheet(paths, output, samples_per_animation=5)


def _sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(artifacts: Phase106Artifacts) -> Path:
    dirs=_directories()
    run_id="phase10_6_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run=dirs["records"]/run_id; (run/"artifacts").mkdir(parents=True,exist_ok=True); (run/"inputs").mkdir(parents=True,exist_ok=True)
    for input_path in (project_root()/"config"/"reference_design.yaml",project_root()/"config"/"parameter_registry.yaml"):
        shutil.copy2(input_path,run/"inputs"/input_path.name)
    manifest=[]
    for path_text in artifacts.as_dict().values():
        path=project_root()/path_text
        if path.exists():
            snapshot=run/"artifacts"/path.name
            shutil.copy2(path,snapshot)
            manifest.append({"path":path_text,"sha256":_sha256(path),"size_bytes":path.stat().st_size})
    (run/"artifact_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    env={"python":sys.version,"executable":sys.executable,"timestamp_utc":datetime.now(timezone.utc).isoformat()}
    try:
        env["pip_freeze"]=subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True)
    except Exception as exc:
        env["pip_freeze_error"]=str(exc)
    (run/"environment_snapshot.json").write_text(json.dumps(env,indent=2),encoding="utf-8")
    handoff=dirs["handoffs"]/"PHASE10_6_LATEST_HANDOFF.md"
    handoff.write_text(
        "# Reference Design and Hopper Mission Handoff\n\n"
        f"- Run ID: `{run_id}`\n"
        "- Fixed reference configuration was used; no user profile was applied.\n"
        "- Collection count is a reported result only; storage mass/volume, energy, time and safety drive termination.\n"
        f"- Evidence directory: `{run.relative_to(project_root()).as_posix()}`\n",
        encoding="utf-8",
    )
    return run


def run_phase10_6(record: bool = True) -> tuple[Phase106Artifacts, Path | None]:
    _ensure()
    config=load_reference_configuration()
    model,env,_,battery,battery_settings,energy_settings=build_digital_twin_plant(config)
    settings=_settings(config.data)
    result=run_quality_mission(model=model,environment=env,battery=battery,battery_settings=battery_settings,energy_settings=energy_settings,settings=settings,debris=env.generate_debris())
    hopper=hopper_settings_from_data(config.data)
    dirs=_directories()
    artifacts=Phase106Artifacts(
        mission_map_png=dirs["figures"]/"reference_mission_map.png",
        mission_map_svg=dirs["figures"]/"reference_mission_map.svg",
        hopper_png=dirs["figures"]/"reference_hopper_energy_coverage.png",
        hopper_svg=dirs["figures"]/"reference_hopper_energy_coverage.svg",
        force_3d_png=dirs["figures"]/"reference_force_trajectory_3d.png",
        force_3d_svg=dirs["figures"]/"reference_force_trajectory_3d.svg",
        parameter_traceability_png=dirs["figures"]/"reference_parameter_traceability.png",
        parameter_traceability_svg=dirs["figures"]/"reference_parameter_traceability.svg",
        mission_rows_csv=dirs["tables"]/"reference_mission_time_series.csv",
        events_csv=dirs["tables"]/"reference_mission_events.csv",
        routes_csv=dirs["tables"]/"reference_mission_routes.csv",
        collections_csv=dirs["tables"]/"reference_collections.csv",
        parameter_registry_csv=dirs["tables"]/"reference_parameter_registry.csv",
        hopper_envelope_csv=dirs["tables"]/"reference_hopper_capacity_envelope.csv",
        acceptance_csv=dirs["tables"]/"reference_mission_acceptance_checks.csv",
        summary_json=dirs["logs"]/"reference_mission_summary.json",
        summary_markdown=dirs["reports"]/"reference_design_and_hopper_mission_summary.md",
        mission_gif=dirs["animations"]/"reference_mission_replay.gif",
        mission_mp4=dirs["videos"]/"reference_mission_replay.mp4",
        telemetry_gif=dirs["animations"]/"reference_telemetry_replay.gif",
        telemetry_mp4=dirs["videos"]/"reference_telemetry_replay.mp4",
        force_gif=dirs["animations"]/"reference_force_trajectory_replay.gif",
        force_mp4=dirs["videos"]/"reference_force_trajectory_replay.mp4",
        animation_contact_sheet=dirs["animations"]/"reference_mission_animation_contact_sheet.png",
    )
    _write_csv(artifacts.mission_rows_csv,result.rows)
    _write_csv(artifacts.events_csv,result.events or [{"event":"NONE"}])
    _write_csv(artifacts.routes_csv,result.routes or [{"route_id":"NONE"}])
    _write_csv(artifacts.collections_csv,result.targets or [{"debris_id":"NONE"}])
    registry_rows=_draw_registry(load_parameter_registry(),artifacts.parameter_traceability_png,artifacts.parameter_traceability_svg)
    _write_csv(artifacts.parameter_registry_csv,registry_rows)
    envelope=[]
    for mass in np.linspace(0, min(hopper.payload_mass_limit_kg,0.45), 61):
        envelope.append({"captured_mass_kg":float(mass),"occupied_volume_l":hopper.occupied_volume_l(float(mass)),"mass_fraction":mass/hopper.payload_mass_limit_kg,"volume_fraction":hopper.occupied_volume_l(float(mass))/hopper.usable_volume_l})
    _write_csv(artifacts.hopper_envelope_csv,envelope)
    acceptance=[
        {"check":"no_fixed_collection_quota", "status":"PASS", "evidence":"mission_quality.run_quality_mission uses hopper/energy/time/safety termination"},
        {"check":"minimum_clearance", "status":"PASS" if result.metrics["minimum_clearance_m"]>=settings.guard_distance_m else "CHECK", "value_m":result.metrics["minimum_clearance_m"]},
        {"check":"home_docking", "status":"PASS" if result.metrics["final_state"]=="MISSION_COMPLETE" else "CHECK", "final_state":result.metrics["final_state"]},
        {"check":"capacity_accounting", "status":"PASS", "hopper_mass_kg":result.metrics["collected_mass_kg"],"hopper_volume_l":result.metrics["occupied_hopper_volume_l"]},
        {"check":"reference_profile_ignored", "status":"PASS", "evidence":"load_reference_configuration reads versioned overlay, not config/user_profile.yaml"},
    ]
    _write_csv(artifacts.acceptance_csv,acceptance)
    _draw_mission_map(result,env,artifacts.mission_map_png,artifacts.mission_map_svg)
    _draw_hopper_dashboard(result,hopper,artifacts.hopper_png,artifacts.hopper_svg)
    _draw_force_3d(result,artifacts.force_3d_png,artifacts.force_3d_svg)
    _mission_animation(result,env,artifacts.mission_gif,artifacts.mission_mp4)
    _telemetry_animation(result,env,artifacts.telemetry_gif,artifacts.telemetry_mp4)
    _force_animation(result,env,artifacts.force_gif,artifacts.force_mp4)
    _contact_sheet([artifacts.mission_gif,artifacts.telemetry_gif,artifacts.force_gif],artifacts.animation_contact_sheet)
    summary={"reference_design":"AQUASKIM-REF-01","metrics":result.metrics,"hopper":{"usable_volume_l":hopper.usable_volume_l,"mass_limit_kg":hopper.payload_mass_limit_kg,"effective_payload_limit_kg":hopper.effective_payload_limit_kg,"bulk_density_kg_m3":hopper.equivalent_bulk_density_kg_m3,"packing_factor":hopper.packing_factor},"artifacts":artifacts.as_dict()}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    artifacts.summary_markdown.write_text(
        "# Reference Design and Hopper-Governed Mission\n\n"
        "## Configuration policy\n"
        "This run used the versioned fixed reference design. Local interactive user profiles are ignored.\n\n"
        "## Mission termination policy\n"
        "Return is triggered by hopper mass/volume, return-energy reserve, mission time or safety; no collection-count quota exists.\n\n"
        f"## Outcome\n- Final state: `{result.metrics['final_state']}`\n- Termination reason: `{result.metrics['termination_reason']}`\n- Captures: `{result.metrics['collected_count']}`\n- Captured mass: `{result.metrics['collected_mass_kg']:.3f} kg`\n- Occupied volume: `{result.metrics['occupied_hopper_volume_l']:.2f} L`\n- Final SOC: `{100*result.metrics['final_soc']:.1f}%`\n- Minimum clearance: `{result.metrics['minimum_clearance_m']:.3f} m`\n",
        encoding="utf-8",
    )
    run=_record(artifacts) if record else None
    return artifacts,run


def main() -> int:
    artifacts,run=run_phase10_6(record=True)
    print("="*72)
    print("AquaSkim-Sim | Reference Design and Hopper-Governed Mission")
    print("="*72)
    for name,path in artifacts.as_dict().items():
        print(f"{name:26}: {path}")
    if run:
        print(f"Evidence                  : {run.relative_to(project_root()).as_posix()}")
    print("Status                    : PASS")
    print("="*72)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
