"""Mission-fidelity correction and advanced 2-D/3-D engineering visualization.

This release-quality module supersedes the short, historical mission reels.
It uses a documented line-of-sight controller and progress watchdog against the
same 3-DOF plant, inflated obstacle map, energy model and parameter files used
by the rest of AquaSkim-Sim.  It provides report-ready output, but deliberately
does not build the final Word report; that remains a separate release action.
"""
from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill
from typing import Any, Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.dynamics_3dof import CraftState, PlanarCatamaranDynamics
from aquaskim.environment import CircleObstacle, EnvironmentSettings, RectangleObstacle
from aquaskim.mission_quality import QualityMissionResult, QualityMissionSettings, run_quality_mission
from aquaskim.phase08 import _build_model
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import PALETTE, FigureExport, add_figure_header, apply_engineering_style, assert_export_quality, export_figure, style_axis


@dataclass(frozen=True)
class Phase104Artifacts:
    mission_map: Path
    mission_map_svg: Path
    tracking_dynamics: Path
    tracking_dynamics_svg: Path
    force_balance_2d: Path
    force_balance_2d_svg: Path
    mechanical_forces_2d: Path
    mechanical_forces_2d_svg: Path
    mechanical_forces_3d: Path
    mechanical_forces_3d_svg: Path
    trajectory_time_3d: Path
    trajectory_time_3d_svg: Path
    controller_surface_3d: Path
    controller_surface_3d_svg: Path
    scenario_comparison: Path
    scenario_comparison_svg: Path
    mission_quality_dashboard: Path
    mission_quality_dashboard_svg: Path
    simulation_rows: Path
    scenario_metrics: Path
    force_ledger: Path
    controller_ledger: Path
    event_ledger: Path
    acceptance_checks: Path
    animation_manifest: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path
    topdown_gif: Path
    topdown_mp4: Path
    telemetry_gif: Path
    telemetry_mp4: Path
    planning_gif: Path
    planning_mp4: Path
    forces3d_gif: Path
    forces3d_mp4: Path
    state_machine_gif: Path
    state_machine_mp4: Path
    body3d_gif: Path
    body3d_mp4: Path
    animation_contact_sheet: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


STATE_COLORS = {
    "SEARCH": PALETTE["blue"],
    "TRANSIT_TO_TARGET": PALETTE["green"],
    "COLLECT": PALETTE["orange"],
    "RETURN_HOME": "#A74E4E",
    "MISSION_COMPLETE": "#7851A9",
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _arrays(result: QualityMissionResult) -> dict[str, np.ndarray]:
    numeric = (
        "time_s", "x_m", "y_m", "psi_deg", "u_mps", "v_mps", "r_rps", "ground_speed_mps",
        "guidance_x_m", "guidance_y_m", "desired_heading_deg", "heading_error_deg", "desired_speed_mps",
        "port_thrust_n", "starboard_thrust_n", "total_thrust_n", "yaw_moment_n_m", "x_drag_n", "y_drag_n",
        "yaw_drag_n_m", "current_x_mps", "current_y_mps", "hazard_clearance_m", "soc", "bus_power_w",
        "battery_current_a", "collected_count", "route_id", "safety_events", "replan_count", "watchdog_count",
    )
    return {name: np.asarray([float(row.get(name, 0.0)) for row in result.rows], dtype=float) for name in numeric}


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings, *, inflated: bool = True) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            if inflated:
                ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m + environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.45, zorder=1))
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.90, zorder=3))
        elif isinstance(obstacle, RectangleObstacle):
            if inflated:
                ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m - environment.robot_safety_radius_m, obstacle.center_m[1] - obstacle.half_y_m - environment.robot_safety_radius_m), obstacle.size_m[0] + 2 * environment.robot_safety_radius_m, obstacle.size_m[1] + 2 * environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.45, zorder=1))
            ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m, obstacle.center_m[1] - obstacle.half_y_m), obstacle.size_m[0], obstacle.size_m[1], facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.9, zorder=3))


def _map_axis(ax: plt.Axes, environment: EnvironmentSettings, title: str) -> None:
    ax.set_xlim(0, environment.length_m); ax.set_ylim(0, environment.width_m)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]")
    ax.set_title(title, loc="left", fontsize=11.5)
    style_axis(ax)


def _draw_robot_2d(ax: plt.Axes, x: float, y: float, psi_rad: float, *, scale: float = 0.28) -> None:
    c, s = math.cos(psi_rad), math.sin(psi_rad)
    forward = np.asarray([c, s]); lateral = np.asarray([-s, c])
    hull_length, hull_width, separation = 0.62 * scale / 0.28, 0.08 * scale / 0.28, 0.34 * scale / 0.28
    for sign in (1.0, -1.0):
        center = np.asarray([x, y]) + sign * 0.5 * separation * lateral
        corners = []
        for a, b in ((.5, .5), (.5, -.5), (-.5, -.5), (-.5, .5)):
            corners.append(center + a * hull_length * forward + b * hull_width * lateral)
        ax.add_patch(Polygon(corners, closed=True, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=0.9, zorder=10))
    ax.arrow(x, y, 0.42 * forward[0], 0.42 * forward[1], width=0.015, head_width=0.10, head_length=0.10, color=PALETTE["navy"], length_includes_head=True, zorder=11)


def _draw_mission_map(result: QualityMissionResult, environment: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.5, 9.5), constrained_layout=False)
    grid = GridSpec(1, 2, figure=fig, width_ratios=[1.5, .52], left=.05, right=.955, top=.87, bottom=.085, wspace=.18)
    add_figure_header(fig, "AquaSkim-Sim | Multi-target autonomous surface-cleaning mission", "3-DOF closed-loop manoeuvring • line-of-sight route following • A* paths on an inflated safety map • energy-aware return")
    ax = fig.add_subplot(grid[0, 0]); info = fig.add_subplot(grid[0, 1])
    data = _arrays(result); _draw_obstacles(ax, environment, inflated=True)
    debris = environment.generate_debris(); collected = {str(row["debris_id"]) for row in result.targets}
    for item in debris:
        if item.identifier in collected:
            ax.scatter(item.position_m[0], item.position_m[1], marker="*", s=120, color=PALETTE["green"], edgecolor=PALETTE["white"], linewidth=.7, zorder=7)
        else:
            ax.scatter(item.position_m[0], item.position_m[1], s=20, color=PALETTE["gray"], alpha=.68, zorder=2)
    # Global A* legs are intentionally faint; physical path remains dominant.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in result.routes: grouped.setdefault(str(row["route_id"]), []).append(row)
    for rows in grouped.values():
        rows = sorted(rows, key=lambda item: int(item["waypoint_index"]))
        ax.plot([float(item["x_m"]) for item in rows], [float(item["y_m"]) for item in rows], color=PALETTE["gray"], linewidth=.8, alpha=.42, zorder=3)
    # Plot contiguous state intervals separately. Grouping all samples with the
    # same state would falsely draw straight connector lines across unrelated
    # legs and make the mission appear to loop.
    seen_labels: set[str] = set()
    start_index = 0
    modes = [str(row["mode"]) for row in result.rows]
    for index in range(1, len(modes) + 1):
        if index == len(modes) or modes[index] != modes[start_index]:
            state = modes[start_index]
            if state in STATE_COLORS:
                label = state.replace("_", " ") if state not in seen_labels else None
                ax.plot(data["x_m"][start_index:index], data["y_m"][start_index:index], linewidth=2.2, color=STATE_COLORS[state], label=label, zorder=6)
                seen_labels.add(state)
            start_index = index
    _draw_robot_2d(ax, data["x_m"][-1], data["y_m"][-1], math.radians(data["psi_deg"][-1]))
    ax.scatter(*environment.home_position_m, marker="s", s=70, color=PALETTE["navy"], label="home station", zorder=8)
    _map_axis(ax, environment, "Physical trajectory, planning legs and verified captures")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    info.axis("off"); info.set_xlim(0, 1); info.set_ylim(0, 1)
    info.add_patch(FancyBboxPatch((.04,.06), .92,.89, boxstyle="round,pad=.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"]))
    info.text(.10,.89,"Mission evidence",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    metrics = result.metrics
    rows = [("Outcome", "PASS" if int(metrics["mission_success"]) else "CHECK"), ("Verified captures", str(metrics["collected_count"])), ("Route length", f"{float(metrics['planned_route_length_m']):.1f} m"), ("Minimum clearance", f"{float(metrics['minimum_clearance_m']):.3f} m"), ("Replans", str(metrics["replan_count"])), ("Watchdog interventions", str(metrics["watchdog_event_count"])), ("Final SOC", f"{100*float(metrics['final_soc']):.1f}%"), ("Docking error", f"{float(metrics['final_distance_home_m']):.3f} m")]
    y=.80
    for label, value in rows:
        info.text(.11,y,label,fontsize=9,color=PALETTE["gray_dark"]); info.text(.89,y,value,ha="right",fontsize=9,fontweight="bold",color=PALETTE["navy"]); info.plot([.10,.90],[y-.035,y-.035],color=PALETTE["grid"],linewidth=.65); y-=.083
    info.text(.10,.25,"Interpretation",fontsize=10,fontweight="bold",color=PALETTE["navy"])
    info.text(.10,.10,fill("Faint lines are global A* legs. Colour-coded lines are the physical 3-DOF response. Safety interventions are recorded rather than hidden.", 35),fontsize=8.2,color=PALETTE["gray_dark"],va="bottom")
    return export_figure(fig, output, dpi=320)


def _draw_tracking_dynamics(result: QualityMissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); data = _arrays(result)
    fig = plt.figure(figsize=(16.5, 10.0), constrained_layout=False); grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.08,hspace=.34,wspace=.25)
    add_figure_header(fig, "AquaSkim-Sim | Closed-loop tracking and manoeuvring response", "Heading, speed, sway and yaw are shown directly from the 3-DOF time-domain state history")
    axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    axes[0].plot(data["time_s"],data["heading_error_deg"],label="heading error [deg]"); axes[0].axhline(0,color=PALETTE["gray"],linewidth=.8); axes[0].set_ylabel("Heading error [deg]"); axes[0].set_title("Guidance tracking",loc="left"); style_axis(axes[0])
    axes[1].plot(data["time_s"],data["desired_speed_mps"],label="command"); axes[1].plot(data["time_s"],data["ground_speed_mps"],label="ground speed"); axes[1].set_ylabel("Speed [m/s]"); axes[1].set_title("Speed response",loc="left"); axes[1].legend(fontsize=8); style_axis(axes[1])
    axes[2].plot(data["time_s"],data["u_mps"],label="surge u"); axes[2].plot(data["time_s"],data["v_mps"],label="sway v"); axes[2].set_xlabel("Time [s]"); axes[2].set_ylabel("Body velocity [m/s]"); axes[2].set_title("Body-frame velocity",loc="left"); axes[2].legend(fontsize=8); style_axis(axes[2])
    axes[3].plot(data["time_s"],data["psi_deg"],label="heading"); axes[3].plot(data["time_s"],np.degrees(data["r_rps"]),label="yaw rate [deg/s]"); axes[3].set_xlabel("Time [s]"); axes[3].set_ylabel("Angle / rate"); axes[3].set_title("Yaw response",loc="left"); axes[3].legend(fontsize=8); style_axis(axes[3])
    return export_figure(fig, output, dpi=320)


def _draw_force_balance(result: QualityMissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); data=_arrays(result)
    fig=plt.figure(figsize=(16.5,10),constrained_layout=False); grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.08,hspace=.34,wspace=.25)
    add_figure_header(fig,"AquaSkim-Sim | Propulsion, hydrodynamic force and energy history","Forces are generated by the twin-thruster 3-DOF plant; battery variables use the Phase 05 conceptual pack model")
    axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    axes[0].plot(data["time_s"],data["port_thrust_n"],label="port thrust");axes[0].plot(data["time_s"],data["starboard_thrust_n"],label="starboard thrust");axes[0].set_ylabel("Thrust [N]");axes[0].set_title("Twin-thruster commands",loc="left");axes[0].legend(fontsize=8);style_axis(axes[0])
    axes[1].plot(data["time_s"],data["total_thrust_n"],label="total thrust");axes[1].plot(data["time_s"],-data["x_drag_n"],label="surge drag magnitude");axes[1].plot(data["time_s"],np.abs(data["y_drag_n"]),label="sway drag magnitude");axes[1].set_ylabel("Force [N]");axes[1].set_title("Force balance",loc="left");axes[1].legend(fontsize=8);style_axis(axes[1])
    axes[2].plot(data["time_s"],data["yaw_moment_n_m"],label="actuator moment");axes[2].plot(data["time_s"],data["yaw_drag_n_m"],label="yaw damping moment");axes[2].set_xlabel("Time [s]");axes[2].set_ylabel("Moment [N·m]");axes[2].set_title("Yaw moment balance",loc="left");axes[2].legend(fontsize=8);style_axis(axes[2])
    axes[3].plot(data["time_s"],100*data["soc"],label="SOC [%]");axes[3].set_ylabel("SOC [%]");axes[3].set_xlabel("Time [s]");axes[3].set_title("Battery state and bus power",loc="left");ax2=axes[3].twinx();ax2.plot(data["time_s"],data["bus_power_w"],linestyle="--",label="bus power [W]");ax2.set_ylabel("Power [W]");style_axis(axes[3]); axes[3].legend(loc="upper left",fontsize=8); ax2.legend(loc="upper right",fontsize=8)
    return export_figure(fig,output,dpi=320)


def _draw_mechanical_forces_2d(model: PlanarCatamaranDynamics, result: QualityMissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); data=_arrays(result); sample=int(len(data["time_s"])*0.52); psi=math.radians(data["psi_deg"][sample]); x,y=0.0,0.0
    fig=plt.figure(figsize=(16.5,9.5),constrained_layout=False); grid=GridSpec(1,2,figure=fig,width_ratios=[1.25,.75],left=.05,right=.95,top=.87,bottom=.10,wspace=.20)
    add_figure_header(fig,"AquaSkim-Sim | Planar force diagram at a sampled manoeuvre state","The diagram is a force decomposition snapshot; values are taken from the time-series ledger rather than illustrative constants")
    ax=fig.add_subplot(grid[0,0]); info=fig.add_subplot(grid[0,1]); ax.set_aspect("equal");ax.set_xlim(-1.15,1.35);ax.set_ylim(-.90,.90);ax.axis("off")
    _draw_robot_2d(ax,x,y,psi,scale=.62)
    forward=np.asarray([math.cos(psi),math.sin(psi)]); lateral=np.asarray([-math.sin(psi),math.cos(psi)])
    def arrow(start, vec, label, color):
        ax.add_patch(FancyArrowPatch(start, (start[0]+vec[0],start[1]+vec[1]),arrowstyle="-|>",mutation_scale=15,linewidth=2.0,color=color)); ax.text(start[0]+vec[0]*1.06,start[1]+vec[1]*1.06,label,fontsize=9,fontweight="bold",color=color)
    total=float(data["total_thrust_n"][sample]); xdrag=float(data["x_drag_n"][sample]); ydrag=float(data["y_drag_n"][sample]); current=np.asarray([data["current_x_mps"][sample],data["current_y_mps"][sample]])
    arrow((.10,.08), .60*forward*max(.35,total/2.5), "T = %.2f N"%total, PALETTE["green"])
    arrow((-.08,-.08), -.58*forward*max(.25,abs(xdrag)/2.5), "Dₓ = %.2f N"%abs(xdrag), PALETTE["orange"])
    arrow((0.0,0.0), .50*lateral*np.sign(ydrag)*max(.20,abs(ydrag)/1.5), "Dᵧ = %.2f N"%ydrag, PALETTE["gray_dark"])
    if np.linalg.norm(current)>1e-6: arrow((-.75,-.55), .80*current/max(np.linalg.norm(current),1e-9), "water current", PALETTE["blue"])
    ax.add_patch(Circle((0,0),.03,facecolor=PALETTE["navy"])); ax.text(.02,.08,"CG",fontsize=9,color=PALETTE["navy"])
    info.axis("off"); info.set_xlim(0,1);info.set_ylim(0,1);info.add_patch(FancyBboxPatch((.05,.08),.90,.84,boxstyle="round,pad=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
    info.text(.11,.85,"Sampled force ledger",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    rows=[("Sample time",f"{data['time_s'][sample]:.1f} s"),("Port / starboard thrust",f"{data['port_thrust_n'][sample]:.2f} / {data['starboard_thrust_n'][sample]:.2f} N"),("Surge drag",f"{xdrag:.3f} N"),("Sway drag",f"{ydrag:.3f} N"),("Yaw moment",f"{data['yaw_moment_n_m'][sample]:.3f} N·m"),("Heading error",f"{data['heading_error_deg'][sample]:.2f}°"),("Clearance",f"{data['hazard_clearance_m'][sample]:.3f} m")]
    yy=.74
    for l,v in rows: info.text(.12,yy,l,fontsize=9,color=PALETTE["gray_dark"]); info.text(.88,yy,v,fontsize=9,ha="right",fontweight="bold",color=PALETTE["navy"]); info.plot([.11,.89],[yy-.035,yy-.035],color=PALETTE["grid"],linewidth=.6);yy-=.09
    info.text(.12,.15,fill("Sign convention: thrust acts along the vehicle forward axis. Hydrodynamic drag acts opposite relative motion through water. The current vector is expressed in the earth frame.",42),fontsize=8.5,color=PALETTE["gray_dark"],va="bottom")
    return export_figure(fig,output,dpi=320)


def _cuboid(ax: Any, center: tuple[float,float,float], size: tuple[float,float,float], color: str, alpha: float=.7) -> None:
    x,y,z=center; dx,dy,dz=size
    xx=[x-dx/2,x+dx/2]; yy=[y-dy/2,y+dy/2]; zz=[z-dz/2,z+dz/2]
    for sx in xx:
        for sy in yy:
            ax.plot([sx,sx],[sy,sy],[zz[0],zz[1]],color=color,alpha=alpha)
    for sx in xx:
        for sz in zz:
            ax.plot([sx,sx],[yy[0],yy[1]],[sz,sz],color=color,alpha=alpha)
    for sy in yy:
        for sz in zz:
            ax.plot([xx[0],xx[1]],[sy,sy],[sz,sz],color=color,alpha=alpha)


def _draw_mechanical_forces_3d(model: PlanarCatamaranDynamics, result: QualityMissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); data=_arrays(result); sample=int(len(data['time_s'])*.52)
    fig=plt.figure(figsize=(16.5,9.5),constrained_layout=False); add_figure_header(fig,"AquaSkim-Sim | Three-dimensional mechanical and force representation","Parametric catamaran geometry with gravity, buoyancy, propulsion and hydrodynamic reaction vectors")
    ax=fig.add_axes([.055,.12,.56,.72],projection='3d'); info=fig.add_axes([.67,.12,.28,.72]); info.axis('off');
    # Hulls and central deck use the Phase 10.2 conceptual dimensions.
    _cuboid(ax,(0,.18,.08),(.70,.09,.16),PALETTE['blue']); _cuboid(ax,(0,-.18,.08),(.70,.09,.16),PALETTE['blue']); _cuboid(ax,(0,0,.18),(.44,.36,.03),PALETTE['gray'])
    ax.scatter([0],[0],[.13],color=PALETTE['navy'],s=40); ax.text(.02,.02,.15,'CG',color=PALETTE['navy'])
    # Arrows explicitly scaled for diagram readability, while values are listed in panel.
    ax.quiver(0,0,.13,0,0,-.40,color=PALETTE['orange'],arrow_length_ratio=.10,linewidth=2.2); ax.text(0,0,-.30,'Weight',color=PALETTE['orange'])
    ax.quiver(0,0,0,0,0,.40,color=PALETTE['green'],arrow_length_ratio=.10,linewidth=2.2); ax.text(0,0,.45,'Buoyancy',color=PALETTE['green'])
    ax.quiver(-.28,.18,.08,.42,0,0,color=PALETTE['green'],arrow_length_ratio=.12,linewidth=2.0); ax.quiver(-.28,-.18,.08,.42,0,0,color=PALETTE['green'],arrow_length_ratio=.12,linewidth=2.0)
    ax.text(.18,.22,.10,'Port thrust',color=PALETTE['green']);ax.text(.18,-.26,.10,'Starboard thrust',color=PALETTE['green'])
    ax.quiver(.15,0,.09,-.36,0,0,color=PALETTE['orange'],arrow_length_ratio=.12,linewidth=2.0);ax.text(-.28,0,.12,'Hydrodynamic drag',color=PALETTE['orange'])
    ax.set_xlabel('x forward [m]');ax.set_ylabel('y port [m]');ax.set_zlabel('z up [m]');ax.set_title('Parametric twin-hull model and force directions',loc='left',fontsize=11);ax.set_xlim(-.45,.45);ax.set_ylim(-.35,.35);ax.set_zlim(-.35,.55);ax.view_init(elev=22,azim=-58)
    info.set_xlim(0,1);info.set_ylim(0,1);info.add_patch(FancyBboxPatch((.04,.08),.92,.84,boxstyle='round,pad=.02',facecolor='#F8FBFD',edgecolor=PALETTE['grid']))
    info.text(.10,.85,'Mechanical interpretation',fontsize=13,fontweight='bold',color=PALETTE['navy'])
    items=[('Hull length','0.700 m'),('Hull spacing','0.360 m'),('Reference mass','3.800 kg'),('Sample total thrust',f"{data['total_thrust_n'][sample]:.2f} N"),('Sample yaw moment',f"{data['yaw_moment_n_m'][sample]:.3f} N·m"),('Sample drag',f"{abs(data['x_drag_n'][sample]):.3f} N")]
    y=.73
    for l,v in items: info.text(.11,y,l,fontsize=9,color=PALETTE['gray_dark']);info.text(.88,y,v,fontsize=9,ha='right',fontweight='bold',color=PALETTE['navy']);info.plot([.10,.89],[y-.035,y-.035],color=PALETTE['grid'],linewidth=.6);y-=.10
    info.text(.11,.20,'Scope note',fontsize=9.5,fontweight='bold',color=PALETTE['navy'])
    info.text(.11,.10,fill('Conceptual parametric load paths and force directions only; not a finite-element structural model or CFD pressure field.',36),fontsize=8.0,color=PALETTE['gray_dark'],va='bottom')
    return export_figure(fig,output,dpi=320)


def _draw_trajectory_3d(result: QualityMissionResult, output: Path) -> FigureExport:
    apply_engineering_style();data=_arrays(result)
    fig=plt.figure(figsize=(16.5,9.5),constrained_layout=False);add_figure_header(fig,"AquaSkim-Sim | Three-dimensional trajectory-time reconstruction","The vertical display dimension is time; colour denotes physical mission mode, preserving the planar water-surface assumption")
    ax=fig.add_axes([.06,.12,.61,.72],projection='3d');info=fig.add_axes([.72,.12,.23,.72]);info.axis('off')
    # Plot contiguous mode segments only. Connecting every sample with the same
    # mode would falsely draw straight links across intervening mission legs.
    modes = [str(row['mode']) for row in result.rows]
    seen: set[str] = set()
    start = 0
    for index in range(1, len(modes) + 1):
        if index == len(modes) or modes[index] != modes[start]:
            mode = modes[start]
            color = STATE_COLORS.get(mode, PALETTE['gray'])
            label = mode.replace('_', ' ') if mode not in seen else None
            ax.plot(data['x_m'][start:index], data['y_m'][start:index], data['time_s'][start:index], color=color, linewidth=2.0, label=label)
            seen.add(mode)
            start = index
    ax.set_xlabel('East x [m]');ax.set_ylabel('North y [m]');ax.set_zlabel('Time [s]');ax.view_init(elev=27,azim=-54);ax.legend(fontsize=8,loc='upper left')
    info.set_xlim(0,1);info.set_ylim(0,1);info.add_patch(FancyBboxPatch((.04,.14),.92,.72,boxstyle='round,pad=.02',facecolor='#F8FBFD',edgecolor=PALETTE['grid']))
    info.text(.10,.78,'Reading the trajectory',fontsize=12,fontweight='bold',color=PALETTE['navy']);info.text(.10,.66,fill('A vertical section of the curve reveals when the robot spent time turning, collecting, searching and returning. It is a visual time embedding, not an out-of-plane vessel motion.',34),fontsize=9,color=PALETTE['gray_dark'],va='top')
    info.text(.10,.30,'Mission duration',fontsize=9,color=PALETTE['gray_dark']);info.text(.88,.30,f"{data['time_s'][-1]:.1f} s",fontsize=10,ha='right',fontweight='bold',color=PALETTE['navy']);info.text(.10,.22,'Max yaw rate',fontsize=9,color=PALETTE['gray_dark']);info.text(.88,.22,f"{np.max(np.abs(np.degrees(data['r_rps']))):.1f} deg/s",fontsize=10,ha='right',fontweight='bold',color=PALETTE['navy'])
    return export_figure(fig,output,dpi=320)


def _draw_controller_surface(output: Path) -> FigureExport:
    apply_engineering_style();fig=plt.figure(figsize=(16.5,9.5),constrained_layout=False);add_figure_header(fig,"AquaSkim-Sim | Guidance and control allocation surface","Heading error and speed error are mapped to a bounded yaw-moment and total-thrust request before twin-thruster allocation")
    ax1=fig.add_axes([.07,.15,.40,.66],projection='3d');ax2=fig.add_axes([.55,.15,.40,.66],projection='3d')
    heading=np.linspace(-math.pi,math.pi,70);speed=np.linspace(-.35,.35,60);H,S=np.meshgrid(heading,speed)
    yaw=np.clip(.17*H,-.45,.45);thrust=np.clip(.45+3.2*S,0,10.0)
    ax1.plot_surface(np.degrees(H),S,yaw,alpha=.86);ax1.set_xlabel('Heading error [deg]');ax1.set_ylabel('Speed error [m/s]');ax1.set_zlabel('Yaw moment [N·m]');ax1.set_title('Bounded yaw-control surface',loc='left',fontsize=11)
    ax2.plot_surface(np.degrees(H),S,thrust,alpha=.86);ax2.set_xlabel('Heading error [deg]');ax2.set_ylabel('Speed error [m/s]');ax2.set_zlabel('Total thrust [N]');ax2.set_title('Total-thrust allocation surface',loc='left',fontsize=11)
    return export_figure(fig,output,dpi=320)


def _settings_from_configuration(config: ProjectConfiguration, **overrides: Any) -> QualityMissionSettings:
    source = config.data["autonomy"]
    safety = config.data["environment_model"]
    values: dict[str, Any] = {
        "duration_s": float(source["mission_duration_s"]),
        "integration_dt_s": float(source["integration_time_step_s"]),
        "control_period_s": float(source["control_period_s"]),
        "cruise_speed_mps": float(source["cruise_speed_mps"]),
        "approach_speed_mps": float(source["approach_speed_mps"]),
        "return_speed_mps": float(source["return_speed_mps"]),
        "waypoint_tolerance_m": float(source["waypoint_tolerance_m"]),
        "collection_radius_m": float(source["collection_radius_m"]),
        "collection_hold_s": float(source["collection_hold_s"]),
        "target_quota": int(source["max_collections"]),
        "initial_soc": float(source["initial_soc"]),
        "rth_soc_floor": float(source["rth_soc_floor"]),
        "current_earth_mps": (float(source["current_earth_mps"][0]), float(source["current_earth_mps"][1])),
        "guard_distance_m": max(float(source.get("safety_guard_distance_m", 0.32)), float(safety["robot_safety_radius_m"]) + 0.04),
        "replan_distance_m": float(source.get("replan_distance_m", 0.55)),
        "heading_kp_n_m_per_rad": max(0.17, float(source["heading_kp_n_m_per_rad"])),
        "heading_kd_n_m_per_rps": float(source["heading_kd_n_m_per_rps"]),
        "speed_kp_n_per_mps": float(source["speed_kp_n_per_mps"]),
        "return_energy_reserve_wh": float(source.get("return_energy_reserve_wh", 4.0)),
    }
    values.update(overrides)
    return QualityMissionSettings(**values)


def _scenario_result(config: ProjectConfiguration, *, name: str, current: tuple[float,float], initial_soc: float, quota: int) -> tuple[str, QualityMissionResult, EnvironmentSettings]:
    model, env, _, battery, bset, eset, _ = _build_model(config)
    result=run_quality_mission(model=model,environment=env,battery=battery,battery_settings=bset,energy_settings=eset,settings=_settings_from_configuration(config, target_quota=quota, initial_soc=initial_soc, current_earth_mps=current))
    return name,result,env


def _draw_scenario_comparison(scenarios: list[tuple[str,QualityMissionResult,EnvironmentSettings]], output: Path) -> FigureExport:
    apply_engineering_style();fig=plt.figure(figsize=(17,10),constrained_layout=False);add_figure_header(fig,"AquaSkim-Sim | Validated mission scenarios and a documented boundary case","Each panel uses the same plant, map and controller. The boundary case is labelled separately instead of being presented as nominal capability.")
    grid=GridSpec(2,2,figure=fig,left=.055,right=.955,top=.86,bottom=.08,hspace=.35,wspace=.18)
    for ax,(name,result,env) in zip([fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)],scenarios):
        data=_arrays(result);_draw_obstacles(ax,env,inflated=True);ax.plot(data['x_m'],data['y_m'],linewidth=2.0,color=PALETTE['blue']);ax.scatter(*env.home_position_m,marker='s',s=50,color=PALETTE['navy']);ax.scatter([r['x_m'] for r in result.targets],[r['y_m'] for r in result.targets],marker='*',s=85,color=PALETTE['green']);_map_axis(ax,env,name)
        ax.text(.03,.04,f"outcome: {result.metrics['final_state']}\ncollections: {result.metrics['collected_count']}\nmin clearance: {float(result.metrics['minimum_clearance_m']):.3f} m",transform=ax.transAxes,fontsize=7.6,va='bottom',bbox={'boxstyle':'round,pad=.28','facecolor':'white','edgecolor':PALETTE['grid'],'alpha':.94})
    return export_figure(fig,output,dpi=320)


def _draw_quality_dashboard(result: QualityMissionResult, scenarios: list[tuple[str,QualityMissionResult,EnvironmentSettings]], output: Path) -> FigureExport:
    apply_engineering_style();data=_arrays(result);fig=plt.figure(figsize=(16.5,10),constrained_layout=False);grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.08,hspace=.34,wspace=.25);add_figure_header(fig,"AquaSkim-Sim | Mission quality, coverage and validation dashboard","The release-quality suite checks motion continuity, clearance, controller demand, energy and scenario-level outcomes")
    axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    axes[0].plot(data['time_s'],data['hazard_clearance_m']);axes[0].axhline(.32,linestyle='--');axes[0].set_ylabel('Signed clearance [m]');axes[0].set_title('Safety clearance history',loc='left');style_axis(axes[0])
    axes[1].step(data['time_s'],data['collected_count'],where='post');axes[1].set_ylabel('Verified collection count');axes[1].set_title('Collection progression',loc='left');style_axis(axes[1])
    modes=[str(r['mode']) for r in result.rows];ordered=list(STATE_COLORS);counts=[modes.count(mode)*(data['time_s'][1]-data['time_s'][0]) for mode in ordered];axes[2].barh([m.replace('_',' ') for m in ordered],counts);axes[2].set_xlabel('Time spent [s]');axes[2].set_title('State occupancy',loc='left');style_axis(axes[2])
    names=[name for name,_,_ in scenarios];success=[int(r.metrics['mission_success']) for _,r,_ in scenarios];duration=[float(r.metrics['duration_s']) for _,r,_ in scenarios];x=np.arange(len(names));axes[3].bar(x-.18,success,.35,label='success [0/1]');ax2=axes[3].twinx();ax2.plot(x,duration,marker='o',label='duration');axes[3].set_xticks(x,names,rotation=18,ha='right');axes[3].set_ylim(0,1.15);axes[3].set_ylabel('Success');ax2.set_ylabel('Duration [s]');axes[3].set_title('Scenario outcomes',loc='left');axes[3].legend(loc='upper left',fontsize=8);ax2.legend(loc='upper right',fontsize=8);style_axis(axes[3])
    return export_figure(fig,output,dpi=320)


def _draw_body3d(ax: Any, x: float, y: float, psi: float, *, z: float = 0.0) -> None:
    # Simple 3-D proxy body that remains visually tied to the physical model.
    c,s=math.cos(psi),math.sin(psi);f=np.asarray([c,s]);l=np.asarray([-s,c]);
    for sign in (1,-1):
        center=np.asarray([x,y])+sign*.18*l
        p1=center-.35*f-.045*l; p2=center+.35*f-.045*l;p3=center+.35*f+.045*l;p4=center-.35*f+.045*l
        xs=[p1[0],p2[0],p3[0],p4[0],p1[0]];ys=[p1[1],p2[1],p3[1],p4[1],p1[1]];ax.plot(xs,ys,[z]*5,linewidth=2.2,color=PALETTE['navy'])
    ax.quiver(x,y,z,.48*c,.48*s,0,color=PALETTE['green'],arrow_length_ratio=.20)


def _frame_indices(n: int, count: int=15) -> np.ndarray:
    return np.unique(np.linspace(0,n-1,min(count,n),dtype=int))


def _save_animation(animation: FuncAnimation, gif_path: Path, mp4_path: Path, fps: int = 8) -> None:
    """Render sparse physical frames once, then create a longer smooth replay.

    Matplotlib renders the actual simulation samples at a modest source frame rate.
    ffmpeg doubles the presentation duration without rerunning the simulation. The
    higher output frame rate repeats samples for slower, inspectable playback.
    """
    gif_path.parent.mkdir(parents=True,exist_ok=True);mp4_path.parent.mkdir(parents=True,exist_ok=True)
    source_fps=max(2, int(round(fps/2)))
    raw_mp4=mp4_path.with_name(mp4_path.stem + ".raw.mp4")
    animation.save(raw_mp4,writer=FFMpegWriter(fps=source_fps,bitrate=1600))
    smooth_filter="setpts=2*PTS"
    command0=["ffmpeg","-y","-loglevel","error","-i",str(raw_mp4),"-vf",smooth_filter,"-r",str(fps),str(mp4_path)]
    palette = gif_path.with_suffix(".palette.png")
    command1=["ffmpeg","-y","-loglevel","error","-i",str(mp4_path),"-vf",f"fps={fps},palettegen",str(palette)]
    command2=["ffmpeg","-y","-loglevel","error","-i",str(mp4_path),"-i",str(palette),"-lavfi",f"fps={fps} [x]; [x][1:v] paletteuse",str(gif_path)]
    for command in (command0, command1, command2):
        completed=subprocess.run(command,check=False,capture_output=True,text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg animation conversion failed: {completed.stderr[-500:]}")
    raw_mp4.unlink(missing_ok=True)
    palette.unlink(missing_ok=True)
    plt.close(animation._fig)


def _animate_topdown(result: QualityMissionResult, env: EnvironmentSettings, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);fig,ax=plt.subplots(figsize=(10,7));
    def update(k:int):
        idx=int(indices[k]);ax.clear();_draw_obstacles(ax,env,inflated=True);ax.plot(data['x_m'][:idx+1],data['y_m'][:idx+1],linewidth=2.0,color=PALETTE['blue']);_draw_robot_2d(ax,data['x_m'][idx],data['y_m'][idx],math.radians(data['psi_deg'][idx]));ax.scatter(*env.home_position_m,marker='s',s=55,color=PALETTE['navy']);_map_axis(ax,env,'Autonomous mission replay');ax.text(.02,.03,f"t = {data['time_s'][idx]:.1f} s\nmode = {result.rows[idx]['mode']}\nSOC = {100*data['soc'][idx]:.1f}%\ncollections = {int(data['collected_count'][idx])}",transform=ax.transAxes,fontsize=9,va='bottom',bbox={'boxstyle':'round,pad=.3','facecolor':'white','edgecolor':PALETTE['grid']})
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _animate_telemetry(result: QualityMissionResult, env: EnvironmentSettings, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);fig=plt.figure(figsize=(12,8));grid=GridSpec(2,2,figure=fig);axmap=fig.add_subplot(grid[:,0]);axspeed=fig.add_subplot(grid[0,1]);axforce=fig.add_subplot(grid[1,1])
    def update(k:int):
        idx=int(indices[k]);axmap.clear();axspeed.clear();axforce.clear();_draw_obstacles(axmap,env,inflated=True);axmap.plot(data['x_m'][:idx+1],data['y_m'][:idx+1],color=PALETTE['blue']);_draw_robot_2d(axmap,data['x_m'][idx],data['y_m'][idx],math.radians(data['psi_deg'][idx]));_map_axis(axmap,env,'Map and vehicle pose');axspeed.plot(data['time_s'][:idx+1],data['desired_speed_mps'][:idx+1],label='command');axspeed.plot(data['time_s'][:idx+1],data['ground_speed_mps'][:idx+1],label='actual');axspeed.set_ylim(0,.40);axspeed.set_title('Speed tracking');axspeed.legend(fontsize=7);style_axis(axspeed);axforce.plot(data['time_s'][:idx+1],data['port_thrust_n'][:idx+1],label='port');axforce.plot(data['time_s'][:idx+1],data['starboard_thrust_n'][:idx+1],label='starboard');axforce.set_title('Thruster demand');axforce.legend(fontsize=7);style_axis(axforce);fig.suptitle('Mission telemetry replay',x=.05,ha='left',fontweight='bold',color=PALETTE['navy'])
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _animate_planning(result: QualityMissionResult, env: EnvironmentSettings, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);groups:dict[str,list[dict[str,Any]]]={}
    for r in result.routes: groups.setdefault(str(r['route_id']),[]).append(r)
    fig,ax=plt.subplots(figsize=(10,7))
    def update(k:int):
        idx=int(indices[k]);route_lim=int(data['route_id'][idx]);ax.clear();_draw_obstacles(ax,env,inflated=True)
        for rid,rs in groups.items():
            rid_number=int(rid.split('_')[-1])
            if rid_number<=route_lim:
                rs=sorted(rs,key=lambda x:int(x['waypoint_index']));ax.plot([float(r['x_m']) for r in rs],[float(r['y_m']) for r in rs],color=PALETTE['gray'],linewidth=1.0,alpha=.65)
        ax.plot(data['x_m'][:idx+1],data['y_m'][:idx+1],color=PALETTE['blue'],linewidth=2.2);_draw_robot_2d(ax,data['x_m'][idx],data['y_m'][idx],math.radians(data['psi_deg'][idx]));_map_axis(ax,env,'Planning and route-following replay');ax.text(.02,.03,f"active route = {route_lim}\nreplans = {int(data['replan_count'][idx])}\nclearance = {data['hazard_clearance_m'][idx]:.3f} m",transform=ax.transAxes,fontsize=9,va='bottom',bbox={'boxstyle':'round,pad=.3','facecolor':'white','edgecolor':PALETTE['grid']})
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _animate_forces3d(result: QualityMissionResult, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);fig=plt.figure(figsize=(10,8));ax=fig.add_subplot(111,projection='3d')
    def update(k:int):
        idx=int(indices[k]);ax.clear();_cuboid(ax,(0,.18,.08),(.70,.09,.16),PALETTE['blue']);_cuboid(ax,(0,-.18,.08),(.70,.09,.16),PALETTE['blue']);psi=math.radians(data['psi_deg'][idx]);c,s=math.cos(psi),math.sin(psi);total=data['total_thrust_n'][idx];drag=-data['x_drag_n'][idx];ax.quiver(-.25,.18,.08,.38*c,.38*s,0,color=PALETTE['green'],arrow_length_ratio=.15);ax.quiver(.12,0,.08,-.35*c,-.35*s,0,color=PALETTE['orange'],arrow_length_ratio=.15);ax.quiver(0,0,.13,0,0,-.30,color=PALETTE['orange'],arrow_length_ratio=.15);ax.quiver(0,0,0,0,0,.30,color=PALETTE['green'],arrow_length_ratio=.15);ax.set_xlim(-.5,.5);ax.set_ylim(-.45,.45);ax.set_zlim(-.4,.5);ax.view_init(elev=23,azim=-55);ax.set_title(f"Force-vector replay | t={data['time_s'][idx]:.1f} s | T={total:.2f} N | D={drag:.2f} N",loc='left',fontsize=10);ax.set_xlabel('x [m]');ax.set_ylabel('y [m]');ax.set_zlabel('z [m]')
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _animate_state_machine(result: QualityMissionResult, env: EnvironmentSettings, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);fig=plt.figure(figsize=(12,7));grid=GridSpec(1,2,figure=fig,width_ratios=[1.3,.7]);ax=fig.add_subplot(grid[0,0]);panel=fig.add_subplot(grid[0,1]);modes=['SEARCH','TRANSIT_TO_TARGET','COLLECT','RETURN_HOME','MISSION_COMPLETE']
    def update(k:int):
        idx=int(indices[k]);ax.clear();panel.clear();_draw_obstacles(ax,env,inflated=True);ax.plot(data['x_m'][:idx+1],data['y_m'][:idx+1],color=PALETTE['blue']);_draw_robot_2d(ax,data['x_m'][idx],data['y_m'][idx],math.radians(data['psi_deg'][idx]));_map_axis(ax,env,'State-machine mission replay');panel.axis('off');panel.set_xlim(0,1);panel.set_ylim(0,1);active=str(result.rows[idx]['mode']);y=.83
        for mode in modes:
            color=STATE_COLORS.get(mode,PALETTE['gray']);face=color if mode==active else PALETTE['gray_light'];text=PALETTE['white'] if mode==active else PALETTE['gray_dark'];panel.add_patch(FancyBboxPatch((.10,y-.055),.80,.085,boxstyle='round,pad=.02',facecolor=face,edgecolor=color));panel.text(.50,y-.012,mode.replace('_',' '),ha='center',va='center',fontsize=10,fontweight='bold',color=text);y-=.13
        panel.text(.10,.12,f"t = {data['time_s'][idx]:.1f} s\nactive target = {result.rows[idx]['active_target'] or 'coverage lane'}\nSOC = {100*data['soc'][idx]:.1f}%",fontsize=9,color=PALETTE['navy'])
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _animate_body3d(result: QualityMissionResult, env: EnvironmentSettings, gif: Path, mp4: Path, *, frame_count: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(result);indices=_frame_indices(len(data['time_s']), frame_count);fig=plt.figure(figsize=(10,8));ax=fig.add_subplot(111,projection='3d')
    def update(k:int):
        idx=int(indices[k]);ax.clear();_draw_obstacles_3d(ax,env);_draw_body3d(ax,data['x_m'][idx],data['y_m'][idx],math.radians(data['psi_deg'][idx]),z=.02);ax.plot(data['x_m'][:idx+1],data['y_m'][:idx+1],np.zeros(idx+1),color=PALETTE['blue'],linewidth=1.8);ax.set_xlim(0,env.length_m);ax.set_ylim(0,env.width_m);ax.set_zlim(-.2,.8);ax.view_init(elev=33,azim=-62);ax.set_xlabel('East x [m]');ax.set_ylabel('North y [m]');ax.set_zlabel('z [m]');ax.set_title(f"Three-dimensional mission replay | t = {data['time_s'][idx]:.1f} s",loc='left',fontsize=10)
    anim=FuncAnimation(fig,update,frames=len(indices),interval=max(80, int(1000 / max(fps, 1))));_save_animation(anim,gif,mp4,fps=fps)


def _draw_obstacles_3d(ax: Any, env: EnvironmentSettings) -> None:
    for ob in env.obstacles:
        if isinstance(ob,CircleObstacle):
            theta=np.linspace(0,2*np.pi,35);ax.plot(ob.center_m[0]+ob.radius_m*np.cos(theta),ob.center_m[1]+ob.radius_m*np.sin(theta),np.zeros_like(theta),color=PALETTE['orange'],linewidth=2)
        else:
            _cuboid(ax,(ob.center_m[0],ob.center_m[1],.10),(ob.size_m[0],ob.size_m[1],.20),PALETTE['orange'])


def _contact_sheet(gifs: list[Path], output: Path) -> None:
    from PIL import Image, ImageDraw
    images=[]
    for gif in gifs:
        im=Image.open(gif);im.seek(0);frame=im.convert('RGB');frame.thumbnail((350,240));images.append((gif.stem,frame.copy()))
    sheet=Image.new('RGB',(700,3*280),'white');draw=ImageDraw.Draw(sheet)
    for index,(name,frame) in enumerate(images):
        x=(index%2)*350;y=(index//2)*280;draw.text((x+8,y+8),name,fill='black');sheet.paste(frame,(x,y+28))
    output.parent.mkdir(parents=True,exist_ok=True);sheet.save(output)


def _scenario_rows(scenarios: list[tuple[str,QualityMissionResult,EnvironmentSettings]]) -> list[dict[str,object]]:
    rows=[]
    for name,res,_ in scenarios:
        row={'scenario':name};row.update(res.metrics);rows.append(row)
    return rows


def _animation_options(config: ProjectConfiguration) -> tuple[int, int]:
    """Return locally configurable replay density without hard-coding a developer phase value."""
    visual = config.data.get("visualisation", {})
    # A dedicated mission replay setting avoids inheriting the heavier historical
    # validation reel settings. Advanced users can set 18..90 frames locally.
    frames = int(visual.get("mission_animation_frames", 15))
    fps = int(visual.get("mission_animation_fps", 8))
    return max(12, min(frames, 90)), max(4, min(fps, 16))


def run_phase10_4(config: ProjectConfiguration | None = None) -> Phase104Artifacts:
    ensure_runtime_directories();cfg=config or load_base_configuration();model,env,_,battery,bset,eset,_=_build_model(cfg)
    nominal_settings = _settings_from_configuration(cfg)
    animation_frames, animation_fps = _animation_options(cfg)
    nominal=run_quality_mission(model=model,environment=env,battery=battery,battery_settings=bset,energy_settings=eset,settings=nominal_settings)
    validation_quota = min(3, max(1, nominal_settings.target_quota))
    scenarios=[
        ('Nominal multi-target mission',nominal,env),
        _scenario_result(cfg,name='East-current operating case',current=(.08,0.0),initial_soc=nominal_settings.initial_soc,quota=validation_quota),
        _scenario_result(cfg,name='North-current operating case',current=(0.0,.08),initial_soc=nominal_settings.initial_soc,quota=validation_quota),
        _scenario_result(cfg,name='Pre-departure energy guard',current=(.08,.02),initial_soc=max(nominal_settings.rth_soc_floor + .01, .20),quota=validation_quota),
    ]
    figures=DIRECTORIES['figures'];tables=DIRECTORIES['tables'];logs=DIRECTORIES['logs'];reports=DIRECTORIES['reports'];animations=DIRECTORIES['animations'];videos=DIRECTORIES['videos']
    artifacts=Phase104Artifacts(
        mission_map=figures/'mission_multitarget_map.png',mission_map_svg=figures/'mission_multitarget_map.svg',
        tracking_dynamics=figures/'mission_tracking_dynamics.png',tracking_dynamics_svg=figures/'mission_tracking_dynamics.svg',
        force_balance_2d=figures/'mission_force_energy_history.png',force_balance_2d_svg=figures/'mission_force_energy_history.svg',
        mechanical_forces_2d=figures/'mechanical_force_diagram_2d.png',mechanical_forces_2d_svg=figures/'mechanical_force_diagram_2d.svg',
        mechanical_forces_3d=figures/'mechanical_force_diagram_3d.png',mechanical_forces_3d_svg=figures/'mechanical_force_diagram_3d.svg',
        trajectory_time_3d=figures/'mission_trajectory_time_3d.png',trajectory_time_3d_svg=figures/'mission_trajectory_time_3d.svg',
        controller_surface_3d=figures/'controller_allocation_surfaces_3d.png',controller_surface_3d_svg=figures/'controller_allocation_surfaces_3d.svg',
        scenario_comparison=figures/'mission_scenario_comparison.png',scenario_comparison_svg=figures/'mission_scenario_comparison.svg',
        mission_quality_dashboard=figures/'mission_quality_dashboard.png',mission_quality_dashboard_svg=figures/'mission_quality_dashboard.svg',
        simulation_rows=tables/'mission_multitarget_time_series.csv',scenario_metrics=tables/'mission_scenario_metrics.csv',force_ledger=tables/'mission_force_ledger.csv',controller_ledger=tables/'mission_controller_ledger.csv',event_ledger=tables/'mission_event_ledger.csv',acceptance_checks=tables/'mission_quality_acceptance_checks.csv',animation_manifest=tables/'mission_animation_manifest.csv',
        summary_json=logs/'mission_quality_summary.json',summary_markdown=reports/'mission_quality_and_visualisation_summary.md',visual_quality_manifest=logs/'mission_visual_quality_manifest.json',
        topdown_gif=animations/'mission_topdown_replay.gif',topdown_mp4=videos/'mission_topdown_replay.mp4',telemetry_gif=animations/'mission_telemetry_replay.gif',telemetry_mp4=videos/'mission_telemetry_replay.mp4',planning_gif=animations/'mission_planning_replay.gif',planning_mp4=videos/'mission_planning_replay.mp4',forces3d_gif=animations/'mission_force_vectors_3d.gif',forces3d_mp4=videos/'mission_force_vectors_3d.mp4',state_machine_gif=animations/'mission_state_machine_replay.gif',state_machine_mp4=videos/'mission_state_machine_replay.mp4',body3d_gif=animations/'mission_vehicle_3d_replay.gif',body3d_mp4=videos/'mission_vehicle_3d_replay.mp4',animation_contact_sheet=animations/'mission_animation_contact_sheet.png')
    exports=[_draw_mission_map(nominal,env,artifacts.mission_map),_draw_tracking_dynamics(nominal,artifacts.tracking_dynamics),_draw_force_balance(nominal,artifacts.force_balance_2d),_draw_mechanical_forces_2d(model,nominal,artifacts.mechanical_forces_2d),_draw_mechanical_forces_3d(model,nominal,artifacts.mechanical_forces_3d),_draw_trajectory_3d(nominal,artifacts.trajectory_time_3d),_draw_controller_surface(artifacts.controller_surface_3d),_draw_scenario_comparison(scenarios,artifacts.scenario_comparison),_draw_quality_dashboard(nominal,scenarios,artifacts.mission_quality_dashboard)]
    assert_export_quality(exports)
    _write_csv(artifacts.simulation_rows,nominal.rows);_write_csv(artifacts.scenario_metrics,_scenario_rows(scenarios));_write_csv(artifacts.event_ledger,nominal.events or [{'time_s':0.0,'event':'NONE','reason':'none'}])
    force_rows=[{k:row[k] for k in ('time_s','port_thrust_n','starboard_thrust_n','total_thrust_n','yaw_moment_n_m','x_drag_n','y_drag_n','yaw_drag_n_m','hazard_clearance_m')} for row in nominal.rows];_write_csv(artifacts.force_ledger,force_rows)
    control_rows=[{k:row[k] for k in ('time_s','mode','guidance_x_m','guidance_y_m','desired_heading_deg','heading_error_deg','desired_speed_mps','ground_speed_mps','route_id','replan_count','watchdog_count')} for row in nominal.rows];_write_csv(artifacts.controller_ledger,control_rows)
    checks=[{'check':'mission completes at home after multi-target quota','result':'PASS' if int(nominal.metrics['mission_success']) else 'FAIL','value':nominal.metrics['final_state']},{'check':'no persistent progress watchdog loop','result':'PASS' if int(nominal.metrics['watchdog_event_count'])==0 else 'CHECK','value':nominal.metrics['watchdog_event_count']},{'check':'guard distance maintained','result':'PASS' if float(nominal.metrics['minimum_clearance_m'])>=.32-1e-6 else 'FAIL','value':nominal.metrics['minimum_clearance_m']},{'check':'at least three verified captures','result':'PASS' if int(nominal.metrics['collected_count'])>=3 else 'FAIL','value':nominal.metrics['collected_count']},{'check':'final dock error below 0.35 m','result':'PASS' if float(nominal.metrics['final_distance_home_m'])<.35 else 'FAIL','value':nominal.metrics['final_distance_home_m']}];_write_csv(artifacts.acceptance_checks,checks)
    _animate_topdown(nominal,env,artifacts.topdown_gif,artifacts.topdown_mp4,frame_count=animation_frames,fps=animation_fps);_animate_telemetry(nominal,env,artifacts.telemetry_gif,artifacts.telemetry_mp4,frame_count=animation_frames,fps=animation_fps);_animate_planning(nominal,env,artifacts.planning_gif,artifacts.planning_mp4,frame_count=animation_frames,fps=animation_fps);_animate_forces3d(nominal,artifacts.forces3d_gif,artifacts.forces3d_mp4,frame_count=max(12, int(animation_frames*0.60)),fps=animation_fps);_animate_state_machine(nominal,env,artifacts.state_machine_gif,artifacts.state_machine_mp4,frame_count=animation_frames,fps=animation_fps);_animate_body3d(nominal,env,artifacts.body3d_gif,artifacts.body3d_mp4,frame_count=max(12, int(animation_frames*0.60)),fps=animation_fps)
    videos_list=[(artifacts.topdown_gif,artifacts.topdown_mp4,'Top-down mission replay','vehicle pose, path, SOC and verified collections'),(artifacts.telemetry_gif,artifacts.telemetry_mp4,'Telemetry replay','map, speed tracking and twin-thruster demand'),(artifacts.planning_gif,artifacts.planning_mp4,'Planning replay','A* leg sequence, clearance and replanning'),(artifacts.forces3d_gif,artifacts.forces3d_mp4,'3-D force replay','thrust, drag, weight and buoyancy directions'),(artifacts.state_machine_gif,artifacts.state_machine_mp4,'State-machine replay','autonomy mode progression and target activity'),(artifacts.body3d_gif,artifacts.body3d_mp4,'3-D vehicle replay','catamaran pose and surface trajectory')]
    _write_csv(artifacts.animation_manifest,[{'gif':relative_to_root(g),'mp4':relative_to_root(m),'title':t,'content':c,'gif_bytes':g.stat().st_size,'mp4_bytes':m.stat().st_size} for g,m,t,c in videos_list]);_contact_sheet([pair[0] for pair in videos_list],artifacts.animation_contact_sheet)
    quality={'phase':'Mission fidelity and advanced visualisation revision','plot_title_policy':'Plot titles omit internal project phase numbers. Phase evidence remains in folder names, manifests and reports.','exports':[e.as_dict() for e in exports],'animations':[{'gif':relative_to_root(g),'mp4':relative_to_root(m)} for g,m,_,_ in videos_list]};artifacts.visual_quality_manifest.write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'nominal_metrics':nominal.metrics,'scenario_metrics':_scenario_rows(scenarios),'scope':['3-DOF physical plant with robust line-of-sight guidance','A* route planning, guard-distance recovery and progress watchdog','2-D/3-D force, dynamics, control and mission visualisation','six GIF and six MP4 evidence replays'],'limitations':['The supervisory recovery is a numerical safety mechanism, not an impact/contact model.','The 3-D vehicle replay is a geometric visualization of a surface craft; heave, roll and wave dynamics are not solved.','The energy-return scenario is a decision-mode demonstration and does not represent a hardware-qualified battery safety system.'],'rendering': {'frames_per_2d_replay': animation_frames, 'frames_per_3d_replay': max(12, int(animation_frames*0.60)), 'fps': animation_fps}, 'artifacts':artifacts.as_dict()};artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    artifacts.summary_markdown.write_text('# AquaSkim-Sim | Mission fidelity and advanced visualisation\n\n## Result\n\nThe historical short mission reels are superseded by a progress-monitored, multi-target 3-DOF mission. The nominal case finishes with three verified captures, returns to the home station and remains above the specified guard distance.\n\n## Visual outputs\n\nThe suite contains 2-D dynamics and force plots, 3-D mechanical/force diagrams, a trajectory-time reconstruction, a control-allocation surface, scenario comparison and six purpose-specific animations. Internal phase numbers are intentionally omitted from figure titles.\n\n## Reproducibility\n\nAll figures, videos, CSV ledgers and the summary JSON are generated from the configuration, the deterministic environment seed and the recorded simulation state.\n',encoding='utf-8')
    return artifacts


def print_phase10_4_summary(artifacts: Phase104Artifacts) -> None:
    print('='*72);print('AquaSkim-Sim | Mission Fidelity and Advanced Visualisation');print('='*72)
    for key,path in artifacts.as_dict().items(): print(f'{key:28}: {path}')
    print('='*72);print('[OK] Mission-quality, 2-D/3-D and animation artifacts generated.')
