"""Current-aware guidance and operating-envelope validation evidence.

The phase adds deterministic low-current feedforward validation and clearly
separates a documented boundary case from validated mission capability. It does
not create Word reports, delivery ZIPs or a release build.
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
from matplotlib.patches import FancyBboxPatch, Polygon
import numpy as np
import yaml

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.operating_envelope import (
    EnvelopeScenario,
    ScenarioAssessment,
    assess_scenario,
    envelope_scenarios,
    load_operating_envelope,
    run_envelope_scenario,
)
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.phase10_6 import _arrays, _draw_obstacles, _draw_robot, _map_axis
from aquaskim.phase10_11 import _frame_indices, _visual_manifest
from aquaskim.reference_design import project_root
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class ScenarioRun:
    scenario: EnvelopeScenario
    result: Any
    environment: Any
    assessment: ScenarioAssessment


@dataclass(frozen=True)
class Phase1012Artifacts:
    scenarios_map_png: Path
    scenarios_map_svg: Path
    current_compensation_png: Path
    current_compensation_svg: Path
    scorecard_png: Path
    scorecard_svg: Path
    resources_png: Path
    resources_svg: Path
    boundary_matrix_png: Path
    boundary_matrix_svg: Path
    metrics_csv: Path
    checks_csv: Path
    events_csv: Path
    compensation_samples_csv: Path
    acceptance_csv: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest_json: Path
    cross_current_gif: Path
    cross_current_mp4: Path
    diagonal_current_gif: Path
    diagonal_current_mp4: Path
    energy_return_gif: Path
    energy_return_mp4: Path
    boundary_gif: Path
    boundary_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _dirs() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": DIRECTORIES["figures"], "tables": DIRECTORIES["tables"],
        "logs": DIRECTORIES["logs"], "reports": DIRECTORIES["reports"],
        "animations": DIRECTORIES["animations"], "videos": DIRECTORIES["videos"],
        "records": root / "records" / "phases" / "phase_10_12" / "runs",
        "handoffs": DIRECTORIES["handoffs"],
    }


def _read_visual_protocol() -> dict[str, Any]:
    path = project_root() / "config" / "reference_operating_visualisation.yaml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    protocol = parsed.get("reference_operating_visualisation") if isinstance(parsed, dict) else None
    if not isinstance(protocol, dict):
        raise ValueError("reference_operating_visualisation.yaml requires a mapping.")
    return protocol


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
        rows = [{"status": "NO_ROWS"}]
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


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, fps: int, bitrate: int) -> None:
    gif.parent.mkdir(parents=True, exist_ok=True)
    mp4.parent.mkdir(parents=True, exist_ok=True)
    animation.save(gif, writer=PillowWriter(fps=fps))
    animation.save(mp4, writer=FFMpegWriter(fps=fps, bitrate=bitrate))
    plt.close(animation._fig)


def _add_robot_patches(ax: plt.Axes, x: float, y: float, psi: float, scale: float = .23) -> list[Any]:
    """Draw a removable top-view catamaran marker for replay animation."""
    c, s = math.cos(psi), math.sin(psi)
    forward = np.asarray([c, s]); lateral = np.asarray([-s, c])
    patches: list[Any] = []
    for side in (-1.0, 1.0):
        centre = np.asarray([x, y]) + side * .17 * lateral
        corners = [
            centre - .31 * forward - .035 * lateral,
            centre + .31 * forward - .035 * lateral,
            centre + .31 * forward + .035 * lateral,
            centre - .31 * forward + .035 * lateral,
        ]
        patch = Polygon(corners, closed=True, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=.8, zorder=14)
        ax.add_patch(patch); patches.append(patch)
    arrow = ax.arrow(x, y, scale * forward[0], scale * forward[1], color=PALETTE["navy"], width=.009, head_width=.06, head_length=.06, zorder=15)
    patches.append(arrow)
    return patches


def _scenario_metric_row(run: ScenarioRun) -> dict[str, Any]:
    result = run.result
    vector = run.scenario.overrides.get("autonomy", {}).get("current_earth_mps", [0.0, 0.0])
    row = {
        "scenario": run.scenario.identifier,
        "title": run.scenario.title,
        "class": run.scenario.classification,
        "assessment_status": run.assessment.status,
        "accepted_by_contract": run.assessment.accepted,
        "current_x_mps": float(vector[0]),
        "current_y_mps": float(vector[1]),
        "current_magnitude_mps": math.hypot(float(vector[0]), float(vector[1])),
    }
    row.update(result.metrics)
    return row


def _draw_scenario_maps(runs: list[ScenarioRun], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(18.0, 10.6))
    add_figure_header(
        fig,
        "Operating-envelope trajectories and documented boundary",
        "Validated cases use deterministic current-aware guidance. The boundary case is shown as an observed limit, not a performance claim.",
    )
    grid = GridSpec(2, 4, figure=fig, left=.04, right=.975, top=.86, bottom=.08, hspace=.34, wspace=.20)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(4)]
    for ax, run in zip(axes, runs):
        d = _arrays(run.result)
        _draw_obstacles(ax, run.environment, True)
        color = PALETTE["blue"] if run.scenario.classification == "validated" else PALETTE["orange"]
        ax.plot(d["x_m"], d["y_m"], color=color, linewidth=1.55, zorder=5)
        ax.scatter(*run.environment.home_position_m, marker="s", s=34, color=PALETTE["navy"], zorder=8)
        if run.result.targets:
            ax.scatter([float(row["x_m"]) for row in run.result.targets], [float(row["y_m"]) for row in run.result.targets], marker="*", s=55, color=PALETTE["green"], zorder=9)
        _draw_robot(ax, float(d["x_m"][-1]), float(d["y_m"][-1]), math.radians(float(d["psi_deg"][-1])), scale=.15)
        _map_axis(ax, run.environment, run.scenario.title)
        text = (
            f"{run.assessment.status}\n"
            f"current = {math.hypot(float(d['current_x_mps'][0]), float(d['current_y_mps'][0])):.3f} m/s\n"
            f"coverage = {100*float(run.result.metrics['coverage_fraction']):.1f}%\n"
            f"termination = {str(run.result.metrics['termination_reason'])[:30]}"
        )
        ax.text(.02, .02, text, transform=ax.transAxes, fontsize=6.5, va="bottom",
                bbox={"boxstyle": "round,pad=.24", "facecolor": "white", "edgecolor": PALETTE["grid"], "alpha": .94})
    for ax in axes[len(runs):]:
        ax.axis("off")
    _save(fig, png, svg)


def _unwrap_deg(values: np.ndarray) -> np.ndarray:
    return np.degrees(np.unwrap(np.radians(values)))


def _draw_current_compensation(run: ScenarioRun, png: Path, svg: Path) -> list[dict[str, Any]]:
    apply_engineering_style()
    d = _arrays(run.result)
    rows = run.result.rows
    track_indices = [index for index, row in enumerate(rows) if str(row.get("control_regime")) == "TRACK" and float(row.get("desired_ground_speed_mps", 0.0)) > 0.05]
    sample = track_indices[len(track_indices) // 2] if track_indices else len(rows) // 2
    ground_heading = float(d["ground_track_heading_deg"][sample])
    water_heading = float(d["desired_heading_deg"][sample])
    current = (float(d["current_x_mps"][sample]), float(d["current_y_mps"][sample]))
    speed_ground = float(d["desired_ground_speed_mps"][sample])
    speed_water = float(d["desired_water_speed_mps"][sample])
    gx, gy = speed_ground * math.cos(math.radians(ground_heading)), speed_ground * math.sin(math.radians(ground_heading))
    wx, wy = speed_water * math.cos(math.radians(water_heading)), speed_water * math.sin(math.radians(water_heading))

    fig = plt.figure(figsize=(17.2, 10.0))
    add_figure_header(
        fig,
        "Current-aware ground-track guidance",
        "The controller requests a water-relative vector whose sum with the known current vector equals the desired ground-track vector in the model.",
    )
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.96, top=.86, bottom=.10, hspace=.36, wspace=.30)
    axv, axh, axs, axc = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    axv.axhline(0, color=PALETTE["grid"], linewidth=.8); axv.axvline(0, color=PALETTE["grid"], linewidth=.8)
    axv.quiver(0, 0, gx, gy, angles="xy", scale_units="xy", scale=1, color=PALETTE["blue"], label="desired ground track")
    axv.quiver(0, 0, current[0], current[1], angles="xy", scale_units="xy", scale=1, color=PALETTE["orange"], label="known current")
    axv.quiver(0, 0, wx, wy, angles="xy", scale_units="xy", scale=1, color=PALETTE["green"], label="commanded water-relative")
    lim = max(.08, abs(gx), abs(gy), abs(wx), abs(wy), abs(current[0]), abs(current[1])) * 1.45
    axv.set_xlim(-lim, lim); axv.set_ylim(-lim, lim); axv.set_aspect("equal", adjustable="box")
    axv.set_xlabel("East velocity [m/s]"); axv.set_ylabel("North velocity [m/s]"); axv.set_title("Vector balance at a representative TRACK sample", loc="left"); axv.legend(fontsize=7.2); style_axis(axv)

    # Keep headings wrapped for presentation. An unwrapped course can accumulate
    # multiple full turns and obscure the actual crab-angle relationship.
    axh.plot(d["time_s"], d["ground_track_heading_deg"], label="ground-track heading", linewidth=1.1, color=PALETTE["blue"])
    axh.plot(d["time_s"], d["desired_heading_deg"], label="water-command course", linewidth=1.0, color=PALETTE["green"])
    axh.plot(d["time_s"], d["psi_deg"], label="actual heading", linewidth=.9, color=PALETTE["orange"])
    axh.set_ylim(-200, 200); axh.set_xlabel("Time [s]"); axh.set_ylabel("Wrapped heading [deg]"); axh.set_title("Crab-angle course adjustment", loc="left"); axh.legend(fontsize=7.2); style_axis(axh)

    axs.plot(d["time_s"], d["desired_ground_speed_mps"], label="ground request", color=PALETTE["blue"])
    axs.plot(d["time_s"], d["desired_water_speed_mps"], label="water-relative request", color=PALETTE["green"])
    axs.plot(d["time_s"], d["ground_speed_mps"], label="realised ground speed", color=PALETTE["orange"], alpha=.85)
    axs.set_xlabel("Time [s]"); axs.set_ylabel("Speed [m/s]"); axs.set_title("Speed request transformation", loc="left"); axs.legend(fontsize=7.2); style_axis(axs)

    crab_line, = axc.plot(d["time_s"], d["crab_angle_deg"], color=PALETTE["orange"], label="commanded crab angle")
    axc.set_xlabel("Time [s]"); axc.set_ylabel("Crab angle [deg]"); axc.set_title("Compensation demand and safety margin", loc="left"); style_axis(axc)
    axc_clearance = axc.twinx()
    clearance_line, = axc_clearance.plot(d["time_s"], d["hazard_clearance_m"], color=PALETTE["green"], label="safety clearance")
    guard_line = axc_clearance.axhline(.35, color=PALETTE["gray_dark"], linestyle="--", linewidth=.9, label="guard distance")
    axc_clearance.set_ylabel("Clearance [m]"); axc_clearance.set_ylim(0.0, max(.8, float(np.nanmax(d["hazard_clearance_m"])) * 1.08))
    axc.legend([crab_line, clearance_line, guard_line], ["commanded crab angle", "safety clearance", "guard distance"], fontsize=7.2, loc="lower left")
    _save(fig, png, svg)

    return [{
        "scenario": run.scenario.identifier,
        "sample_time_s": float(d["time_s"][sample]),
        "ground_track_heading_deg": ground_heading,
        "water_command_heading_deg": water_heading,
        "crab_angle_deg": float(d["crab_angle_deg"][sample]),
        "desired_ground_speed_mps": speed_ground,
        "desired_water_speed_mps": speed_water,
        "current_x_mps": current[0],
        "current_y_mps": current[1],
    }]


def _draw_scorecard(runs: list[ScenarioRun], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(17.2, 9.7))
    add_figure_header(fig, "Operating-envelope scorecard", "Validated scenarios and the documented boundary observation are reported separately.")
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.96, top=.86, bottom=.10, hspace=.35, wspace=.28)
    ax1, ax2, ax3, ax4 = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    labels = [run.scenario.identifier.replace("_", "\n") for run in runs]
    x = np.arange(len(runs))
    color = [PALETTE["blue"] if run.scenario.classification == "validated" else PALETTE["orange"] for run in runs]
    magnitudes = [math.hypot(float(run.scenario.overrides.get("autonomy", {}).get("current_earth_mps", [0, 0])[0]), float(run.scenario.overrides.get("autonomy", {}).get("current_earth_mps", [0, 0])[1])) for run in runs]
    coverage = [100 * float(run.result.metrics.get("coverage_fraction", 0.0)) for run in runs]
    duration = [float(run.result.metrics.get("duration_s", 0.0)) for run in runs]
    clearance = [float(run.result.metrics.get("minimum_clearance_m", 0.0)) for run in runs]
    home = [float(run.result.metrics.get("final_distance_home_m", 0.0)) for run in runs]
    ax1.bar(x, magnitudes, color=color); ax1.axhline(.03, color=PALETTE["gray_dark"], linestyle="--", linewidth=.9, label="validated current limit")
    ax1.set_ylabel("Current magnitude [m/s]"); ax1.set_title("Scenario disturbance magnitude", loc="left"); ax1.legend(fontsize=7.2); ax1.set_xticks(x, labels, fontsize=6.7); style_axis(ax1)
    ax2.bar(x, coverage, color=color); ax2.set_ylim(0, 110); ax2.set_ylabel("Coverage [%]"); ax2.set_title("Coverage outcome", loc="left"); ax2.set_xticks(x, labels, fontsize=6.7); style_axis(ax2)
    ax3.bar(x, duration, color=color); ax3.set_ylabel("Mission duration [s]"); ax3.set_title("Mission time", loc="left"); ax3.set_xticks(x, labels, fontsize=6.7); style_axis(ax3)
    ax4.scatter(clearance, home, s=70, c=color, edgecolor="white", linewidth=.8)
    for index, run in enumerate(runs): ax4.annotate(run.scenario.identifier, (clearance[index], home[index]), fontsize=6.7, xytext=(4, 3), textcoords="offset points")
    ax4.axvline(.35, color=PALETTE["gray_dark"], linestyle="--", linewidth=.9); ax4.axhline(.35, color=PALETTE["gray_dark"], linestyle="--", linewidth=.9)
    ax4.set_xlabel("Minimum clearance [m]"); ax4.set_ylabel("Final home error [m]"); ax4.set_title("Safety and docking criteria", loc="left"); style_axis(ax4)
    _save(fig, png, svg)


def _draw_resources(energy: ScenarioRun, capacity: ScenarioRun, png: Path, svg: Path) -> None:
    apply_engineering_style()
    de, dc = _arrays(energy.result), _arrays(capacity.result)
    fig = plt.figure(figsize=(17.2, 9.4))
    add_figure_header(fig, "Energy-aware and capacity-aware return behaviour", "Return causes are independent engineering conditions: available energy reserve and hopper occupied volume.")
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.96, top=.86, bottom=.10, hspace=.35, wspace=.28)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    axes[0].plot(de["time_s"], 100 * de["soc"], color=PALETTE["navy"]); axes[0].set_ylabel("SOC [%]"); axes[0].set_title("Energy-reserve scenario", loc="left"); style_axis(axes[0])
    axes[1].plot(de["time_s"], de["hazard_clearance_m"], color=PALETTE["green"]); axes[1].axhline(.35, linestyle="--", color=PALETTE["gray_dark"]); axes[1].set_ylabel("Clearance [m]"); axes[1].set_title("Energy return safety margin", loc="left"); style_axis(axes[1])
    axes[2].step(dc["time_s"], dc["hopper_volume_l"], where="post", color=PALETTE["orange"]); axes[2].set_ylabel("Occupied hopper volume [L]"); axes[2].set_title("High-loading capacity progression", loc="left"); style_axis(axes[2])
    axes[3].plot(dc["time_s"], 100 * dc["soc"], color=PALETTE["navy"], label="SOC"); axes[3].step(dc["time_s"], dc["collected_count"], where="post", color=PALETTE["green"], label="captures"); axes[3].set_title("Storage return with retained energy reserve", loc="left"); axes[3].legend(fontsize=7.2); style_axis(axes[3])
    for ax in axes: ax.set_xlabel("Time [s]")
    _save(fig, png, svg)


def _draw_boundary_matrix(runs: list[ScenarioRun], png: Path, svg: Path) -> None:
    apply_engineering_style()
    fig = plt.figure(figsize=(17.2, 8.7))
    add_figure_header(fig, "Validated envelope and boundary-observation matrix", "A boundary outcome is retained for transparency but is excluded from the validated capability statement.")
    ax = fig.add_axes([.06, .13, .89, .68]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    cols = [(.03, "Scenario"), (.29, "Class"), (.42, "Current [m/s]"), (.57, "Observed outcome"), (.75, "Termination / interpretation")]
    for x, label in cols: ax.text(x, .94, label, fontsize=10, fontweight="bold", color=PALETTE["navy"])
    y = .85
    for run in runs:
        vector = run.scenario.overrides.get("autonomy", {}).get("current_earth_mps", [0.0, 0.0])
        magnitude = math.hypot(float(vector[0]), float(vector[1]))
        is_boundary = run.scenario.classification == "boundary"
        face = "#FFF5E8" if is_boundary else "#F5FAFD"
        edge = PALETTE["orange"] if is_boundary else PALETTE["grid"]
        ax.add_patch(FancyBboxPatch((.02, y-.06), .94, .085, boxstyle="round,pad=.012", facecolor=face, edgecolor=edge, linewidth=.8))
        ax.text(.03, y, run.scenario.title, fontsize=8.2, color=PALETTE["navy"], va="center")
        ax.text(.29, y, "Boundary" if is_boundary else "Validated", fontsize=8.2, color=PALETTE["orange"] if is_boundary else PALETTE["blue"], va="center", fontweight="bold")
        ax.text(.42, y, f"{magnitude:.3f}", fontsize=8.2, color=PALETTE["gray_dark"], va="center")
        ax.text(.57, y, run.assessment.status, fontsize=8.1, color=PALETTE["green"] if run.assessment.accepted else PALETTE["orange"], va="center", fontweight="bold")
        interpretation = str(run.result.metrics.get("termination_reason", ""))
        ax.text(.75, y, fill(interpretation, 33), fontsize=7.4, color=PALETTE["gray_dark"], va="center")
        y -= .108
    ax.text(.03, .03, "Validated current envelope is bounded by the versioned protocol. The diagonal boundary case is visible here so that model limits are not hidden or reported as nominal performance.", fontsize=8.6, color=PALETTE["gray_dark"])
    _save(fig, png, svg)


def _render_replay(run: ScenarioRun, gif: Path, mp4: Path, visual: dict[str, Any], *, title: str, boundary: bool = False) -> None:
    apply_engineering_style()
    d = _arrays(run.result)
    indices = _frame_indices(run.result.rows, run.result.events, int(visual["render"]["frame_count"]))
    fps, bitrate = int(visual["render"]["fps"]), int(visual["render"]["mp4_bitrate_kbps"])
    fig = plt.figure(figsize=(14.4, 8.2)); grid = GridSpec(1, 2, figure=fig, width_ratios=[1.38, .62], left=.05, right=.96, top=.90, bottom=.10, wspace=.17)
    ax, panel = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    _draw_obstacles(ax, run.environment, True)
    path, = ax.plot([], [], color=PALETTE["orange"] if boundary else PALETTE["blue"], linewidth=1.75)
    dot = ax.scatter([], [], s=28, color=PALETTE["green"])
    _map_axis(ax, run.environment, title)
    panel.axis("off"); panel.set_xlim(0, 1); panel.set_ylim(0, 1)
    face = "#FFF5E8" if boundary else "#F8FBFD"
    panel.add_patch(FancyBboxPatch((.04, .08), .92, .84, boxstyle="round,pad=.02", facecolor=face, edgecolor=PALETTE["orange"] if boundary else PALETTE["grid"]))
    panel.text(.10, .85, "Boundary observation" if boundary else "Current-aware mission state", fontsize=12, fontweight="bold", color=PALETTE["orange"] if boundary else PALETTE["navy"])
    live = panel.text(.10, .75, "", fontsize=8.7, color=PALETTE["gray_dark"], va="top")
    robot: list[Any] = []
    def update(frame: int):
        nonlocal robot
        for patch in robot: patch.remove()
        robot = []
        i = int(indices[frame]); row = run.result.rows[i]
        path.set_data(d["x_m"][:i+1], d["y_m"][:i+1]); dot.set_offsets(np.asarray([[d["x_m"][i], d["y_m"][i]]]))
        robot = _add_robot_patches(ax, float(d["x_m"][i]), float(d["y_m"][i]), math.radians(float(d["psi_deg"][i])), scale=.23)
        current_mag = math.hypot(float(d["current_x_mps"][i]), float(d["current_y_mps"][i]))
        live.set_text(
            f"t = {d['time_s'][i]:.1f} s\nstate = {row['mode']}\nregime = {row['control_regime']}\ncurrent = {current_mag:.3f} m/s\ncrab command = {d['crab_angle_deg'][i]:.1f} deg\ncoverage = {100*d['coverage_progress'][i]:.1f}%\nSOC = {100*d['soc'][i]:.1f}%\nclearance = {d['hazard_clearance_m'][i]:.3f} m\ntermination target: {str(run.scenario.expected.get('termination_contains',''))}"
        )
        return [path, dot, live, *robot]
    animation = FuncAnimation(fig, update, frames=len(indices), interval=1000 / fps, blit=False)
    _save_animation(animation, gif, mp4, fps, bitrate)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(artifacts: Phase1012Artifacts) -> Path:
    dirs = _dirs(); run_id = "phase10_12_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = dirs["records"] / run_id; (run / "artifacts").mkdir(parents=True, exist_ok=True); (run / "inputs").mkdir(parents=True, exist_ok=True)
    for name in ("reference_design.yaml", "reference_operating_envelope.yaml", "reference_operating_visualisation.yaml", "parameter_registry.yaml"):
        source = project_root() / "config" / name
        shutil.copy2(source, run / "inputs" / name)
    manifest = []
    for relative in artifacts.as_dict().values():
        source = project_root() / relative
        if source.exists():
            target = run / "artifacts" / source.name; shutil.copy2(source, target)
            manifest.append({"path": relative, "sha256": _sha256(source), "size_bytes": source.stat().st_size})
    (run / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    environment = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "executable": sys.executable}
    try: environment["pip_freeze"] = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    except Exception as exc: environment["pip_freeze_error"] = str(exc)
    (run / "environment_snapshot.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8")
    handoff = dirs["handoffs"] / "PHASE10_12_LATEST_HANDOFF.md"
    handoff.write_text(
        "# Current-aware operating-envelope validation handoff\n\n"
        f"- Run ID: `{run_id}`\n"
        "- Validated current scenarios and an explicitly segregated boundary observation were executed.\n"
        "- No Word report, delivery ZIP or release build was invoked.\n"
        f"- Evidence: `{relative_to_root(run)}`\n",
        encoding="utf-8",
    )
    return run


def run_phase10_12(*, record: bool = True, render: bool = True) -> tuple[Phase1012Artifacts, Path | None]:
    ensure_runtime_directories(); dirs = _dirs(); protocol = load_operating_envelope(); visual = _read_visual_protocol()
    runs: list[ScenarioRun] = []
    for scenario in envelope_scenarios(protocol):
        result, environment = run_envelope_scenario(scenario)
        assessment = assess_scenario(scenario, result)
        runs.append(ScenarioRun(scenario, result, environment, assessment))
    invalid = [run for run in runs if not run.assessment.accepted]
    if invalid:
        names = ", ".join(run.scenario.identifier for run in invalid)
        raise RuntimeError(f"Operating-envelope contract failed: {names}")

    artifacts = Phase1012Artifacts(
        scenarios_map_png=dirs["figures"] / "reference_operating_envelope_scenarios.png", scenarios_map_svg=dirs["figures"] / "reference_operating_envelope_scenarios.svg",
        current_compensation_png=dirs["figures"] / "reference_current_compensation_dashboard.png", current_compensation_svg=dirs["figures"] / "reference_current_compensation_dashboard.svg",
        scorecard_png=dirs["figures"] / "reference_operating_envelope_scorecard.png", scorecard_svg=dirs["figures"] / "reference_operating_envelope_scorecard.svg",
        resources_png=dirs["figures"] / "reference_operating_return_resources.png", resources_svg=dirs["figures"] / "reference_operating_return_resources.svg",
        boundary_matrix_png=dirs["figures"] / "reference_operating_boundary_matrix.png", boundary_matrix_svg=dirs["figures"] / "reference_operating_boundary_matrix.svg",
        metrics_csv=dirs["tables"] / "reference_operating_envelope_metrics.csv", checks_csv=dirs["tables"] / "reference_operating_envelope_checks.csv", events_csv=dirs["tables"] / "reference_operating_envelope_events.csv", compensation_samples_csv=dirs["tables"] / "reference_current_compensation_samples.csv", acceptance_csv=dirs["tables"] / "reference_operating_envelope_acceptance.csv",
        summary_json=dirs["logs"] / "reference_operating_envelope_summary.json", summary_markdown=dirs["reports"] / "reference_operating_envelope_validation.md", visual_quality_manifest_json=dirs["logs"] / "reference_operating_envelope_visual_quality_manifest.json",
        cross_current_gif=dirs["animations"] / "reference_cross_current_compensated_replay.gif", cross_current_mp4=dirs["videos"] / "reference_cross_current_compensated_replay.mp4",
        diagonal_current_gif=dirs["animations"] / "reference_diagonal_current_compensated_replay.gif", diagonal_current_mp4=dirs["videos"] / "reference_diagonal_current_compensated_replay.mp4",
        energy_return_gif=dirs["animations"] / "reference_energy_reserve_return_replay.gif", energy_return_mp4=dirs["videos"] / "reference_energy_reserve_return_replay.mp4",
        boundary_gif=dirs["animations"] / "reference_diagonal_boundary_replay.gif", boundary_mp4=dirs["videos"] / "reference_diagonal_boundary_replay.mp4",
        contact_sheet_png=dirs["animations"] / "reference_operating_envelope_contact_sheet.png",
    )
    by_id = {run.scenario.identifier: run for run in runs}
    _write_csv(artifacts.metrics_csv, [_scenario_metric_row(run) for run in runs])
    _write_csv(artifacts.checks_csv, [check for run in runs for check in run.assessment.checks])
    event_rows: list[dict[str, Any]] = []
    for run in runs:
        event_rows.extend([{"scenario": run.scenario.identifier, "class": run.scenario.classification, **event} for event in run.result.events])
    _write_csv(artifacts.events_csv, event_rows)
    compensation_samples = _draw_current_compensation(by_id["north_current_0_02"], artifacts.current_compensation_png, artifacts.current_compensation_svg)
    _write_csv(artifacts.compensation_samples_csv, compensation_samples)
    _write_csv(artifacts.acceptance_csv, [{"scenario": run.scenario.identifier, "class": run.scenario.classification, "status": run.assessment.status, "accepted": run.assessment.accepted} for run in runs])
    _draw_scenario_maps(runs, artifacts.scenarios_map_png, artifacts.scenarios_map_svg)
    _draw_scorecard(runs, artifacts.scorecard_png, artifacts.scorecard_svg)
    _draw_resources(by_id["proactive_energy_return"], by_id["hopper_capacity_return"], artifacts.resources_png, artifacts.resources_svg)
    _draw_boundary_matrix(runs, artifacts.boundary_matrix_png, artifacts.boundary_matrix_svg)

    media = [artifacts.cross_current_gif, artifacts.cross_current_mp4, artifacts.diagonal_current_gif, artifacts.diagonal_current_mp4, artifacts.energy_return_gif, artifacts.energy_return_mp4, artifacts.boundary_gif, artifacts.boundary_mp4]
    if render:
        _render_replay(by_id["north_current_0_02"], artifacts.cross_current_gif, artifacts.cross_current_mp4, visual, title="Cross-current compensated coverage replay")
        _render_replay(by_id["diagonal_current_0_02"], artifacts.diagonal_current_gif, artifacts.diagonal_current_mp4, visual, title="Diagonal-current compensated coverage replay")
        _render_replay(by_id["proactive_energy_return"], artifacts.energy_return_gif, artifacts.energy_return_mp4, visual, title="Energy-reserve return replay")
        _render_replay(by_id["diagonal_boundary_0_05"], artifacts.boundary_gif, artifacts.boundary_mp4, visual, title="Diagonal-current boundary replay", boundary=True)
        write_animation_audit_sheet([artifacts.cross_current_gif, artifacts.diagonal_current_gif, artifacts.energy_return_gif, artifacts.boundary_gif], artifacts.contact_sheet_png, samples_per_animation=int(visual["render"]["contact_sheet_samples"]))
    quality = _visual_manifest(media, visual)
    artifacts.visual_quality_manifest_json.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    if render and not (quality["all_gif_frame_counts_ok"] and quality["all_gif_durations_ok"] and quality["all_gif_resolutions_ok"] and quality["all_mp4_exist"] and quality["observed_animation_count"] == quality["required_animation_count"] and quality["observed_video_count"] == quality["required_video_count"]):
        raise RuntimeError("Operating-envelope media quality gate failed.")

    summary = {
        "identifier": protocol["identifier"], "validated_current_limit_mps": protocol["validated_current_limit_mps"],
        "current_compensation_model": protocol["current_compensation_model"],
        "scenarios": [_scenario_metric_row(run) for run in runs],
        "checks": [check for run in runs for check in run.assessment.checks],
        "visual_quality": quality, "artifacts": artifacts.as_dict(), "non_interactive": True,
    }
    artifacts.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    validated = [run for run in runs if run.scenario.classification == "validated"]
    boundary = [run for run in runs if run.scenario.classification == "boundary"]
    lines = [
        "# Current-aware guidance and operating-envelope validation", "",
        "## Scope", "This evidence suite executes deterministic reference scenarios only. It does not generate Word, a delivery ZIP or a release artifact.", "",
        "## Validated envelope", f"- Versioned current-magnitude limit: `{float(protocol['validated_current_limit_mps']):.3f} m/s`.",
        f"- Validated scenarios accepted: `{sum(run.assessment.accepted for run in validated)}/{len(validated)}`.",
        "- Current-aware guidance uses the explicit water-relative vector relation `V_water = V_ground - V_current`.", "",
        "## Boundary observation",
    ]
    for run in boundary:
        lines.extend([f"- `{run.scenario.title}`: `{run.assessment.status}`; termination `{run.result.metrics['termination_reason']}`."])
    lines.extend(["", "## Media QA", f"- Required GIF / observed GIF: `{quality['required_animation_count']} / {quality['observed_animation_count']}`.", f"- Required MP4 / observed MP4: `{quality['required_video_count']} / {quality['observed_video_count']}`.", f"- Frame, duration and resolution checks: `{quality['all_gif_frame_counts_ok'] and quality['all_gif_durations_ok'] and quality['all_gif_resolutions_ok']}`.", "", "## Model boundary", "Results are numerical evidence from the documented low-speed 3-DOF sheltered-basin model. The boundary replay is intentionally retained to show a limit of the simulated controller rather than a sea-trial result or a validated operating claim."])
    artifacts.summary_markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run = _record(artifacts) if record else None
    return artifacts, run


def print_phase10_12_summary(result: tuple[Phase1012Artifacts, Path | None] | Phase1012Artifacts) -> None:
    artifacts, run = result if isinstance(result, tuple) else (result, None)
    print("=" * 72)
    print("AquaSkim-Sim | Current-aware Operating-envelope Validation")
    print("=" * 72)
    print(f"Scenario map  : {relative_to_root(artifacts.scenarios_map_png)}")
    print(f"Contact sheet : {relative_to_root(artifacts.contact_sheet_png)}")
    print(f"Visual QA     : {relative_to_root(artifacts.visual_quality_manifest_json)}")
    if run: print(f"Evidence      : {relative_to_root(run)}")
    print("Status        : PASS")
    print("=" * 72)


def main() -> int:
    artifacts, run = run_phase10_12(record=True, render=True)
    print_phase10_12_summary((artifacts, run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
