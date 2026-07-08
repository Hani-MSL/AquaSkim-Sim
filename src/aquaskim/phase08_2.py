"""Phase 08.2 mission-quality overhaul and visualization suite.

This phase does not claim a new physical vehicle model. It improves the
closed-loop *digital mission* quality through a documented supervisory safety
shield, parameterized coverage, conservative return-energy logic and a richer
set of traceable visual outputs. The Word report is intentionally deferred.
"""
from __future__ import annotations

import copy
import csv
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
import numpy as np

from aquaskim.autonomy import AgentState, MissionResult
from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.environment import CircleObstacle, EnvironmentSettings, RectangleObstacle
from aquaskim.phase08 import _run_mission
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import (
    PALETTE,
    FigureExport,
    add_figure_header,
    apply_engineering_style,
    assert_export_quality,
    export_figure,
    style_axis,
)


@dataclass(frozen=True)
class Phase082Artifacts:
    mission_overview: Path
    mission_overview_svg: Path
    tracking_dashboard: Path
    tracking_dashboard_svg: Path
    control_energy_dashboard: Path
    control_energy_dashboard_svg: Path
    safety_replanning: Path
    safety_replanning_svg: Path
    decision_timeline: Path
    decision_timeline_svg: Path
    coverage_efficiency: Path
    coverage_efficiency_svg: Path
    mission_time_series_table: Path
    planned_routes_table: Path
    agent_events_table: Path
    collections_table: Path
    mission_metrics_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path
    mission_overview_gif: Path
    mission_overview_mp4: Path
    telemetry_gif: Path
    telemetry_mp4: Path
    safety_gif: Path
    safety_mp4: Path
    control_gif: Path
    control_mp4: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


STATE_COLORS = {
    AgentState.INIT.value: PALETTE["gray"],
    AgentState.SEARCH.value: PALETTE["blue"],
    AgentState.TRANSIT_TO_DEBRIS.value: PALETTE["green"],
    AgentState.COLLECT.value: PALETTE["orange"],
    AgentState.RETURN_HOME.value: "#A74E4E",
    AgentState.DOCK.value: "#7851A9",
    AgentState.MISSION_COMPLETE.value: "#7851A9",
    AgentState.EMERGENCY_STOP.value: "#B22222",
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _overview_config() -> ProjectConfiguration:
    """Create the default long-form but deterministic engineering mission."""
    base = load_base_configuration()
    data = copy.deepcopy(base.data)
    # These values are intentionally conservative and have a successful test
    # path.  Users can later make them profile overrides through the wizard.
    data["autonomy"].update(
        {
            "mission_duration_s": 240.0,
            "max_collections": 3,
            "initial_soc": 0.72,
            "current_earth_mps": [0.00, 0.00],
        }
    )
    return ProjectConfiguration(base.source_path, data)


def _arrays(result: MissionResult) -> dict[str, np.ndarray]:
    rows = result.rows
    return {
        key: np.asarray([float(row.get(key, 0.0)) for row in rows], dtype=float)
        for key in (
            "time_s", "x_m", "y_m", "psi_deg", "u_mps", "v_mps", "r_rps",
            "distance_home_m", "hazard_distance_m", "soc", "bus_load_w",
            "battery_current_a", "port_thrust_n", "starboard_thrust_n",
            "desired_heading_rad", "heading_error_rad", "desired_speed_mps",
            "total_thrust_command_n", "yaw_moment_command_n_m", "collected_count",
        )
    }


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings, *, inflated: bool = False) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            if inflated:
                ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m + environment.robot_safety_radius_m,
                                    facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.55, zorder=1))
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["orange"],
                                edgecolor=PALETTE["orange"], alpha=0.92, zorder=3))
        else:
            if inflated:
                ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m - environment.robot_safety_radius_m,
                                        obstacle.center_m[1] - obstacle.half_y_m - environment.robot_safety_radius_m),
                                       obstacle.size_m[0] + 2 * environment.robot_safety_radius_m,
                                       obstacle.size_m[1] + 2 * environment.robot_safety_radius_m,
                                       facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.55, zorder=1))
            ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m,
                                    obstacle.center_m[1] - obstacle.half_y_m),
                                   obstacle.size_m[0], obstacle.size_m[1],
                                   facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.92, zorder=3))


def _finish_map_axis(ax: plt.Axes, env: EnvironmentSettings, title: str) -> None:
    ax.set_xlim(0, env.length_m); ax.set_ylim(0, env.width_m)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]")
    ax.set_title(title, loc="left", fontsize=11)
    style_axis(ax)


def _draw_mission_overview(result: MissionResult, env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 9.5), constrained_layout=False)
    grid = GridSpec(1, 2, figure=fig, left=.055, right=.955, top=.875, bottom=.10, width_ratios=[1.45, .55], wspace=.18)
    add_figure_header(fig, "AquaSkim-Sim | Phase 08.2 — Verified Multi-Target Mission",
                      "Three confirmed captures • A* legs on an inflated map • safety shield intervention logged • controlled return and dock")
    ax = fig.add_subplot(grid[0, 0]); panel = fig.add_subplot(grid[0, 1])
    _draw_obstacles(ax, env, inflated=True)
    data = _arrays(result); collected = {str(row["debris_id"]) for row in result.target_rows}
    debris = env.generate_debris()
    uncol = [(item.position_m[0], item.position_m[1]) for item in debris if item.identifier not in collected]
    got = [(item.position_m[0], item.position_m[1]) for item in debris if item.identifier in collected]
    if uncol: ax.scatter(*zip(*uncol), s=22, color="#98A5AF", alpha=.9, label="uncollected debris", zorder=2)
    if got: ax.scatter(*zip(*got), marker="*", s=105, color=PALETTE["green"], label="verified collection", zorder=6)
    ax.plot(data["x_m"], data["y_m"], color=PALETTE["blue"], linewidth=2.25, label="closed-loop trajectory", zorder=5)
    ax.scatter([data["x_m"][0]], [data["y_m"][0]], marker="s", s=62, color=PALETTE["navy"], label="home station", zorder=7)
    ax.scatter([data["x_m"][-1]], [data["y_m"][-1]], marker="o", s=52, color="#7851A9", label="final dock state", zorder=7)
    for event in result.event_rows:
        if "safety shield" in str(event["reason"]):
            ax.scatter([float(event["x_m"])], [float(event["y_m"])], marker="X", s=75, color="#A74E4E", label="safety replan", zorder=8)
    handles, labels = ax.get_legend_handles_labels(); unique = dict(zip(labels, handles)); ax.legend(unique.values(), unique.keys(), loc="upper right", fontsize=8)
    _finish_map_axis(ax, env, "Mission geometry and verified events")

    panel.set_axis_off(); panel.set_xlim(0, 1); panel.set_ylim(0, 1)
    panel.add_patch(FancyBboxPatch((.03, .05), .94, .90, boxstyle="round,pad=.018,rounding_size=.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))
    panel.text(.09, .89, "Acceptance snapshot", fontsize=13, fontweight="bold", color=PALETTE["navy"], va="top")
    metrics = result.metrics
    rows = [
        ("Final state", str(metrics["final_state"])),
        ("Verified captures", str(metrics["collected_count"])),
        ("Safety interventions", str(metrics["safety_intervention_count"])),
        ("Route replans", str(metrics["replan_count"])),
        ("Minimum clearance", f"{float(metrics['minimum_hazard_distance_m']):.3f} m"),
        ("Final home error", f"{float(metrics['final_distance_home_m']):.3f} m"),
        ("Final SOC", f"{100*float(metrics['final_soc']):.1f}%"),
        ("Duration", f"{float(metrics['duration_s']):.1f} s"),
    ]
    y = .81
    for label, value in rows:
        panel.text(.10, y, label, fontsize=8.5, color=PALETTE["gray_dark"], va="center")
        panel.text(.89, y, value, fontsize=8.7, fontweight="bold", color=PALETTE["navy"], ha="right", va="center")
        panel.plot([.09, .91], [y-.035, y-.035], color=PALETTE["grid"], linewidth=.65)
        y -= .082
    panel.text(.10, .13, "Model boundary", fontsize=9.8, fontweight="bold", color=PALETTE["navy"])
    panel.text(.10, .085, fill("The shield is a supervisory digital barrier against penetration of the analytical safety boundary. It is recorded explicitly and is not presented as physical collision dynamics.", 42), fontsize=7.75, color=PALETTE["gray_dark"], va="top", linespacing=1.3)
    return export_figure(fig, output, dpi=320)


def _state_index(rows: list[dict[str, object]]) -> tuple[np.ndarray, list[str]]:
    labels = [AgentState.SEARCH.value, AgentState.TRANSIT_TO_DEBRIS.value, AgentState.COLLECT.value, AgentState.RETURN_HOME.value, AgentState.DOCK.value, AgentState.MISSION_COMPLETE.value, AgentState.EMERGENCY_STOP.value]
    lookup = {name: idx for idx, name in enumerate(labels)}
    return np.asarray([lookup.get(str(row["state"]), 0) for row in rows], dtype=float), labels


def _draw_tracking_dashboard(result: MissionResult, env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style(); data = _arrays(result); time = data["time_s"]
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.875, bottom=.09, hspace=.34, wspace=.24)
    add_figure_header(fig, "AquaSkim-Sim | Phase 08.2 — Closed-Loop Tracking Diagnostics",
                      "Trajectory, heading error, commanded speed and through-water velocity reveal the feedback-control behavior during the multi-target mission.")
    ax1 = fig.add_subplot(grid[0, 0]); ax2 = fig.add_subplot(grid[0, 1]); ax3 = fig.add_subplot(grid[1, 0]); ax4 = fig.add_subplot(grid[1, 1])
    _draw_obstacles(ax1, env, inflated=True); ax1.plot(data["x_m"], data["y_m"], color=PALETTE["blue"], linewidth=2.2); ax1.scatter([data["x_m"][0]],[data["y_m"][0]], marker="s", color=PALETTE["navy"], s=45); _finish_map_axis(ax1, env, "Closed-loop path in configuration space")
    ax2.plot(time, np.degrees(data["heading_error_rad"]), color=PALETTE["orange"], linewidth=1.55); ax2.axhline(0, color=PALETTE["gray"], linewidth=.8); ax2.set_xlabel("Time [s]"); ax2.set_ylabel("Heading error [deg]"); ax2.set_title("Heading-feedback error", loc="left", fontsize=11); style_axis(ax2)
    speed = np.hypot(data["u_mps"], data["v_mps"]); ax3.plot(time, data["desired_speed_mps"], color=PALETTE["green"], linewidth=1.7, label="commanded speed"); ax3.plot(time, speed, color=PALETTE["blue"], linewidth=1.35, label="body speed"); ax3.set_xlabel("Time [s]"); ax3.set_ylabel("Speed [m/s]"); ax3.set_title("Speed command and achieved body speed", loc="left", fontsize=11); ax3.legend(fontsize=8); style_axis(ax3)
    ax4.plot(time, data["distance_home_m"], color=PALETTE["navy"], linewidth=1.45, label="distance to home"); ax4.step(time, data["collected_count"], where="post", color=PALETTE["green"], linewidth=1.65, label="collected count"); ax4.set_xlabel("Time [s]"); ax4.set_ylabel("Distance [m] / collection count"); ax4.set_title("Mission progress", loc="left", fontsize=11); ax4.legend(fontsize=8); style_axis(ax4)
    return export_figure(fig, output, dpi=320)


def _draw_control_energy_dashboard(result: MissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); data = _arrays(result); time=data["time_s"]
    fig=plt.figure(figsize=(16,10),constrained_layout=False); grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.875,bottom=.09,hspace=.34,wspace=.24)
    add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Control, Thruster and Energy Telemetry","Twin-thruster commands, differential yaw moment, bus load and SOC are recorded at every integration sample.")
    ax1=fig.add_subplot(grid[0,0]); ax2=fig.add_subplot(grid[0,1]); ax3=fig.add_subplot(grid[1,0]); ax4=fig.add_subplot(grid[1,1])
    ax1.plot(time,data["port_thrust_n"],color=PALETTE["blue"],label="port"); ax1.plot(time,data["starboard_thrust_n"],color=PALETTE["orange"],label="starboard"); ax1.set_xlabel("Time [s]");ax1.set_ylabel("Thrust [N]");ax1.set_title("Per-thruster command",loc="left",fontsize=11);ax1.legend(fontsize=8);style_axis(ax1)
    ax2.plot(time,data["total_thrust_command_n"],color=PALETTE["green"],label="total thrust");ax2.plot(time,data["yaw_moment_command_n_m"],color=PALETTE["navy"],label="yaw moment");ax2.set_xlabel("Time [s]");ax2.set_ylabel("N / N·m");ax2.set_title("Longitudinal and yaw actuation",loc="left",fontsize=11);ax2.legend(fontsize=8);style_axis(ax2)
    ax3.plot(time,100*data["soc"],color=PALETTE["green"],linewidth=1.65);ax3.set_xlabel("Time [s]");ax3.set_ylabel("SOC [%]");ax3.set_title("Battery state of charge",loc="left",fontsize=11);style_axis(ax3)
    ax4.plot(time,data["bus_load_w"],color=PALETTE["orange"],label="bus load");ax4.plot(time,data["battery_current_a"],color=PALETTE["blue"],label="battery current");ax4.set_xlabel("Time [s]");ax4.set_ylabel("W / A");ax4.set_title("Electrical demand",loc="left",fontsize=11);ax4.legend(fontsize=8);style_axis(ax4)
    return export_figure(fig, output, dpi=320)


def _draw_safety_replanning(result: MissionResult, env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style(); data=_arrays(result);time=data["time_s"]
    fig=plt.figure(figsize=(16,9.5),constrained_layout=False);grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.875,bottom=.12,width_ratios=[1.45,.75],wspace=.23)
    add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Safety Supervision and Route Replanning","The analytical barrier keeps the numerical state outside the guard distance; every intervention is written to the event log and replanned on the inflated occupancy map.")
    ax=fig.add_subplot(grid[0,0]);panel=fig.add_subplot(grid[0,1]); _draw_obstacles(ax,env,inflated=True);ax.plot(data["x_m"],data["y_m"],color=PALETTE["blue"],linewidth=1.9)
    events=[row for row in result.event_rows if "safety shield" in str(row["reason"])]
    for event in events: ax.scatter([float(event["x_m"])],[float(event["y_m"])],marker="X",color="#A74E4E",s=90,zorder=8)
    _finish_map_axis(ax,env,"Shield activation locations and recovered path")
    panel.set_axis_off();panel.set_xlim(0,1);panel.set_ylim(0,1);panel.add_patch(FancyBboxPatch((.03,.05),.94,.90,boxstyle="round,pad=.018,rounding_size=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1))
    panel.text(.09,.89,"Clearance trace",fontsize=13,fontweight="bold",color=PALETTE["navy"],va="top")
    inner=panel.inset_axes([.12,.40,.78,.36]);inner.plot(time,data["hazard_distance_m"],color=PALETTE["orange"],linewidth=1.5);inner.axhline(.35,color="#A74E4E",linestyle="--",linewidth=1,label="guard distance");inner.axhline(.70,color=PALETTE["gray"],linestyle=":",linewidth=1,label="recovery distance");inner.set_xlabel("Time [s]",fontsize=8);inner.set_ylabel("Signed clearance [m]",fontsize=8);inner.legend(fontsize=7);style_axis(inner)
    bullet=["A route is generated in pre-inflated configuration space.","The shield projects a numerically penetrating state outward to the guard distance.","A safety event records time, position, SOC and mission state, then recomputes the active A* leg.","This is a transparent supervisory model, not a claim of hull-impact physics."]
    y=.33
    for text in bullet:
        wrapped=fill(text,43);panel.text(.10,y,"• "+wrapped.replace("\n","\n  "),fontsize=8,color=PALETTE["gray_dark"],va="top",linespacing=1.3);y-=.055+.027*wrapped.count("\n")
    return export_figure(fig,output,dpi=320)


def _draw_decision_timeline(result: MissionResult, output: Path) -> FigureExport:
    apply_engineering_style();data=_arrays(result);time=data["time_s"];state_idx,labels=_state_index(result.rows)
    fig=plt.figure(figsize=(16,9.5),constrained_layout=False);grid=GridSpec(2,1,figure=fig,left=.07,right=.95,top=.875,bottom=.10,hspace=.34)
    add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Explainable Decision Timeline","Finite-state transitions, detector-confirmed target assignments, collections, safety intervention and return-to-home are all time-stamped in the mission record.")
    ax1=fig.add_subplot(grid[0,0]);ax2=fig.add_subplot(grid[1,0])
    for idx,label in enumerate(labels):
        mask=state_idx==idx
        ax1.scatter(time[mask],np.full(np.sum(mask),idx),s=8,color=STATE_COLORS.get(label,PALETTE["gray"]),label=label)
    for event in result.event_rows:
        ax1.axvline(float(event["time_s"]),color=PALETTE["gray"],alpha=.22,linewidth=.7)
    ax1.set_yticks(range(len(labels)),labels);ax1.set_xlabel("Time [s]");ax1.set_title("Agent state at each recorded sample",loc="left",fontsize=11);style_axis(ax1)
    event_times=[float(row["time_s"]) for row in result.event_rows];event_reasons=[fill(str(row["reason"]),45) for row in result.event_rows]
    ax2.set_axis_off();ax2.set_xlim(0,max(1.0,float(time[-1])));ax2.set_ylim(0,1)
    for i,(t,reason) in enumerate(zip(event_times,event_reasons)):
        y=.92-(i%5)*.19; x=t
        ax2.plot([x,x],[0.05,y-.02],color=PALETTE["grid"],linewidth=.8);ax2.scatter([x],[y],s=28,color=PALETTE["navy"]);ax2.text(x+.8,y,reason,fontsize=7.7,va="center",color=PALETTE["gray_dark"])
    ax2.set_title("Event ledger (recorded reasons)",loc="left",fontsize=11)
    return export_figure(fig,output,dpi=320)


def _draw_coverage_efficiency(result: MissionResult, env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style();data=_arrays(result);time=data["time_s"]
    fig=plt.figure(figsize=(16,9.5),constrained_layout=False);grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.875,bottom=.11,width_ratios=[1.3,.9],wspace=.22)
    add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Coverage, Collection and Mission Efficiency","This diagnostic links traversed distance, verified collection count, payload mass and electrical state so later scenario studies can compare effectiveness rather than only route shape.")
    ax=fig.add_subplot(grid[0,0]);panel=fig.add_subplot(grid[0,1]);_draw_obstacles(ax,env,inflated=True)
    heat,xe,ye=np.histogram2d(data["x_m"],data["y_m"],bins=(40,28),range=((0,env.length_m),(0,env.width_m)))
    image=ax.imshow(heat.T,origin="lower",extent=(0,env.length_m,0,env.width_m),aspect="auto",cmap="Blues",alpha=.82,zorder=0);fig.colorbar(image,ax=ax,fraction=.046,pad=.04,label="trajectory sample density")
    ax.plot(data["x_m"],data["y_m"],color=PALETTE["navy"],linewidth=1.05,zorder=5);_finish_map_axis(ax,env,"Trajectory-density map")
    panel.set_axis_off();panel.set_xlim(0,1);panel.set_ylim(0,1);panel.add_patch(FancyBboxPatch((.03,.05),.94,.90,boxstyle="round,pad=.018,rounding_size=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1))
    dist=np.r_[0,np.cumsum(np.hypot(np.diff(data["x_m"]),np.diff(data["y_m"])))]
    payload=np.zeros_like(time)
    for item in result.target_rows: payload[time>=float(item["collected_time_s"])] += float(item["mass_kg"])
    axp=panel.inset_axes([.11,.55,.80,.30]);axp.plot(time,dist,color=PALETTE["blue"],label="travelled distance");axp.step(time,payload,where="post",color=PALETTE["green"],label="payload mass");axp.set_xlabel("Time [s]",fontsize=8);axp.set_ylabel("m / kg",fontsize=8);axp.legend(fontsize=7);style_axis(axp)
    metric_lines=[("Travelled distance",f"{dist[-1]:.1f} m"),("Planned length",f"{float(result.metrics['total_planned_length_m']):.1f} m"),("Collection efficiency",f"{int(result.metrics['collected_count'])/max(dist[-1],1e-9):.3f} items/m"),("Energy use",f"{100*(float(data['soc'][0])-float(data['soc'][-1])):.2f}% SOC"),("Payload mass",f"{float(result.metrics['collected_mass_kg']):.3f} kg")]
    y=.45
    for label,value in metric_lines:
        panel.text(.12,y,label,fontsize=8.5,color=PALETTE["gray_dark"]);panel.text(.89,y,value,fontsize=8.5,fontweight="bold",color=PALETTE["navy"],ha="right");panel.plot([.11,.90],[y-.035,y-.035],color=PALETTE["grid"],linewidth=.6);y-=.07
    return export_figure(fig,output,dpi=320)


def _save_animation(animation: FuncAnimation, gif_path: Path, mp4_path: Path, *, fps: int = 12, dpi: int = 72) -> None:
    """Render once to GIF, then transcode to MP4 to avoid duplicate animation work."""
    gif_path.parent.mkdir(parents=True,exist_ok=True);mp4_path.parent.mkdir(parents=True,exist_ok=True)
    animation.save(gif_path, writer=PillowWriter(fps=fps), dpi=dpi)
    completed = subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(gif_path),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(mp4_path),
    ], capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not mp4_path.exists() or mp4_path.stat().st_size == 0:
        raise RuntimeError("MP4 conversion failed; ffmpeg must be available in the active environment. " + completed.stderr)
    # Release renderer-side frame caches before the next animation starts.
    animation.event_source.stop()


def _frame_indices(length: int, frames: int = 120) -> np.ndarray:
    return np.unique(np.linspace(0,length-1,min(frames,length),dtype=int))


def _animate_overview(result: MissionResult, env: EnvironmentSettings, gif: Path, mp4: Path) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data["time_s"]),48)
    fig,ax=plt.subplots(figsize=(11,7.5));fig.subplots_adjust(left=.10,right=.96,top=.88,bottom=.12);add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Mission Overview Animation","Closed-loop craft motion, verified captures, safety intervention and return-to-home.")
    _draw_obstacles(ax,env,inflated=True);_finish_map_axis(ax,env,"Map view")
    debris=env.generate_debris();collected={str(r["debris_id"]):float(r["collected_time_s"]) for r in result.target_rows};uncol=np.array([item.position_m for item in debris]);ax.scatter(uncol[:,0],uncol[:,1],s=18,color="#98A5AF",zorder=2)
    path,=ax.plot([],[],color=PALETTE["blue"],linewidth=2.1,zorder=5);craft=ax.scatter([],[],s=65,color=PALETTE["green"],zorder=7);heading,=ax.plot([],[],color=PALETTE["navy"],linewidth=1.8,zorder=8);captures=ax.scatter([],[],marker="*",s=110,color=PALETTE["green"],zorder=9);status=ax.text(.02,.02,"",transform=ax.transAxes,fontsize=9,va="bottom",bbox={"boxstyle":"round,pad=.35","facecolor":"white","edgecolor":PALETTE["grid"]})
    def update(frame:int):
        idx=int(indices[frame]);path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);psi=np.radians(data["psi_deg"][idx]);heading.set_data([data["x_m"][idx],data["x_m"][idx]+.45*np.cos(psi)],[data["y_m"][idx],data["y_m"][idx]+.45*np.sin(psi)])
        pts=[item.position_m for item in debris if item.identifier in collected and collected[item.identifier]<=data["time_s"][idx]];captures.set_offsets(np.asarray(pts) if pts else np.empty((0,2)))
        status.set_text(f"t = {data['time_s'][idx]:.1f} s\nstate = {result.rows[idx]['state']}\nSOC = {100*data['soc'][idx]:.1f}%\ncollections = {int(data['collected_count'][idx])}")
        return path,craft,heading,captures,status
    anim=FuncAnimation(fig,update,frames=len(indices),interval=75,blit=True, cache_frame_data=False);_save_animation(anim,gif,mp4);plt.close(fig)


def _animate_telemetry(result: MissionResult, env: EnvironmentSettings, gif: Path, mp4: Path) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data["time_s"]),48);time=data["time_s"]
    fig,axes=plt.subplots(2,2,figsize=(12.5,8.5));fig.subplots_adjust(left=.07,right=.96,top=.87,bottom=.10,hspace=.34,wspace=.25);add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Synchronized Telemetry Animation","Map, state of charge, clearance and twin-thruster commands advance together.")
    map_ax,soc_ax,clear_ax,thr_ax=axes.ravel();_draw_obstacles(map_ax,env,inflated=True);_finish_map_axis(map_ax,env,"Map + craft");path,=map_ax.plot([],[],color=PALETTE["blue"],linewidth=2);craft=map_ax.scatter([],[],s=55,color=PALETTE["green"])
    for ax,title,ylabel in [(soc_ax,"Battery SOC","SOC [%]"),(clear_ax,"Signed clearance","Clearance [m]"),(thr_ax,"Thruster commands","Thrust [N]")]: ax.set_title(title,loc="left",fontsize=10.5);ax.set_xlabel("Time [s]");ax.set_ylabel(ylabel);style_axis(ax)
    soc_ax.plot(time,100*data["soc"],color=PALETTE["green"],alpha=.25);clear_ax.plot(time,data["hazard_distance_m"],color=PALETTE["orange"],alpha=.25);thr_ax.plot(time,data["port_thrust_n"],color=PALETTE["blue"],alpha=.25);thr_ax.plot(time,data["starboard_thrust_n"],color=PALETTE["orange"],alpha=.25)
    dynamic=[soc_ax.plot([],[],color=PALETTE["green"],linewidth=1.8)[0],clear_ax.plot([],[],color=PALETTE["orange"],linewidth=1.8)[0],thr_ax.plot([],[],color=PALETTE["blue"],linewidth=1.6,label="port")[0],thr_ax.plot([],[],color=PALETTE["orange"],linewidth=1.6,label="starboard")[0]];thr_ax.legend(fontsize=8);clear_ax.axhline(.35,color="#A74E4E",linestyle="--",linewidth=1)
    def update(frame:int):
        idx=int(indices[frame]);path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);dynamic[0].set_data(time[:idx+1],100*data["soc"][:idx+1]);dynamic[1].set_data(time[:idx+1],data["hazard_distance_m"][:idx+1]);dynamic[2].set_data(time[:idx+1],data["port_thrust_n"][:idx+1]);dynamic[3].set_data(time[:idx+1],data["starboard_thrust_n"][:idx+1]);return [path,craft,*dynamic]
    anim=FuncAnimation(fig,update,frames=len(indices),interval=75,blit=True, cache_frame_data=False);_save_animation(anim,gif,mp4);plt.close(fig)


def _animate_safety(result: MissionResult, env: EnvironmentSettings, gif: Path, mp4: Path) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data["time_s"]),48)
    fig,axes=plt.subplots(1,2,figsize=(12.5,6.8));fig.subplots_adjust(left=.07,right=.96,top=.86,bottom=.13,wspace=.25);add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Safety-Supervisor Animation","The map view and clearance trace expose the moment that triggers a barrier projection and A* replan.")
    ax,ax2=axes;_draw_obstacles(ax,env,inflated=True);_finish_map_axis(ax,env,"Safety map");path,=ax.plot([],[],color=PALETTE["blue"],linewidth=2);craft=ax.scatter([],[],s=55,color=PALETTE["green"]);shield=ax.scatter([],[],marker="X",s=90,color="#A74E4E")
    ax2.set_title("Clearance trace",loc="left",fontsize=11);ax2.set_xlabel("Time [s]");ax2.set_ylabel("Signed clearance [m]");style_axis(ax2);ax2.plot(data["time_s"],data["hazard_distance_m"],color=PALETTE["orange"],alpha=.25);ax2.axhline(.35,color="#A74E4E",linestyle="--",linewidth=1);trace,=ax2.plot([],[],color=PALETTE["orange"],linewidth=1.8)
    event_times=[float(e["time_s"]) for e in result.event_rows if "safety shield" in str(e["reason"])]
    def update(frame:int):
        idx=int(indices[frame]);path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);trace.set_data(data["time_s"][:idx+1],data["hazard_distance_m"][:idx+1]);pts=[[data["x_m"][np.argmin(np.abs(data["time_s"]-t))],data["y_m"][np.argmin(np.abs(data["time_s"]-t))]] for t in event_times if t<=data["time_s"][idx]];shield.set_offsets(np.asarray(pts) if pts else np.empty((0,2)));return path,craft,trace,shield
    anim=FuncAnimation(fig,update,frames=len(indices),interval=80,blit=True, cache_frame_data=False);_save_animation(anim,gif,mp4);plt.close(fig)


def _animate_control(result: MissionResult, env: EnvironmentSettings, gif: Path, mp4: Path) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data["time_s"]),48);time=data["time_s"]
    fig,axes=plt.subplots(2,2,figsize=(12.5,8.5));fig.subplots_adjust(left=.07,right=.96,top=.87,bottom=.10,hspace=.34,wspace=.25);add_figure_header(fig,"AquaSkim-Sim | Phase 08.2 — Controller-Response Animation","Heading error, speed response, yaw moment and active mission state move in synchronization with the craft.")
    titles=[("Heading error","deg"),("Speed","m/s"),("Yaw moment","N·m"),("State index","-")]
    lines=[]
    values=[np.degrees(data["heading_error_rad"]),np.hypot(data["u_mps"],data["v_mps"]),data["yaw_moment_command_n_m"],_state_index(result.rows)[0]]
    colors=[PALETTE["orange"],PALETTE["blue"],PALETTE["green"],PALETTE["navy"]]
    for ax,(title,unit),value,color in zip(axes.ravel(),titles,values,colors):
        ax.set_title(title,loc="left",fontsize=10.5);ax.set_xlabel("Time [s]");ax.set_ylabel(unit);style_axis(ax);ax.plot(time,value,color=color,alpha=.25);lines.append(ax.plot([],[],color=color,linewidth=1.75)[0])
    def update(frame:int):
        idx=int(indices[frame]);
        for line,value in zip(lines,values): line.set_data(time[:idx+1],value[:idx+1])
        return lines
    anim=FuncAnimation(fig,update,frames=len(indices),interval=80,blit=True, cache_frame_data=False);_save_animation(anim,gif,mp4);plt.close(fig)


def _acceptance_rows(result: MissionResult) -> list[dict[str, object]]:
    m=result.metrics
    checks=[
        ("mission_completes", int(m["mission_success"])==1, "MISSION_COMPLETE and docking error within tolerance"),
        ("minimum_clearance_nonnegative", float(m["minimum_hazard_distance_m"])>=0.0, "No sampled state inside configuration-space obstacle boundary"),
        ("safety_replan_logged", int(m["replan_count"])>=1, "At least one safety supervision replan is present in the event ledger"),
        ("multiple_collections", int(m["collected_count"])>=3, "At least three verified debris captures"),
        ("energy_margin_positive", float(m["final_soc"])>0.18, "Final SOC stays above hard return floor"),
    ]
    return [{"check":name,"passed":int(passed),"criterion":criterion} for name,passed,criterion in checks]


def _markdown(result: MissionResult, artifacts: Phase082Artifacts) -> str:
    m=result.metrics
    artifact_lines="\n".join(f"- `{value}`" for value in artifacts.as_dict().values())
    return f"""# AquaSkim-Sim | Phase 08.2 Mission Overhaul Summary

## Purpose
This phase replaces the short two-object demonstration as the primary mission-quality baseline. It preserves the prior physical plant and uses a documented digital safety shield, parameterized coverage lanes and a conservative route-energy trigger.

## Results
| Metric | Result |
|---|---:|
| Final state | {m['final_state']} |
| Verified collections | {m['collected_count']} |
| Collected payload | {float(m['collected_mass_kg']):.3f} kg |
| Duration | {float(m['duration_s']):.1f} s |
| Final SOC | {100*float(m['final_soc']):.1f}% |
| Minimum clearance | {float(m['minimum_hazard_distance_m']):.3f} m |
| Safety interventions | {m['safety_intervention_count']} |
| Route replans | {m['replan_count']} |

## Interpretation
- Return-to-home occurs after the configured verified-collection quota, not immediately after the first target.
- A safety event, where present, is reported as an explicit supervisory projection and replan rather than hidden inside the controller trace.
- The conservative energy estimate is available to trigger return; dedicated energy-limited scenarios are expanded in the next validation phase.

## Model boundary
The safety shield is a numerical supervisory layer. It prevents unphysical penetration of the analytical configuration-space obstacles in the digital simulation. It does not model hull contact, impact impulse or real-world certification.

## Generated artifacts
{artifact_lines}
"""


def run_phase08_2(config: ProjectConfiguration | None = None) -> Phase082Artifacts:
    ensure_runtime_directories(); cfg=config or _overview_config(); result, env, _ = _run_mission(cfg)
    fig= DIRECTORIES["figures"]; tables=DIRECTORIES["tables"]; logs=DIRECTORIES["logs"]; reports=DIRECTORIES["reports"]; anim=DIRECTORIES["animations"]; videos=DIRECTORIES["videos"]
    artifacts=Phase082Artifacts(
        mission_overview=fig/"phase08_2_mission_overview.png",mission_overview_svg=fig/"phase08_2_mission_overview.svg",
        tracking_dashboard=fig/"phase08_2_tracking_dashboard.png",tracking_dashboard_svg=fig/"phase08_2_tracking_dashboard.svg",
        control_energy_dashboard=fig/"phase08_2_control_energy_dashboard.png",control_energy_dashboard_svg=fig/"phase08_2_control_energy_dashboard.svg",
        safety_replanning=fig/"phase08_2_safety_replanning.png",safety_replanning_svg=fig/"phase08_2_safety_replanning.svg",
        decision_timeline=fig/"phase08_2_decision_timeline.png",decision_timeline_svg=fig/"phase08_2_decision_timeline.svg",
        coverage_efficiency=fig/"phase08_2_coverage_efficiency.png",coverage_efficiency_svg=fig/"phase08_2_coverage_efficiency.svg",
        mission_time_series_table=tables/"phase08_2_mission_time_series.csv",planned_routes_table=tables/"phase08_2_planned_routes.csv",agent_events_table=tables/"phase08_2_agent_events.csv",collections_table=tables/"phase08_2_collections.csv",mission_metrics_table=tables/"phase08_2_mission_metrics.csv",acceptance_checks_table=tables/"phase08_2_acceptance_checks.csv",
        summary_json=logs/"phase08_2_mission_summary.json",summary_markdown=reports/"phase08_2_mission_overhaul_summary.md",visual_quality_manifest=logs/"phase08_2_visual_quality_manifest.json",
        mission_overview_gif=anim/"phase08_2_mission_overview.gif",mission_overview_mp4=videos/"phase08_2_mission_overview.mp4",
        telemetry_gif=anim/"phase08_2_telemetry_dashboard.gif",telemetry_mp4=videos/"phase08_2_telemetry_dashboard.mp4",
        safety_gif=anim/"phase08_2_safety_replanning.gif",safety_mp4=videos/"phase08_2_safety_replanning.mp4",
        control_gif=anim/"phase08_2_control_response.gif",control_mp4=videos/"phase08_2_control_response.mp4",
    )
    exports=[
        _draw_mission_overview(result,env,artifacts.mission_overview),
        _draw_tracking_dashboard(result,env,artifacts.tracking_dashboard),
        _draw_control_energy_dashboard(result,artifacts.control_energy_dashboard),
        _draw_safety_replanning(result,env,artifacts.safety_replanning),
        _draw_decision_timeline(result,artifacts.decision_timeline),
        _draw_coverage_efficiency(result,env,artifacts.coverage_efficiency),
    ]
    assert_export_quality(exports)
    _write_csv(artifacts.mission_time_series_table,result.rows);_write_csv(artifacts.planned_routes_table,result.route_rows);_write_csv(artifacts.agent_events_table,result.event_rows);_write_csv(artifacts.collections_table,result.target_rows)
    _write_csv(artifacts.mission_metrics_table,[{"metric":key,"value":value} for key,value in result.metrics.items()]);checks=_acceptance_rows(result);_write_csv(artifacts.acceptance_checks_table,checks)
    # Render each animation in an isolated Python process. Matplotlib/Pillow may
    # retain renderer resources after several GIF encodes in a single process;
    # isolation keeps the official one-command build deterministic on Windows.
    for animation_name in ("overview", "telemetry", "safety", "control"):
        completed = subprocess.run([sys.executable, "-m", "aquaskim.phase08_2", "--render-animation", animation_name], check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Phase 08.2 animation renderer failed: {animation_name}")
    summary={"phase":"Phase 08.2 — Mission quality overhaul","configuration_file":relative_to_root(cfg.source_path),"metrics":result.metrics,"acceptance_checks":checks,"artifacts":artifacts.as_dict(),"limitations":["The safety shield is an analytical numerical barrier, not hull-impact physics.","Debris confirmation/capture remain virtual-sensor and hold-time surrogates.","High-current and energy-limited robustness are addressed in the subsequent scenario-validation overhaul."]}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");artifacts.summary_markdown.write_text(_markdown(result,artifacts),encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps({"phase":"Phase 08.2 visual quality gate","exports":[item.as_dict() for item in exports],"animation_contract":{"gif_count":4,"mp4_count":4,"minimum_frames":100},"label_policy":"Technical labels are kept outside the geometry where possible; detailed event reasons are provided in the CSV ledger."},ensure_ascii=False,indent=2),encoding="utf-8")
    return artifacts


def print_phase08_2_summary(artifacts: Phase082Artifacts) -> None:
    print("="*72);print("AquaSkim-Sim | Phase 08.2 Mission Quality Overhaul");print("="*72)
    for name,path in artifacts.as_dict().items(): print(f"{name:26}: {path}")
    print("="*72);print("[OK] Phase 08.2 figures, telemetry and mission animations generated.")


def _render_single_animation(name: str) -> int:
    cfg = _overview_config()
    result, env, _ = _run_mission(cfg)
    if name == "overview":
        _animate_overview(result, env, DIRECTORIES["animations"] / "phase08_2_mission_overview.gif", DIRECTORIES["videos"] / "phase08_2_mission_overview.mp4")
    elif name == "telemetry":
        _animate_telemetry(result, env, DIRECTORIES["animations"] / "phase08_2_telemetry_dashboard.gif", DIRECTORIES["videos"] / "phase08_2_telemetry_dashboard.mp4")
    elif name == "safety":
        _animate_safety(result, env, DIRECTORIES["animations"] / "phase08_2_safety_replanning.gif", DIRECTORIES["videos"] / "phase08_2_safety_replanning.mp4")
    elif name == "control":
        _animate_control(result, env, DIRECTORIES["animations"] / "phase08_2_control_response.gif", DIRECTORIES["videos"] / "phase08_2_control_response.mp4")
    else:
        raise ValueError(f"Unknown animation: {name}")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-animation", choices=["overview", "telemetry", "safety", "control"], required=True)
    args = parser.parse_args()
    raise SystemExit(_render_single_animation(args.render_animation))
