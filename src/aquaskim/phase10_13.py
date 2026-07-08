"""Current-aware dynamic manoeuvre and gain-sensitivity evidence build.

The build is deliberately downstream of source-integrity, reference-fidelity and
operating-envelope checks.  It produces bounded control evidence only; Word,
delivery ZIP and release artifacts remain disabled.
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
import numpy as np
import yaml

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.control_robustness import (
    TrackHoldResult,
    assess_control_suite,
    load_control_robustness,
    run_control_suite,
)
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import project_root
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class Phase1013Artifacts:
    track_comparison_png: Path
    track_comparison_svg: Path
    control_response_png: Path
    control_response_svg: Path
    sensitivity_map_png: Path
    sensitivity_map_svg: Path
    scorecard_png: Path
    scorecard_svg: Path
    validation_matrix_png: Path
    validation_matrix_svg: Path
    case_metrics_csv: Path
    sensitivity_metrics_csv: Path
    nominal_timeseries_csv: Path
    events_csv: Path
    acceptance_checks_csv: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest_json: Path
    comparison_gif: Path
    comparison_mp4: Path
    response_gif: Path
    response_mp4: Path
    sensitivity_gif: Path
    sensitivity_mp4: Path
    force_gif: Path
    force_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _dirs() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": DIRECTORIES["figures"], "tables": DIRECTORIES["tables"], "logs": DIRECTORIES["logs"],
        "reports": DIRECTORIES["reports"], "animations": DIRECTORIES["animations"], "videos": DIRECTORIES["videos"],
        "records": root / "records" / "phases" / "phase_10_13" / "runs", "handoffs": DIRECTORIES["handoffs"],
    }


def _read_visual_protocol() -> dict[str, Any]:
    path = project_root() / "config" / "reference_control_visualisation.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    protocol = data.get("reference_control_visualisation") if isinstance(data, dict) else None
    if not isinstance(protocol, dict) or not isinstance(protocol.get("render"), dict):
        raise ValueError("reference_control_visualisation.yaml requires reference_control_visualisation.render.")
    return protocol


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = ["status"]; rows = [{"status": "NO_ROWS"}]
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
    gif.parent.mkdir(parents=True, exist_ok=True); mp4.parent.mkdir(parents=True, exist_ok=True)
    animation.save(gif, writer=PillowWriter(fps=fps))
    animation.save(mp4, writer=FFMpegWriter(fps=fps, bitrate=bitrate))
    plt.close(animation._fig)


def _array(result: TrackHoldResult, key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, 0.0)) for row in result.rows], dtype=float)


def _indices(result: TrackHoldResult, frames: int) -> np.ndarray:
    return np.linspace(0, len(result.rows) - 1, max(2, int(frames))).round().astype(int)


def _draw_track_comparison(open_loop: TrackHoldResult, nominal: TrackHoldResult, partial: TrackHoldResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(17.2, 9.8))
    add_figure_header(fig, "Cross-current drift and current-aware path holding", "The reference line is earth-fixed. Current-aware guidance commands a crab angle and the feedback controller removes residual cross-track error.")
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.86, bottom=.10, hspace=.35, wspace=.28)
    ax_map, ax_cross, ax_track, panel = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    cases = [(open_loop, PALETTE["orange"], "open-loop"), (partial, PALETTE["cyan"], "half feedforward"), (nominal, PALETTE["blue"], "current-aware nominal")]
    for result, color, label in cases:
        ax_map.plot(_array(result, "x_m"), _array(result, "y_m"), color=color, linewidth=1.8, label=label)
        ax_cross.plot(_array(result, "time_s"), _array(result, "cross_track_error_m"), color=color, linewidth=1.5, label=label)
        ax_track.plot(_array(result, "time_s"), _array(result, "speed_over_ground_mps"), color=color, linewidth=1.4, label=label)
    ax_map.axhline(0, color=PALETTE["gray"], linestyle="--", linewidth=.9, label="earth-fixed reference line")
    ax_map.set_xlabel("East x [m]"); ax_map.set_ylabel("North y [m]"); ax_map.set_title("Plan-view path holding", loc="left"); ax_map.legend(fontsize=8); style_axis(ax_map); ax_map.set_aspect("auto"); ax_map.text(.02, .96, "Vertical display scale expanded for drift visibility", transform=ax_map.transAxes, fontsize=7.4, color=PALETTE["gray"], va="top")
    ax_cross.axhline(0, color=PALETTE["gray"], linewidth=.8); ax_cross.set_xlabel("Time [s]"); ax_cross.set_ylabel("Cross-track error [m]"); ax_cross.set_title("Cross-track response", loc="left"); ax_cross.legend(fontsize=8); style_axis(ax_cross)
    ax_track.axhline(float(nominal.rows[-1]["desired_ground_speed_mps"]), color=PALETTE["gray"], linestyle="--", linewidth=.9, label="command")
    ax_track.set_xlabel("Time [s]"); ax_track.set_ylabel("Ground speed [m/s]"); ax_track.set_title("Translation response", loc="left"); ax_track.legend(fontsize=8); style_axis(ax_track)
    panel.axis("off"); panel.set_xlim(0, 1); panel.set_ylim(0, 1)
    lines = [
        ("Open-loop final drift", f"{open_loop.metrics['final_abs_cross_track_error_m']:.3f} m"),
        ("Current-aware final error", f"{nominal.metrics['final_abs_cross_track_error_m']:.3f} m"),
        ("Current-aware p95 error", f"{nominal.metrics['p95_abs_cross_track_error_m']:.3f} m"),
        ("Mean crab demand", f"{nominal.metrics['mean_abs_crab_angle_deg']:.2f} deg"),
        ("Validated current", f"{nominal.metrics['current_magnitude_mps']:.3f} m/s"),
    ]
    panel.text(.06, .92, "Recorded comparison ledger", fontsize=12, fontweight="bold", color=PALETTE["navy"], va="top")
    y = .79
    for label, value in lines:
        panel.text(.08, y, label, fontsize=9, color=PALETTE["gray_dark"])
        panel.text(.94, y, value, fontsize=9, ha="right", fontweight="bold", color=PALETTE["navy"])
        panel.plot([.08, .94], [y-.045, y-.045], color=PALETTE["grid"], linewidth=.6)
        y -= .13
    panel.text(.08, .12, "The open-loop case is a plant comparison, not a validated mission claim.", fontsize=8.2, color=PALETTE["gray"], wrap=True)
    _save(fig, png, svg)


def _draw_control_response(result: TrackHoldResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    t = _array(result, "time_s")
    fig = plt.figure(figsize=(17.0, 10.0))
    add_figure_header(fig, "Current-aware heading, yaw and twin-thruster response", "All traces come from the fixed current-aware path-holding manoeuvre using the reference 3-DOF plant and documented gain set.")
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.86, bottom=.10, hspace=.34, wspace=.28)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    axes[0].plot(t, _array(result, "desired_heading_deg"), label="water-relative course")
    axes[0].plot(t, _array(result, "psi_deg"), label="craft heading")
    axes[0].plot(t, _array(result, "ground_track_heading_deg"), linestyle="--", label="ground-track request")
    axes[0].set_ylabel("Heading [deg]"); axes[0].set_title("Current-aware course command", loc="left"); axes[0].legend(fontsize=8); style_axis(axes[0])
    axes[1].plot(t, _array(result, "heading_error_deg"), label="heading error")
    axes[1].plot(t, _array(result, "crab_angle_deg"), label="crab command")
    axes[1].plot(t, np.degrees(_array(result, "r_rps")), label="yaw rate [deg/s]")
    axes[1].axhline(0, linewidth=.8); axes[1].set_ylabel("Angle / rate"); axes[1].set_title("Heading correction demand", loc="left"); axes[1].legend(fontsize=8); style_axis(axes[1])
    axes[2].plot(t, _array(result, "port_thrust_n"), label="port thrust")
    axes[2].plot(t, _array(result, "starboard_thrust_n"), label="starboard thrust")
    axes[2].plot(t, _array(result, "yaw_moment_n_m"), linestyle="--", label="yaw moment")
    axes[2].set_xlabel("Time [s]"); axes[2].set_ylabel("Thrust [N] / moment [N m]"); axes[2].set_title("Differential actuation", loc="left"); axes[2].legend(fontsize=8); style_axis(axes[2])
    axes[3].plot(t, _array(result, "cross_track_error_m"), label="cross-track error")
    axes[3].plot(t, _array(result, "speed_over_ground_mps"), label="ground speed")
    axes[3].plot(t, _array(result, "u_relative_water_mps"), label="surge relative to water")
    axes[3].set_xlabel("Time [s]"); axes[3].set_ylabel("m / m s⁻¹"); axes[3].set_title("Path error and translation", loc="left"); axes[3].legend(fontsize=8); style_axis(axes[3])
    _save(fig, png, svg)


def _draw_sensitivity_map(results: list[TrackHoldResult], png: Path, svg: Path) -> None:
    apply_engineering_style()
    kp = sorted({float(item.metrics["heading_kp_scale"]) for item in results})
    kd = sorted({float(item.metrics["heading_kd_scale"]) for item in results})
    cross = np.full((len(kp), len(kd)), np.nan); heading = np.full_like(cross, np.nan)
    for item in results:
        i = kp.index(float(item.metrics["heading_kp_scale"])); j = kd.index(float(item.metrics["heading_kd_scale"]))
        cross[i, j] = float(item.metrics["p95_abs_cross_track_error_m"]); heading[i, j] = float(item.metrics["p95_abs_heading_error_deg"])
    fig = plt.figure(figsize=(16.8, 8.8))
    add_figure_header(fig, "Bounded heading-gain sensitivity under the validated cross-current", "A nine-point grid around the documented reference gains. Values are deterministic response metrics, not an automatic tuning claim.")
    grid = GridSpec(1, 3, figure=fig, left=.06, right=.95, top=.84, bottom=.16, width_ratios=[1, 1, .95], wspace=.30)
    for ax, data, title, label, fmt in [
        (fig.add_subplot(grid[0, 0]), cross, "p95 absolute cross-track error", "Error [m]", ".3f"),
        (fig.add_subplot(grid[0, 1]), heading, "p95 absolute heading error", "Error [deg]", ".2f"),
    ]:
        image = ax.imshow(data, origin="lower", aspect="auto", cmap="Blues")
        ax.set_xticks(range(len(kd)), [f"{value:.2f}" for value in kd]); ax.set_yticks(range(len(kp)), [f"{value:.2f}" for value in kp])
        ax.set_xlabel("Heading Kd scale"); ax.set_ylabel("Heading Kp scale"); ax.set_title(title, loc="left")
        for i in range(len(kp)):
            for j in range(len(kd)):
                ax.text(j, i, format(float(data[i, j]), fmt), ha="center", va="center", fontsize=9, color=PALETTE["navy"])
        fig.colorbar(image, ax=ax, fraction=.046, pad=.04, label=label)
    panel = fig.add_subplot(grid[0, 2]); panel.axis("off"); panel.set_xlim(0,1); panel.set_ylim(0,1)
    nominal = next(item for item in results if abs(float(item.metrics["heading_kp_scale"]) - 1.0) < 1e-12 and abs(float(item.metrics["heading_kd_scale"]) - 1.0) < 1e-12)
    panel.text(.05, .92, "Sensitivity interpretation", fontsize=12, fontweight="bold", color=PALETTE["navy"], va="top")
    text = (
        f"Grid: {len(kp)} × {len(kd)} deterministic samples\n\n"
        f"Nominal p95 cross-track: {nominal.metrics['p95_abs_cross_track_error_m']:.3f} m\n"
        f"Nominal p95 heading: {nominal.metrics['p95_abs_heading_error_deg']:.2f} deg\n\n"
        "All cases use the same imposed current and plant. The grid describes local robustness around the documented gains; it does not establish global optimality."
    )
    panel.text(.05, .77, text, fontsize=9.1, color=PALETTE["gray_dark"], va="top", wrap=True)
    _save(fig, png, svg)


def _draw_scorecard(cases: list[TrackHoldResult], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(17.0, 8.6))
    add_figure_header(fig, "Current-aware control comparison scorecard", "Open-loop drift is retained to demonstrate the plant disturbance. The nominal current-aware case is the validated control reference.")
    grid = GridSpec(1, 2, figure=fig, left=.06, right=.95, top=.84, bottom=.14, width_ratios=[1.15,.85], wspace=.30)
    ax = fig.add_subplot(grid[0, 0])
    labels = [item.case.title for item in cases]
    metrics = ["final_abs_cross_track_error_m", "p95_abs_cross_track_error_m", "p95_abs_heading_error_deg"]
    x = np.arange(len(labels)); width = .23
    for idx, key in enumerate(metrics):
        values = [float(item.metrics[key]) for item in cases]
        ax.bar(x + (idx-1)*width, values, width, label=key.replace("_", " "))
    ax.set_xticks(x, labels, rotation=14, ha="right"); ax.set_ylabel("Recorded response metric"); ax.set_title("Error comparison", loc="left"); ax.legend(fontsize=7.5); style_axis(ax)
    tab = fig.add_subplot(grid[0, 1]); tab.axis("off")
    table_rows = [["Case", "Final x-track", "p95 x-track", "Mean speed"]]
    for item in cases:
        table_rows.append([item.case.identifier, f"{item.metrics['final_abs_cross_track_error_m']:.3f} m", f"{item.metrics['p95_abs_cross_track_error_m']:.3f} m", f"{item.metrics['mean_ground_speed_mps']:.3f} m/s"])
    table = tab.table(cellText=table_rows[1:], colLabels=table_rows[0], loc="center", cellLoc="left", colLoc="left")
    table.auto_set_font_size(False); table.set_fontsize(8.1); table.scale(1.15, 2.05)
    tab.set_title("Recorded control ledger", loc="left", fontsize=11)
    _save(fig, png, svg)


def _draw_validation_matrix(checks: list[dict[str, Any]], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.6, 8.2))
    add_figure_header(fig, "Control robustness acceptance matrix", "Every acceptance condition is calculated from logged dynamics. This is a bounded low-current verification, not a final release gate.")
    ax = fig.add_axes([.06,.15,.89,.66]); ax.axis("off")
    rows = [[item["check"], str(item["observed"]), item["criterion"], item["status"]] for item in checks]
    table = ax.table(cellText=rows, colLabels=["Check", "Observed", "Criterion", "Status"], loc="center", cellLoc="left", colLoc="left", colWidths=[.34,.20,.30,.12])
    table.auto_set_font_size(False); table.set_fontsize(8.8); table.scale(1.0, 2.05)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor(PALETTE["sky"]); cell.set_text_props(weight="bold", color=PALETTE["navy"])
        elif col == 3:
            cell.set_facecolor(PALETTE["green_light"] if rows[row-1][3] == "PASS" else PALETTE["orange_light"])
    _save(fig, png, svg)


def _render_comparison(open_loop: TrackHoldResult, nominal: TrackHoldResult, gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style(); render = visual["render"]; frames = int(render["frames"]); fps=int(render["fps"])
    oi, ni = _indices(open_loop, frames), _indices(nominal, frames)
    fig = plt.figure(figsize=(14.4, 8.19)); grid = GridSpec(1,2,figure=fig,left=.06,right=.96,top=.86,bottom=.10,wspace=.28)
    add_figure_header(fig,"Open-loop drift versus current-aware path holding","Both markers evolve over the same imposed northward current; only the blue case applies current-aware course feedforward and feedback correction.")
    ax, panel = fig.add_subplot(grid[0,0]), fig.add_subplot(grid[0,1])
    ax.axhline(0,color=PALETTE["gray"],linestyle="--",linewidth=.8,label="earth-fixed reference")
    xlim = max(float(_array(open_loop,"x_m")[-1]), float(_array(nominal,"x_m")[-1])) + .7; ylim = max(1.0, float(np.max(np.abs(np.concatenate([_array(open_loop,"y_m"), _array(nominal,"y_m")])))) + .25)
    ax.set_xlim(-.3,xlim); ax.set_ylim(-ylim,ylim); ax.set_aspect("auto"); ax.set_xlabel("East x [m]"); ax.text(.02,.96,"Vertical display scale expanded for drift visibility",transform=ax.transAxes,fontsize=7.2,color=PALETTE['gray'],va='top'); ax.set_ylabel("North y [m]"); ax.set_title("Trajectory comparison",loc="left"); style_axis(ax)
    open_path, = ax.plot([],[],color=PALETTE["orange"],linewidth=1.7,label="open-loop"); comp_path, = ax.plot([],[],color=PALETTE["blue"],linewidth=1.9,label="current-aware")
    open_dot=ax.scatter([],[],color=PALETTE["orange"],s=34,zorder=5); comp_dot=ax.scatter([],[],color=PALETTE["blue"],s=34,zorder=5); ax.legend(fontsize=8)
    panel.axis("off"); panel.set_xlim(0,1); panel.set_ylim(0,1); live=panel.text(.07,.88,"",va="top",fontsize=10,color=PALETTE["gray_dark"])
    def update(frame: int):
        a,b=int(oi[frame]),int(ni[frame]); orow=open_loop.rows[a]; nrow=nominal.rows[b]
        open_path.set_data(_array(open_loop,"x_m")[:a+1],_array(open_loop,"y_m")[:a+1]); comp_path.set_data(_array(nominal,"x_m")[:b+1],_array(nominal,"y_m")[:b+1])
        open_dot.set_offsets(np.asarray([[float(orow['x_m']),float(orow['y_m'])]])); comp_dot.set_offsets(np.asarray([[float(nrow['x_m']),float(nrow['y_m'])]]))
        live.set_text(f"t = {float(nrow['time_s']):.1f} s\n\nOPEN LOOP\nCross-track = {float(orow['cross_track_error_m']):+.3f} m\nHeading = {float(orow['psi_deg']):+.2f} deg\n\nCURRENT-AWARE\nCross-track = {float(nrow['cross_track_error_m']):+.3f} m\nCrab command = {float(nrow['crab_angle_deg']):+.2f} deg\nHeading error = {float(nrow['heading_error_deg']):+.2f} deg\nGround speed = {float(nrow['speed_over_ground_mps']):.3f} m/s")
        return [open_path,comp_path,open_dot,comp_dot,live]
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False); _save_animation(animation,gif,mp4,fps,int(render["mp4_bitrate_kbps"]))


def _render_response(result: TrackHoldResult, gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style(); render=visual["render"]; frames=int(render["frames"]); fps=int(render["fps"]); indices=_indices(result,frames); t=_array(result,"time_s")
    fig=plt.figure(figsize=(14.8,8.5));grid=GridSpec(2,2,figure=fig,left=.06,right=.96,top=.86,bottom=.10,hspace=.36,wspace=.30)
    add_figure_header(fig,"Current-aware telemetry replay","The moving cursor exposes the logged relationship among path error, heading correction and twin-thruster demand.")
    ax_map,ax_cross,ax_head,ax_force=[fig.add_subplot(grid[i,j]) for i in range(2) for j in range(2)]
    x=_array(result,"x_m");y=_array(result,"y_m");ax_map.axhline(0,color=PALETTE["gray"],linestyle="--",linewidth=.8);ax_map.set_xlim(-.2,float(x[-1])+.5);bound=max(.55,float(np.max(np.abs(y)))+.15);ax_map.set_ylim(-bound,bound);ax_map.set_aspect("auto");ax_map.set_xlabel("East x [m]");ax_map.text(.02,.96,"Vertical display scale expanded for drift visibility",transform=ax_map.transAxes,fontsize=7.0,color=PALETTE['gray'],va='top');ax_map.set_ylabel("North y [m]");ax_map.set_title("Ground track",loc="left");style_axis(ax_map)
    path,=ax_map.plot([],[],color=PALETTE["blue"],linewidth=1.9);dot=ax_map.scatter([],[],color=PALETTE["green"],s=35)
    for ax, key, label, title in [(ax_cross,"cross_track_error_m","Cross-track error [m]","Path error"),(ax_head,"heading_error_deg","Heading error [deg]","Heading response")]:
        ax.plot(t,_array(result,key),color=PALETTE["blue"],linewidth=1.25);ax.axhline(0,color=PALETTE["gray"],linewidth=.8);ax.set_xlabel("Time [s]");ax.set_ylabel(label);ax.set_title(title,loc="left");style_axis(ax)
    c1=ax_cross.axvline(0,color=PALETTE["orange"],linewidth=1.2);c2=ax_head.axvline(0,color=PALETTE["orange"],linewidth=1.2)
    ax_force.plot(t,_array(result,"port_thrust_n"),label="port");ax_force.plot(t,_array(result,"starboard_thrust_n"),label="starboard");ax_force.set_xlabel("Time [s]");ax_force.set_ylabel("Thrust [N]");ax_force.set_title("Twin-thruster demand",loc="left");ax_force.legend(fontsize=8);style_axis(ax_force);c3=ax_force.axvline(0,color=PALETTE["orange"],linewidth=1.2)
    def update(frame:int):
        i=int(indices[frame]);path.set_data(x[:i+1],y[:i+1]);dot.set_offsets(np.asarray([[x[i],y[i]]])); now=t[i];c1.set_xdata([now,now]);c2.set_xdata([now,now]);c3.set_xdata([now,now]);return [path,dot,c1,c2,c3]
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False);_save_animation(animation,gif,mp4,fps,int(render["mp4_bitrate_kbps"]))


def _render_sensitivity(results: list[TrackHoldResult], gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style();render=visual["render"];frames=int(render["frames"]);fps=int(render["fps"])
    kp=sorted({float(item.metrics['heading_kp_scale']) for item in results});kd=sorted({float(item.metrics['heading_kd_scale']) for item in results});ordered=sorted(results,key=lambda x:(x.metrics['heading_kp_scale'],x.metrics['heading_kd_scale']))
    fig=plt.figure(figsize=(14.4,8.19));grid=GridSpec(1,2,figure=fig,left=.06,right=.96,top=.86,bottom=.12,wspace=.32)
    add_figure_header(fig,"Bounded controller-gain sweep replay","Cells appear in deterministic evaluation order; each value is a logged p95 cross-track response from the same current and plant.")
    ax, panel=fig.add_subplot(grid[0,0]),fig.add_subplot(grid[0,1]);matrix=np.full((len(kp),len(kd)),np.nan);image=ax.imshow(matrix,origin='lower',vmin=0,vmax=max(float(item.metrics['p95_abs_cross_track_error_m']) for item in results)*1.15,cmap='Blues');ax.set_xticks(range(len(kd)),[f'{v:.2f}' for v in kd]);ax.set_yticks(range(len(kp)),[f'{v:.2f}' for v in kp]);ax.set_xlabel('Heading Kd scale');ax.set_ylabel('Heading Kp scale');ax.set_title('p95 cross-track error [m]',loc='left');fig.colorbar(image,ax=ax,fraction=.046,pad=.04);style_axis(ax,grid=False);panel.axis('off');panel.set_xlim(0,1);panel.set_ylim(0,1);live=panel.text(.06,.88,'',va='top',fontsize=10,color=PALETTE['gray_dark']); progress=panel.text(.06,.08,'',va='bottom',fontsize=8.5,color=PALETTE['gray'])
    def update(frame:int):
        count=max(1,min(len(ordered),int(round((frame+1)*len(ordered)/frames))))
        matrix[:]=np.nan
        for item in ordered[:count]:
            i=kp.index(float(item.metrics['heading_kp_scale']));j=kd.index(float(item.metrics['heading_kd_scale']));matrix[i,j]=float(item.metrics['p95_abs_cross_track_error_m'])
        image.set_data(matrix);active=ordered[count-1];live.set_text(f"Samples completed: {count}/{len(ordered)}\n\nKp scale = {active.metrics['heading_kp_scale']:.2f}\nKd scale = {active.metrics['heading_kd_scale']:.2f}\np95 cross-track = {active.metrics['p95_abs_cross_track_error_m']:.3f} m\np95 heading error = {active.metrics['p95_abs_heading_error_deg']:.2f} deg\nmean ground speed = {active.metrics['mean_ground_speed_mps']:.3f} m/s\n\nGrid values are sensitivity evidence, not a tuning optimizer.")
        # A changing progress indicator intentionally prevents GIF encoders from
        # collapsing visually identical intermediate frames in the sweep replay.
        progress.set_text(f"replay frame {frame + 1}/{frames}")
        return [image,live,progress]
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False);_save_animation(animation,gif,mp4,fps,int(render['mp4_bitrate_kbps']))


def _render_force(result: TrackHoldResult, gif: Path, mp4: Path, visual: dict[str, Any]) -> None:
    apply_engineering_style();render=visual['render'];frames=int(render['frames']);fps=int(render['fps']);indices=_indices(result,frames);t=_array(result,'time_s');x=_array(result,'x_m');y=_array(result,'y_m')
    fig=plt.figure(figsize=(14.4,8.19));grid=GridSpec(1,2,figure=fig,left=.06,right=.96,top=.86,bottom=.10,wspace=.30)
    add_figure_header(fig,"Current-aware force and yaw-moment replay","The force arrows are derived from the logged twin-thruster commands; their imbalance creates the recorded yaw moment.")
    ax,panel=fig.add_subplot(grid[0,0]),fig.add_subplot(grid[0,1]);ax.axhline(0,color=PALETTE['gray'],linestyle='--',linewidth=.8);ax.set_xlim(-.2,float(x[-1])+.5);bound=max(.55,float(np.max(np.abs(y)))+.15);ax.set_ylim(-bound,bound);ax.set_aspect('equal',adjustable='box');ax.set_xlabel('East x [m]');ax.set_ylabel('North y [m]');ax.set_title('Path and instantaneous force vectors',loc='left');style_axis(ax)
    path,=ax.plot([],[],color=PALETTE['blue'],linewidth=1.8);dot=ax.scatter([],[],color=PALETTE['green'],s=36);arrows=[];live=panel.text(.06,.88,'',va='top',fontsize=10,color=PALETTE['gray_dark']);panel.axis('off');panel.set_xlim(0,1);panel.set_ylim(0,1)
    def update(frame:int):
        nonlocal arrows
        for artist in arrows: artist.remove()
        arrows=[];i=int(indices[frame]);path.set_data(x[:i+1],y[:i+1]);dot.set_offsets(np.asarray([[x[i],y[i]]]))
        psi=math.radians(float(result.rows[i]['psi_deg']));forward=np.asarray([math.cos(psi),math.sin(psi)]);lateral=np.asarray([-math.sin(psi),math.cos(psi)])
        port=float(result.rows[i]['port_thrust_n']);star=float(result.rows[i]['starboard_thrust_n']);
        for side,thrust,color in [(-1,port,PALETTE['orange']), (1,star,PALETTE['blue'])]:
            base=np.asarray([x[i],y[i]])+side*.12*lateral;arrow=ax.arrow(base[0],base[1],.22*thrust*forward[0],.22*thrust*forward[1],width=.006,head_width=.045,head_length=.04,color=color,length_includes_head=True,zorder=7);arrows.append(arrow)
        live.set_text(f"t = {t[i]:.1f} s\n\nport thrust = {port:.3f} N\nstarboard thrust = {star:.3f} N\nyaw moment = {float(result.rows[i]['yaw_moment_n_m']):+.4f} N m\nheading error = {float(result.rows[i]['heading_error_deg']):+.2f} deg\ncross-track = {float(result.rows[i]['cross_track_error_m']):+.3f} m\nregime = {result.rows[i]['control_regime']}")
        return [path,dot,live,*arrows]
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False);_save_animation(animation,gif,mp4,fps,int(render['mp4_bitrate_kbps']))


def _visual_manifest(paths: list[Path], visual: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image
    render=visual['render'];entries=[]
    for path in paths:
        item={'path':relative_to_root(path),'exists':path.exists(),'size_bytes':path.stat().st_size if path.exists() else 0}
        if path.suffix.lower()=='.gif' and path.exists():
            image=Image.open(path);frames=int(getattr(image,'n_frames',1));duration=sum(int(image.seek(i) or image.info.get('duration',0)) for i in range(frames))/1000.0
            # Pillow GIF delays are stored at centisecond granularity. At 8 fps
            # the writer records 120 ms rather than the ideal 125 ms, so compare
            # against the encoder-representable duration instead of an MP4-only
            # frame-rate ideal.
            expected_delay_ms = max(10, int((1000.0 / float(render['fps'])) // 10) * 10)
            expected_duration_s = frames * expected_delay_ms / 1000.0
            item.update({'frames':frames,'duration_s':duration,'expected_duration_s':expected_duration_s,'width_px':image.width,'height_px':image.height,'frame_count_ok':frames==int(render['frames']),'duration_ok':abs(duration-expected_duration_s)<.05,'resolution_ok':image.width>=int(render['min_width_px']) and image.height>=int(render['min_height_px'])})
        entries.append(item)
    gifs=[entry for entry in entries if entry['path'].endswith('.gif')];mp4s=[entry for entry in entries if entry['path'].endswith('.mp4')]
    return {'identifier':'AQUASKIM-REF-CTRL-VIS-01','entries':entries,'required_animation_count':4,'observed_animation_count':len(gifs),'required_video_count':4,'observed_video_count':len(mp4s),'all_gif_frame_counts_ok':all(entry.get('frame_count_ok',False) for entry in gifs),'all_gif_durations_ok':all(entry.get('duration_ok',False) for entry in gifs),'all_gif_resolutions_ok':all(entry.get('resolution_ok',False) for entry in gifs),'all_mp4_exist':all(entry.get('exists',False) and entry.get('size_bytes',0)>0 for entry in mp4s)}


def _sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def _record(artifacts: Phase1013Artifacts) -> Path:
    dirs=_dirs();run_id='phase10_13_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run=dirs['records']/run_id;(run/'artifacts').mkdir(parents=True,exist_ok=True);(run/'inputs').mkdir(parents=True,exist_ok=True)
    for name in ('reference_design.yaml','reference_control_robustness.yaml','reference_control_visualisation.yaml','parameter_registry.yaml'):
        source=project_root()/'config'/name;shutil.copy2(source,run/'inputs'/name)
    manifest=[]
    for relative in artifacts.as_dict().values():
        source=project_root()/relative
        if source.exists():
            shutil.copy2(source,run/'artifacts'/source.name);manifest.append({'path':relative,'sha256':_sha256(source),'size_bytes':source.stat().st_size})
    (run/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    environment={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable}
    try:environment['pip_freeze']=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
    except Exception as exc:environment['pip_freeze_error']=str(exc)
    (run/'environment_snapshot.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
    handoff=dirs['handoffs']/'PHASE10_13_LATEST_HANDOFF.md';handoff.write_text('# Current-aware dynamic-control robustness handoff\n\n'+f'- Run ID: `{run_id}`\n'+'- The comparison, bounded gain sweep and media QA were generated from the fixed reference plant.\n'+'- No Word report, delivery ZIP or release build was invoked.\n'+f'- Evidence: `{relative_to_root(run)}`\n',encoding='utf-8')
    return run


def run_phase10_13(*, record: bool = True, render: bool = False, require_media: bool = False) -> tuple[Phase1013Artifacts, Path | None]:
    ensure_runtime_directories();dirs=_dirs();protocol=load_control_robustness();visual=_read_visual_protocol();cases,sensitivity,_=run_control_suite(protocol);checks=assess_control_suite(cases,sensitivity,protocol)
    if any(str(row['status'])!='PASS' for row in checks):
        failures=', '.join(str(row['check']) for row in checks if str(row['status'])!='PASS');raise RuntimeError(f'Control robustness contract failed: {failures}')
    by_id={item.case.identifier:item for item in cases};nominal=by_id['compensated_nominal'];open_loop=by_id['open_loop_cross_current'];partial=by_id['compensated_partial_gain']
    artifacts=Phase1013Artifacts(
        track_comparison_png=dirs['figures']/'reference_current_track_comparison.png',track_comparison_svg=dirs['figures']/'reference_current_track_comparison.svg',
        control_response_png=dirs['figures']/'reference_current_control_response.png',control_response_svg=dirs['figures']/'reference_current_control_response.svg',
        sensitivity_map_png=dirs['figures']/'reference_controller_sensitivity_map.png',sensitivity_map_svg=dirs['figures']/'reference_controller_sensitivity_map.svg',
        scorecard_png=dirs['figures']/'reference_current_control_scorecard.png',scorecard_svg=dirs['figures']/'reference_current_control_scorecard.svg',
        validation_matrix_png=dirs['figures']/'reference_control_robustness_matrix.png',validation_matrix_svg=dirs['figures']/'reference_control_robustness_matrix.svg',
        case_metrics_csv=dirs['tables']/'reference_current_control_case_metrics.csv',sensitivity_metrics_csv=dirs['tables']/'reference_current_control_sensitivity_metrics.csv',nominal_timeseries_csv=dirs['tables']/'reference_current_control_nominal_timeseries.csv',events_csv=dirs['tables']/'reference_current_control_events.csv',acceptance_checks_csv=dirs['tables']/'reference_current_control_acceptance_checks.csv',
        summary_json=dirs['logs']/'reference_current_control_robustness_summary.json',summary_markdown=dirs['reports']/'reference_current_control_robustness_validation.md',visual_quality_manifest_json=dirs['logs']/'reference_current_control_visual_quality_manifest.json',
        comparison_gif=dirs['animations']/'reference_open_loop_vs_current_aware_replay.gif',comparison_mp4=dirs['videos']/'reference_open_loop_vs_current_aware_replay.mp4',
        response_gif=dirs['animations']/'reference_current_control_response_replay.gif',response_mp4=dirs['videos']/'reference_current_control_response_replay.mp4',
        sensitivity_gif=dirs['animations']/'reference_controller_sensitivity_replay.gif',sensitivity_mp4=dirs['videos']/'reference_controller_sensitivity_replay.mp4',
        force_gif=dirs['animations']/'reference_current_force_yaw_replay.gif',force_mp4=dirs['videos']/'reference_current_force_yaw_replay.mp4',contact_sheet_png=dirs['animations']/'reference_current_control_contact_sheet.png')
    _write_csv(artifacts.case_metrics_csv,[item.metrics for item in cases]);_write_csv(artifacts.sensitivity_metrics_csv,[item.metrics for item in sensitivity]);_write_csv(artifacts.nominal_timeseries_csv,nominal.rows);_write_csv(artifacts.events_csv,[{'case':item.case.identifier,**event} for item in cases+sensitivity for event in item.events]);_write_csv(artifacts.acceptance_checks_csv,checks)
    _draw_track_comparison(open_loop,nominal,partial,artifacts.track_comparison_png,artifacts.track_comparison_svg);_draw_control_response(nominal,artifacts.control_response_png,artifacts.control_response_svg);_draw_sensitivity_map(sensitivity,artifacts.sensitivity_map_png,artifacts.sensitivity_map_svg);_draw_scorecard(cases,artifacts.scorecard_png,artifacts.scorecard_svg);_draw_validation_matrix(checks,artifacts.validation_matrix_png,artifacts.validation_matrix_svg)
    media=[artifacts.comparison_gif,artifacts.comparison_mp4,artifacts.response_gif,artifacts.response_mp4,artifacts.sensitivity_gif,artifacts.sensitivity_mp4,artifacts.force_gif,artifacts.force_mp4]
    if render:
        raise RuntimeError(
            "Patch 10.13 media must be rendered by the recorded prepare/render/finalize workflow. "
            "This intentionally isolates each high-resolution writer in a fresh Python process."
        )
    quality=_visual_manifest(media,visual);artifacts.visual_quality_manifest_json.write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    if require_media and not (quality['observed_animation_count']==quality['required_animation_count'] and quality['observed_video_count']==quality['required_video_count'] and quality['all_gif_frame_counts_ok'] and quality['all_gif_durations_ok'] and quality['all_gif_resolutions_ok'] and quality['all_mp4_exist']):raise RuntimeError('Control robustness media quality gate failed.')
    summary={'identifier':protocol['identifier'],'validated_current_magnitude_mps':protocol['validated_current_magnitude_mps'],'cases':[item.metrics for item in cases],'sensitivity':[item.metrics for item in sensitivity],'acceptance_checks':checks,'visual_quality':quality,'artifacts':artifacts.as_dict(),'non_interactive':True}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Current-aware path-holding and control robustness validation','', '## Scope','This evidence suite evaluates a fixed earth-track manoeuvre in the low-speed 3-DOF digital twin. It does not generate Word, a delivery ZIP or a release artifact.','', '## Current-aware comparison',f"- Imposed current magnitude: `{float(nominal.metrics['current_magnitude_mps']):.3f} m/s`.",f"- Open-loop final cross-track drift: `{float(open_loop.metrics['final_abs_cross_track_error_m']):.3f} m`.",f"- Current-aware final cross-track error: `{float(nominal.metrics['final_abs_cross_track_error_m']):.3f} m`.",f"- Current-aware p95 cross-track error: `{float(nominal.metrics['p95_abs_cross_track_error_m']):.3f} m`.",f"- Current-aware p95 heading error: `{float(nominal.metrics['p95_abs_heading_error_deg']):.2f} deg`.",'', '## Bounded gain sensitivity',f"- Deterministic gain samples: `{len(sensitivity)}`.",f"- Worst p95 cross-track response: `{max(float(item.metrics['p95_abs_cross_track_error_m']) for item in sensitivity):.3f} m`.",f"- Worst p95 heading response: `{max(float(item.metrics['p95_abs_heading_error_deg']) for item in sensitivity):.2f} deg`.",'', '## Acceptance and media QA',f"- Acceptance checks passed: `{sum(str(row['status']) == 'PASS' for row in checks)}/{len(checks)}`.",f"- Required GIF / observed GIF: `{quality['required_animation_count']} / {quality['observed_animation_count']}`.",f"- Required MP4 / observed MP4: `{quality['required_video_count']} / {quality['observed_video_count']}`.",f"- Frame, duration and resolution checks: `{quality['all_gif_frame_counts_ok'] and quality['all_gif_durations_ok'] and quality['all_gif_resolutions_ok']}`.",'', '## Model boundary',str(protocol['model_boundary'])]
    artifacts.summary_markdown.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    run=_record(artifacts) if record else None
    return artifacts,run


def print_phase10_13_summary(result: tuple[Phase1013Artifacts, Path | None] | Phase1013Artifacts) -> None:
    artifacts,run=result if isinstance(result,tuple) else (result,None)
    print('='*72);print('AquaSkim-Sim | Current-aware Control Robustness Validation');print('='*72);print(f'Track comparison: {relative_to_root(artifacts.track_comparison_png)}');print(f'Contact sheet   : {relative_to_root(artifacts.contact_sheet_png)}');print(f'Visual QA       : {relative_to_root(artifacts.visual_quality_manifest_json)}');
    if run:print(f'Evidence        : {relative_to_root(run)}')
    print('Status          : PASS');print('='*72)


def main() -> int:
    result=run_phase10_13(record=False,render=False,require_media=False)
    print_phase10_13_summary(result)
    print("[INFO] Static control evidence prepared. Use the recorded Patch 10.13 script to render isolated media and finalize evidence.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
