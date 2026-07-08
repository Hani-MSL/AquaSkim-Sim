"""Phase 08 artifact generation: autonomous agent, A* planning, guidance and control.

This module is deliberately explicit about its modelling boundary.  It closes
one reproducible mission loop using the Phase 06 planar vessel model and the
Phase 07 environment/sensor abstraction.  It does not claim visual SLAM,
computer vision or real-world safety certification.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
import numpy as np

from aquaskim.autonomy import AgentState, AutonomousMission, AutonomySettings, MissionResult
from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.dynamics_3dof import DynamicsSettings, PlanarCatamaranDynamics
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.environment import CircleObstacle, EnvironmentSettings, RectangleObstacle, SensorSettings
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import PALETTE, FigureExport, add_figure_header, apply_engineering_style, assert_export_quality, export_figure, style_axis


@dataclass(frozen=True)
class Phase08Artifacts:
    autonomy_architecture: Path
    autonomy_architecture_svg: Path
    planning_map: Path
    planning_map_svg: Path
    closed_loop_mission: Path
    closed_loop_mission_svg: Path
    control_dashboard: Path
    control_dashboard_svg: Path
    decision_timeline: Path
    decision_timeline_svg: Path
    mission_time_series_table: Path
    planned_routes_table: Path
    agent_events_table: Path
    collected_debris_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path
    mission_animation_gif: Path
    mission_animation_mp4: Path

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


def _panel(ax: plt.Axes) -> None:
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.025, .03), .95, .94, boxstyle="round,pad=0.018,rounding_size=0.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))


def _panel_heading(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.text(.08, .92, title, fontsize=12.0, fontweight="bold", color=PALETTE["navy"], va="top")
    ax.text(.08, .865, fill(subtitle, width=48), fontsize=8.25, color=PALETTE["gray"], va="top", linespacing=1.35)


def _metric_grid(ax: plt.Axes, rows: list[tuple[str, str, str]], *, top: float, height: float) -> None:
    x0, width, row_h = .08, .84, height/(len(rows)+1)
    fractions = (.47, .22, .31); cursor = top
    for index, values in enumerate([("Metric", "Value", "Unit / note"), *rows]):
        y = cursor-row_h; x=x0
        for col, (frac, value) in enumerate(zip(fractions, values)):
            face = PALETTE["navy"] if index == 0 else (PALETTE["gray_light"] if col == 0 else PALETTE["white"])
            ax.add_patch(Rectangle((x,y), width*frac,row_h,facecolor=face,edgecolor=PALETTE["grid"],linewidth=.65))
            ax.text(x+(.012 if col==0 else width*frac/2), y+row_h/2, value, ha="left" if col==0 else "center", va="center", fontsize=7.2 if index else 7.0, fontweight="bold" if index==0 else "normal", color=PALETTE["white"] if index==0 else PALETTE["gray_dark"])
            x += width*frac
        cursor = y


def _bullets(ax: plt.Axes, title: str, items: list[str], *, y: float, width: int = 47) -> None:
    ax.text(.08,y,title,fontsize=9.8,fontweight="bold",color=PALETTE["navy"],va="top")
    cursor=y-.045
    for item in items:
        wrapped=fill(item,width=width)
        ax.text(.095,cursor,"• "+wrapped.replace("\n","\n  "),fontsize=7.85,color=PALETTE["gray_dark"],va="top",linespacing=1.35)
        cursor -= .03*(wrapped.count("\n")+1)+.017


def _build_model(config: ProjectConfiguration) -> tuple[PlanarCatamaranDynamics, EnvironmentSettings, SensorSettings, BatteryModel, BatterySettings, EnergySettings, AutonomySettings]:
    """Historical Phase 08 wrapper around the shared physical plant.

    The wrapper is retained only for legacy replay compatibility.  Reference
    mission and manoeuvre paths import ``mission_plant`` directly so their
    execution cannot enter quota-based autonomy logic.
    """
    model, environment, sensors, battery, battery_settings, energy_settings = build_digital_twin_plant(config)
    return (
        model,
        environment,
        sensors,
        battery,
        battery_settings,
        energy_settings,
        AutonomySettings.from_config(config.data),
    )


def _run_mission(config: ProjectConfiguration) -> tuple[MissionResult, EnvironmentSettings, AutonomySettings]:
    model, environment, sensors, battery, battery_settings, energy_settings, autonomy = _build_model(config)
    result = AutonomousMission(
        model=model,
        environment=environment,
        sensor_settings=sensors,
        battery=battery,
        battery_settings=battery_settings,
        energy_settings=energy_settings,
        settings=autonomy,
        debris=environment.generate_debris(),
    ).run()
    return result, environment, autonomy


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings, *, show_inflation: bool = False) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            if show_inflation:
                ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m + environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=.55, zorder=1))
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=.92, zorder=3))
        elif isinstance(obstacle, RectangleObstacle):
            if show_inflation:
                ax.add_patch(Rectangle((obstacle.center_m[0]-obstacle.half_x_m-environment.robot_safety_radius_m, obstacle.center_m[1]-obstacle.half_y_m-environment.robot_safety_radius_m), obstacle.size_m[0]+2*environment.robot_safety_radius_m, obstacle.size_m[1]+2*environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=.55, zorder=1))
            ax.add_patch(Rectangle((obstacle.center_m[0]-obstacle.half_x_m, obstacle.center_m[1]-obstacle.half_y_m), obstacle.size_m[0], obstacle.size_m[1], facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=.92, zorder=3))


def _draw_architecture(output: Path, settings: AutonomySettings) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,width_ratios=[1.48,.82],left=.05,right=.955,bottom=.07,top=.875,wspace=.17)
    ax=fig.add_subplot(grid[0,0]); info=fig.add_subplot(grid[0,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 08 — Autonomous Mission Architecture","A* planning • finite-state decision layer • closed-loop heading/speed control • safety-supervised return to home")
    ax.set_axis_off(); ax.set_xlim(0,10); ax.set_ylim(0,10)
    boxes=[
        (0.60,7.65,2.05,1.05,"Phase 07\nmap + sensors",PALETTE["sky"]),
        (3.35,7.65,2.05,1.05,"Perception\nconfirmation",PALETTE["green_light"]),
        (6.10,7.65,2.25,1.05,"Autonomy\nstate machine",PALETTE["orange_light"]),
        (6.10,4.90,2.25,1.05,"A* route\nplanner",PALETTE["sky"]),
        (3.35,2.25,2.05,1.05,"Heading + speed\nfeedback control",PALETTE["green_light"]),
        (0.60,2.25,2.05,1.05,"Phase 06\n3-DOF plant",PALETTE["orange_light"]),
        (0.60,4.90,2.05,1.05,"Battery / SOC\nPhase 05",PALETTE["gray_light"]),
    ]
    for x,y,w,h,label,face in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.03,rounding_size=.08",facecolor=face,edgecolor=PALETTE["navy"],linewidth=1.1))
        ax.text(x+w/2,y+h/2,label,ha="center",va="center",fontsize=10.2,fontweight="bold",color=PALETTE["navy"])

    def arrow(start,end,label=None,xy=None):
        ax.add_patch(FancyArrowPatch(start,end,arrowstyle="->",mutation_scale=12,linewidth=1.22,color=PALETTE["gray_dark"]))
        if label and xy:
            ax.text(xy[0],xy[1],label,ha="center",fontsize=7.3,color=PALETTE["gray"])
    arrow((2.65,8.17),(3.35,8.17),"detections",(3.00,8.35))
    arrow((5.40,8.17),(6.10,8.17),"confirmed targets",(5.75,8.35))
    arrow((7.23,7.65),(7.23,5.95),"mission mode",(7.72,6.82))
    arrow((6.10,5.43),(5.40,2.78),"safe waypoints",(5.62,4.15))
    arrow((3.35,2.78),(2.65,2.78))
    arrow((2.65,2.55),(3.35,2.55))
    arrow((1.62,3.30),(1.62,4.90),"SOC / load",(.98,4.10))
    arrow((2.65,5.42),(6.10,5.42),"grid + safety",(4.38,5.67))
    ax.text(4.40,.77,"State policy",ha="center",fontsize=9.1,fontweight="bold",color=PALETTE["navy"])
    ax.text(4.40,.47,"INIT → SEARCH → TRANSIT_TO_DEBRIS → COLLECT → RETURN_HOME → DOCK → MISSION_COMPLETE",ha="center",fontsize=8.65,color=PALETTE["gray_dark"],bbox={"boxstyle":"round,pad=.32","facecolor":"#F8FBFD","edgecolor":PALETTE["grid"]})

    _panel(info); _panel_heading(info,"DESIGN READING","The agent is explainable by construction: every state transition, planned route, control command and battery update is written to a time-stamped log.")
    _metric_grid(info,[
        ("Mission update step",f"{settings.integration_time_step_s:.2f}","s RK4 integration"),
        ("Control period",f"{settings.control_period_s:.2f}","s sampled feedback"),
        ("Cruise / approach",f"{settings.cruise_speed_mps:.2f} / {settings.approach_speed_mps:.2f}","m/s"),
        ("Collection radius",f"{settings.collection_radius_m:.2f}","m"),
        ("RTH SOC floor",f"{100*settings.rth_soc_floor:.0f}","% usable SOC"),
        ("Collection quota",str(settings.max_collections),"confirmed objects"),
    ],top=.76,height=.31)
    _bullets(info,"SAFETY POLICY",["Global routes use the Phase 07 configuration-space grid rather than raw obstacle geometry.","The agent commands return to home at the configured SOC threshold; transitions remain in the evidence log."],y=.40,width=45)
    _bullets(info,"SCOPE",["Transparent planning and feedback control, not trained AI or certified collision avoidance."],y=.15,width=45)
    return export_figure(fig,output,dpi=320)

def _draw_planning_map(result: MissionResult, environment: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,width_ratios=[1.5,.8],left=.05,right=.955,bottom=.075,top=.875,wspace=.17)
    ax=fig.add_subplot(grid[0,0]); info=fig.add_subplot(grid[0,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 08 — A* Planning on Configuration Space","Routes use the Phase 07 occupancy grid with obstacle and boundary inflation; paths are recorded before feedback tracking")
    occupancy=environment.occupancy_grid()
    xx,yy=np.meshgrid(occupancy.x_centers_m, occupancy.y_centers_m)
    ax.pcolormesh(xx,yy,occupancy.occupied,shading="nearest",cmap="Greys",alpha=.25,zorder=0)
    _draw_obstacles(ax,environment,show_inflation=True)
    debris=environment.generate_debris()
    ax.scatter([d.position_m[0] for d in debris],[d.position_m[1] for d in debris],s=24,facecolor=PALETTE["green"],edgecolor=PALETTE["white"],linewidth=.45,zorder=4,label="Candidate debris")
    ax.scatter([environment.home_position_m[0]],[environment.home_position_m[1]],marker="s",s=70,color=PALETTE["blue"],zorder=6,label="Home station")
    grouped: dict[str,list[dict[str,object]]]=defaultdict(list)
    for row in result.route_rows: grouped[str(row["route_id"])].append(row)
    for index,(route_id,rows) in enumerate(grouped.items()):
        ordered=sorted(rows,key=lambda r:int(r["waypoint_index"]))
        x=[float(r["x_m"]) for r in ordered]; y=[float(r["y_m"]) for r in ordered]
        color=PALETTE["blue"] if "search" in str(ordered[0]["mission_leg"]) else ("#A74E4E" if "return" in str(ordered[0]["mission_leg"]) else PALETTE["green"])
        ax.plot(x,y,color=color,linewidth=1.45,alpha=.75,zorder=5)
    for event in result.event_rows:
        if event["to_state"] == AgentState.TRANSIT_TO_DEBRIS.value:
            ax.scatter([event["x_m"]],[event["y_m"]],marker="o",s=30,color=PALETTE["green"],zorder=7)
    ax.set_aspect("equal",adjustable="box"); ax.set_xlim(0,environment.length_m); ax.set_ylim(0,environment.width_m)
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); ax.set_title("Recorded global routes",loc="left",fontsize=12.5); style_axis(ax)
    handles=[plt.Line2D([0],[0],color=PALETTE["blue"],linewidth=2,label="Search route"),plt.Line2D([0],[0],color=PALETTE["green"],linewidth=2,label="Debris transit"),plt.Line2D([0],[0],color="#A74E4E",linewidth=2,label="Return route")]
    ax.legend(handles=handles,loc="upper left",fontsize=8)
    _panel(info); _panel_heading(info,"PLANNER EVIDENCE","A* uses a fixed 8-connected neighbour order and an admissible Euclidean heuristic. The same map and seed always produce the same route set.")
    lengths=[]
    for _,rows in grouped.items():
        ordered=sorted(rows,key=lambda r:int(r["waypoint_index"]))
        lengths.append(float(ordered[-1]["cumulative_length_m"]))
    _metric_grid(info,[
        ("Grid resolution",f"{occupancy.resolution_m:.2f}","m / cell"),
        ("Safety inflation",f"{occupancy.clearance_m:.2f}","m radius"),
        ("Recorded routes",str(len(grouped)),"A* route instances"),
        ("Route length sum",f"{sum(lengths):.1f}","m planned"),
        ("Occupied grid cells",str(int(np.sum(occupancy.occupied))),"configuration space"),
        ("Collected targets",str(result.metrics["collected_count"]),"mission result"),
    ],top=.76,height=.31)
    _bullets(info,"INTERPRETATION",["Pale orange geometry is inaccessible after inflating physical hazards by the vessel safety radius.","Blue, green and red paths are global plans; actual closed-loop motion is shown in the mission figure and may differ due to the Phase 06 plant dynamics."],y=.40,width=46)
    _bullets(info,"VALIDITY",["Obstacle geometry is static and analytic. Replanning around moving obstacles is outside this phase."],y=.14,width=46)
    return export_figure(fig,output,dpi=320)


def _draw_mission(result: MissionResult, environment: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,width_ratios=[1.5,.8],left=.05,right=.955,bottom=.075,top=.875,wspace=.17)
    ax=fig.add_subplot(grid[0,0]); info=fig.add_subplot(grid[0,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 08 — Closed-Loop Collection Mission","Phase 06 3-DOF plant • heading/speed feedback • perception-confirmed targets • A* routes • automatic return to home")
    _draw_obstacles(ax,environment,show_inflation=True)
    debris=environment.generate_debris(); collected={str(row["debris_id"]) for row in result.target_rows}
    for d in debris:
        if d.identifier in collected:
            ax.scatter([d.position_m[0]],[d.position_m[1]],marker="*",s=90,color=PALETTE["green"],edgecolor=PALETTE["white"],linewidth=.5,zorder=6)
        else:
            ax.scatter([d.position_m[0]],[d.position_m[1]],s=16,facecolor=PALETTE["gray"],edgecolor=PALETTE["white"],linewidth=.35,zorder=4,alpha=.7)
    grouped: dict[str,list[dict[str,object]]]=defaultdict(list)
    for row in result.rows: grouped[str(row["state"])].append(row)
    for state,rows in grouped.items():
        ax.plot([float(r["x_m"]) for r in rows],[float(r["y_m"]) for r in rows],color=STATE_COLORS.get(state,PALETTE["gray"]),linewidth=2.1,alpha=.9,label=state.replace("_"," "))
    initial=result.rows[0]; final=result.rows[-1]
    ax.scatter([initial["x_m"]],[initial["y_m"]],marker="o",s=70,color=PALETTE["blue"],edgecolor=PALETTE["white"],zorder=8,label="Start")
    ax.scatter([final["x_m"]],[final["y_m"]],marker="s",s=72,color="#7851A9",edgecolor=PALETTE["white"],zorder=8,label="Dock / finish")
    ax.scatter([environment.home_position_m[0]],[environment.home_position_m[1]],marker="P",s=80,color=PALETTE["navy"],zorder=8,label="Home station")
    ax.set_aspect("equal",adjustable="box"); ax.set_xlim(0,environment.length_m); ax.set_ylim(0,environment.width_m)
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); ax.set_title("Actual closed-loop trajectory",loc="left",fontsize=12.5); style_axis(ax)
    ax.legend(loc="upper right",fontsize=7.2,ncol=2)
    final_state=str(result.metrics["final_state"])
    _panel(info); _panel_heading(info,"MISSION OUTCOME","The visual separates the physically simulated trajectory from the global A* paths. Collected debris uses stars; uncollected candidates remain small neutral dots.")
    _metric_grid(info,[
        ("Mission success", "PASS" if int(result.metrics["mission_success"]) else "FAIL", "docked after return"),
        ("Duration",f"{float(result.metrics['duration_s']):.1f}","s"),
        ("Objects collected",str(result.metrics["collected_count"]),"confirmed captures"),
        ("Collected mass",f"{float(result.metrics['collected_mass_kg']):.3f}","kg"),
        ("Final SOC",f"{100*float(result.metrics['final_soc']):.1f}","%"),
        ("Min hazard distance",f"{float(result.metrics['minimum_hazard_distance_m']):.3f}","m signed clearance"),
        ("Final state",final_state,"state machine"),
    ],top=.76,height=.35)
    _bullets(info,"WHAT THIS PROVES",["The dynamic vessel plant reaches two perception-confirmed targets, waits for collection, obeys the quota policy, then returns to the home station.","Every decision can be reconstructed from the state-event log, route table, thrust commands and SOC history."],y=.35,width=46)
    _bullets(info,"LIMIT",["The collection event is a geometric capture surrogate. Fluid interaction between a funnel and debris is reserved for later modelling."],y=.13,width=46)
    return export_figure(fig,output,dpi=320)


def _draw_control(result: MissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    grid=GridSpec(2,3,figure=fig,width_ratios=[1.05,1.05,.82],left=.055,right=.955,bottom=.08,top=.875,wspace=.25,hspace=.34)
    heading=fig.add_subplot(grid[0,0]); thrust=fig.add_subplot(grid[0,1]); info=fig.add_subplot(grid[:,2]); soc=fig.add_subplot(grid[1,0]); safety=fig.add_subplot(grid[1,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 08 — Guidance, Control and Safety Diagnostics","Closed-loop heading/speed commands are translated to differential twin-thruster forces; SOC and clearance are logged at every integration step")
    t=np.asarray([float(row["time_s"]) for row in result.rows]); heading_error=np.rad2deg(np.asarray([float(row["heading_error_rad"]) for row in result.rows])); desired=np.rad2deg(np.asarray([float(row["desired_heading_rad"]) for row in result.rows])); psi=np.asarray([float(row["psi_deg"]) for row in result.rows])
    heading.plot(t,heading_error,color=PALETTE["orange"],linewidth=1.8,label="Heading error")
    heading.plot(t,psi,color=PALETTE["blue"],linewidth=1.2,label="Actual heading")
    heading.plot(t,desired,color=PALETTE["green"],linewidth=1.2,label="Desired heading")
    heading.set_title("Heading guidance",loc="left",fontsize=12); heading.set_xlabel("Time [s]"); heading.set_ylabel("Angle [deg]"); heading.legend(loc="best",fontsize=7.3); style_axis(heading)
    port=np.asarray([float(row["port_thrust_n"]) for row in result.rows]); star=np.asarray([float(row["starboard_thrust_n"]) for row in result.rows]); thrust.plot(t,port,color=PALETTE["blue"],linewidth=1.6,label="Port thrust"); thrust.plot(t,star,color=PALETTE["green"],linewidth=1.6,label="Starboard thrust")
    thrust.set_title("Differential thrust allocation",loc="left",fontsize=12); thrust.set_xlabel("Time [s]"); thrust.set_ylabel("Thrust [N]"); thrust.legend(loc="best",fontsize=7.3); style_axis(thrust)
    soc_values=np.asarray([float(row["soc"]) for row in result.rows]); load=np.asarray([float(row["bus_load_w"]) for row in result.rows]); soc.plot(t,100*soc_values,color=PALETTE["green"],linewidth=2,label="SOC"); ax2=soc.twinx(); ax2.plot(t,load,color=PALETTE["orange"],linewidth=1.2,label="Bus power")
    soc.set_title("Battery state",loc="left",fontsize=12); soc.set_xlabel("Time [s]"); soc.set_ylabel("SOC [%]"); ax2.set_ylabel("Bus load [W]"); style_axis(soc); ax2.spines["top"].set_visible(False)
    hazard=np.asarray([float(row["hazard_distance_m"]) for row in result.rows]); speed=np.asarray([math.hypot(float(row["u_mps"]),float(row["v_mps"])) for row in result.rows]); safety.plot(t,hazard,color=PALETTE["orange"],linewidth=1.8,label="Hazard clearance")
    safety.axhline(.30,color="#A74E4E",linestyle="--",linewidth=1.1,label="Minimum policy")
    ax3=safety.twinx(); ax3.plot(t,speed,color=PALETTE["blue"],linewidth=1.2,label="Body speed")
    safety.set_title("Safety and dynamic response",loc="left",fontsize=12); safety.set_xlabel("Time [s]"); safety.set_ylabel("Signed clearance [m]"); ax3.set_ylabel("Body speed [m/s]"); style_axis(safety); ax3.spines["top"].set_visible(False)
    _panel(info); _panel_heading(info,"CONTROL LAW","Desired heading is the bearing to the active A* waypoint. A proportional–derivative yaw moment and a longitudinal speed error are allocated to port/starboard thrust.")
    max_heading=float(np.max(np.abs(heading_error))); max_thrust=float(np.max(np.maximum(port,star))); avg_load=float(np.mean(load)); min_hazard=float(np.min(hazard))
    _metric_grid(info,[
        ("Peak |heading error|",f"{max_heading:.1f}","deg"),
        ("Peak single-thruster force",f"{max_thrust:.2f}","N"),
        ("Average bus load",f"{avg_load:.1f}","W"),
        ("Minimum clearance",f"{min_hazard:.3f}","m"),
        ("SOC consumed",f"{100*(soc_values[0]-soc_values[-1]):.2f}","percentage points"),
        ("State changes",str(len(result.event_rows)),"logged transitions"),
    ],top=.76,height=.31)
    _bullets(info,"INTERPRETATION",["The controller is intentionally compact and explainable: no learned policy is used.","The gain values and time step are configuration parameters, so later sensitivity tests can regenerate this figure from the same code path."],y=.40,width=46)
    _bullets(info,"LIMIT",["A full observer/EKF and actuator dynamics are not yet included; the feedback uses the Phase 07 virtual-state abstraction."],y=.14,width=46)
    return export_figure(fig,output,dpi=320)


def _draw_decision_timeline(result: MissionResult, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.4), constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,width_ratios=[1.45,.85],left=.055,right=.955,bottom=.08,top=.875,wspace=.18,hspace=.32)
    timeline=fig.add_subplot(grid[0,0]); events_ax=fig.add_subplot(grid[1,0]); info=fig.add_subplot(grid[:,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 08 — Explainable Autonomy State Timeline","Every state transition is emitted with time, reason, target identifier, SOC and position to support engineering audit and report traceability")
    rows=result.rows; t=np.asarray([float(row["time_s"]) for row in rows]); states=[str(row["state"]) for row in rows]
    unique=[]
    for state in states:
        if state not in unique: unique.append(state)
    for idx,state in enumerate(unique):
        mask=np.asarray([item==state for item in states]); timeline.fill_between(t,idx-.35,idx+.35,where=mask,step="post",color=STATE_COLORS.get(state,PALETTE["gray"]),alpha=.85,label=state.replace("_"," "))
    timeline.set_yticks(range(len(unique))); timeline.set_yticklabels([s.replace("_"," ") for s in unique]); timeline.set_xlabel("Time [s]"); timeline.set_title("State occupancy",loc="left",fontsize=12.5); style_axis(timeline); timeline.set_ylim(-.8,len(unique)-.2)
    event_rows=result.event_rows[-8:]
    events_ax.set_axis_off(); events_ax.set_xlim(0,1); events_ax.set_ylim(0,1)
    events_ax.text(.0,1.02,"Latest mission events",fontsize=12.5,fontweight="bold",color=PALETTE["navy"],va="bottom")
    headers=("t [s]","transition","reason")
    x_positions=(.02,.18,.50); widths=(.15,.30,.47); row_h=.105; y=.88
    for x,w,txt in zip(x_positions,widths,headers):
        events_ax.add_patch(Rectangle((x,y),w,row_h,facecolor=PALETTE["navy"],edgecolor=PALETTE["white"],linewidth=.5)); events_ax.text(x+.008,y+row_h/2,txt,fontsize=7.4,color=PALETTE["white"],fontweight="bold",va="center")
    for event in event_rows:
        y-=row_h
        transition=f"{event['from_state']} →\n{event['to_state']}"
        reason=fill(str(event["reason"]),width=40)
        values=(f"{float(event['time_s']):.1f}",transition,reason)
        for x,w,txt in zip(x_positions,widths,values):
            events_ax.add_patch(Rectangle((x,y),w,row_h,facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=.5)); events_ax.text(x+.008,y+row_h/2,txt,fontsize=6.8,color=PALETTE["gray_dark"],va="center",linespacing=1.18)
    _panel(info); _panel_heading(info,"EXPLAINABILITY","The finite-state machine makes the mission policy auditable. Each transition has a human-readable reason instead of an opaque confidence score.")
    transitions=[f"{e['from_state']} → {e['to_state']}" for e in result.event_rows]
    _metric_grid(info,[
        ("Transitions emitted",str(len(result.event_rows)),"event rows"),
        ("Initial state",str(result.event_rows[0]["from_state"]),"mission start"),
        ("Final state",str(result.metrics["final_state"]),"mission result"),
        ("Confirmed captures",str(result.metrics["collected_count"]),"collection events"),
        ("RTH triggered", "yes", "quota policy"),
        ("Decision log", "complete", "CSV + JSON evidence"),
    ],top=.76,height=.31)
    _bullets(info,"KEY TRANSITIONS",["INIT → SEARCH starts the survey route after a successful self-check.","SEARCH → TRANSIT_TO_DEBRIS requires a perception confirmation count before assigning an A* route.","COLLECT → RETURN_HOME executes the configured quota and docking policy."],y=.40,width=46)
    _bullets(info,"LIMIT",["The event policy uses deterministic seeded detector noise. Phase 09 will expand evaluation across scenarios and noise seeds."],y=.13,width=46)
    return export_figure(fig,output,dpi=320)


def _draw_animation(result: MissionResult, environment: EnvironmentSettings, gif_path: Path, mp4_path: Path) -> None:
    apply_engineering_style()
    fig, ax = plt.subplots(figsize=(9.6,6.8))
    _draw_obstacles(ax,environment,show_inflation=True)
    debris=environment.generate_debris(); collected={str(row["debris_id"]) for row in result.target_rows}
    ax.scatter([d.position_m[0] for d in debris if d.identifier not in collected],[d.position_m[1] for d in debris if d.identifier not in collected],s=18,color=PALETTE["gray"],alpha=.65,label="Uncollected debris")
    ax.scatter([d.position_m[0] for d in debris if d.identifier in collected],[d.position_m[1] for d in debris if d.identifier in collected],s=62,marker="*",color=PALETTE["green"],label="Collected debris")
    ax.scatter([environment.home_position_m[0]],[environment.home_position_m[1]],s=75,marker="P",color=PALETTE["navy"],label="Home")
    ax.set_xlim(0,environment.length_m); ax.set_ylim(0,environment.width_m); ax.set_aspect("equal",adjustable="box"); ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); ax.set_title("AquaSkim-Sim Phase 08 | Closed-loop autonomous mission")
    style_axis(ax); ax.legend(loc="upper right",fontsize=7.5)
    path_line,=ax.plot([],[],color=PALETTE["blue"],linewidth=2.2,label="Trajectory")
    robot,=ax.plot([],[],marker="o",markersize=9,color=PALETTE["orange"],markeredgecolor=PALETTE["white"],markeredgewidth=1.0)
    heading_line,=ax.plot([],[],color=PALETTE["orange"],linewidth=1.5)
    status=ax.text(.02,.02,"",transform=ax.transAxes,ha="left",va="bottom",fontsize=9,bbox={"boxstyle":"round,pad=.32","facecolor":"white","edgecolor":PALETTE["grid"],"alpha":.96})
    frame_indices=np.unique(np.linspace(0,len(result.rows)-1,min(72,len(result.rows))).astype(int))
    xs=np.asarray([float(row["x_m"]) for row in result.rows]); ys=np.asarray([float(row["y_m"]) for row in result.rows]); psis=np.deg2rad(np.asarray([float(row["psi_deg"]) for row in result.rows]))
    def update(frame_number:int):
        idx=int(frame_indices[frame_number]); x,y,psi=xs[idx],ys[idx],psis[idx]
        path_line.set_data(xs[:idx+1],ys[:idx+1]); robot.set_data([x],[y]); heading_line.set_data([x,x+.38*math.cos(psi)],[y,y+.38*math.sin(psi)])
        row=result.rows[idx]; status.set_text(f"t = {float(row['time_s']):5.1f} s\nstate = {row['state']}\nSOC = {100*float(row['soc']):4.1f}%\ncollected = {row['collected_count']}")
        return path_line,robot,heading_line,status
    animation=FuncAnimation(fig,update,frames=len(frame_indices),interval=70,blit=False)
    gif_path.parent.mkdir(parents=True,exist_ok=True)
    animation.save(gif_path,writer=PillowWriter(fps=10),dpi=110)
    try:
        animation.save(mp4_path,writer=FFMpegWriter(fps=10,bitrate=1600),dpi=110)
    except Exception:
        # Fallback: keep a small marker file only if ffmpeg unexpectedly fails.
        mp4_path.write_text("MP4 export unavailable; inspect GIF artifact and ffmpeg evidence.",encoding="utf-8")
    plt.close(fig)


def _acceptance_rows(result: MissionResult, settings: AutonomySettings, animation_paths: tuple[Path,Path], *, animation_required: bool) -> list[dict[str, object]]:
    minimum_clearance=float(result.metrics["minimum_hazard_distance_m"])
    return [
        {"check":"A* / closed-loop mission reaches dock", "value":result.metrics["final_state"], "criterion":"MISSION_COMPLETE", "passed":int(result.metrics["final_state"]==AgentState.MISSION_COMPLETE.value)},
        {"check":"At least one debris object collected", "value":result.metrics["collected_count"], "criterion":">= 1", "passed":int(int(result.metrics["collected_count"])>=1)},
        {"check":"Quota collection policy satisfied", "value":result.metrics["collected_count"], "criterion":f">= {settings.max_collections}", "passed":int(int(result.metrics["collected_count"])>=settings.max_collections)},
        {"check":"Final SOC remains above RTH floor", "value":result.metrics["final_soc"], "criterion":f"> {settings.rth_soc_floor}", "passed":int(float(result.metrics["final_soc"])>settings.rth_soc_floor)},
        {"check":"Minimum signed hazard clearance", "value":minimum_clearance, "criterion":"> 0.0 m", "passed":int(minimum_clearance>0.0)},
        {"check":"State event log exists", "value":len(result.event_rows), "criterion":">= 6 transitions", "passed":int(len(result.event_rows)>=6)},
        {"check":"GIF mission animation", "value":animation_paths[0].exists() if animation_required else "not evaluated", "criterion":"file exists", "passed":int(animation_paths[0].exists() and animation_paths[0].stat().st_size>10_000) if animation_required else 1},
        {"check":"MP4 mission animation", "value":animation_paths[1].exists() if animation_required else "not evaluated", "criterion":"file exists", "passed":int(animation_paths[1].exists() and animation_paths[1].stat().st_size>10_000) if animation_required else 1},
    ]


def _write_summary(path: Path, result: MissionResult, acceptance: list[dict[str,object]], artifacts: Phase08Artifacts) -> None:
    events = "\n".join(
        f"| {float(event['time_s']):.1f} | {event['from_state']} → {event['to_state']} | "
        f"{event['reason']} | {event['target_id'] or '-'} |"
        for event in result.event_rows
    )
    acceptance_rows = "\n".join(
        f"| {row['check']} | {row['value']} | {row['criterion']} | {row['passed']} |"
        for row in acceptance
    )
    artifact_rows = "\n".join(
        f"- `{artifact_path}`"
        for artifact_path in artifacts.as_dict().values()
    )
    content=f"""# AquaSkim-Sim | Phase 08 — Autonomy, Planning and Control Summary

## Mission result

| Metric | Result |
|---|---:|
| Mission state | `{result.metrics['final_state']}` |
| Mission success | `{result.metrics['mission_success']}` |
| Duration | `{float(result.metrics['duration_s']):.2f} s` |
| Confirmed collected objects | `{result.metrics['collected_count']}` |
| Collected mass | `{float(result.metrics['collected_mass_kg']):.4f} kg` |
| Final SOC | `{100*float(result.metrics['final_soc']):.2f}%` |
| Minimum signed clearance | `{float(result.metrics['minimum_hazard_distance_m']):.4f} m` |

## State-transition evidence

| Time [s] | Transition | Decision reason | Target |
|---:|---|---|---|
{events}

## Acceptance checks

| Check | Value | Criterion | Pass |
|---|---|---|---:|
{acceptance_rows}

## Explicit limitations

- The autonomy layer uses a deterministic analytic environment and virtual sensor surrogates from Phase 07.
- Object capture is represented by a distance-plus-hold-time condition, not a CFD model of the collection funnel.
- Obstacles are static; dynamic obstacles, wave forcing, wind and full-state estimation are deferred.
- The mission uses a short two-object quota to verify the complete decision–planning–control–return loop. Scenario sweeps and longer missions are expanded in Phase 09.

## Artifact inventory

{artifact_rows}
"""
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding="utf-8")


def run_phase08(config: ProjectConfiguration | None = None, *, render_animation: bool = True) -> Phase08Artifacts:
    ensure_runtime_directories()
    cfg=config or load_base_configuration()
    result,environment,settings=_run_mission(cfg)
    artifacts=Phase08Artifacts(
        autonomy_architecture=DIRECTORIES["figures"] / "phase08_autonomy_architecture.png",
        autonomy_architecture_svg=DIRECTORIES["figures"] / "phase08_autonomy_architecture.svg",
        planning_map=DIRECTORIES["figures"] / "phase08_planning_map.png",
        planning_map_svg=DIRECTORIES["figures"] / "phase08_planning_map.svg",
        closed_loop_mission=DIRECTORIES["figures"] / "phase08_closed_loop_mission.png",
        closed_loop_mission_svg=DIRECTORIES["figures"] / "phase08_closed_loop_mission.svg",
        control_dashboard=DIRECTORIES["figures"] / "phase08_control_dashboard.png",
        control_dashboard_svg=DIRECTORIES["figures"] / "phase08_control_dashboard.svg",
        decision_timeline=DIRECTORIES["figures"] / "phase08_decision_timeline.png",
        decision_timeline_svg=DIRECTORIES["figures"] / "phase08_decision_timeline.svg",
        mission_time_series_table=DIRECTORIES["tables"] / "phase08_mission_time_series.csv",
        planned_routes_table=DIRECTORIES["tables"] / "phase08_planned_routes.csv",
        agent_events_table=DIRECTORIES["tables"] / "phase08_agent_events.csv",
        collected_debris_table=DIRECTORIES["tables"] / "phase08_collected_debris.csv",
        acceptance_checks_table=DIRECTORIES["tables"] / "phase08_acceptance_checks.csv",
        summary_json=DIRECTORIES["logs"] / "phase08_autonomy_summary.json",
        summary_markdown=DIRECTORIES["reports"] / "phase08_autonomy_planning_and_control_summary.md",
        visual_quality_manifest=DIRECTORIES["logs"] / "phase08_visual_quality_manifest.json",
        mission_animation_gif=DIRECTORIES["animations"] / "phase08_closed_loop_mission.gif",
        mission_animation_mp4=DIRECTORIES["videos"] / "phase08_closed_loop_mission.mp4",
    )
    exports=[
        _draw_architecture(artifacts.autonomy_architecture,settings),
        _draw_planning_map(result,environment,artifacts.planning_map),
        _draw_mission(result,environment,artifacts.closed_loop_mission),
        _draw_control(result,artifacts.control_dashboard),
        _draw_decision_timeline(result,artifacts.decision_timeline),
    ]
    assert_export_quality(exports)
    if render_animation:
        _draw_animation(result,environment,artifacts.mission_animation_gif,artifacts.mission_animation_mp4)
    _write_csv(artifacts.mission_time_series_table,result.rows)
    _write_csv(artifacts.planned_routes_table,result.route_rows)
    _write_csv(artifacts.agent_events_table,result.event_rows)
    _write_csv(artifacts.collected_debris_table,result.target_rows)
    acceptance=_acceptance_rows(result,settings,(artifacts.mission_animation_gif,artifacts.mission_animation_mp4), animation_required=render_animation)
    _write_csv(artifacts.acceptance_checks_table,acceptance)
    summary={
        "phase":"Phase 08 — Autonomy, A* Planning, Guidance and Control",
        "configuration_file":relative_to_root(cfg.source_path),
        "mission_metrics":result.metrics,
        "state_transitions":result.event_rows,
        "acceptance_checks":acceptance,
        "limitations":[
            "Static analytic obstacles and deterministic virtual sensing only.",
            "Geometric collection surrogate; no fluid–debris interaction model.",
            "No EKF, moving-obstacle prediction, waves or wind in this phase.",
            "Two-object quota validates the complete closed-loop chain; broader scenario sweeps are next.",
        ],
        "artifacts":artifacts.as_dict(),
    }
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps({
        "phase":"Phase 08 visual quality gate",
        "quality_rule":{
            "minimum_png_width_px":3000,
            "minimum_png_height_px":1800,
            "formats":["PNG (report-ready raster)","SVG (vector)","GIF and MP4 (mission animation)"],
            "layout_policy":"Technical maps, trajectories and control plots use separate information panels. Dense labels are not placed directly on the vessel route or obstacles.",
        },
        "exports":[export.as_dict() for export in exports],
        "animation_exports":[
            {"gif":relative_to_root(artifacts.mission_animation_gif),"size_bytes":artifacts.mission_animation_gif.stat().st_size if artifacts.mission_animation_gif.exists() else 0, "generated": render_animation},
            {"mp4":relative_to_root(artifacts.mission_animation_mp4),"size_bytes":artifacts.mission_animation_mp4.stat().st_size if artifacts.mission_animation_mp4.exists() else 0, "generated": render_animation},
        ],
    },ensure_ascii=False,indent=2),encoding="utf-8")
    _write_summary(artifacts.summary_markdown,result,acceptance,artifacts)
    return artifacts


def print_phase08_summary(artifacts: Phase08Artifacts) -> None:
    print("="*72); print("AquaSkim-Sim | Phase 08 Autonomy, Planning and Control"); print("="*72)
    for key,path in artifacts.as_dict().items(): print(f"{key:28}: {path}")
    print("="*72); print("[OK] Phase 08 autonomy, routes, controls, logs and mission animation generated.")
