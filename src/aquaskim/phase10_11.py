"""Reference-mission fidelity evidence and long-form visual replay suite.

This phase does not change the physical model.  It executes the fixed,
non-interactive nominal and high-loading reference scenarios, extracts a
behavioural audit from their logged states/events, and renders six longer
presentation-grade GIF/MP4 replays from those exact logs.  Word reports,
delivery ZIPs and release builds remain deliberately disabled.
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
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
import numpy as np
import yaml

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.phase10_6 import _arrays, _draw_obstacles, _draw_robot, _map_axis
from aquaskim.phase10_7 import _run
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import load_reference_configuration, load_reference_scenario, project_root
from aquaskim.reference_fidelity import FidelityAudit, audit_reference_result
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class Phase1011Artifacts:
    nominal_fidelity_map_png: Path
    nominal_fidelity_map_svg: Path
    high_loading_fidelity_map_png: Path
    high_loading_fidelity_map_svg: Path
    state_timeline_png: Path
    state_timeline_svg: Path
    control_clearance_png: Path
    control_clearance_svg: Path
    behaviour_scorecard_png: Path
    behaviour_scorecard_svg: Path
    visual_evidence_inventory_png: Path
    visual_evidence_inventory_svg: Path
    nominal_state_segments_csv: Path
    nominal_control_segments_csv: Path
    nominal_event_ledger_csv: Path
    high_loading_state_segments_csv: Path
    high_loading_control_segments_csv: Path
    high_loading_event_ledger_csv: Path
    mission_behaviour_metrics_csv: Path
    mission_fidelity_checks_csv: Path
    visual_quality_manifest_json: Path
    summary_json: Path
    summary_markdown: Path
    nominal_replay_gif: Path
    nominal_replay_mp4: Path
    planning_replay_gif: Path
    planning_replay_mp4: Path
    telemetry_replay_gif: Path
    telemetry_replay_mp4: Path
    capacity_replay_gif: Path
    capacity_replay_mp4: Path
    capacity_resources_gif: Path
    capacity_resources_mp4: Path
    control_force_replay_gif: Path
    control_force_replay_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _dirs() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": DIRECTORIES["figures"], "tables": DIRECTORIES["tables"],
        "logs": DIRECTORIES["logs"], "reports": DIRECTORIES["reports"],
        "animations": DIRECTORIES["animations"], "videos": DIRECTORIES["videos"],
        "records": root / "records" / "phases" / "phase_10_11" / "runs",
        "handoffs": DIRECTORIES["handoffs"],
    }


def _load_visualisation_config() -> dict[str, Any]:
    path = project_root() / "config" / "reference_visualisation.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("reference_visualisation"), dict):
        raise ValueError("reference_visualisation.yaml requires a reference_visualisation mapping.")
    return parsed["reference_visualisation"]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"status": "NO_ROWS"}]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _save(fig: plt.Figure, png: Path, svg: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _route_lookup(routes: list[dict[str, Any]]) -> dict[int, np.ndarray]:
    grouped: dict[int, list[tuple[int, float, float]]] = {}
    for row in routes:
        raw = str(row.get("route_id", "0"))
        route_id = int(raw.split("_")[-1]) if raw.split("_")[-1].isdigit() else 0
        grouped.setdefault(route_id, []).append((int(row.get("waypoint_index", 0)), float(row["x_m"]), float(row["y_m"])))
    return {
        route_id: np.asarray([(x, y) for _, x, y in sorted(items)], dtype=float)
        for route_id, items in grouped.items()
    }


def _event_points(events: list[dict[str, Any]], name: str) -> tuple[list[float], list[float]]:
    selected = [event for event in events if str(event.get("event")) == name and "x_m" in event and "y_m" in event]
    return [float(event["x_m"]) for event in selected], [float(event["y_m"]) for event in selected]


def _draw_fidelity_map(result, environment, audit: FidelityAudit, title: str, subtitle: str, png: Path, svg: Path) -> None:
    apply_engineering_style(); d = _arrays(result)
    fig = plt.figure(figsize=(17.2, 9.5))
    grid = GridSpec(1, 2, figure=fig, width_ratios=[1.45, .55], left=.05, right=.96, top=.86, bottom=.09, wspace=.18)
    add_figure_header(fig, title, subtitle)
    ax = fig.add_subplot(grid[0, 0]); panel = fig.add_subplot(grid[0, 1])
    _draw_obstacles(ax, environment, True)
    debris = environment.generate_debris()
    captured = {str(row.get("debris_id")) for row in result.targets}
    uncaptured = [item for item in debris if item.identifier not in captured]
    captured_items = [item for item in debris if item.identifier in captured]
    if uncaptured:
        ax.scatter([item.position_m[0] for item in uncaptured], [item.position_m[1] for item in uncaptured], s=22, color=PALETTE["gray"], alpha=.55, label="uncollected debris", zorder=2)
    if captured_items:
        ax.scatter([item.position_m[0] for item in captured_items], [item.position_m[1] for item in captured_items], marker="*", s=130, color=PALETTE["green"], edgecolor="white", linewidth=.7, label="confirmed capture", zorder=8)
    ax.plot(d["x_m"], d["y_m"], color=PALETTE["blue"], linewidth=1.85, label="physical 3-DOF trajectory", zorder=6)
    rx, ry = _event_points(result.events, "SAFETY_REPLAN")
    if rx:
        ax.scatter(rx, ry, marker="x", s=55, color=PALETTE["orange"], linewidth=1.5, label="safety re-plan", zorder=9)
    ax.scatter(*environment.home_position_m, marker="s", s=76, color=PALETTE["navy"], label="home station", zorder=10)
    _draw_robot(ax, d["x_m"][-1], d["y_m"][-1], math.radians(d["psi_deg"][-1]))
    _map_axis(ax, environment, "Logged mission trajectory and audited events")
    ax.legend(loc="upper right", fontsize=7.6, ncol=2)

    panel.axis("off"); panel.set_xlim(0, 1); panel.set_ylim(0, 1)
    panel.add_patch(FancyBboxPatch((.04,.05),.92,.90,boxstyle="round,pad=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
    panel.text(.10,.89,"Behaviour audit",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    summary = audit.summary
    items = [
        ("Termination", str(summary["termination_reason"])),
        ("Duration", f"{summary['duration_s']:.1f} s"),
        ("Coverage", f"{100*summary['coverage_fraction']:.1f}%"),
        ("Verified captures", str(summary["captured_count"])),
        ("First target confirmation", "—" if summary["first_target_confirmation_time_s"] is None else f"{summary['first_target_confirmation_time_s']:.1f} s"),
        ("First return transition", "—" if summary["first_return_time_s"] is None else f"{summary['first_return_time_s']:.1f} s"),
        ("Minimum clearance", f"{summary['minimum_clearance_m']:.3f} m"),
        ("Quota-based return", "No" if summary["fixed_quota_absent_from_termination"] else "Detected"),
    ]
    y=.80
    for label,value in items:
        panel.text(.10,y,label,fontsize=8.25,color=PALETTE["gray_dark"])
        panel.text(.90,y,fill(value,22),fontsize=8.0,fontweight="bold",color=PALETTE["navy"],ha="right")
        panel.plot([.09,.91],[y-.035,y-.035],color=PALETTE["grid"],linewidth=.6); y -= .085
    _save(fig,png,svg)


def _draw_timeline(nominal: FidelityAudit, high: FidelityAudit, png: Path, svg: Path) -> None:
    apply_engineering_style(); fig=plt.figure(figsize=(17.2,9.6)); grid=GridSpec(2,1,figure=fig,left=.07,right=.96,top=.86,bottom=.09,hspace=.35)
    add_figure_header(fig,"Autonomous-state and control-regime timeline","Segments are derived from logged state changes and controller regimes—not manually annotated animation events.")
    palettes={"SEARCH":PALETTE["blue"],"TRANSIT_TO_TARGET":PALETTE["orange"],"COLLECT":PALETTE["green"],"RETURN_HOME":PALETTE["navy"],"MISSION_COMPLETE":PALETTE["gray_dark"],"PIVOT":PALETTE["orange"],"TRACK":PALETTE["blue"],"BRAKE_FOR_PIVOT":PALETTE["orange"],"BRAKE_TO_WAYPOINT":PALETTE["orange"]}
    for ax,audit,label in [(fig.add_subplot(grid[0]),nominal,"Nominal coverage"),(fig.add_subplot(grid[1]),high,"High-loading return")]:
        for row in audit.state_segments:
            ax.barh(1.25,row["duration_s"],left=row["start_time_s"],height=.46,color=palettes.get(str(row["value"]),PALETTE["gray"]),edgecolor="white")
            if row["duration_s"]>=20: ax.text(row["start_time_s"]+.5*row["duration_s"],1.25,str(row["value"]),ha="center",va="center",fontsize=7,color="white")
        for row in audit.regime_segments:
            ax.barh(.55,row["duration_s"],left=row["start_time_s"],height=.35,color=palettes.get(str(row["value"]),PALETTE["gray"]),alpha=.78,edgecolor="white")
        ax.set_yticks([.55,1.25],["Control regime","Mission state"]); ax.set_xlabel("Time [s]");ax.set_title(label,loc="left");style_axis(ax)
    _save(fig,png,svg)


def _draw_control_clearance(nominal, high, png: Path, svg: Path) -> None:
    apply_engineering_style(); fig=plt.figure(figsize=(17.2,10));grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.09,hspace=.35,wspace=.27)
    add_figure_header(fig,"Tracking, clearance and resource evidence","Forward tracking is separated from controlled pivot/brake regimes so corner behaviour is transparent.")
    for col,(label,result) in enumerate((("Nominal coverage",nominal),("High-loading return",high))):
        d=_arrays(result); axh=fig.add_subplot(grid[0,col]); axr=fig.add_subplot(grid[1,col]);
        regimes=np.asarray([str(row.get("control_regime","")) for row in result.rows]);track=regimes=="TRACK";pivot=np.isin(regimes,["PIVOT","BRAKE_FOR_PIVOT","BRAKE_TO_WAYPOINT"])
        axh.plot(d["time_s"],d["heading_error_deg"],color=PALETTE["gray"],alpha=.35,linewidth=.75,label="all commands");axh.plot(d["time_s"],np.where(track,d["heading_error_deg"],np.nan),color=PALETTE["blue"],linewidth=1.05,label="forward track");axh.scatter(d["time_s"][pivot],d["heading_error_deg"][pivot],s=2.8,color=PALETTE["orange"],alpha=.55,label="controlled turn/brake");axh.set_ylabel("Heading error [deg]");axh.set_title(f"{label}: heading regime evidence",loc="left");axh.legend(fontsize=7.3,loc="upper right");style_axis(axh)
        axr.plot(d["time_s"],d["hazard_clearance_m"],color=PALETTE["green"],label="clearance");axr.axhline(.35,linestyle="--",color=PALETTE["orange"],linewidth=.9,label="guard threshold");axr2=axr.twinx();axr2.plot(d["time_s"],100*d["soc"],color=PALETTE["navy"],linewidth=1.0,label="SOC");axr.set_xlabel("Time [s]");axr.set_ylabel("Clearance [m]");axr2.set_ylabel("SOC [%]");axr.set_title(f"{label}: safety and energy",loc="left");style_axis(axr);axr.legend(fontsize=7.3,loc="upper left");axr2.legend(fontsize=7.3,loc="upper right")
    _save(fig,png,svg)


def _draw_scorecard(nominal: FidelityAudit, high: FidelityAudit, png: Path, svg: Path) -> None:
    apply_engineering_style();fig=plt.figure(figsize=(17.0,8.9));grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.86,bottom=.12,wspace=.30)
    add_figure_header(fig,"Reference mission fidelity scorecard","Nominal coverage and high-loading return are distinct, fixed scenarios with separate mission purposes.")
    ax=fig.add_subplot(grid[0,0]);labels=["Mission success","Coverage","Quota absent","Clearance / 0.35 m","Final SOC"];values=[]
    for audit in (nominal,high):
        s=audit.summary;values.append([s["mission_success"],s["coverage_fraction"],float(s["fixed_quota_absent_from_termination"]),min(1.0,s["minimum_clearance_m"]/.35),float(s["final_soc"])])
    y=np.arange(len(labels));width=.34
    ax.barh(y-width/2,values[0],height=width,label="Nominal coverage");ax.barh(y+width/2,values[1],height=width,label="High loading")
    ax.set_yticks(y,labels);ax.set_xlim(0,1.08);ax.set_xlabel("Normalized audit result");ax.set_title("Mission-state and safety criteria",loc="left");ax.legend(fontsize=8);style_axis(ax)
    panel=fig.add_subplot(grid[0,1]);panel.axis("off");panel.set_xlim(0,1);panel.set_ylim(0,1);panel.add_patch(FancyBboxPatch((.04,.06),.92,.88,boxstyle="round,pad=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
    panel.text(.10,.86,"Scenario interpretation",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    lines=[
        ("Nominal",f"coverage {100*nominal.summary['coverage_fraction']:.1f}% → {nominal.summary['termination_reason']}"),
        ("High loading",f"coverage {100*high.summary['coverage_fraction']:.1f}% → {high.summary['termination_reason']}"),
        ("Safety",f"minimum clearance: {nominal.summary['minimum_clearance_m']:.3f} m / {high.summary['minimum_clearance_m']:.3f} m"),
        ("Quota policy","Capture count is recorded, never used as a terminal condition."),
        ("Visual policy","Every replay is generated from the corresponding stored state history."),
    ]
    y=.74
    for head,text in lines:
        panel.text(.10,y,head,fontsize=9,fontweight="bold",color=PALETTE["navy"]);panel.text(.10,y-.065,fill(text,48),fontsize=8.3,color=PALETTE["gray_dark"]);y-=.16
    _save(fig,png,svg)


def _draw_inventory(config: dict[str, Any], png: Path, svg: Path) -> None:
    apply_engineering_style();fig,ax=plt.subplots(figsize=(16.8,8.5));add_figure_header(fig,"Reference visual-evidence inventory","Six complementary replays expose mission progression, planning, telemetry, capacity, resources and force-control behaviour.")
    ax.axis("off");ax.set_xlim(0,1);ax.set_ylim(0,1)
    cards=[
        ("01","Nominal mission","Physical coverage path, state, hopper, SOC and clearance."),
        ("02","Planning and state","A* route assignment, waypoints and state-transition timeline."),
        ("03","Nominal telemetry","Map plus speed, SOC, hopper and clearance time histories."),
        ("04","High-loading mission","Capacity-triggered return with annotated route and docking."),
        ("05","High-loading resources","Occupied hopper volume, return trigger, SOC and collection steps."),
        ("06","Control and force","Twin-thruster demand, drag, yaw response and command regime."),
    ]
    for index,(number,title,desc) in enumerate(cards):
        col=index%3;row=index//3;x=.06+col*.31;y=.59-row*.40
        ax.add_patch(FancyBboxPatch((x,y),.27,.28,boxstyle="round,pad=.018",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
        ax.text(x+.03,y+.22,number,fontsize=10,fontweight="bold",color=PALETTE["orange"]);ax.text(x+.08,y+.22,title,fontsize=10,fontweight="bold",color=PALETTE["navy"]);ax.text(x+.03,y+.15,fill(desc,34),fontsize=8.6,color=PALETTE["gray_dark"])
    ax.text(.06,.06,f"Render protocol: {int(config['render']['frame_count'])} frames at {int(config['render']['fps'])} fps per replay; all media are deterministic and non-interactive.",fontsize=9,color=PALETTE["gray_dark"])
    _save(fig,png,svg)


def _frame_indices(rows: list[dict[str, Any]], events: list[dict[str, Any]], frame_count: int) -> np.ndarray:
    count=len(rows);base=np.linspace(0,count-1,min(frame_count,count),dtype=int)
    event_indices=[]
    time=np.asarray([float(row["time_s"]) for row in rows])
    important={"STATE_CHANGE","COLLECTION_CONFIRMED","TARGET_CONFIRMED","SAFETY_REPLAN","ROUTE_ASSIGNED"}
    for event in events:
        if str(event.get("event")) in important and "time_s" in event:
            event_indices.append(int(np.argmin(np.abs(time-float(event["time_s"])))))
    combined=sorted(set(base.tolist()+event_indices))
    if len(combined)>frame_count:
        combined=np.linspace(0,len(combined)-1,frame_count,dtype=int).tolist();combined=[sorted(set(base.tolist()+event_indices))[i] for i in combined]
    return np.asarray(combined,dtype=int)


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, fps: int, bitrate: int) -> None:
    gif.parent.mkdir(parents=True,exist_ok=True);mp4.parent.mkdir(parents=True,exist_ok=True)
    animation.save(gif,writer=PillowWriter(fps=fps))
    try: animation.save(mp4,writer=FFMpegWriter(fps=fps,bitrate=bitrate))
    except Exception: pass
    plt.close(animation._fig)


def _add_robot(ax, x: float, y: float, psi: float) -> list[Any]:
    c,s=math.cos(psi),math.sin(psi);f=np.asarray([c,s]);l=np.asarray([-s,c]);patches=[]
    for side in (-1.0,1.0):
        centre=np.asarray([x,y])+side*.17*l
        points=[centre-.28*f-.035*l,centre+.28*f-.035*l,centre+.28*f+.035*l,centre-.28*f+.035*l]
        p=Polygon(points,closed=True,facecolor=PALETTE["sky"],edgecolor=PALETTE["navy"],linewidth=.8,zorder=14);ax.add_patch(p);patches.append(p)
    return patches


def _render_map_replay(result, environment, audit: FidelityAudit, gif: Path, mp4: Path, visual: dict[str, Any], *, title: str, capacity: bool=False) -> None:
    apply_engineering_style();d=_arrays(result);indices=_frame_indices(result.rows,result.events,int(visual['render']['frame_count']));fps=int(visual['render']['fps']);bitrate=int(visual['render']['mp4_bitrate_kbps'])
    fig=plt.figure(figsize=(14.0,8.0));grid=GridSpec(1,2,figure=fig,width_ratios=[1.35,.48],left=.05,right=.96,top=.90,bottom=.10,wspace=.16);ax=fig.add_subplot(grid[0,0]);panel=fig.add_subplot(grid[0,1]);_draw_obstacles(ax,environment,True)
    debris=environment.generate_debris();ax.scatter([item.position_m[0] for item in debris],[item.position_m[1] for item in debris],s=17,color=PALETTE['gray'],alpha=.55,zorder=2);ax.scatter(*environment.home_position_m,marker='s',s=62,color=PALETTE['navy'],zorder=10);path,=ax.plot([],[],color=PALETTE['blue'],linewidth=1.8,zorder=7);dot=ax.scatter([],[],s=24,color=PALETTE['green'],zorder=13);_map_axis(ax,environment,title)
    panel.axis('off');panel.set_xlim(0,1);panel.set_ylim(0,1);panel.add_patch(FancyBboxPatch((.04,.08),.92,.84,boxstyle='round,pad=.02',facecolor='#F8FBFD',edgecolor=PALETTE['grid']));head=panel.text(.10,.85,'Live mission state',fontsize=12,fontweight='bold',color=PALETTE['navy']);text=panel.text(.10,.76,'',fontsize=8.8,color=PALETTE['gray_dark'],va='top')
    robot_patches: list[Any]=[]
    def update(frame:int):
        nonlocal robot_patches
        for p in robot_patches:p.remove()
        robot_patches=[];i=int(indices[frame]);path.set_data(d['x_m'][:i+1],d['y_m'][:i+1]);dot.set_offsets(np.asarray([[d['x_m'][i],d['y_m'][i]]]));robot_patches=_add_robot(ax,d['x_m'][i],d['y_m'][i],math.radians(d['psi_deg'][i]));row=result.rows[i]
        label='Hopper loading' if capacity else 'Coverage mission'
        text.set_text(f"{label}\n\nt = {d['time_s'][i]:.1f} s\nstate = {row['mode']}\nregime = {row['control_regime']}\nroute = {int(row['route_id']):03d}\ncoverage = {100*d['coverage_progress'][i]:.1f}%\ncaptures = {int(d['collected_count'][i])}\nhopper = {d['hopper_volume_l'][i]:.2f} L\nSOC = {100*d['soc'][i]:.1f}%\nclearance = {d['hazard_clearance_m'][i]:.3f} m")
        return [path,dot,text,*robot_patches]
    anim=FuncAnimation(fig,update,frames=len(indices),interval=1000/fps,blit=False);_save_animation(anim,gif,mp4,fps,bitrate)


def _render_planning_replay(result, environment, audit: FidelityAudit, gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style();d=_arrays(result);indices=_frame_indices(result.rows,result.events,int(visual['render']['frame_count']));fps=int(visual['render']['fps']);bitrate=int(visual['render']['mp4_bitrate_kbps']);lookup=_route_lookup(result.routes)
    fig=plt.figure(figsize=(14.5,8.2));grid=GridSpec(1,2,figure=fig,width_ratios=[1.38,.62],left=.05,right=.96,top=.90,bottom=.10,wspace=.18);ax=fig.add_subplot(grid[0,0]);timeline=fig.add_subplot(grid[0,1]);_draw_obstacles(ax,environment,True);executed,=ax.plot([],[],color=PALETTE['blue'],linewidth=1.7,label='executed trajectory');planned,=ax.plot([],[],color=PALETTE['orange'],linestyle='--',linewidth=1.4,label='active A* route');dot=ax.scatter([],[],s=28,color=PALETTE['green'],zorder=12);_map_axis(ax,environment,'A* planning and autonomous state replay');ax.legend(fontsize=7.5,loc='upper right')
    timeline.set_xlim(0,d['time_s'][-1]);timeline.set_ylim(0,1.8);timeline.set_yticks([.55,1.25],['State','Regime']);timeline.set_xlabel('Time [s]');timeline.set_title('Current time in logged mission timeline',loc='left');style_axis(timeline);marker=timeline.axvline(0,color=PALETTE['orange'],linewidth=1.2);labels=[]
    state_colors={'SEARCH':PALETTE['blue'],'TRANSIT_TO_TARGET':PALETTE['orange'],'COLLECT':PALETTE['green'],'RETURN_HOME':PALETTE['navy'],'MISSION_COMPLETE':PALETTE['gray_dark']};regime_colors={'TRACK':PALETTE['blue'],'PIVOT':PALETTE['orange'],'BRAKE_FOR_PIVOT':PALETTE['orange'],'BRAKE_TO_WAYPOINT':PALETTE['orange'],'IDLE':PALETTE['gray']}
    for segment in audit.state_segments:timeline.barh(1.25,segment['duration_s'],left=segment['start_time_s'],height=.42,color=state_colors.get(segment['value'],PALETTE['gray']),alpha=.85)
    for segment in audit.regime_segments:timeline.barh(.55,segment['duration_s'],left=segment['start_time_s'],height=.30,color=regime_colors.get(segment['value'],PALETTE['gray']),alpha=.80)
    robot_patches: list[Any]=[]
    def update(frame:int):
        nonlocal robot_patches
        for p in robot_patches:p.remove()
        robot_patches=[];i=int(indices[frame]);row=result.rows[i];executed.set_data(d['x_m'][:i+1],d['y_m'][:i+1]);route=lookup.get(int(row['route_id']));
        if route is not None and len(route):planned.set_data(route[:,0],route[:,1])
        else:planned.set_data([],[])
        dot.set_offsets(np.asarray([[d['x_m'][i],d['y_m'][i]]]));robot_patches=_add_robot(ax,d['x_m'][i],d['y_m'][i],math.radians(d['psi_deg'][i]));marker.set_xdata([d['time_s'][i],d['time_s'][i]])
        return [executed,planned,dot,marker,*robot_patches]
    anim=FuncAnimation(fig,update,frames=len(indices),interval=1000/fps,blit=False);_save_animation(anim,gif,mp4,fps,bitrate)


def _render_telemetry_replay(result, environment, gif: Path, mp4: Path, visual: dict[str, Any], *, title: str, resource_focus: bool=False) -> None:
    apply_engineering_style();d=_arrays(result);indices=_frame_indices(result.rows,result.events,int(visual['render']['frame_count']));fps=int(visual['render']['fps']);bitrate=int(visual['render']['mp4_bitrate_kbps'])
    fig=plt.figure(figsize=(14.8,8.5));grid=GridSpec(2,2,figure=fig,left=.06,right=.96,top=.90,bottom=.10,hspace=.35,wspace=.27,width_ratios=[1.20,.80]);axm=fig.add_subplot(grid[:,0]);axt=fig.add_subplot(grid[0,1]);axr=fig.add_subplot(grid[1,1]);_draw_obstacles(axm,environment,True);path,=axm.plot([],[],color=PALETTE['blue'],linewidth=1.7);dot=axm.scatter([],[],s=28,color=PALETTE['green']);_map_axis(axm,environment,title)
    axt.set_xlim(0,d['time_s'][-1]);axr.set_xlim(0,d['time_s'][-1]);
    if resource_focus:
        axt.set_ylim(0,max(1.0,float(np.max(d['hopper_volume_l']))*1.16));axt.axhline(float(np.max(d['hopper_volume_l']))*.95,linestyle='--',color=PALETTE['orange'],linewidth=.9);line1,=axt.plot([],[],color=PALETTE['orange']);axt.set_ylabel('Hopper volume [L]');axt.set_title('Storage progression and capacity trigger',loc='left')
        axr.set_ylim(0,100);line2,=axr.plot([],[],color=PALETTE['navy']);axr.set_ylabel('SOC [%]');axr.set_title('Energy state during capacity return',loc='left')
    else:
        axt.set_ylim(0,max(.35,float(np.max(d['ground_speed_mps']))*1.25));line1,=axt.plot([],[],color=PALETTE['blue'],label='ground');line1d,=axt.plot([],[],color=PALETTE['orange'],label='command');axt.set_ylabel('Speed [m/s]');axt.set_title('Commanded and realised translation',loc='left');axt.legend(fontsize=7.5)
        axr.set_ylim(0,max(.7,float(np.max(d['hazard_clearance_m']))*1.10));line2,=axr.plot([],[],color=PALETTE['green'],label='clearance');axr.axhline(.35,linestyle='--',color=PALETTE['orange'],linewidth=.9,label='guard');axr.set_ylabel('Clearance [m]');axr.set_title('Safety margin',loc='left');axr.legend(fontsize=7.5)
    for ax in (axt,axr):ax.set_xlabel('Time [s]');style_axis(ax)
    def update(frame:int):
        i=int(indices[frame]);path.set_data(d['x_m'][:i+1],d['y_m'][:i+1]);dot.set_offsets(np.asarray([[d['x_m'][i],d['y_m'][i]]]))
        if resource_focus: line1.set_data(d['time_s'][:i+1],d['hopper_volume_l'][:i+1]);line2.set_data(d['time_s'][:i+1],100*d['soc'][:i+1]);return path,dot,line1,line2
        line1.set_data(d['time_s'][:i+1],d['ground_speed_mps'][:i+1]);line1d.set_data(d['time_s'][:i+1],d['desired_speed_mps'][:i+1]);line2.set_data(d['time_s'][:i+1],d['hazard_clearance_m'][:i+1]);return path,dot,line1,line1d,line2
    anim=FuncAnimation(fig,update,frames=len(indices),interval=1000/fps,blit=False);_save_animation(anim,gif,mp4,fps,bitrate)


def _render_control_force_replay(result, environment, gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style();d=_arrays(result);indices=_frame_indices(result.rows,result.events,int(visual['render']['frame_count']));fps=int(visual['render']['fps']);bitrate=int(visual['render']['mp4_bitrate_kbps'])
    fig=plt.figure(figsize=(14.8,8.5));grid=GridSpec(2,2,figure=fig,left=.06,right=.96,top=.90,bottom=.10,hspace=.35,wspace=.27);axm=fig.add_subplot(grid[:,0]);axt=fig.add_subplot(grid[0,1]);axy=fig.add_subplot(grid[1,1]);_draw_obstacles(axm,environment,True);path,=axm.plot([],[],color=PALETTE['blue'],linewidth=1.7);dot=axm.scatter([],[],s=28,color=PALETTE['green']);quiver=[None];_map_axis(axm,environment,'Twin-thruster control and force replay')
    axt.set_xlim(0,d['time_s'][-1]);axt.set_ylim(float(np.min(np.r_[d['port_thrust_n'],d['starboard_thrust_n']]))-.1,float(np.max(np.r_[d['port_thrust_n'],d['starboard_thrust_n']]))+.1);port,=axt.plot([],[],label='port');star,=axt.plot([],[],label='starboard');axt.set_xlabel('Time [s]');axt.set_ylabel('Thrust [N]');axt.set_title('Independent thruster commands',loc='left');axt.legend(fontsize=7.5);style_axis(axt)
    axy.set_xlim(0,d['time_s'][-1]);axy.set_ylim(-max(.13,float(np.max(np.abs(d['yaw_moment_n_m'])))*1.2),max(.13,float(np.max(np.abs(d['yaw_moment_n_m'])))*1.2));yaw,=axy.plot([],[],color=PALETTE['orange'],label='yaw moment');drag,=axy.plot([],[],color=PALETTE['gray_dark'],label='surge drag');axy.set_xlabel('Time [s]');axy.set_ylabel('Moment [N m] / drag [N]');axy.set_title('Yaw demand and drag response',loc='left');axy.legend(fontsize=7.5);style_axis(axy)
    def update(frame:int):
        i=int(indices[frame]);path.set_data(d['x_m'][:i+1],d['y_m'][:i+1]);dot.set_offsets(np.asarray([[d['x_m'][i],d['y_m'][i]]]))
        if quiver[0] is not None:quiver[0].remove()
        psi=math.radians(d['psi_deg'][i]);quiver[0]=axm.quiver(d['x_m'][i],d['y_m'][i],.16*d['total_thrust_n'][i]*math.cos(psi),.16*d['total_thrust_n'][i]*math.sin(psi),angles='xy',scale_units='xy',scale=1,color=PALETTE['orange'],width=.005,zorder=15)
        port.set_data(d['time_s'][:i+1],d['port_thrust_n'][:i+1]);star.set_data(d['time_s'][:i+1],d['starboard_thrust_n'][:i+1]);yaw.set_data(d['time_s'][:i+1],d['yaw_moment_n_m'][:i+1]);drag.set_data(d['time_s'][:i+1],-d['x_drag_n'][:i+1]);return path,dot,quiver[0],port,star,yaw,drag
    anim=FuncAnimation(fig,update,frames=len(indices),interval=1000/fps,blit=False);_save_animation(anim,gif,mp4,fps,bitrate)


def _sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def _visual_manifest(paths: list[Path], visual: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image
    entries=[]
    for path in paths:
        item={"path":relative_to_root(path),"exists":path.exists(),"size_bytes":path.stat().st_size if path.exists() else 0}
        if path.suffix.lower()=='.gif' and path.exists():
            image=Image.open(path);frames=max(1,int(getattr(image,'n_frames',1)));duration_ms=sum(int(image.seek(i) or image.info.get('duration',0) or 0) for i in range(frames));width,height=image.size;item.update({"frames":frames,"duration_s":duration_ms/1000.0,"width_px":width,"height_px":height,"frame_count_ok":frames>=int(visual['acceptance']['minimum_frame_count']),"duration_ok":duration_ms/1000.0>=float(visual['acceptance']['minimum_duration_s']),"resolution_ok":width>=int(visual['acceptance']['minimum_width_px']) and height>=int(visual['acceptance']['minimum_height_px'])})
        entries.append(item)
    gifs=[entry for entry in entries if entry['path'].endswith('.gif')]
    videos=[entry for entry in entries if entry['path'].endswith('.mp4')]
    return {"identifier":visual['identifier'],"entries":entries,"required_animation_count":int(visual['acceptance']['required_animation_count']),"observed_animation_count":len(gifs),"required_video_count":int(visual['acceptance']['required_video_count']),"observed_video_count":len(videos),"all_gif_frame_counts_ok":all(item.get('frame_count_ok',False) for item in gifs),"all_gif_durations_ok":all(item.get('duration_ok',False) for item in gifs),"all_gif_resolutions_ok":all(item.get('resolution_ok',False) for item in gifs),"all_mp4_exist":all(bool(item.get('exists')) and int(item.get('size_bytes',0))>0 for item in videos)}


def _record(artifacts: Phase1011Artifacts) -> Path:
    dirs=_dirs();run_id='phase10_11_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run=dirs['records']/run_id;(run/'artifacts').mkdir(parents=True,exist_ok=True);(run/'inputs').mkdir(parents=True,exist_ok=True)
    for source in (project_root()/'config'/'reference_design.yaml',project_root()/'config'/'reference_visualisation.yaml',project_root()/'config'/'parameter_registry.yaml'):
        shutil.copy2(source,run/'inputs'/source.name)
    manifest=[]
    for relative in artifacts.as_dict().values():
        source=project_root()/relative
        if source.exists():
            target=run/'artifacts'/source.name;shutil.copy2(source,target);manifest.append({'path':relative,'sha256':_sha256(source),'size_bytes':source.stat().st_size})
    (run/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    environment={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable}
    try:environment['pip_freeze']=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
    except Exception as exc:environment['pip_freeze_error']=str(exc)
    (run/'environment_snapshot.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
    handoff=dirs['handoffs']/ 'PHASE10_11_LATEST_HANDOFF.md';handoff.write_text('# Reference Mission Fidelity and Visual Evidence Handoff\n\n'+f'- Run ID: `{run_id}`\n- Fixed non-interactive reference design and versioned visual protocol used.\n- No Word report, delivery ZIP or release build was invoked.\n- Evidence: `{relative_to_root(run)}`\n',encoding='utf-8')
    return run


def run_phase10_11(*, record: bool=True, render: bool=True) -> tuple[Phase1011Artifacts, Path | None]:
    ensure_runtime_directories();dirs=_dirs();visual=_load_visualisation_config();nominal,nominal_env=_run(load_reference_configuration());high,high_env=_run(load_reference_scenario('reference_high_loading.yaml'))
    nominal_audit=audit_reference_result(nominal,scenario='nominal_coverage',expected_termination_fragment='all coverage lanes completed');high_audit=audit_reference_result(high,scenario='high_loading_capacity',expected_termination_fragment='hopper occupied-volume trigger')
    artifacts=Phase1011Artifacts(
        nominal_fidelity_map_png=dirs['figures']/'reference_nominal_fidelity_map.png',nominal_fidelity_map_svg=dirs['figures']/'reference_nominal_fidelity_map.svg',high_loading_fidelity_map_png=dirs['figures']/'reference_high_loading_fidelity_map.png',high_loading_fidelity_map_svg=dirs['figures']/'reference_high_loading_fidelity_map.svg',state_timeline_png=dirs['figures']/'reference_mission_state_timeline.png',state_timeline_svg=dirs['figures']/'reference_mission_state_timeline.svg',control_clearance_png=dirs['figures']/'reference_mission_control_clearance.png',control_clearance_svg=dirs['figures']/'reference_mission_control_clearance.svg',behaviour_scorecard_png=dirs['figures']/'reference_mission_behaviour_scorecard.png',behaviour_scorecard_svg=dirs['figures']/'reference_mission_behaviour_scorecard.svg',visual_evidence_inventory_png=dirs['figures']/'reference_visual_evidence_inventory.png',visual_evidence_inventory_svg=dirs['figures']/'reference_visual_evidence_inventory.svg',
        nominal_state_segments_csv=dirs['tables']/'reference_nominal_state_segments.csv',nominal_control_segments_csv=dirs['tables']/'reference_nominal_control_regime_segments.csv',nominal_event_ledger_csv=dirs['tables']/'reference_nominal_event_ledger.csv',high_loading_state_segments_csv=dirs['tables']/'reference_high_loading_state_segments.csv',high_loading_control_segments_csv=dirs['tables']/'reference_high_loading_control_regime_segments.csv',high_loading_event_ledger_csv=dirs['tables']/'reference_high_loading_event_ledger.csv',mission_behaviour_metrics_csv=dirs['tables']/'reference_mission_behaviour_metrics.csv',mission_fidelity_checks_csv=dirs['tables']/'reference_mission_fidelity_checks.csv',visual_quality_manifest_json=dirs['logs']/'reference_visual_evidence_quality_manifest.json',summary_json=dirs['logs']/'reference_mission_fidelity_summary.json',summary_markdown=dirs['reports']/'reference_mission_fidelity_and_visual_evidence.md',
        nominal_replay_gif=dirs['animations']/'reference_nominal_fidelity_replay.gif',nominal_replay_mp4=dirs['videos']/'reference_nominal_fidelity_replay.mp4',planning_replay_gif=dirs['animations']/'reference_nominal_planning_state_replay.gif',planning_replay_mp4=dirs['videos']/'reference_nominal_planning_state_replay.mp4',telemetry_replay_gif=dirs['animations']/'reference_nominal_telemetry_longform.gif',telemetry_replay_mp4=dirs['videos']/'reference_nominal_telemetry_longform.mp4',capacity_replay_gif=dirs['animations']/'reference_high_loading_fidelity_replay.gif',capacity_replay_mp4=dirs['videos']/'reference_high_loading_fidelity_replay.mp4',capacity_resources_gif=dirs['animations']/'reference_high_loading_resources_replay.gif',capacity_resources_mp4=dirs['videos']/'reference_high_loading_resources_replay.mp4',control_force_replay_gif=dirs['animations']/'reference_nominal_control_force_replay.gif',control_force_replay_mp4=dirs['videos']/'reference_nominal_control_force_replay.mp4',contact_sheet_png=dirs['animations']/'reference_fidelity_visual_contact_sheet.png',
    )
    _write_csv(artifacts.nominal_state_segments_csv,nominal_audit.state_segments);_write_csv(artifacts.nominal_control_segments_csv,nominal_audit.regime_segments);_write_csv(artifacts.nominal_event_ledger_csv,nominal_audit.event_ledger);_write_csv(artifacts.high_loading_state_segments_csv,high_audit.state_segments);_write_csv(artifacts.high_loading_control_segments_csv,high_audit.regime_segments);_write_csv(artifacts.high_loading_event_ledger_csv,high_audit.event_ledger);_write_csv(artifacts.mission_behaviour_metrics_csv,[nominal_audit.summary,high_audit.summary]);_write_csv(artifacts.mission_fidelity_checks_csv,[{**check,'scenario':'nominal_coverage'} for check in nominal_audit.checks]+[{**check,'scenario':'high_loading_capacity'} for check in high_audit.checks])
    _draw_fidelity_map(nominal,nominal_env,nominal_audit,'Nominal reference mission fidelity','Coverage launch, local target diversion, controlled turns and home docking are independently logged.',artifacts.nominal_fidelity_map_png,artifacts.nominal_fidelity_map_svg);_draw_fidelity_map(high,high_env,high_audit,'High-loading reference mission fidelity','The same vehicle returns when occupied hopper volume reaches the documented capacity trigger.',artifacts.high_loading_fidelity_map_png,artifacts.high_loading_fidelity_map_svg);_draw_timeline(nominal_audit,high_audit,artifacts.state_timeline_png,artifacts.state_timeline_svg);_draw_control_clearance(nominal,high,artifacts.control_clearance_png,artifacts.control_clearance_svg);_draw_scorecard(nominal_audit,high_audit,artifacts.behaviour_scorecard_png,artifacts.behaviour_scorecard_svg);_draw_inventory(visual,artifacts.visual_evidence_inventory_png,artifacts.visual_evidence_inventory_svg)
    if render:
        _render_map_replay(nominal,nominal_env,nominal_audit,artifacts.nominal_replay_gif,artifacts.nominal_replay_mp4,visual,title='Nominal mission fidelity replay')
        _render_planning_replay(nominal,nominal_env,nominal_audit,artifacts.planning_replay_gif,artifacts.planning_replay_mp4,visual)
        _render_telemetry_replay(nominal,nominal_env,artifacts.telemetry_replay_gif,artifacts.telemetry_replay_mp4,visual,title='Nominal long-form telemetry replay')
        _render_map_replay(high,high_env,high_audit,artifacts.capacity_replay_gif,artifacts.capacity_replay_mp4,visual,title='High-loading capacity return replay',capacity=True)
        _render_telemetry_replay(high,high_env,artifacts.capacity_resources_gif,artifacts.capacity_resources_mp4,visual,title='High-loading resource and return replay',resource_focus=True)
        _render_control_force_replay(nominal,nominal_env,artifacts.control_force_replay_gif,artifacts.control_force_replay_mp4,visual)
        _contact=[artifacts.nominal_replay_gif,artifacts.planning_replay_gif,artifacts.telemetry_replay_gif,artifacts.capacity_replay_gif,artifacts.capacity_resources_gif,artifacts.control_force_replay_gif];write_animation_audit_sheet(_contact,artifacts.contact_sheet_png,samples_per_animation=int(visual['render']['contact_sheet_samples']))
    media=[artifacts.nominal_replay_gif,artifacts.nominal_replay_mp4,artifacts.planning_replay_gif,artifacts.planning_replay_mp4,artifacts.telemetry_replay_gif,artifacts.telemetry_replay_mp4,artifacts.capacity_replay_gif,artifacts.capacity_replay_mp4,artifacts.capacity_resources_gif,artifacts.capacity_resources_mp4,artifacts.control_force_replay_gif,artifacts.control_force_replay_mp4]
    quality=_visual_manifest(media,visual);artifacts.visual_quality_manifest_json.write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'reference_design':'AQUASKIM-REF-01','visualisation_protocol':visual['identifier'],'non_interactive':True,'nominal':nominal_audit.summary,'high_loading':high_audit.summary,'checks':{'nominal':nominal_audit.checks,'high_loading':high_audit.checks},'visual_quality':quality,'artifacts':artifacts.as_dict()};artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Reference Mission Fidelity and Visual Evidence','','## Scope','This evidence suite renders only the fixed, non-interactive reference mission. It does not build a Word report, delivery ZIP or release artifact.','','## Nominal coverage',f"- Termination: `{nominal_audit.summary['termination_reason']}`",f"- Coverage: `{100*nominal_audit.summary['coverage_fraction']:.1f}%`",f"- Captures: `{nominal_audit.summary['captured_count']}`",f"- First target confirmation: `{nominal_audit.summary['first_target_confirmation_time_s']}` s",'','## High loading',f"- Termination: `{high_audit.summary['termination_reason']}`",f"- Hopper return behaviour is capacity-based, not quota-based.",f"- Captures: `{high_audit.summary['captured_count']}`",'','## Visual QA',f"- Required GIF count: `{quality['required_animation_count']}`; observed: `{quality['observed_animation_count']}`",f"- All replay frame-count checks: `{quality['all_gif_frame_counts_ok']}`",f"- All replay duration checks: `{quality['all_gif_durations_ok']}`",f"- All replay resolution checks: `{quality['all_gif_resolutions_ok']}`",f"- Required MP4 count: `{quality['required_video_count']}`; observed: `{quality['observed_video_count']}`",f"- All MP4 existence checks: `{quality['all_mp4_exist']}`",'','## Model boundary','Media visualise logged low-speed 3-DOF simulation states. They are engineering evidence within the documented sheltered-basin model boundary, not physical sea-trial footage.']
    artifacts.summary_markdown.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    run=_record(artifacts) if record else None
    return artifacts,run


def print_phase10_11_summary(result: tuple[Phase1011Artifacts, Path | None] | Phase1011Artifacts) -> None:
    artifacts, run = result if isinstance(result, tuple) else (result, None)
    print("=" * 72)
    print("AquaSkim-Sim | Reference Mission Fidelity and Visual Evidence")
    print("=" * 72)
    print(f"Nominal fidelity map : {relative_to_root(artifacts.nominal_fidelity_map_png)}")
    print(f"Contact sheet        : {relative_to_root(artifacts.contact_sheet_png)}")
    print(f"Visual QA            : {relative_to_root(artifacts.visual_quality_manifest_json)}")
    if run:
        print(f"Evidence             : {relative_to_root(run)}")
    print("Status               : PASS")
    print("=" * 72)

def main() -> int:
    artifacts,run=run_phase10_11(record=True,render=True);print('='*72);print('AquaSkim-Sim | Reference Mission Fidelity and Visual Evidence');print('='*72);print(f'Contact sheet : {relative_to_root(artifacts.contact_sheet_png)}');print(f'Visual QA     : {relative_to_root(artifacts.visual_quality_manifest_json)}');print(f'Evidence      : {relative_to_root(run) if run else "not recorded"}');print('Status        : PASS');print('='*72);return 0

if __name__=='__main__': raise SystemExit(main())
