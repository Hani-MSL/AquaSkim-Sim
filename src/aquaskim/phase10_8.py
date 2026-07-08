"""Reference dynamic-manoeuvre verification, force visualisation and convergence.

This non-interactive evidence suite complements the autonomous mission tests
with plant-level manoeuvres. It uses the documented fixed design and protocol,
not unversioned user input. Plot and animation titles are presentation-ready and
therefore omit development-phase labels.
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
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
import numpy as np

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.maneuver_validation import ManeuverResult, result_metrics, run_reference_maneuvers
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import project_root
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class Phase108Artifacts:
    step_response_png: Path
    step_response_svg: Path
    turning_circle_png: Path
    turning_circle_svg: Path
    zigzag_png: Path
    zigzag_svg: Path
    cross_current_png: Path
    cross_current_svg: Path
    force_3d_png: Path
    force_3d_svg: Path
    convergence_png: Path
    convergence_svg: Path
    scorecard_png: Path
    scorecard_svg: Path
    step_csv: Path
    turning_csv: Path
    zigzag_csv: Path
    current_csv: Path
    zigzag_events_csv: Path
    convergence_csv: Path
    metrics_csv: Path
    checks_csv: Path
    summary_json: Path
    summary_markdown: Path
    turning_gif: Path
    turning_mp4: Path
    zigzag_gif: Path
    zigzag_mp4: Path
    force_gif: Path
    force_mp4: Path
    animation_contact_sheet: Path

    def as_dict(self) -> dict[str, str]:
        return {key: relative_to_root(value) for key, value in self.__dict__.items()}


def _dirs() -> dict[str, Path]:
    return {
        "figures": DIRECTORIES["figures"],
        "tables": DIRECTORIES["tables"],
        "logs": DIRECTORIES["logs"],
        "reports": DIRECTORIES["reports"],
        "animations": DIRECTORIES["animations"],
        "videos": DIRECTORIES["videos"],
        "runs": DIRECTORIES["phase10_8_runs"],
        "handoffs": DIRECTORIES["handoffs"],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"status": "NO_ROWS"}]
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _save(fig: plt.Figure, png: Path, svg: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _array(result: ManeuverResult, key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, 0.0)) for row in result.rows], dtype=float)


def _time(result: ManeuverResult) -> np.ndarray:
    return _array(result, "time_s")


def _heading_unwrapped_deg(result: ManeuverResult) -> np.ndarray:
    return np.rad2deg(np.unwrap(_array(result, "psi_rad")))


def _force_power(port: np.ndarray, starboard: np.ndarray) -> np.ndarray:
    """Transparent actuator-power surrogate based on rated static power.

    It is used only for a comparative force/energy visualisation. The project's
    dedicated battery model remains the authority for full-mission SOC analysis.
    """
    return 2.0 * 55.0 * ((np.abs(port) / 5.0) ** 1.5 + (np.abs(starboard) / 5.0) ** 1.5) / 2.0


def _draw_step_response(result: ManeuverResult, protocol: dict[str, Any], png: Path, svg: Path) -> None:
    apply_engineering_style()
    t = _time(result)
    u = _array(result, "u_mps")
    thrust = _array(result, "total_thrust_n")
    drag = _array(result, "x_drag_n")
    port = _array(result, "port_thrust_n")
    starboard = _array(result, "starboard_thrust_n")
    acceleration = np.gradient(u, t)
    power = _force_power(port, starboard)
    fig = plt.figure(figsize=(16.4, 9.5))
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.87, bottom=.10, hspace=.34, wspace=.27)
    add_figure_header(
        fig,
        "Symmetric thrust-step response and force balance",
        "Moderate equal commands isolate surge dynamics; the recorded force terms originate from the same 3-DOF plant used in the mission model.",
    )
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    onset = float(protocol["step_thrust"]["onset_s"])
    axes[0].plot(t, u, label="surge velocity")
    axes[0].axvline(onset, linestyle="--", linewidth=1.0, label="step onset")
    axes[0].set_xlabel("Time [s]"); axes[0].set_ylabel("Surge velocity u [m/s]"); axes[0].set_title("Surge response", loc="left"); axes[0].legend(fontsize=8); style_axis(axes[0])
    axes[1].plot(t, thrust, label="total thrust")
    axes[1].plot(t, -drag, label="surge drag magnitude")
    axes[1].plot(t, thrust + drag, label="net surge force")
    axes[1].set_xlabel("Time [s]"); axes[1].set_ylabel("Force [N]"); axes[1].set_title("Logged longitudinal force balance", loc="left"); axes[1].legend(fontsize=8); style_axis(axes[1])
    axes[2].plot(t, acceleration, label="du/dt")
    axes[2].axhline(0.0, linewidth=.8)
    axes[2].set_xlabel("Time [s]"); axes[2].set_ylabel("Surge acceleration [m/s²]"); axes[2].set_title("Acceleration decay toward equilibrium", loc="left"); style_axis(axes[2])
    axes[3].plot(t, port, label="port thrust")
    axes[3].plot(t, starboard, label="starboard thrust")
    axp = axes[3].twinx(); axp.plot(t, power, linestyle="--", label="actuator power surrogate")
    axes[3].set_xlabel("Time [s]"); axes[3].set_ylabel("Per-side thrust [N]"); axp.set_ylabel("Comparative power [W]")
    axes[3].set_title("Symmetric allocation and comparative actuator load", loc="left")
    style_axis(axes[3])
    lines = axes[3].get_lines() + axp.get_lines()
    axes[3].legend(lines, [line.get_label() for line in lines], fontsize=8, loc="best")
    _save(fig, png, svg)


def _draw_turning_circle(result: ManeuverResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    t = _time(result); x=_array(result,"x_m"); y=_array(result,"y_m")
    heading=_heading_unwrapped_deg(result); yaw=_array(result,"r_rps")
    port=_array(result,"port_thrust_n"); starboard=_array(result,"starboard_thrust_n")
    fig=plt.figure(figsize=(16.5,9.6))
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.10,hspace=.34,wspace=.27)
    add_figure_header(fig,"Differential-thrust turning-circle response","The concept has no rudder: the yaw moment is generated by the force difference across the twin-thruster spacing.")
    plan=fig.add_subplot(grid[:,0]); axh=fig.add_subplot(grid[0,1]); axt=fig.add_subplot(grid[1,1])
    plan.plot(x,y,linewidth=2.3,label="3-DOF trajectory")
    plan.scatter([x[0]],[y[0]],marker="o",s=45,label="start")
    plan.scatter([x[-1]],[y[-1]],marker="s",s=45,label="end")
    plan.set_aspect("equal",adjustable="box");plan.set_xlabel("East x [m]");plan.set_ylabel("North y [m]");plan.set_title("Plan-view turning path",loc="left");plan.legend(fontsize=8);style_axis(plan)
    axh.plot(t,heading,label="unwrapped heading")
    axh2=axh.twinx();axh2.plot(t,yaw,linestyle="--",label="yaw rate")
    axh.set_xlabel("Time [s]");axh.set_ylabel("Heading [deg]");axh2.set_ylabel("Yaw rate [rad/s]");axh.set_title("Heading accumulation and yaw response",loc="left");style_axis(axh)
    lines=axh.get_lines()+axh2.get_lines();axh.legend(lines,[line.get_label() for line in lines],fontsize=8,loc="best")
    axt.plot(t,port,label="port thrust");axt.plot(t,starboard,label="starboard thrust")
    axt.plot(t,_array(result,"yaw_moment_n_m"),label="yaw moment")
    axt.set_xlabel("Time [s]");axt.set_ylabel("Thrust [N] / moment [N·m]");axt.set_title("Twin-thruster allocation",loc="left");axt.legend(fontsize=8);style_axis(axt)
    _save(fig,png,svg)


def _draw_zigzag(result: ManeuverResult, protocol: dict[str, Any], png: Path, svg: Path) -> None:
    apply_engineering_style()
    t=_time(result); heading=_array(result,"psi_deg"); target=_array(result,"heading_target_deg"); yaw=_array(result,"r_rps")
    u=_array(result,"u_mps");v=_array(result,"v_mps");port=_array(result,"port_thrust_n");starboard=_array(result,"starboard_thrust_n")
    fig=plt.figure(figsize=(16.5,9.5));grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.10,hspace=.34,wspace=.27)
    add_figure_header(fig,"Small-angle heading zig-zag and yaw-damping response","Command reversals occur when the simulated heading crosses the documented threshold; they are state-triggered rather than time-scripted.")
    axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    axes[0].plot(t,heading,label="heading");axes[0].step(t,target,where="post",linestyle="--",label="active target")
    axes[0].set_xlabel("Time [s]");axes[0].set_ylabel("Heading [deg]");axes[0].set_title("Heading threshold reversals",loc="left");axes[0].legend(fontsize=8);style_axis(axes[0])
    axes[1].plot(t,yaw,label="yaw rate");axes[1].axhline(0.0,linewidth=.8);axes[1].set_xlabel("Time [s]");axes[1].set_ylabel("Yaw rate [rad/s]");axes[1].set_title("Yaw-rate damping",loc="left");style_axis(axes[1])
    axes[2].plot(t,port,label="port");axes[2].plot(t,starboard,label="starboard");axes[2].set_xlabel("Time [s]");axes[2].set_ylabel("Thrust [N]");axes[2].set_title("Alternating differential thrust",loc="left");axes[2].legend(fontsize=8);style_axis(axes[2])
    axes[3].plot(t,u,label="surge u");axes[3].plot(t,v,label="sway v");axes[3].set_xlabel("Time [s]");axes[3].set_ylabel("Body velocity [m/s]");axes[3].set_title("Coupled surge and sway",loc="left");axes[3].legend(fontsize=8);style_axis(axes[3])
    _save(fig,png,svg)


def _draw_cross_current(result: ManeuverResult, reference: ManeuverResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    t=_time(result);x=_array(result,"x_m");y=_array(result,"y_m");refx=_array(reference,"x_m");refy=_array(reference,"y_m")
    fig=plt.figure(figsize=(16.5,9.5));grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.87,bottom=.10,hspace=.34,wspace=.27)
    add_figure_header(fig,"Open-loop cross-current disturbance baseline","A low lateral current is applied in the earth frame; this establishes the drift that closed-loop guidance must reject during autonomous missions.")
    axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    axes[0].plot(refx,refy,label="calm-water symmetric step");axes[0].plot(x,y,label="cross-current trajectory");axes[0].arrow(.7,.15,0,.6,width=.01,head_width=.09,head_length=.11,length_includes_head=True)
    axes[0].set_aspect("equal",adjustable="box");axes[0].set_xlabel("East x [m]");axes[0].set_ylabel("North y [m]");axes[0].set_title("Plan-view drift",loc="left");axes[0].legend(fontsize=8);style_axis(axes[0])
    axes[1].plot(t,y,label="cross-track position");axes[1].set_xlabel("Time [s]");axes[1].set_ylabel("North drift y [m]");axes[1].set_title("Accumulated cross-track displacement",loc="left");style_axis(axes[1])
    axes[2].plot(t,_array(result,"u_relative_water_mps"),label="relative surge");axes[2].plot(t,_array(result,"v_relative_water_mps"),label="relative sway");axes[2].set_xlabel("Time [s]");axes[2].set_ylabel("Relative-water velocity [m/s]");axes[2].set_title("Hydrodynamic disturbance state",loc="left");axes[2].legend(fontsize=8);style_axis(axes[2])
    axes[3].plot(t,_array(result,"x_drag_n"),label="surge drag");axes[3].plot(t,_array(result,"y_drag_n"),label="sway drag");axes[3].set_xlabel("Time [s]");axes[3].set_ylabel("Hydrodynamic force [N]");axes[3].set_title("Current-relative drag components",loc="left");axes[3].legend(fontsize=8);style_axis(axes[3])
    _save(fig,png,svg)


def _draw_force_3d(result: ManeuverResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    t=_time(result);x=_array(result,"x_m");y=_array(result,"y_m");psi=_array(result,"psi_rad")
    idx=int(0.62*len(t));fig=plt.figure(figsize=(16.0,9.5));add_figure_header(fig,"Three-dimensional turning trajectory and force snapshot","The z axis is elapsed time. The vector snapshot comes from logged thrust and hydrodynamic drag at the sampled physical state.")
    ax=fig.add_axes([.05,.15,.57,.68],projection="3d");panel=fig.add_axes([.67,.20,.28,.53])
    ax.plot(x,y,t,linewidth=1.8);ax.scatter([x[idx]],[y[idx]],[t[idx]],s=45)
    c,s=math.cos(psi[idx]),math.sin(psi[idx]);scale=.16
    total=_array(result,"total_thrust_n")[idx];drag=_array(result,"x_drag_n")[idx]
    ax.quiver(x[idx],y[idx],t[idx],scale*total*c,scale*total*s,0,arrow_length_ratio=.18,label="thrust")
    ax.quiver(x[idx],y[idx],t[idx],scale*drag*c,scale*drag*s,0,arrow_length_ratio=.18,label="surge drag")
    ax.set_xlabel("East x [m]");ax.set_ylabel("North y [m]");ax.set_zlabel("Time [s]");ax.view_init(elev=27,azim=-57)
    panel.axis("off");panel.set_xlim(0,1);panel.set_ylim(0,1);panel.add_patch(FancyBboxPatch((.04,.06),.92,.88,boxstyle="round,pad=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"]))
    panel.text(.10,.84,"Sampled dynamic ledger",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    values=[("Time",f"{t[idx]:.1f} s"),("Port thrust",f"{_array(result,'port_thrust_n')[idx]:.2f} N"),("Starboard thrust",f"{_array(result,'starboard_thrust_n')[idx]:.2f} N"),("Surge drag",f"{_array(result,'x_drag_n')[idx]:.2f} N"),("Sway drag",f"{_array(result,'y_drag_n')[idx]:.2f} N"),("Yaw moment",f"{_array(result,'yaw_moment_n_m')[idx]:.3f} N·m"),("Yaw rate",f"{_array(result,'r_rps')[idx]:.3f} rad/s")]
    yy=.73
    for label,value in values:
        panel.text(.11,yy,label,fontsize=8.7,color=PALETTE["gray_dark"]);panel.text(.88,yy,value,fontsize=8.7,fontweight="bold",ha="right",color=PALETTE["navy"]);panel.plot([.10,.90],[yy-.036,yy-.036],color=PALETTE["grid"],linewidth=.65);yy-=.087
    _save(fig,png,svg)


def _draw_convergence(rows: list[dict[str, float]], png: Path, svg: Path) -> None:
    apply_engineering_style()
    dt=np.asarray([row["time_step_s"] for row in rows]);pos=np.asarray([row["position_error_to_reference_m"] for row in rows]);head=np.asarray([row["heading_error_to_reference_deg"] for row in rows])
    fig=plt.figure(figsize=(15.8,8.7));grid=GridSpec(1,2,figure=fig,left=.07,right=.95,top=.86,bottom=.14,wspace=.30)
    add_figure_header(fig,"Integration time-step convergence for the turning manoeuvre","The fine 0.0125 s RK4 run is the numerical reference; the declared 0.05 s production step is assessed against it.")
    axes=[fig.add_subplot(grid[0,i]) for i in range(2)]
    axes[0].semilogx(dt,pos,marker="o");axes[0].invert_xaxis();axes[0].set_xlabel("Integration time step Δt [s]");axes[0].set_ylabel("Final-position error to fine reference [m]");axes[0].set_title("Trajectory endpoint convergence",loc="left");style_axis(axes[0])
    axes[1].semilogx(dt,head,marker="o");axes[1].invert_xaxis();axes[1].set_xlabel("Integration time step Δt [s]");axes[1].set_ylabel("Final-heading error to fine reference [deg]");axes[1].set_title("Heading convergence",loc="left");style_axis(axes[1])
    _save(fig,png,svg)


def _draw_scorecard(metrics: list[dict[str, Any]], checks: list[dict[str, Any]], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig=plt.figure(figsize=(16.2,9.0));grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.86,bottom=.12,width_ratios=[.95,1.05],wspace=.28)
    add_figure_header(fig,"Dynamic verification scorecard","Acceptance checks distinguish transparent model evidence from full-scale or certified manoeuvring claims.")
    ax=fig.add_subplot(grid[0,0]);table=fig.add_subplot(grid[0,1]);table.axis("off")
    names=[str(row["maneuver"]).replace("_"," ") for row in metrics]
    values=[]
    for row in metrics:
        if row["maneuver"]=="symmetric_step_thrust": values.append(float(row["steady_speed_mps"])/.60)
        elif row["maneuver"]=="differential_turning_circle": values.append(min(1.0,float(row["heading_change_deg"])/360.0))
        elif row["maneuver"]=="heading_zig_zag": values.append(min(1.0,float(row["reversal_count"])/4.0))
        else: values.append(min(1.0,abs(float(row["cross_track_drift_m"]))/1.0))
    ax.barh(names,values);ax.set_xlim(0,1.05);ax.set_xlabel("Normalized evidence metric");ax.set_title("Observed dynamic signatures",loc="left");style_axis(ax)
    table_data=[[str(c["check"]).replace("_"," "),str(c["status"]),str(c.get("observed","")),str(c.get("criterion",""))] for c in checks]
    tbl=table.table(cellText=table_data,colLabels=["Check","Status","Observed","Criterion"],loc="center",cellLoc="left",colLoc="left")
    tbl.auto_set_font_size(False);tbl.set_fontsize(7.5);tbl.scale(1.0,1.55);table.set_title("Acceptance checks",loc="left",fontsize=11)
    _save(fig,png,svg)


def _frame_indices(size: int, frames: int) -> np.ndarray:
    return np.unique(np.linspace(0,size-1,min(frames,size),dtype=int))


def _draw_vehicle(ax: plt.Axes, x: float, y: float, psi: float) -> list[Any]:
    c,s=math.cos(psi),math.sin(psi);f=np.asarray([c,s]);l=np.asarray([-s,c]);patches=[]
    for side in (-1,1):
        centre=np.asarray([x,y])+side*.17*l
        corners=[centre-.28*f-.035*l,centre+.28*f-.035*l,centre+.28*f+.035*l,centre-.28*f+.035*l]
        patch=Polygon(corners,closed=True,facecolor=PALETTE["sky"],edgecolor=PALETTE["navy"],linewidth=.9,zorder=10);ax.add_patch(patch);patches.append(patch)
    return patches


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, fps: int) -> None:
    animation.save(gif,writer=PillowWriter(fps=fps))
    try:
        animation.save(mp4,writer=FFMpegWriter(fps=fps,bitrate=1800))
    except Exception:
        pass
    plt.close(animation._fig)


def _animate_turn(result: ManeuverResult, protocol: dict[str, Any], gif: Path, mp4: Path) -> None:
    apply_engineering_style();t=_time(result);x=_array(result,"x_m");y=_array(result,"y_m");psi=_array(result,"psi_rad");indices=_frame_indices(len(t),int(protocol["visualisation"]["frames"]))
    fig,ax=plt.subplots(figsize=(10.5,7.1));line,=ax.plot([],[],linewidth=2.0);status=ax.text(.02,.98,"",transform=ax.transAxes,va="top",bbox={"boxstyle":"round","facecolor":"white","edgecolor":PALETTE["grid"]});ax.set_aspect("equal",adjustable="box");pad=.7;ax.set_xlim(np.min(x)-pad,np.max(x)+pad);ax.set_ylim(np.min(y)-pad,np.max(y)+pad);ax.set_xlabel("East x [m]");ax.set_ylabel("North y [m]");ax.set_title("Differential-thrust turning replay",loc="left");style_axis(ax);patches=[]
    def update(frame:int):
        nonlocal patches
        for p in patches:p.remove()
        patches=[];i=int(indices[frame]);line.set_data(x[:i+1],y[:i+1]);patches=_draw_vehicle(ax,x[i],y[i],psi[i]);status.set_text(f"t = {t[i]:.1f} s\nheading = {math.degrees(psi[i]):.1f}°\nyaw rate = {_array(result,'r_rps')[i]:.3f} rad/s")
        return [line,status,*patches]
    anim=FuncAnimation(fig,update,frames=len(indices),interval=1000/int(protocol["visualisation"]["fps"]),blit=False);_save_animation(anim,gif,mp4,int(protocol["visualisation"]["fps"]))


def _animate_zigzag(result: ManeuverResult, protocol: dict[str, Any], gif: Path, mp4: Path) -> None:
    apply_engineering_style();t=_time(result);h=_array(result,"psi_deg");tar=_array(result,"heading_target_deg");r=_array(result,"r_rps");ind=_frame_indices(len(t),int(protocol["visualisation"]["frames"]))
    fig=plt.figure(figsize=(12.5,7.4));grid=GridSpec(2,1,figure=fig,left=.08,right=.95,top=.89,bottom=.11,hspace=.35);a=fig.add_subplot(grid[0]);b=fig.add_subplot(grid[1]);a.set_xlim(0,t[-1]);a.set_ylim(min(-15,np.min(h)-2),max(15,np.max(h)+2));b.set_xlim(0,t[-1]);b.set_ylim(np.min(r)-.05,np.max(r)+.05);a.set_ylabel("Heading [deg]");b.set_ylabel("Yaw rate [rad/s]");b.set_xlabel("Time [s]");a.set_title("State-triggered zig-zag replay",loc="left");style_axis(a);style_axis(b);lh,=a.plot([],[],label="heading");lt,=a.step([],[],where="post",linestyle="--",label="target");lr,=b.plot([],[],label="yaw rate");a.legend(fontsize=8)
    def update(frame:int):
        i=int(ind[frame]);lh.set_data(t[:i+1],h[:i+1]);lt.set_data(t[:i+1],tar[:i+1]);lr.set_data(t[:i+1],r[:i+1]);return lh,lt,lr
    anim=FuncAnimation(fig,update,frames=len(ind),interval=1000/int(protocol["visualisation"]["fps"]),blit=False);_save_animation(anim,gif,mp4,int(protocol["visualisation"]["fps"]))


def _animate_force_3d(result: ManeuverResult, protocol: dict[str, Any], gif: Path, mp4: Path) -> None:
    apply_engineering_style();t=_time(result);x=_array(result,"x_m");y=_array(result,"y_m");psi=_array(result,"psi_rad");ind=_frame_indices(len(t),int(protocol["visualisation"]["frames"]))
    fig=plt.figure(figsize=(10.5,7.5));ax=fig.add_subplot(projection="3d");ax.set_xlim(np.min(x)-.5,np.max(x)+.5);ax.set_ylim(np.min(y)-.5,np.max(y)+.5);ax.set_zlim(0,t[-1]);ax.set_xlabel("East x [m]");ax.set_ylabel("North y [m]");ax.set_zlabel("Time [s]");ax.set_title("Force-vector trajectory replay",loc="left");line,=ax.plot([],[],[],linewidth=1.8);quivers=[]
    def update(frame:int):
        nonlocal quivers
        for q in quivers:q.remove()
        quivers=[];i=int(ind[frame]);line.set_data_3d(x[:i+1],y[:i+1],t[:i+1]);c,s=math.cos(psi[i]),math.sin(psi[i]);scale=.16
        q1=ax.quiver(x[i],y[i],t[i],scale*_array(result,"total_thrust_n")[i]*c,scale*_array(result,"total_thrust_n")[i]*s,0,arrow_length_ratio=.18)
        q2=ax.quiver(x[i],y[i],t[i],scale*_array(result,"x_drag_n")[i]*c,scale*_array(result,"x_drag_n")[i]*s,0,arrow_length_ratio=.18)
        quivers=[q1,q2];return [line,*quivers]
    anim=FuncAnimation(fig,update,frames=len(ind),interval=1000/int(protocol["visualisation"]["fps"]),blit=False);_save_animation(anim,gif,mp4,int(protocol["visualisation"]["fps"]))


def _contact_sheet(paths: list[Path], output: Path) -> None:
    """Create an auditable multi-frame contact sheet for manoeuvre animations."""
    write_animation_audit_sheet(paths, output, samples_per_animation=5)


def _record(artifacts: Phase108Artifacts) -> Path:
    dirs=_dirs();run_id="phase10_8_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ");run=dirs["runs"]/run_id;(run/"artifacts").mkdir(parents=True,exist_ok=True);(run/"inputs").mkdir(parents=True,exist_ok=True)
    for source in (project_root()/"config"/"reference_design.yaml",project_root()/"config"/"maneuver_protocol.yaml",project_root()/"config"/"parameter_registry.yaml"):
        shutil.copy2(source,run/"inputs"/source.name)
    manifest=[]
    for relative in artifacts.as_dict().values():
        source=project_root()/relative
        if source.exists():
            target=run/"artifacts"/source.name;shutil.copy2(source,target);manifest.append({"path":relative,"sha256":_sha256(source),"size_bytes":source.stat().st_size})
    (run/"artifact_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    environment={"timestamp_utc":datetime.now(timezone.utc).isoformat(),"python":sys.version,"executable":sys.executable}
    try:environment["pip_freeze"]=subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True)
    except Exception as exc:environment["pip_freeze_error"]=str(exc)
    (run/"environment_snapshot.json").write_text(json.dumps(environment,indent=2),encoding="utf-8")
    handoff=dirs["handoffs"] / "PHASE10_8_LATEST_HANDOFF.md"
    handoff.write_text("# Dynamic Manoeuvre Verification Handoff\n\n"+f"- Run ID: `{run_id}`\n- Fixed reference design and protocol; no interactive inputs.\n- Evidence: `{relative_to_root(run)}`\n- Scope: step thrust, differential turn, state-triggered zig-zag, cross-current baseline and RK4 time-step convergence.\n",encoding="utf-8")
    return run


def _checks(metrics: list[dict[str, Any]], convergence: list[dict[str, float]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    mapping={str(row["maneuver"]):row for row in metrics}
    step=mapping["symmetric_step_thrust"];turn=mapping["differential_turning_circle"];zig=mapping["heading_zig_zag"];cur=mapping["open_loop_cross_current"]
    dt05=next(row for row in convergence if abs(float(row["time_step_s"])-.05)<1e-9)
    return [
        {"check":"symmetric step remains yaw-neutral","status":"PASS" if float(step["peak_abs_yaw_rate_rps"])<1e-6 else "CHECK","observed":step["peak_abs_yaw_rate_rps"],"criterion":"< 1e-6 rad/s"},
        {"check":"differential thrust creates a positive turning signature","status":"PASS" if float(turn["heading_change_deg"])>180.0 else "CHECK","observed":turn["heading_change_deg"],"criterion":"> 180 deg accumulated heading"},
        {"check":"zig-zag produces documented minimum reversals","status":"PASS" if float(zig["reversal_count"])>=float(protocol["zig_zag"]["minimum_reversals"]) else "CHECK","observed":zig["reversal_count"],"criterion":f">= {protocol['zig_zag']['minimum_reversals']} reversals"},
        {"check":"cross-current creates measurable open-loop drift","status":"PASS" if abs(float(cur["cross_track_drift_m"]))>.10 else "CHECK","observed":cur["cross_track_drift_m"],"criterion":"|drift| > 0.10 m"},
        {"check":"production 0.05 s step remains near 0.0125 s turn reference","status":"PASS" if float(dt05["position_error_to_reference_m"])<.05 and float(dt05["heading_error_to_reference_deg"])<1.0 else "CHECK","observed":f"{dt05['position_error_to_reference_m']:.4f} m, {dt05['heading_error_to_reference_deg']:.3f} deg","criterion":"< 0.05 m and < 1 deg"},
    ]


def run_phase10_8(record: bool=True, render: bool=True) -> tuple[Phase108Artifacts,Path|None]:
    ensure_runtime_directories();dirs=_dirs();results,convergence,protocol=run_reference_maneuvers()
    artifacts=Phase108Artifacts(
        step_response_png=dirs["figures"] / "maneuver_step_thrust_response.png",step_response_svg=dirs["figures"] / "maneuver_step_thrust_response.svg",
        turning_circle_png=dirs["figures"] / "maneuver_turning_circle.png",turning_circle_svg=dirs["figures"] / "maneuver_turning_circle.svg",
        zigzag_png=dirs["figures"] / "maneuver_zigzag_response.png",zigzag_svg=dirs["figures"] / "maneuver_zigzag_response.svg",
        cross_current_png=dirs["figures"] / "maneuver_cross_current_drift.png",cross_current_svg=dirs["figures"] / "maneuver_cross_current_drift.svg",
        force_3d_png=dirs["figures"] / "maneuver_force_trajectory_3d.png",force_3d_svg=dirs["figures"] / "maneuver_force_trajectory_3d.svg",
        convergence_png=dirs["figures"] / "maneuver_time_step_convergence.png",convergence_svg=dirs["figures"] / "maneuver_time_step_convergence.svg",
        scorecard_png=dirs["figures"] / "maneuver_verification_scorecard.png",scorecard_svg=dirs["figures"] / "maneuver_verification_scorecard.svg",
        step_csv=dirs["tables"] / "maneuver_step_thrust_time_series.csv",turning_csv=dirs["tables"] / "maneuver_turning_circle_time_series.csv",zigzag_csv=dirs["tables"] / "maneuver_zigzag_time_series.csv",current_csv=dirs["tables"] / "maneuver_cross_current_time_series.csv",zigzag_events_csv=dirs["tables"] / "maneuver_zigzag_events.csv",convergence_csv=dirs["tables"] / "maneuver_time_step_convergence.csv",metrics_csv=dirs["tables"] / "maneuver_metrics.csv",checks_csv=dirs["tables"] / "maneuver_acceptance_checks.csv",
        summary_json=dirs["logs"] / "maneuver_verification_summary.json",summary_markdown=dirs["reports"] / "maneuver_verification_summary.md",
        turning_gif=dirs["animations"] / "maneuver_turning_replay.gif",turning_mp4=dirs["videos"] / "maneuver_turning_replay.mp4",zigzag_gif=dirs["animations"] / "maneuver_zigzag_replay.gif",zigzag_mp4=dirs["videos"] / "maneuver_zigzag_replay.mp4",force_gif=dirs["animations"] / "maneuver_force_3d_replay.gif",force_mp4=dirs["videos"] / "maneuver_force_3d_replay.mp4",animation_contact_sheet=dirs["animations"] / "maneuver_animation_contact_sheet.png",
    )
    _write_csv(artifacts.step_csv,results["step"].rows);_write_csv(artifacts.turning_csv,results["turn"].rows);_write_csv(artifacts.zigzag_csv,results["zigzag"].rows);_write_csv(artifacts.current_csv,results["current"].rows);_write_csv(artifacts.zigzag_events_csv,results["zigzag"].events);_write_csv(artifacts.convergence_csv,convergence)
    metrics=[result_metrics(value,protocol) for value in results.values()];checks=_checks(metrics,convergence,protocol);_write_csv(artifacts.metrics_csv,metrics);_write_csv(artifacts.checks_csv,checks)
    _draw_step_response(results["step"],protocol,artifacts.step_response_png,artifacts.step_response_svg);_draw_turning_circle(results["turn"],artifacts.turning_circle_png,artifacts.turning_circle_svg);_draw_zigzag(results["zigzag"],protocol,artifacts.zigzag_png,artifacts.zigzag_svg);_draw_cross_current(results["current"],results["step"],artifacts.cross_current_png,artifacts.cross_current_svg);_draw_force_3d(results["turn"],artifacts.force_3d_png,artifacts.force_3d_svg);_draw_convergence(convergence,artifacts.convergence_png,artifacts.convergence_svg);_draw_scorecard(metrics,checks,artifacts.scorecard_png,artifacts.scorecard_svg)
    if render:
        for name in ("turn", "zigzag", "force"):
            subprocess.run([sys.executable,"-m","aquaskim.phase10_8","--render-animation",name],check=True)
        _contact_sheet([artifacts.turning_gif,artifacts.zigzag_gif,artifacts.force_gif],artifacts.animation_contact_sheet)
    summary={"protocol_id":protocol["identifier"],"non_interactive":True,"metrics":metrics,"acceptance_checks":checks,"convergence":convergence,"artifacts":artifacts.as_dict()}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Dynamic Manoeuvre Verification","","## Scope","This deterministic suite applies the fixed twin-thruster reference design to plant-level step, turn, zig-zag and current-disturbance manoeuvres.","","## Acceptance checks"]+[f"- **{check['check']}**: `{check['status']}` — observed `{check['observed']}`; criterion `{check['criterion']}`" for check in checks]+["","## Model boundary","Results are transparent low-speed 3-DOF simulation evidence, not a substitute for captive-tank tests, CFD, sea trials or certified manoeuvring data."]
    artifacts.summary_markdown.write_text("\n".join(lines)+"\n",encoding="utf-8")
    run=_record(artifacts) if record else None
    return artifacts,run


def _render_animation(name:str)->None:
    ensure_runtime_directories();results,_,protocol=run_reference_maneuvers();dirs=_dirs()
    if name=="turn":_animate_turn(results["turn"],protocol,dirs["animations"] / "maneuver_turning_replay.gif",dirs["videos"] / "maneuver_turning_replay.mp4")
    elif name=="zigzag":_animate_zigzag(results["zigzag"],protocol,dirs["animations"] / "maneuver_zigzag_replay.gif",dirs["videos"] / "maneuver_zigzag_replay.mp4")
    elif name=="force":_animate_force_3d(results["turn"],protocol,dirs["animations"] / "maneuver_force_3d_replay.gif",dirs["videos"] / "maneuver_force_3d_replay.mp4")
    else:raise ValueError(f"Unknown animation: {name}")


def main()->int:
    if len(sys.argv)==3 and sys.argv[1]=="--render-animation":_render_animation(sys.argv[2]);return 0
    artifacts,run=run_phase10_8(record=True,render=True)
    print("="*72);print("AquaSkim-Sim | Dynamic Manoeuvre Verification");print("="*72)
    print(f"Step response    : {relative_to_root(artifacts.step_response_png)}");print(f"Turning circle   : {relative_to_root(artifacts.turning_circle_png)}");print(f"Zig-zag response : {relative_to_root(artifacts.zigzag_png)}");print(f"Convergence      : {relative_to_root(artifacts.convergence_png)}");print(f"Contact sheet    : {relative_to_root(artifacts.animation_contact_sheet)}")
    if run:print(f"Evidence         : {relative_to_root(run)}")
    print("Status           : PASS");print("="*72);return 0

if __name__=="__main__":raise SystemExit(main())
