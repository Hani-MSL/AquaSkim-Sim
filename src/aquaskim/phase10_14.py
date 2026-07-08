"""Payload stability sensitivity and low-current manoeuvre evidence build.

The module produces reference engineering evidence from the existing, versioned
hydrostatics and 3-DOF manoeuvring models.  It intentionally does not build a
Word report, delivery archive or release artifact.
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
from matplotlib.patches import Rectangle
import numpy as np

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.payload_maneuver_validation import (
    ManeuverResult,
    PayloadStaticResult,
    assess_suite,
    load_payload_maneuver_protocol,
    load_visual_protocol,
    run_payload_maneuver_suite,
)
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import project_root
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class Phase1014Artifacts:
    stability_envelope_png: Path
    stability_envelope_svg: Path
    offset_heel_budget_png: Path
    offset_heel_budget_svg: Path
    dynamic_maneuvers_png: Path
    dynamic_maneuvers_svg: Path
    current_maneuver_matrix_png: Path
    current_maneuver_matrix_svg: Path
    scorecard_png: Path
    scorecard_svg: Path
    static_cases_csv: Path
    heel_curve_csv: Path
    maneuver_metrics_csv: Path
    maneuver_timeseries_csv: Path
    acceptance_checks_csv: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest_json: Path
    stability_gif: Path
    stability_mp4: Path
    step_gif: Path
    step_mp4: Path
    turn_gif: Path
    turn_mp4: Path
    zigzag_gif: Path
    zigzag_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _dirs() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": DIRECTORIES["figures"], "tables": DIRECTORIES["tables"], "logs": DIRECTORIES["logs"],
        "reports": DIRECTORIES["reports"], "animations": DIRECTORIES["animations"], "videos": DIRECTORIES["videos"],
        "records": root / "records" / "phases" / "phase_10_14" / "runs", "handoffs": DIRECTORIES["handoffs"],
    }


def _artifacts() -> Phase1014Artifacts:
    d = _dirs()
    return Phase1014Artifacts(
        stability_envelope_png=d["figures"] / "reference_payload_stability_envelope.png",
        stability_envelope_svg=d["figures"] / "reference_payload_stability_envelope.svg",
        offset_heel_budget_png=d["figures"] / "reference_payload_offset_heel_budget.png",
        offset_heel_budget_svg=d["figures"] / "reference_payload_offset_heel_budget.svg",
        dynamic_maneuvers_png=d["figures"] / "reference_payload_dynamic_maneuvers.png",
        dynamic_maneuvers_svg=d["figures"] / "reference_payload_dynamic_maneuvers.svg",
        current_maneuver_matrix_png=d["figures"] / "reference_payload_current_maneuver_matrix.png",
        current_maneuver_matrix_svg=d["figures"] / "reference_payload_current_maneuver_matrix.svg",
        scorecard_png=d["figures"] / "reference_payload_maneuver_scorecard.png",
        scorecard_svg=d["figures"] / "reference_payload_maneuver_scorecard.svg",
        static_cases_csv=d["tables"] / "reference_payload_static_cases.csv",
        heel_curve_csv=d["tables"] / "reference_payload_heel_curves.csv",
        maneuver_metrics_csv=d["tables"] / "reference_payload_maneuver_metrics.csv",
        maneuver_timeseries_csv=d["tables"] / "reference_payload_maneuver_time_series.csv",
        acceptance_checks_csv=d["tables"] / "reference_payload_maneuver_acceptance_checks.csv",
        summary_json=d["logs"] / "reference_payload_maneuver_summary.json",
        summary_markdown=d["reports"] / "reference_payload_maneuver_validation.md",
        visual_quality_manifest_json=d["logs"] / "reference_payload_maneuver_visual_quality_manifest.json",
        stability_gif=d["animations"] / "reference_payload_stability_replay.gif",
        stability_mp4=d["videos"] / "reference_payload_stability_replay.mp4",
        step_gif=d["animations"] / "reference_payload_step_response_replay.gif",
        step_mp4=d["videos"] / "reference_payload_step_response_replay.mp4",
        turn_gif=d["animations"] / "reference_payload_turn_current_replay.gif",
        turn_mp4=d["videos"] / "reference_payload_turn_current_replay.mp4",
        zigzag_gif=d["animations"] / "reference_payload_zigzag_replay.gif",
        zigzag_mp4=d["videos"] / "reference_payload_zigzag_replay.mp4",
        contact_sheet_png=d["animations"] / "reference_payload_maneuver_contact_sheet.png",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        rows, fields = [{"status": "NO_ROWS"}], ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _save(fig: plt.Figure, png: Path, svg: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, fps: int, bitrate: int) -> None:
    """Save the GIF once, then transcode that exact frame stream to MP4.

    Matplotlib can consume a cached animation frame generator after a Pillow
    save on some Windows/Pillow combinations, leaving a truncated MP4.  The
    GIF is the canonical audited source here; FFmpeg transcodes it so both
    media formats carry the same sampled frames and duration.
    """
    gif.parent.mkdir(parents=True, exist_ok=True); mp4.parent.mkdir(parents=True, exist_ok=True)
    animation.save(gif, writer=PillowWriter(fps=fps))
    plt.close(animation._fig)
    completed = subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(gif),
        "-movflags", "+faststart", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-b:v", f"{int(bitrate)}k", str(mp4),
    ], capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg could not transcode {gif.name}: {completed.stderr.strip()}")


def _array(result: ManeuverResult, key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, 0.0)) for row in result.rows], dtype=float)


def _sample_indices(length: int, frames: int) -> np.ndarray:
    return np.linspace(0, max(0, length - 1), max(2, int(frames))).round().astype(int)


def _color_for_case(identifier: str) -> str:
    return {
        "dry_empty": PALETTE["blue"], "half_low_central": PALETTE["cyan"], "full_low_central": PALETTE["green"],
        "full_raised_central": PALETTE["orange"], "full_port_offset": PALETTE["orange"],
    }.get(identifier, PALETTE["gray_dark"])


def _draw_stability_envelope(static: list[PayloadStaticResult], artifacts: Phase1014Artifacts) -> None:
    apply_engineering_style(); fig = plt.figure(figsize=(17.0, 9.7)); add_figure_header(fig, "Payload placement sensitivity: draft, freeboard and transverse stability", "All cases use the same two-hull reference geometry. Raised and port-offset payloads are sensitivity cases, not recommended operating configurations.")
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.86, bottom=.10, hspace=.36, wspace=.28)
    ax_mass=fig.add_subplot(grid[0,0]); ax_gm=fig.add_subplot(grid[0,1]); ax_fb=fig.add_subplot(grid[1,0]); panel=fig.add_subplot(grid[1,1]); panel.axis("off"); panel.set_xlim(0,1);panel.set_ylim(0,1)
    labels=[item.payload_case.identifier.replace("_","\n") for item in static]; xpos=np.arange(len(static)); colors=[_color_for_case(item.payload_case.identifier) for item in static]
    ax_mass.bar(xpos,[item.mass_properties.total_mass_kg for item in static],color=colors); ax_mass.set_xticks(xpos,labels,fontsize=8); ax_mass.set_ylabel("Total mass [kg]"); ax_mass.set_title("Mass and draft",loc="left"); ax_d=ax_mass.twinx(); ax_d.plot(xpos,[item.hydro_case.draft_m for item in static],"o--",color=PALETTE["navy"],label="draft");ax_d.set_ylabel("Draft [m]");style_axis(ax_mass);ax_d.grid(False)
    ax_gm.bar(xpos,[item.hydro_case.gm_m for item in static],color=colors); ax_gm.axhline(.20,color=PALETTE["orange"],linestyle="--",label="minimum GM");ax_gm.set_xticks(xpos,labels,fontsize=8);ax_gm.set_ylabel("GM [m]");ax_gm.set_title("Initial transverse stability",loc="left");ax_gm.legend(fontsize=8);style_axis(ax_gm)
    ax_fb.bar(xpos,[item.hydro_case.freeboard_m for item in static],color=colors);ax_fb.axhline(.05,color=PALETTE["orange"],linestyle="--",label="minimum freeboard");ax_fb.set_xticks(xpos,labels,fontsize=8);ax_fb.set_ylabel("Freeboard [m]");ax_fb.set_title("Calm-water freeboard",loc="left");ax_fb.legend(fontsize=8);style_axis(ax_fb)
    panel.text(.06,.92,"Design interpretation",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top")
    full=next(x for x in static if x.payload_case.identifier=="full_low_central"); raised=next(x for x in static if x.payload_case.identifier=="full_raised_central"); offset=next(x for x in static if x.payload_case.identifier=="full_port_offset")
    lines=[("Full payload GM",f"{full.hydro_case.gm_m:.3f} m"),("Raised-payload GM",f"{raised.hydro_case.gm_m:.3f} m"),("Full payload freeboard",f"{full.hydro_case.freeboard_m:.3f} m"),("Offset equilibrium heel",f"{offset.offset_equilibrium_heel_deg:.2f} deg"),("Offset righting margin at 5 deg",f"{offset.offset_righting_margin_ratio:.2f} x")]
    y=.79
    for label,value in lines:
        panel.text(.08,y,label,fontsize=9,color=PALETTE["gray_dark"]);panel.text(.92,y,value,fontsize=9,ha="right",fontweight="bold",color=PALETTE["navy"]);panel.plot([.08,.92],[y-.045,y-.045],color=PALETTE["grid"],linewidth=.7);y-=.13
    panel.text(.08,.12,"The static model is a calm-water hydrostatic sensitivity. It does not claim wave, roll-transient, structural or sloshing behaviour.",fontsize=8.2,color=PALETTE["gray"],wrap=True)
    _save(fig,artifacts.stability_envelope_png,artifacts.stability_envelope_svg)


def _draw_offset_budget(static: list[PayloadStaticResult], artifacts: Phase1014Artifacts) -> None:
    apply_engineering_style();fig=plt.figure(figsize=(17.0,9.6));add_figure_header(fig,"Nonlinear righting curves and port-offset payload budget","The port-offset case balances a static payload heeling moment against the strip-integrated righting curve. Positive heel is port-down.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.86,bottom=.10,hspace=.36,wspace=.28);ax_rm=fig.add_subplot(grid[:,0]);ax_gz=fig.add_subplot(grid[0,1]);panel=fig.add_subplot(grid[1,1]);panel.axis("off");panel.set_xlim(0,1);panel.set_ylim(0,1)
    for item in static:
        heel=np.asarray([state.heel_deg for state in item.heel_curve]);rm=np.asarray([state.righting_moment_n_m for state in item.heel_curve]);gz=np.asarray([state.gz_nonlinear_m for state in item.heel_curve]);color=_color_for_case(item.payload_case.identifier)
        ax_rm.plot(heel,rm,color=color,linewidth=2,label=item.payload_case.title);ax_gz.plot(heel,gz,color=color,linewidth=1.9,label=item.payload_case.title)
    offset=next(item for item in static if item.payload_case.identifier=="full_port_offset")
    ax_rm.axhline(offset.payload_heeling_moment_n_m,color=PALETTE["orange"],linestyle="--",label="offset payload moment");ax_rm.axvline(offset.offset_equilibrium_heel_deg,color=PALETTE["orange"],linestyle="--",label="estimated equilibrium heel");ax_rm.axvline(5.0,color=PALETTE["gray"],linestyle=":",label="operational heel limit")
    ax_rm.set_xlabel("Heel [deg]");ax_rm.set_ylabel("Righting moment [N m]");ax_rm.set_title("Righting-moment budget",loc="left");ax_rm.legend(fontsize=7);style_axis(ax_rm)
    ax_gz.axvline(5.0,color=PALETTE["gray"],linestyle=":");ax_gz.set_xlabel("Heel [deg]");ax_gz.set_ylabel("Righting arm GZ [m]");ax_gz.set_title("Nonlinear righting arm",loc="left");style_axis(ax_gz)
    panel.text(.06,.92,"Offset-load sensitivity",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top");text=[("Offset payload",f"{offset.payload_case.payload_mass_kg:.2f} kg at y = {offset.payload_case.payload_position_m[1]:.2f} m"),("Applied heeling moment",f"{offset.payload_heeling_moment_n_m:.3f} N m"),("Estimated equilibrium heel",f"{offset.offset_equilibrium_heel_deg:.2f} deg"),("Righting moment at 5 deg",f"{offset.operating_state.righting_moment_n_m:.3f} N m"),("Margin at 5 deg",f"{offset.offset_righting_margin_ratio:.2f} x")]
    y=.77
    for a,b in text:
        panel.text(.08,y,a,fontsize=9,color=PALETTE["gray_dark"]);panel.text(.92,y,b,fontsize=9,ha="right",fontweight="bold",color=PALETTE["navy"]);panel.plot([.08,.92],[y-.045,y-.045],color=PALETTE["grid"],linewidth=.7);y-=.13
    panel.text(.08,.10,"The equilibrium estimate is quasi-static. The point-mass offset is a conservative placement sensitivity, not a debris-slushing model.",fontsize=8.2,color=PALETTE["gray"],wrap=True)
    _save(fig,artifacts.offset_heel_budget_png,artifacts.offset_heel_budget_svg)


def _draw_dynamic_maneuvers(m: dict[str,ManeuverResult], artifacts: Phase1014Artifacts) -> None:
    apply_engineering_style();fig=plt.figure(figsize=(17.1,9.8));add_figure_header(fig,"Payload-sensitive surge, turn and heading manoeuvres","All response traces are logged from the same low-speed 3-DOF plant with changed mass properties and hydrostatic displacement.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.86,bottom=.10,hspace=.36,wspace=.28);axes=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    for key,label,color in [("step_dry","dry craft",PALETTE["blue"]),("step_full","full payload",PALETTE["green"])]:
        r=m[key];axes[0].plot(_array(r,"time_s"),_array(r,"speed_over_ground_mps"),label=label,color=color)
    axes[0].set_xlabel("Time [s]");axes[0].set_ylabel("Ground speed [m/s]");axes[0].set_title("Symmetric step response",loc="left");axes[0].legend(fontsize=8);style_axis(axes[0])
    for key,label,color in [("turn_dry_calm","dry / calm",PALETTE["blue"]),("turn_full_calm","full / calm",PALETTE["green"]),("turn_full_current","full / current",PALETTE["orange"])]:
        r=m[key];axes[1].plot(_array(r,"x_m"),_array(r,"y_m"),label=label,color=color)
    axes[1].set_xlabel("East x [m]");axes[1].set_ylabel("North y [m]");axes[1].set_title("Differential-thrust turn trajectories",loc="left");axes[1].legend(fontsize=8);axes[1].set_aspect("equal",adjustable="box");style_axis(axes[1])
    for key,label,color in [("turn_dry_calm","dry / calm",PALETTE["blue"]),("turn_full_calm","full / calm",PALETTE["green"]),("turn_full_current","full / current",PALETTE["orange"])]:
        r=m[key];axes[2].plot(_array(r,"time_s"),np.degrees(_array(r,"r_rps")),label=label,color=color)
    axes[2].set_xlabel("Time [s]");axes[2].set_ylabel("Yaw rate [deg/s]");axes[2].set_title("Turning yaw-rate response",loc="left");axes[2].legend(fontsize=8);style_axis(axes[2])
    for key,label,color in [("zigzag_dry","dry craft",PALETTE["blue"]),("zigzag_full","full payload",PALETTE["green"])]:
        r=m[key];axes[3].plot(_array(r,"time_s"),_array(r,"psi_deg"),label=label,color=color)
    axes[3].axhline(10,color=PALETTE["gray"],linestyle=":");axes[3].axhline(-10,color=PALETTE["gray"],linestyle=":");axes[3].set_xlabel("Time [s]");axes[3].set_ylabel("Heading [deg]");axes[3].set_title("State-triggered zig-zag response",loc="left");axes[3].legend(fontsize=8);style_axis(axes[3])
    _save(fig,artifacts.dynamic_maneuvers_png,artifacts.dynamic_maneuvers_svg)


def _draw_current_matrix(m: dict[str,ManeuverResult], artifacts: Phase1014Artifacts) -> None:
    apply_engineering_style();fig=plt.figure(figsize=(17.0,9.7));add_figure_header(fig,"Full-payload turning response with a documented low cross-current","The current case is a deterministic 0.02 m/s earth-frame disturbance. It visualises path displacement, while yaw remains driven by the same differential thrust.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.86,bottom=.10,hspace=.36,wspace=.28);a0=fig.add_subplot(grid[:,0]);a1=fig.add_subplot(grid[0,1]);a2=fig.add_subplot(grid[1,1]);
    calm=m["turn_full_calm"];current=m["turn_full_current"]
    a0.plot(_array(calm,"x_m"),_array(calm,"y_m"),label="calm",color=PALETTE["green"],linewidth=2);a0.plot(_array(current,"x_m"),_array(current,"y_m"),label="cross-current",color=PALETTE["orange"],linewidth=2);a0.arrow(.25,.30,0,.42,width=.008,head_width=.07,head_length=.08,length_includes_head=True,color=PALETTE["cyan"]);a0.text(.32,.55,"0.02 m/s current",fontsize=8,color=PALETTE["cyan"]);a0.set_xlabel("East x [m]");a0.set_ylabel("North y [m]");a0.set_title("Plan-view turn with and without current",loc="left");a0.legend(fontsize=8);a0.set_aspect("equal",adjustable="box");style_axis(a0)
    a1.plot(_array(calm,"time_s"),_array(calm,"y_m"),label="calm y",color=PALETTE["green"]);a1.plot(_array(current,"time_s"),_array(current,"y_m"),label="current y",color=PALETTE["orange"]);a1.set_xlabel("Time [s]");a1.set_ylabel("North position [m]");a1.set_title("Current-driven plan displacement",loc="left");a1.legend(fontsize=8);style_axis(a1)
    a2.axis("off"); a2.set_xlim(0,1); a2.set_ylim(0,1)
    a2.text(.05,.92,"Recorded metric comparison",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top")
    rows=[("Turn radius [m]",float(calm.metrics["turn_radius_m"]),float(current.metrics["turn_radius_m"])),("Final north position [m]",float(calm.metrics["final_y_m"]),float(current.metrics["final_y_m"])),("Peak yaw rate [rad/s]",float(calm.metrics["peak_yaw_rate_rps"]),float(current.metrics["peak_yaw_rate_rps"])),("Final ground speed [m/s]",float(calm.metrics["final_speed_mps"]),float(current.metrics["final_speed_mps"]))]
    a2.text(.54,.81,"calm",fontsize=8.5,fontweight="bold",ha="center",color=PALETTE["green"]); a2.text(.86,.81,"cross-current",fontsize=8.5,fontweight="bold",ha="center",color=PALETTE["orange"])
    yy=.72
    for label,calm_value,current_value in rows:
        a2.text(.06,yy,label,fontsize=8.8,color=PALETTE["gray_dark"]); a2.text(.54,yy,f"{calm_value:.3f}",fontsize=9,ha="center",fontweight="bold",color=PALETTE["green"]); a2.text(.86,yy,f"{current_value:.3f}",fontsize=9,ha="center",fontweight="bold",color=PALETTE["orange"]); a2.plot([.06,.94],[yy-.06,yy-.06],color=PALETTE["grid"],linewidth=.7); yy-=.16
    a2.text(.06,.10,"Values retain their own engineering units; no mixed-unit bar scale is used.",fontsize=8,color=PALETTE["gray"],wrap=True)
    _save(fig,artifacts.current_maneuver_matrix_png,artifacts.current_maneuver_matrix_svg)


def _draw_scorecard(static:list[PayloadStaticResult], m:dict[str,ManeuverResult], checks:list[dict[str,Any]], artifacts:Phase1014Artifacts)->None:
    apply_engineering_style();fig=plt.figure(figsize=(17,9.5));add_figure_header(fig,"Payload stability and manoeuvre verification scorecard","Acceptance checks are explicit engineering thresholds within the calm-water and low-current digital-twin boundary.")
    grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.86,bottom=.10,wspace=.28);ax=fig.add_subplot(grid[0,0]);panel=fig.add_subplot(grid[0,1]);panel.axis("off");panel.set_xlim(0,1);panel.set_ylim(0,1)
    names=[f"{row['check']}\n{row['case']}" for row in checks];passed=np.asarray([bool(row['passed']) for row in checks],dtype=int);colors=[PALETTE["green"] if x else PALETTE["orange"] for x in passed];ax.barh(np.arange(len(checks)),passed,color=colors);ax.set_xlim(0,1.1);ax.set_yticks(np.arange(len(checks)),names,fontsize=7.6);ax.set_xticks([0,1],["not passed","passed"]);ax.set_title("Acceptance ledger",loc="left");style_axis(ax)
    offset=next(x for x in static if x.payload_case.identifier=="full_port_offset");full=m["step_full"].metrics;turn=m["turn_full_current"].metrics
    panel.text(.06,.92,"Recorded governing values",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top");items=[("Full payload GM",f"{next(x for x in static if x.payload_case.identifier=='full_low_central').hydro_case.gm_m:.3f} m"),("Full payload freeboard",f"{next(x for x in static if x.payload_case.identifier=='full_low_central').hydro_case.freeboard_m:.3f} m"),("Port-offset estimated heel",f"{offset.offset_equilibrium_heel_deg:.2f} deg"),("Full-payload steady speed",f"{float(full['steady_speed_mps']):.3f} m/s"),("Current-turn peak yaw",f"{float(turn['peak_yaw_rate_rps']):.3f} rad/s"),("Accepted checks",f"{sum(bool(x['passed']) for x in checks)} / {len(checks)}")]
    y=.78
    for a,b in items:
        panel.text(.08,y,a,fontsize=9,color=PALETTE["gray_dark"]);panel.text(.92,y,b,fontsize=9,ha="right",fontweight="bold",color=PALETTE["navy"]);panel.plot([.08,.92],[y-.045,y-.045],color=PALETTE["grid"],linewidth=.7);y-=.115
    panel.text(.08,.10,"This scorecard does not replace wave, roll-transient, CFD, hardware or certification evidence. It makes the project model boundary explicit.",fontsize=8.2,color=PALETTE["gray"],wrap=True)
    _save(fig,artifacts.scorecard_png,artifacts.scorecard_svg)


def _draw_static_artifacts(static:list[PayloadStaticResult],m:dict[str,ManeuverResult],checks:list[dict[str,Any]],artifacts:Phase1014Artifacts)->None:
    _draw_stability_envelope(static,artifacts);_draw_offset_budget(static,artifacts);_draw_dynamic_maneuvers(m,artifacts);_draw_current_matrix(m,artifacts);_draw_scorecard(static,m,checks,artifacts)


def _render_stability(static:list[PayloadStaticResult], artifacts:Phase1014Artifacts, visual:dict[str,Any])->None:
    render=visual["render"];frames=int(render["frames"]);fps=int(render["fps"]);fig=plt.figure(figsize=(14.4,8.19));add_figure_header(fig,"Payload stability replay: draft, freeboard and righting response","Animated sensitivity replay of the logged hydrostatic payload cases. The section is conceptual and calm-water only.")
    grid=GridSpec(1,2,figure=fig,left=.06,right=.95,top=.84,bottom=.10,wspace=.25);a0=fig.add_subplot(grid[0,0]);a1=fig.add_subplot(grid[0,1]);cases=static
    def update(frame:int):
        fraction=frame/max(1,frames-1);idx=min(len(cases)-1,int(fraction*len(cases)));item=cases[idx];a0.clear();a1.clear();
        labels=[x.payload_case.identifier.replace("_","\n") for x in cases];x=np.arange(len(cases));a0.bar(x,[r.hydro_case.gm_m for r in cases],color=[_color_for_case(r.payload_case.identifier) for r in cases]);a0.bar([idx],[item.hydro_case.gm_m],color=PALETTE["navy"],alpha=.35);a0.axhline(.20,color=PALETTE["orange"],linestyle="--");a0.set_xticks(x,labels,fontsize=8);a0.set_ylim(0,max(r.hydro_case.gm_m for r in cases)*1.25);a0.set_ylabel("GM [m]");a0.set_title("Initial transverse stability",loc="left");style_axis(a0)
        heel=np.asarray([s.heel_deg for s in item.heel_curve]);moment=np.asarray([s.righting_moment_n_m for s in item.heel_curve]);a1.plot(heel,moment,color=_color_for_case(item.payload_case.identifier),linewidth=2.5);a1.axvline(item.offset_equilibrium_heel_deg,color=PALETTE["orange"],linestyle="--");a1.axvline(5,color=PALETTE["gray"],linestyle=":");a1.set_xlim(0,max(15,heel[-1]));a1.set_ylim(0,max(moment)*1.15);a1.set_xlabel("Heel [deg]");a1.set_ylabel("Righting moment [N m]");a1.set_title(item.payload_case.title,loc="left");style_axis(a1);fig.text(.07,.035,f"Case {idx+1}/{len(cases)} | payload={item.payload_case.payload_mass_kg:.2f} kg | KG={item.hydro_case.kg_m:.3f} m | freeboard={item.hydro_case.freeboard_m:.3f} m",fontsize=10,color=PALETTE["gray_dark"])
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps);_save_animation(animation,artifacts.stability_gif,artifacts.stability_mp4,fps,int(render["bitrate_kbps"]))


def _render_step(m:dict[str,ManeuverResult],artifacts:Phase1014Artifacts,visual:dict[str,Any])->None:
    render=visual["render"];frames=int(render["frames"]);fps=int(render["fps"]);dry=m["step_dry"];full=m["step_full"];ix=_sample_indices(len(dry.rows),frames);fig=plt.figure(figsize=(14.4,8.19));add_figure_header(fig,"Payload-sensitive symmetric thrust-step replay","The full-payload case has higher effective mass and slightly different resistance. Both traces come from the same logged 3-DOF plant.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.85,bottom=.10,hspace=.34,wspace=.26);a0=fig.add_subplot(grid[:,0]);a1=fig.add_subplot(grid[0,1]);a2=fig.add_subplot(grid[1,1]);td=_array(dry,"time_s");tf=_array(full,"time_s");
    def update(frame:int):
        k=ix[frame];a0.clear();a1.clear();a2.clear();a0.plot(td[:k+1],_array(dry,"speed_over_ground_mps")[:k+1],color=PALETTE["blue"],label="dry");a0.plot(tf[:k+1],_array(full,"speed_over_ground_mps")[:k+1],color=PALETTE["green"],label="full payload");a0.set_xlim(0,max(td[-1],tf[-1]));a0.set_ylim(0,.7);a0.set_xlabel("Time [s]");a0.set_ylabel("Ground speed [m/s]");a0.set_title("Surge response",loc="left");a0.legend(fontsize=8);style_axis(a0)
        a1.plot(td[:k+1],_array(dry,"x_m")[:k+1],color=PALETTE["blue"],label="dry");a1.plot(tf[:k+1],_array(full,"x_m")[:k+1],color=PALETTE["green"],label="full");a1.set_xlim(0,td[-1]);a1.set_xlabel("Time [s]");a1.set_ylabel("East position [m]");a1.set_title("Accumulated distance",loc="left");a1.legend(fontsize=8);style_axis(a1)
        a2.plot(td[:k+1],_array(dry,"total_thrust_n")[:k+1],color=PALETTE["blue"],label="total thrust");a2.plot(tf[:k+1],-_array(full,"x_drag_n")[:k+1],color=PALETTE["green"],label="full-payload drag magnitude");a2.set_xlim(0,td[-1]);a2.set_xlabel("Time [s]");a2.set_ylabel("Force [N]");a2.set_title("Force terms",loc="left");a2.legend(fontsize=8);style_axis(a2)
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps);_save_animation(animation,artifacts.step_gif,artifacts.step_mp4,fps,int(render["bitrate_kbps"]))


def _render_turn(m:dict[str,ManeuverResult],artifacts:Phase1014Artifacts,visual:dict[str,Any])->None:
    render=visual["render"];frames=int(render["frames"]);fps=int(render["fps"]);calm=m["turn_full_calm"];current=m["turn_full_current"];ix=_sample_indices(len(calm.rows),frames);fig=plt.figure(figsize=(14.4,8.19));add_figure_header(fig,"Full-payload differential turn under a documented low cross-current","The 0.02 m/s earth-frame current displaces the plan-view path. Twin-thruster yaw excitation remains recorded from the same 3-DOF plant.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.85,bottom=.10,hspace=.34,wspace=.26);a0=fig.add_subplot(grid[:,0]);a1=fig.add_subplot(grid[0,1]);a2=fig.add_subplot(grid[1,1]);
    def update(frame:int):
        k=ix[frame];a0.clear();a1.clear();a2.clear();a0.plot(_array(calm,"x_m")[:k+1],_array(calm,"y_m")[:k+1],color=PALETTE["green"],label="calm");a0.plot(_array(current,"x_m")[:k+1],_array(current,"y_m")[:k+1],color=PALETTE["orange"],label="cross-current");a0.scatter([_array(calm,"x_m")[k]],[ _array(calm,"y_m")[k]],color=PALETTE["green"],s=40);a0.scatter([_array(current,"x_m")[k]],[ _array(current,"y_m")[k]],color=PALETTE["orange"],s=40);a0.set_xlabel("East x [m]");a0.set_ylabel("North y [m]");a0.set_title("Plan-view turn",loc="left");a0.legend(fontsize=8);a0.set_aspect("equal",adjustable="box");style_axis(a0)
        t=_array(calm,"time_s");a1.plot(t[:k+1],np.degrees(_array(calm,"r_rps")[:k+1]),color=PALETTE["green"],label="calm yaw");a1.plot(t[:k+1],np.degrees(_array(current,"r_rps")[:k+1]),color=PALETTE["orange"],label="current yaw");a1.set_xlim(0,t[-1]);a1.set_xlabel("Time [s]");a1.set_ylabel("Yaw rate [deg/s]");a1.set_title("Yaw response",loc="left");a1.legend(fontsize=8);style_axis(a1)
        a2.plot(t[:k+1],_array(current,"y_m")[:k+1]-_array(calm,"y_m")[:k+1],color=PALETTE["cyan"],label="current minus calm y");a2.plot(t[:k+1],_array(current,"speed_over_ground_mps")[:k+1],color=PALETTE["navy"],label="current speed");a2.set_xlim(0,t[-1]);a2.set_xlabel("Time [s]");a2.set_ylabel("Displacement [m] / speed [m/s]");a2.set_title("Recorded current effect",loc="left");a2.legend(fontsize=8);style_axis(a2)
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps);_save_animation(animation,artifacts.turn_gif,artifacts.turn_mp4,fps,int(render["bitrate_kbps"]))


def _render_zigzag(m:dict[str,ManeuverResult],artifacts:Phase1014Artifacts,visual:dict[str,Any])->None:
    render=visual["render"];frames=int(render["frames"]);fps=int(render["fps"]);dry=m["zigzag_dry"];full=m["zigzag_full"];ix=_sample_indices(len(dry.rows),frames);fig=plt.figure(figsize=(14.4,8.19));add_figure_header(fig,"Dry and full-payload state-triggered zig-zag replay","The heading reversal is triggered by simulated heading crossings. It is not a time-scripted display sequence.")
    grid=GridSpec(2,2,figure=fig,left=.06,right=.95,top=.85,bottom=.10,hspace=.34,wspace=.26);a0=fig.add_subplot(grid[:,0]);a1=fig.add_subplot(grid[0,1]);a2=fig.add_subplot(grid[1,1]);t=_array(dry,"time_s")
    def update(frame:int):
        k=ix[frame];a0.clear();a1.clear();a2.clear();a0.plot(t[:k+1],_array(dry,"psi_deg")[:k+1],color=PALETTE["blue"],label="dry");a0.plot(t[:k+1],_array(full,"psi_deg")[:k+1],color=PALETTE["green"],label="full payload");a0.axhline(10,color=PALETTE["gray"],linestyle=":");a0.axhline(-10,color=PALETTE["gray"],linestyle=":");a0.set_xlim(0,t[-1]);a0.set_ylim(-14,14);a0.set_xlabel("Time [s]");a0.set_ylabel("Heading [deg]");a0.set_title("Heading reversals",loc="left");a0.legend(fontsize=8);style_axis(a0)
        a1.plot(t[:k+1],np.degrees(_array(dry,"r_rps")[:k+1]),color=PALETTE["blue"],label="dry");a1.plot(t[:k+1],np.degrees(_array(full,"r_rps")[:k+1]),color=PALETTE["green"],label="full payload");a1.set_xlim(0,t[-1]);a1.set_xlabel("Time [s]");a1.set_ylabel("Yaw rate [deg/s]");a1.set_title("Yaw-rate damping",loc="left");a1.legend(fontsize=8);style_axis(a1)
        a2.plot(t[:k+1],_array(dry,"port_thrust_n")[:k+1],color=PALETTE["blue"],label="port");a2.plot(t[:k+1],_array(dry,"starboard_thrust_n")[:k+1],color=PALETTE["orange"],label="starboard");a2.set_xlim(0,t[-1]);a2.set_xlabel("Time [s]");a2.set_ylabel("Thrust [N]");a2.set_title("Recorded differential allocation",loc="left");a2.legend(fontsize=8);style_axis(a2)
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps);_save_animation(animation,artifacts.zigzag_gif,artifacts.zigzag_mp4,fps,int(render["bitrate_kbps"]))


def render_one(kind:str)->None:
    ensure_runtime_directories();artifacts=_artifacts();static,m,_=run_payload_maneuver_suite();visual=load_visual_protocol()
    if kind=="stability":_render_stability(static,artifacts,visual)
    elif kind=="step":_render_step(m,artifacts,visual)
    elif kind=="turn":_render_turn(m,artifacts,visual)
    elif kind=="zigzag":_render_zigzag(m,artifacts,visual)
    else:raise ValueError(f"Unknown payload-maneuver render kind: {kind}")


def _manifest(media:list[Path],visual:dict[str,Any],output:Path)->dict[str,Any]:
    from PIL import Image
    expected=visual["render"];entries=[]
    for path in media:
        entry={"path":relative_to_root(path),"exists":path.exists(),"size_bytes":path.stat().st_size if path.exists() else 0}
        if path.suffix.lower()==".gif" and path.exists():
            with Image.open(path) as image:
                frames=int(getattr(image,"n_frames",1));duration=sum(int(image.seek(i) or image.info.get("duration",0)) for i in range(frames))/1000.0
                entry.update({"frames":frames,"duration_s":duration,"expected_duration_s":float(expected["expected_duration_s"]),"width_px":image.width,"height_px":image.height,"frame_count_ok":frames==int(expected["frames"]),"duration_ok":abs(duration-float(expected["expected_duration_s"]))<0.05,"resolution_ok":image.width>=int(expected["minimum_width_px"]) and image.height>=int(expected["minimum_height_px"])})
        if path.suffix.lower()==".mp4" and path.exists():
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration", "-of", "json", str(path)], capture_output=True, text=True)
            if probe.returncode == 0:
                try:
                    stream = json.loads(probe.stdout).get("streams", [])[0]
                    width = int(stream.get("width", 0)); height = int(stream.get("height", 0)); duration = float(stream.get("duration", 0.0))
                    entry.update({"width_px": width, "height_px": height, "duration_s": duration, "readable": True, "duration_ok": duration >= float(expected["expected_duration_s"]) - 0.30, "resolution_ok": width >= int(expected["minimum_width_px"]) and height >= int(expected["minimum_height_px"])})
                except (IndexError, TypeError, ValueError, json.JSONDecodeError):
                    entry.update({"readable": False, "duration_ok": False, "resolution_ok": False})
            else:
                entry.update({"readable": False, "duration_ok": False, "resolution_ok": False})
        entries.append(entry)
    gifs=[e for e in entries if e["path"].endswith(".gif")];mp4s=[e for e in entries if e["path"].endswith(".mp4")]
    payload={"identifier":"AQUASKIM-REF-PAYMAN-VIS-01","entries":entries,"required_animation_count":4,"observed_animation_count":len(gifs),"required_video_count":4,"observed_video_count":len(mp4s),"all_gif_frame_counts_ok":all(bool(e.get("frame_count_ok")) for e in gifs),"all_gif_durations_ok":all(bool(e.get("duration_ok")) for e in gifs),"all_gif_resolutions_ok":all(bool(e.get("resolution_ok")) for e in gifs),"all_mp4_exist":all(bool(e["exists"]) and int(e["size_bytes"])>0 for e in mp4s),"all_mp4_readable":all(bool(e.get("readable")) and bool(e.get("duration_ok")) and bool(e.get("resolution_ok")) for e in mp4s)}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");return payload


def _write_summary(static:list[PayloadStaticResult],m:dict[str,ManeuverResult],checks:list[dict[str,Any]],artifacts:Phase1014Artifacts,media_manifest:dict[str,Any]|None)->dict[str,Any]:
    full=next(x for x in static if x.payload_case.identifier=="full_low_central");offset=next(x for x in static if x.payload_case.identifier=="full_port_offset");summary={"identifier":"AQUASKIM-REF-PAYMAN-01","status":"PASS" if all(bool(x["passed"]) for x in checks) else "FAIL","full_payload":{"gm_m":full.hydro_case.gm_m,"freeboard_m":full.hydro_case.freeboard_m,"steady_speed_mps":float(m["step_full"].metrics["steady_speed_mps"])},"offset_payload":{"estimated_equilibrium_heel_deg":offset.offset_equilibrium_heel_deg,"righting_margin_at_5deg":offset.offset_righting_margin_ratio},"turn_current":{"current_magnitude_mps":math.hypot(*m["turn_full_current"].current_earth_mps),"peak_yaw_rate_rps":float(m["turn_full_current"].metrics["peak_yaw_rate_rps"]),"path_displacement_y_m":float(m["turn_full_current"].metrics["final_y_m"])-float(m["turn_full_calm"].metrics["final_y_m"])},"acceptance":{"passed":sum(bool(x["passed"]) for x in checks),"total":len(checks)},"media":media_manifest or {"rendered":False},"model_boundary":"Calm-water hydrostatic payload sensitivity and deterministic low-current 3-DOF manoeuvres. No wave, roll-transient, structural, sea-trial or current-estimation claim."}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    text="# Payload stability sensitivity and low-current manoeuvre verification\n\n## Scope\nThis evidence suite combines the project hydrostatic model with deterministic low-speed 3-DOF manoeuvres. It does not generate Word, a delivery ZIP or a release artifact.\n\n## Governing full-payload condition\n- Full payload GM: `%.3f m`.\n- Full payload freeboard: `%.3f m`.\n- Symmetric-step steady speed: `%.3f m/s`.\n\n## Port-offset sensitivity\n- Estimated quasi-static equilibrium heel: `%.2f deg`.\n- Righting-moment margin at 5 deg: `%.2f x`.\n\n## Low-current turn\n- Imposed current magnitude: `%.3f m/s`.\n- Current-induced final north displacement relative to calm turn: `%.3f m`.\n- Peak yaw rate: `%.3f rad/s`.\n\n## Acceptance and media QA\n- Acceptance checks passed: `%d/%d`.\n- Required GIF / observed GIF: `%s / %s`.\n- Required MP4 / observed MP4: `%s / %s`.\n\n## Model boundary\nThe payload offset is evaluated as a quasi-static point-mass heeling sensitivity. Manoeuvres use the documented low-speed 3-DOF sheltered-basin plant. These results do not establish wave response, roll transients, structural strength, sea-trial performance or physical current estimation.\n" % (full.hydro_case.gm_m,full.hydro_case.freeboard_m,float(m["step_full"].metrics["steady_speed_mps"]),offset.offset_equilibrium_heel_deg,offset.offset_righting_margin_ratio,summary["turn_current"]["current_magnitude_mps"],summary["turn_current"]["path_displacement_y_m"],summary["turn_current"]["peak_yaw_rate_rps"],summary["acceptance"]["passed"],summary["acceptance"]["total"],(media_manifest or {}).get("required_animation_count","not rendered"),(media_manifest or {}).get("observed_animation_count","not rendered"),(media_manifest or {}).get("required_video_count","not rendered"),(media_manifest or {}).get("observed_video_count","not rendered"))
    artifacts.summary_markdown.write_text(text,encoding="utf-8")
    return summary


def _record(artifacts:Phase1014Artifacts,summary:dict[str,Any])->Path:
    d=_dirs();run_id="phase10_14_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ");run=d["records"]/run_id;(run/"artifacts").mkdir(parents=True,exist_ok=True);(run/"inputs").mkdir(parents=True,exist_ok=True)
    for source in [project_root()/"config"/"reference_payload_maneuver_validation.yaml",project_root()/"config"/"reference_payload_maneuver_visualisation.yaml",project_root()/"config"/"reference_design.yaml"]:
        shutil.copy2(source,run/"inputs"/source.name)
    hashes={}
    for path in artifacts.__dict__.values():
        if isinstance(path,Path) and path.exists():
            target=run/"artifacts"/path.name;shutil.copy2(path,target);hashes[relative_to_root(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (run/"artifact_manifest.json").write_text(json.dumps({"run_id":run_id,"hashes":hashes,"summary":summary},ensure_ascii=False,indent=2),encoding="utf-8")
    env={"python":sys.version,"executable":sys.executable,"timestamp_utc":datetime.now(timezone.utc).isoformat()}
    try:env["pip_freeze"]=subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True)
    except Exception as exc:env["pip_freeze_error"]=repr(exc)
    (run/"environment_snapshot.json").write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding="utf-8")
    handoff=d["handoffs"] / "PHASE10_14_LATEST_HANDOFF.md";handoff.write_text("# Payload stability and manoeuvre evidence handoff\n\n- Run ID: `%s`\n- Payload hydrostatics, offset righting budget and low-current manoeuvre media were generated from the fixed reference design.\n- No Word report, delivery ZIP or release build was invoked.\n- Evidence: `%s`\n"%(run_id,relative_to_root(run)),encoding="utf-8")
    return run


def run_phase10_14(*,record:bool=True,render:bool=False,require_media:bool=False)->dict[str,Any]:
    ensure_runtime_directories();artifacts=_artifacts();static,m,protocol=run_payload_maneuver_suite();checks=assess_suite(static,m,protocol)
    _write_csv(artifacts.static_cases_csv,[x.as_row() for x in static])
    heel_rows=[]
    for item in static:
        for state in item.heel_curve:
            heel_rows.append({"payload_case":item.payload_case.identifier,**state.as_row(item.payload_case.identifier)})
    _write_csv(artifacts.heel_curve_csv,heel_rows)
    metric_rows=[];time_rows=[]
    for name,result in m.items():
        metric_rows.append({"result_key":name,"maneuver":result.name,"payload_case":result.payload_case.identifier,"current_x_mps":result.current_earth_mps[0],"current_y_mps":result.current_earth_mps[1],**result.metrics})
        time_rows.extend([{**row,"result_key":name} for row in result.rows])
    _write_csv(artifacts.maneuver_metrics_csv,metric_rows);_write_csv(artifacts.maneuver_timeseries_csv,time_rows);_write_csv(artifacts.acceptance_checks_csv,checks)
    _draw_static_artifacts(static,m,checks,artifacts)
    visual=load_visual_protocol()
    if render:
        _render_stability(static,artifacts,visual);_render_step(m,artifacts,visual);_render_turn(m,artifacts,visual);_render_zigzag(m,artifacts,visual)
    media=[artifacts.stability_gif,artifacts.stability_mp4,artifacts.step_gif,artifacts.step_mp4,artifacts.turn_gif,artifacts.turn_mp4,artifacts.zigzag_gif,artifacts.zigzag_mp4]
    if require_media and not all(path.exists() and path.stat().st_size>0 for path in media):
        raise FileNotFoundError("Payload-manoeuvre media set is incomplete; render all GIF/MP4 files before finalizing evidence.")
    manifest=_manifest(media,visual,artifacts.visual_quality_manifest_json) if require_media or render else None
    if require_media:
        if not (manifest["all_gif_frame_counts_ok"] and manifest["all_gif_durations_ok"] and manifest["all_gif_resolutions_ok"] and manifest["all_mp4_exist"] and manifest["all_mp4_readable"]):raise RuntimeError("Payload-manoeuvre media quality checks did not pass.")
        write_animation_audit_sheet([artifacts.stability_gif,artifacts.step_gif,artifacts.turn_gif,artifacts.zigzag_gif],artifacts.contact_sheet_png,samples_per_animation=int(visual["render"]["contact_sheet_samples"]))
    summary=_write_summary(static,m,checks,artifacts,manifest)
    if summary["status"]!="PASS":raise RuntimeError("Payload-manoeuvre acceptance checks failed.")
    run_dir=_record(artifacts,summary) if record and require_media else None
    return {"artifacts":artifacts,"summary":summary,"checks":checks,"run_dir":run_dir}


def print_phase10_14_summary(result:dict[str,Any])->None:
    artifacts:Phase1014Artifacts=result["artifacts"];print("="*72);print("AquaSkim-Sim | Payload Stability and Low-current Manoeuvre Validation");print("="*72);print(f"Stability map : {relative_to_root(artifacts.stability_envelope_png)}");print(f"Contact sheet : {relative_to_root(artifacts.contact_sheet_png)}");print(f"Visual QA     : {relative_to_root(artifacts.visual_quality_manifest_json)}");print(f"Evidence      : {relative_to_root(result['run_dir']) if result['run_dir'] else 'not recorded'}");print("Status        : PASS");print("="*72)


if __name__ == "__main__":
    print_phase10_14_summary(run_phase10_14(record=True,render=True,require_media=True))
