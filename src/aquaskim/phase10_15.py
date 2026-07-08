"""System-level scenario validation and controlled-failure evidence.

This module is deliberately downstream of the fixed reference model.  It does
not create a Word report, delivery ZIP, or release declaration.  Validated,
boundary, and controlled-failure scenarios are kept separate in every table and
plot so a limitation cannot be mistaken for an operating claim.
"""
from __future__ import annotations

import csv
import hashlib
import json
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
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle, Rectangle
import numpy as np

from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import load_reference_configuration, project_root
from aquaskim.system_scenario_validation import (
    SystemAssessment,
    SystemScenario,
    assess_system_scenario,
    configuration_for_system_scenario,
    load_system_validation,
    run_system_scenario,
    system_scenarios,
)
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, style_axis


@dataclass(frozen=True)
class ScenarioRun:
    scenario: SystemScenario
    rows: list[dict[str, Any]]
    events: list[dict[str, Any]]
    metrics: dict[str, Any]
    assessment: SystemAssessment
    environment: Any


@dataclass(frozen=True)
class Phase1015Artifacts:
    trajectories_png: Path
    trajectories_svg: Path
    termination_matrix_png: Path
    termination_matrix_svg: Path
    metrics_dashboard_png: Path
    metrics_dashboard_svg: Path
    failure_evidence_png: Path
    failure_evidence_svg: Path
    acceptance_scorecard_png: Path
    acceptance_scorecard_svg: Path
    scenario_catalog_csv: Path
    metrics_csv: Path
    checks_csv: Path
    events_csv: Path
    timeseries_csv: Path
    state_segments_csv: Path
    acceptance_csv: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest_json: Path
    validated_gif: Path
    validated_mp4: Path
    time_limit_gif: Path
    time_limit_mp4: Path
    boundary_gif: Path
    boundary_mp4: Path
    timeline_gif: Path
    timeline_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(value) for name, value in self.__dict__.items()}


CLASS_COLOR = {
    "validated": PALETTE["green"],
    "boundary": PALETTE["orange"],
    "controlled_failure": PALETTE["gray_dark"],
}


def _dirs() -> dict[str, Path]:
    root = project_root()
    return {
        "figures": DIRECTORIES["figures"], "tables": DIRECTORIES["tables"], "logs": DIRECTORIES["logs"],
        "reports": DIRECTORIES["reports"], "animations": DIRECTORIES["animations"], "videos": DIRECTORIES["videos"],
        "records": root / "records" / "phases" / "phase_10_15" / "runs", "handoffs": DIRECTORIES["handoffs"],
    }


def _artifacts() -> Phase1015Artifacts:
    d = _dirs()
    return Phase1015Artifacts(
        trajectories_png=d["figures"] / "reference_system_scenario_trajectories.png",
        trajectories_svg=d["figures"] / "reference_system_scenario_trajectories.svg",
        termination_matrix_png=d["figures"] / "reference_system_termination_matrix.png",
        termination_matrix_svg=d["figures"] / "reference_system_termination_matrix.svg",
        metrics_dashboard_png=d["figures"] / "reference_system_metrics_dashboard.png",
        metrics_dashboard_svg=d["figures"] / "reference_system_metrics_dashboard.svg",
        failure_evidence_png=d["figures"] / "reference_system_failure_evidence.png",
        failure_evidence_svg=d["figures"] / "reference_system_failure_evidence.svg",
        acceptance_scorecard_png=d["figures"] / "reference_system_acceptance_scorecard.png",
        acceptance_scorecard_svg=d["figures"] / "reference_system_acceptance_scorecard.svg",
        scenario_catalog_csv=d["tables"] / "reference_system_scenario_catalog.csv",
        metrics_csv=d["tables"] / "reference_system_scenario_metrics.csv",
        checks_csv=d["tables"] / "reference_system_scenario_checks.csv",
        events_csv=d["tables"] / "reference_system_scenario_events.csv",
        timeseries_csv=d["tables"] / "reference_system_scenario_time_series.csv",
        state_segments_csv=d["tables"] / "reference_system_state_segments.csv",
        acceptance_csv=d["tables"] / "reference_system_acceptance.csv",
        summary_json=d["logs"] / "reference_system_validation_summary.json",
        summary_markdown=d["reports"] / "reference_system_scenario_validation.md",
        visual_quality_manifest_json=d["logs"] / "reference_system_visual_quality_manifest.json",
        validated_gif=d["animations"] / "reference_system_validated_scenarios_replay.gif",
        validated_mp4=d["videos"] / "reference_system_validated_scenarios_replay.mp4",
        time_limit_gif=d["animations"] / "reference_system_time_limit_controlled_replay.gif",
        time_limit_mp4=d["videos"] / "reference_system_time_limit_controlled_replay.mp4",
        boundary_gif=d["animations"] / "reference_system_boundary_vs_uncompensated_replay.gif",
        boundary_mp4=d["videos"] / "reference_system_boundary_vs_uncompensated_replay.mp4",
        timeline_gif=d["animations"] / "reference_system_event_timeline_replay.gif",
        timeline_mp4=d["videos"] / "reference_system_event_timeline_replay.mp4",
        contact_sheet_png=d["animations"] / "reference_system_scenario_contact_sheet.png",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields, rows = ["status"], [{"status": "NO_ROWS"}]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _save(fig: plt.Figure, png: Path, svg: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=240, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _save_animation(animation: FuncAnimation, gif: Path, mp4: Path, *, fps: int, bitrate: int) -> None:
    gif.parent.mkdir(parents=True, exist_ok=True); mp4.parent.mkdir(parents=True, exist_ok=True)
    animation.save(gif, writer=PillowWriter(fps=fps))
    plt.close(animation._fig)
    completed = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(gif), "-movflags", "+faststart",
         "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p", "-r", str(fps),
         "-b:v", f"{int(bitrate)}k", str(mp4)], capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg could not transcode {gif.name}: {completed.stderr.strip()}")


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _sample_indices(length: int, frames: int) -> np.ndarray:
    return np.linspace(0, max(0, length - 1), max(2, int(frames))).round().astype(int)


def _draw_environment(ax: plt.Axes, environment: Any) -> None:
    ax.add_patch(Rectangle((0, 0), environment.length_m, environment.width_m, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], lw=1.2, zorder=0))
    for obstacle in environment.obstacles:
        if getattr(obstacle, "kind", "") == "circle":
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["gray_light"], edgecolor=PALETTE["gray_dark"], lw=0.9, zorder=2))
        else:
            sx, sy = obstacle.size_m
            ax.add_patch(Rectangle((obstacle.center_m[0] - sx / 2, obstacle.center_m[1] - sy / 2), sx, sy, facecolor=PALETTE["gray_light"], edgecolor=PALETTE["gray_dark"], lw=0.9, zorder=2))
    ax.scatter(*environment.home_position_m, s=46, marker="s", color=PALETTE["navy"], zorder=6)
    ax.set(xlim=(0, environment.length_m), ylim=(0, environment.width_m), aspect="equal", xlabel="East x (m)", ylabel="North y (m)")
    style_axis(ax)


def _add_robot(ax: plt.Axes, x: float, y: float, psi_deg: float, *, color: str) -> list[Any]:
    angle = np.deg2rad(psi_deg)
    dx, dy = 0.28 * np.cos(angle), 0.28 * np.sin(angle)
    body = ax.add_patch(Circle((x, y), 0.13, facecolor=color, edgecolor=PALETTE["white"], lw=1.0, zorder=8))
    arrow = ax.arrow(x, y, dx, dy, width=0.02, head_width=0.13, head_length=0.11, color=PALETTE["navy"], length_includes_head=True, zorder=9)
    return [body, arrow]


def _scenario_row(run: ScenarioRun) -> dict[str, Any]:
    m = run.metrics
    return {
        "scenario": run.scenario.identifier, "title": run.scenario.title, "classification": run.scenario.classification,
        "status": run.assessment.status, "accepted": run.assessment.accepted,
        "termination_reason": m.get("termination_reason", ""), "mission_success": int(m.get("mission_success", 0)),
        "duration_s": float(m.get("duration_s", 0.0)), "coverage_fraction": float(m.get("coverage_fraction", 0.0)),
        "collected_count": int(m.get("collected_count", 0)), "final_soc": float(m.get("final_soc", 0.0)),
        "minimum_clearance_m": float(m.get("minimum_clearance_m", 0.0)), "final_distance_home_m": float(m.get("final_distance_home_m", 0.0)),
        "replan_count": int(m.get("replan_count", 0)), "safety_event_count": int(m.get("safety_event_count", 0)),
        "watchdog_event_count": int(m.get("watchdog_event_count", 0)),
        "current_magnitude_mps": run.scenario.current_magnitude_mps,
    }


def _segments(run: ScenarioRun) -> list[dict[str, Any]]:
    if not run.rows:
        return []
    rows = run.rows; start = 0; current = str(rows[0].get("mode", "UNKNOWN")); segments: list[dict[str, Any]] = []
    for idx in range(1, len(rows) + 1):
        candidate = str(rows[idx].get("mode", "UNKNOWN")) if idx < len(rows) else None
        if candidate != current:
            first, last = rows[start], rows[idx - 1]
            segments.append({"scenario": run.scenario.identifier, "classification": run.scenario.classification, "mode": current,
                             "start_time_s": _float(first, "time_s"), "end_time_s": _float(last, "time_s"),
                             "duration_s": max(0.0, _float(last, "time_s") - _float(first, "time_s")),
                             "start_x_m": _float(first, "x_m"), "start_y_m": _float(first, "y_m"),
                             "end_x_m": _float(last, "x_m"), "end_y_m": _float(last, "y_m")})
            start = idx; current = candidate if candidate is not None else ""
    return segments


def _downsample_rows(rows: list[dict[str, Any]], sample_period_s: float) -> list[dict[str, Any]]:
    """Keep a presentation-grade chronological log without changing mission metrics.

    The 3-DOF integrator runs at 20 Hz; storing every internal integration row
    for seven long scenarios creates a very large CSV and slows static SVG
    generation without improving engineering readability.  A 4 Hz evidence log
    preserves all route, state and resource trends while the original mission
    metrics remain calculated from the complete numerical run.
    """
    if not rows:
        return []
    sampled = [rows[0]]
    last = _float(rows[0], "time_s")
    for row in rows[1:-1]:
        current = _float(row, "time_s")
        if current - last + 1e-12 >= sample_period_s:
            sampled.append(row); last = current
    if rows[-1] is not sampled[-1]:
        sampled.append(rows[-1])
    return sampled


def _draw_trajectories(runs: list[ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    apply_engineering_style(); fig, axes = plt.subplots(2, 4, figsize=(18, 9.6)); axes = axes.ravel()
    add_figure_header(fig, "System scenario trajectories", "Validated, boundary and controlled-failure runs remain visibly segregated.")
    for ax, run in zip(axes, runs):
        _draw_environment(ax, run.environment)
        x = [_float(row, "x_m") for row in run.rows]; y = [_float(row, "y_m") for row in run.rows]
        color = CLASS_COLOR[run.scenario.classification]
        ax.plot(x, y, color=color, lw=1.7, zorder=5)
        ax.scatter(x[0], y[0], s=18, color=PALETTE["navy"], zorder=7)
        ax.scatter(x[-1], y[-1], s=26, color=color, marker="X", zorder=7)
        ax.set_title(run.scenario.title, fontsize=10.5, color=PALETTE["navy"], pad=5)
        ax.text(.02, .02, f"{run.assessment.status}\n{run.metrics['termination_reason']}", transform=ax.transAxes, fontsize=7.3,
                color=PALETTE["gray_dark"], va="bottom", bbox={"boxstyle": "round,pad=0.25", "fc": PALETTE["white"], "ec": PALETTE["grid"], "alpha": .95})
    for ax in axes[len(runs):]:
        ax.axis("off")
    fig.subplots_adjust(left=.05, right=.98, top=.90, bottom=.06, hspace=.38, wspace=.28)
    _save(fig, artifacts.trajectories_png, artifacts.trajectories_svg)


def _draw_termination_matrix(runs: list[ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    apply_engineering_style(); fig, ax = plt.subplots(figsize=(15.5, 7.7)); add_figure_header(fig, "Termination and classification matrix", "Every mission is assessed against a declared outcome; boundary and controlled failures are not counted as validated success.")
    labels = [run.scenario.title for run in runs]; y = np.arange(len(runs))[::-1]
    durations = np.array([_float(run.metrics, "duration_s") for run in runs])
    ax.barh(y, durations, color=[CLASS_COLOR[r.scenario.classification] for r in runs], alpha=.84, zorder=3)
    for yi, run in zip(y, runs):
        text = f"{run.assessment.status} | {run.metrics['termination_reason']}"
        ax.text(min(_float(run.metrics, "duration_s") + 14, max(durations) * 1.02), yi, text, va="center", fontsize=8.5, color=PALETTE["gray_dark"])
    ax.set_yticks(y, labels); ax.set_xlabel("Simulated mission duration (s)"); ax.set_xlim(0, max(durations) * 1.52)
    style_axis(ax); fig.subplots_adjust(left=.24, right=.98, top=.88, bottom=.11)
    _save(fig, artifacts.termination_matrix_png, artifacts.termination_matrix_svg)


def _draw_metrics_dashboard(runs: list[ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    apply_engineering_style(); fig, axes = plt.subplots(2, 2, figsize=(15, 9)); add_figure_header(fig, "System-level mission metrics", "Metrics are shown across validated, boundary and controlled-failure conditions without merging their classifications.")
    labels = [run.scenario.identifier.replace("_", "\n") for run in runs]; x = np.arange(len(runs)); colors = [CLASS_COLOR[r.scenario.classification] for r in runs]
    metrics = [("Coverage fraction", "coverage_fraction", 1.0), ("Final SOC", "final_soc", 1.0), ("Minimum clearance (m)", "minimum_clearance_m", None), ("Collected items", "collected_count", None)]
    for ax, (title, key, ref) in zip(axes.ravel(), metrics):
        values = [_float(run.metrics, key) for run in runs]
        ax.bar(x, values, color=colors, zorder=3)
        if ref is not None: ax.axhline(ref, color=PALETTE["gray_dark"], lw=.9, ls="--")
        if key == "minimum_clearance_m": ax.axhline(.35, color=PALETTE["orange"], lw=.9, ls="--", label="guard criterion")
        ax.set_title(title, fontsize=11.5, color=PALETTE["navy"]); ax.set_xticks(x, labels, fontsize=7.5)
        style_axis(ax)
        if key == "minimum_clearance_m": ax.legend(fontsize=8, loc="upper right")
    fig.subplots_adjust(left=.06, right=.98, top=.89, bottom=.16, hspace=.36, wspace=.24)
    _save(fig, artifacts.metrics_dashboard_png, artifacts.metrics_dashboard_svg)


def _draw_failure_evidence(runs: dict[str, ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    apply_engineering_style(); fig, axes = plt.subplots(1, 2, figsize=(15.5, 7)); add_figure_header(fig, "Controlled-limit evidence", "These scenarios are retained to expose supervisory and control limits; they are not presented as validated operation.")
    keys = ["scheduled_time_limit", "uncompensated_diagonal_crossflow"]
    for ax, key in zip(axes, keys):
        run = runs[key]; _draw_environment(ax, run.environment)
        x = [_float(row, "x_m") for row in run.rows]; y = [_float(row, "y_m") for row in run.rows]
        ax.plot(x, y, color=CLASS_COLOR["controlled_failure"], lw=1.9, zorder=5)
        ax.scatter(x[-1], y[-1], marker="X", s=52, color=PALETTE["orange"], zorder=7)
        ax.set_title(run.scenario.title, color=PALETTE["navy"])
        ax.text(.02, .02, f"{run.assessment.status}\ntermination: {run.metrics['termination_reason']}\nclearance: {_float(run.metrics, 'minimum_clearance_m'):.3f} m", transform=ax.transAxes, fontsize=8.3, va="bottom", bbox={"boxstyle": "round,pad=.3", "fc": PALETTE["white"], "ec": PALETTE["orange"], "alpha": .96})
    fig.subplots_adjust(left=.06, right=.98, top=.87, bottom=.11, wspace=.22)
    _save(fig, artifacts.failure_evidence_png, artifacts.failure_evidence_svg)


def _draw_scorecard(runs: list[ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    apply_engineering_style(); fig, ax = plt.subplots(figsize=(14.5, 6.7)); add_figure_header(fig, "System-validation acceptance scorecard", "The accepted count is reported by classification so controlled failures and boundary observations cannot inflate validated success.")
    classes = ["validated", "boundary", "controlled_failure"]
    labels = ["Validated", "Boundary", "Controlled failure"]
    totals = [sum(run.scenario.classification == cls for run in runs) for cls in classes]
    accepted = [sum(run.scenario.classification == cls and run.assessment.accepted for run in runs) for cls in classes]
    x = np.arange(len(classes)); width=.34
    ax.bar(x - width/2, totals, width, color=PALETTE["gray_light"], edgecolor=PALETTE["gray"], label="Declared scenarios", zorder=2)
    ax.bar(x + width/2, accepted, width, color=[CLASS_COLOR[c] for c in classes], label="Declared outcome observed", zorder=3)
    for xi, a, t in zip(x, accepted, totals): ax.text(xi + width/2, a + .05, f"{a}/{t}", ha="center", fontsize=11, color=PALETTE["navy"], fontweight="bold")
    total_checks = sum(len(run.assessment.checks) for run in runs); passed = sum(check["status"] == "PASS" for run in runs for check in run.assessment.checks)
    ax.text(.02, .06, f"Acceptance checks: {passed}/{total_checks}\nValidated mission success rate: {accepted[0]}/{totals[0]}", transform=ax.transAxes, fontsize=10, color=PALETTE["gray_dark"], bbox={"boxstyle":"round,pad=.35", "fc":PALETTE["white"], "ec":PALETTE["grid"]})
    ax.set_xticks(x, labels); ax.set_ylim(0, max(totals) + 1.0); ax.set_ylabel("Scenario count"); style_axis(ax); ax.legend(loc="upper right")
    fig.subplots_adjust(left=.08, right=.98, top=.87, bottom=.13)
    _save(fig, artifacts.acceptance_scorecard_png, artifacts.acceptance_scorecard_svg)


def _draw_static(runs: list[ScenarioRun], artifacts: Phase1015Artifacts) -> None:
    _draw_trajectories(runs, artifacts); _draw_termination_matrix(runs, artifacts)
    _draw_metrics_dashboard(runs, artifacts); _draw_failure_evidence({r.scenario.identifier: r for r in runs}, artifacts); _draw_scorecard(runs, artifacts)


def _load_prepared() -> tuple[list[ScenarioRun], dict[str, Any]]:
    artifacts = _artifacts(); protocol = load_system_validation(); scenarios = {s.identifier: s for s in system_scenarios(protocol)}
    rows_by: dict[str, list[dict[str, Any]]] = {key: [] for key in scenarios}; events_by: dict[str, list[dict[str, Any]]] = {key: [] for key in scenarios}; checks_by: dict[str, list[dict[str, Any]]] = {key: [] for key in scenarios}
    for row in _read_csv(artifacts.timeseries_csv): rows_by[str(row["scenario"])].append(row)
    for row in _read_csv(artifacts.events_csv): events_by[str(row["scenario"])].append(row)
    for row in _read_csv(artifacts.checks_csv): checks_by[str(row["scenario"])].append(row)
    metrics_rows = {str(row["scenario"]): row for row in _read_csv(artifacts.metrics_csv)}
    assessment_rows = {str(row["scenario"]): row for row in _read_csv(artifacts.acceptance_csv)}
    base = load_reference_configuration(); runs: list[ScenarioRun] = []
    for identifier, scenario in scenarios.items():
        _, environment, _, _, _, _ = build_digital_twin_plant(configuration_for_system_scenario(base, scenario))
        metric = metrics_rows[identifier]
        assessment = SystemAssessment(identifier, scenario.classification, str(assessment_rows[identifier]["status"]), str(assessment_rows[identifier]["accepted"]).lower() == "true", checks_by[identifier], metric)
        runs.append(ScenarioRun(scenario, rows_by[identifier], events_by[identifier], metric, assessment, environment))
    return runs, protocol


def _frame_state(run: ScenarioRun, frame: int, frames: int) -> dict[str, Any]:
    return run.rows[int(_sample_indices(len(run.rows), frames)[frame])]



def _load_visual_protocol() -> dict[str, Any]:
    import yaml
    source = project_root() / "config" / "reference_system_visualisation.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    protocol = data.get("reference_system_visualisation") if isinstance(data, dict) else None
    if not isinstance(protocol, dict) or not isinstance(protocol.get("render"), dict):
        raise ValueError("reference_system_visualisation.yaml requires reference_system_visualisation.render.")
    return protocol


def _render_validated(runs: dict[str, ScenarioRun], artifacts: Phase1015Artifacts, visual: dict[str, Any]) -> None:
    selected = [runs[key] for key in ["nominal_coverage", "cross_current_validated", "energy_reserve_return", "hopper_capacity_return"]]
    frames = int(visual["render"]["frames"]); fps = int(visual["render"]["fps"])
    apply_engineering_style(); fig, axes = plt.subplots(2, 2, figsize=(14.4, 8.2)); axes = axes.ravel()
    add_figure_header(fig, "Validated mission scenarios", "Each panel uses a logged reference mission; markers advance through the same normalized replay fraction.")
    labels: list[Any] = []
    for ax, run in zip(axes, selected):
        _draw_environment(ax, run.environment)
        ax.plot([_float(row, "x_m") for row in run.rows], [_float(row, "y_m") for row in run.rows], color=CLASS_COLOR["validated"], lw=1.4, alpha=.85, zorder=4)
        ax.set_title(run.scenario.title, fontsize=10.5, color=PALETTE["navy"])
        labels.append(ax.text(.02, .02, "", transform=ax.transAxes, fontsize=8, color=PALETTE["gray_dark"],
                              bbox={"boxstyle": "round,pad=.22", "fc": PALETTE["white"], "ec": PALETTE["grid"], "alpha": .94}))
    robot_artists: list[Any] = []
    def update(frame: int):
        nonlocal robot_artists
        for artist in robot_artists:
            artist.remove()
        robot_artists = []
        for label, ax, run in zip(labels, axes, selected):
            row = _frame_state(run, frame, frames)
            robot_artists.extend(_add_robot(ax, _float(row, "x_m"), _float(row, "y_m"), _float(row, "psi_deg"), color=CLASS_COLOR["validated"]))
            label.set_text(f"t = {_float(row, 'time_s'):.0f} s\nmode = {row.get('mode', '')}")
        return robot_artists + labels
    fig.subplots_adjust(left=.05, right=.98, top=.89, bottom=.06, hspace=.35, wspace=.24)
    _save_animation(FuncAnimation(fig, update, frames=frames, interval=1000 / fps, blit=False), artifacts.validated_gif, artifacts.validated_mp4, fps=fps, bitrate=int(visual["render"]["bitrate_kbps"]))


def _render_single(run: ScenarioRun, gif: Path, mp4: Path, visual: dict[str, Any], *, title: str, subtitle: str, color: str) -> None:
    frames = int(visual["render"]["frames"]); fps = int(visual["render"]["fps"])
    apply_engineering_style(); fig, ax = plt.subplots(figsize=(14.4, 8.19)); add_figure_header(fig, title, subtitle); _draw_environment(ax, run.environment)
    x = np.array([_float(row, "x_m") for row in run.rows]); y = np.array([_float(row, "y_m") for row in run.rows])
    ax.plot(x, y, color=color, lw=1.8, zorder=4); indices = _sample_indices(len(run.rows), frames)
    label = ax.text(.02, .02, "", transform=ax.transAxes, fontsize=9, color=PALETTE["gray_dark"],
                    bbox={"boxstyle": "round,pad=.3", "fc": PALETTE["white"], "ec": PALETTE["grid"], "alpha": .96})
    robot_artists: list[Any] = []
    def update(frame: int):
        nonlocal robot_artists
        for artist in robot_artists:
            artist.remove()
        robot_artists = []
        row = run.rows[int(indices[frame])]
        robot_artists.extend(_add_robot(ax, _float(row, "x_m"), _float(row, "y_m"), _float(row, "psi_deg"), color=color))
        label.set_text(f"t = {_float(row, 'time_s'):.1f} s\nmode = {row.get('mode', '')}\nSOC = {_float(row, 'soc'):.3f}\nclearance = {_float(row, 'hazard_clearance_m'):.3f} m")
        return robot_artists + [label]
    fig.subplots_adjust(left=.07, right=.98, top=.88, bottom=.09)
    _save_animation(FuncAnimation(fig, update, frames=frames, interval=1000 / fps, blit=False), gif, mp4, fps=fps, bitrate=int(visual["render"]["bitrate_kbps"]))


def _render_boundary_pair(runs: dict[str, ScenarioRun], artifacts: Phase1015Artifacts, visual: dict[str, Any]) -> None:
    left = runs["diagonal_current_boundary"]; right = runs["uncompensated_diagonal_crossflow"]
    frames = int(visual["render"]["frames"]); fps = int(visual["render"]["fps"])
    apply_engineering_style(); fig, axes = plt.subplots(1, 2, figsize=(14.4, 7.6)); add_figure_header(fig, "Boundary and uncompensated crossflow", "Both panels are intentionally outside the validated operating claim and retain their limiting termination visibly.")
    labels: list[Any] = []
    for ax, run in zip(axes, [left, right]):
        _draw_environment(ax, run.environment)
        ax.plot([_float(row, "x_m") for row in run.rows], [_float(row, "y_m") for row in run.rows], color=CLASS_COLOR[run.scenario.classification], lw=1.7, zorder=4)
        ax.set_title(run.scenario.title, fontsize=10.5, color=PALETTE["navy"])
        labels.append(ax.text(.02, .02, "", transform=ax.transAxes, fontsize=8.5, color=PALETTE["gray_dark"],
                              bbox={"boxstyle": "round,pad=.25", "fc": PALETTE["white"], "ec": PALETTE["orange"], "alpha": .96}))
    robot_artists: list[Any] = []
    def update(frame: int):
        nonlocal robot_artists
        for artist in robot_artists:
            artist.remove()
        robot_artists=[]
        for label, ax, run in zip(labels, axes, [left, right]):
            row=_frame_state(run,frame,frames); color=CLASS_COLOR[run.scenario.classification]
            robot_artists.extend(_add_robot(ax,_float(row,"x_m"),_float(row,"y_m"),_float(row,"psi_deg"),color=color))
            label.set_text(f"{run.assessment.status}\nt = {_float(row,'time_s'):.0f} s\nmode = {row.get('mode','')}")
        return robot_artists + labels
    fig.subplots_adjust(left=.06,right=.98,top=.87,bottom=.10,wspace=.22)
    _save_animation(FuncAnimation(fig, update, frames=frames, interval=1000/fps, blit=False), artifacts.boundary_gif, artifacts.boundary_mp4, fps=fps, bitrate=int(visual["render"]["bitrate_kbps"]))


def _render_timeline(run: ScenarioRun, artifacts: Phase1015Artifacts, visual: dict[str, Any]) -> None:
    frames=int(visual["render"]["frames"]); fps=int(visual["render"]["fps"])
    apply_engineering_style(); fig,(ax_map,ax_tel)=plt.subplots(2,1,figsize=(14.4,8.4),gridspec_kw={"height_ratios":[1.45,1]}); add_figure_header(fig,"Nominal mission state and resource timeline","Map and telemetry are synchronized to logged closed-loop data; no synthetic route is introduced.")
    _draw_environment(ax_map,run.environment)
    x=np.array([_float(row,"x_m") for row in run.rows]);y=np.array([_float(row,"y_m") for row in run.rows]);t=np.array([_float(row,"time_s") for row in run.rows]);soc=np.array([_float(row,"soc") for row in run.rows]);hopper=np.array([_float(row,"hopper_volume_fraction") for row in run.rows]);
    ax_map.plot(x,y,color=CLASS_COLOR["validated"],lw=1.6,zorder=4); ax_tel.plot(t,soc,color=PALETTE["blue"],lw=1.4,label="SOC"); ax_tel.plot(t,hopper,color=PALETTE["orange"],lw=1.4,label="Hopper volume fraction"); ax_tel.set(xlabel="Simulation time (s)",ylabel="Fraction",ylim=(-.03,1.03));style_axis(ax_tel);ax_tel.legend(loc="upper right")
    marker_line=ax_tel.axvline(0,color=PALETTE["gray_dark"],lw=1.0,ls="--"); label=ax_map.text(.02,.02,"",transform=ax_map.transAxes,fontsize=8.7,color=PALETTE["gray_dark"],bbox={"boxstyle":"round,pad=.25","fc":PALETTE["white"],"ec":PALETTE["grid"],"alpha":.96});robot_artists:list[Any]=[];indices=_sample_indices(len(run.rows),frames)
    def update(frame:int):
        nonlocal robot_artists
        for artist in robot_artists: artist.remove()
        robot_artists=[];row=run.rows[int(indices[frame])];time_s=_float(row,"time_s")
        robot_artists.extend(_add_robot(ax_map,_float(row,"x_m"),_float(row,"y_m"),_float(row,"psi_deg"),color=CLASS_COLOR["validated"]))
        marker_line.set_xdata([time_s,time_s]); label.set_text(f"t = {time_s:.0f} s\nmode = {row.get('mode','')}\ncollection count = {row.get('collected_count','0')}")
        return robot_artists+[marker_line,label]
    fig.subplots_adjust(left=.07,right=.98,top=.89,bottom=.09,hspace=.33)
    _save_animation(FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False),artifacts.timeline_gif,artifacts.timeline_mp4,fps=fps,bitrate=int(visual["render"]["bitrate_kbps"]))


def render_one(kind: str) -> None:
    runs, _ = _load_prepared(); by_id={run.scenario.identifier:run for run in runs}; artifacts=_artifacts(); visual=_load_visual_protocol()
    if kind == "validated": _render_validated(by_id, artifacts, visual)
    elif kind == "time_limit": _render_single(by_id["scheduled_time_limit"], artifacts.time_limit_gif, artifacts.time_limit_mp4, visual, title="Scheduled time-limit replay", subtitle="Controlled supervisory termination before coverage completion; this is evidence of the configured time limit, not a validated operating mission.", color=CLASS_COLOR["controlled_failure"])
    elif kind == "boundary": _render_boundary_pair(by_id, artifacts, visual)
    elif kind == "timeline": _render_timeline(by_id["nominal_coverage"], artifacts, visual)
    else: raise ValueError(f"Unknown system-validation render kind: {kind}")


def _gif_info(path: Path) -> dict[str, Any]:
    from PIL import Image
    image=Image.open(path); durations=[]
    for index in range(int(getattr(image,"n_frames",1))):
        image.seek(index);durations.append(int(image.info.get("duration",0)))
    return {"exists":path.exists(),"size_bytes":path.stat().st_size if path.exists() else 0,"frames":int(getattr(image,"n_frames",1)),"duration_s":sum(durations)/1000.0,"width_px":image.width,"height_px":image.height}


def _mp4_info(path: Path) -> dict[str, Any]:
    payload={"exists":path.exists(),"size_bytes":path.stat().st_size if path.exists() else 0}
    if not path.exists(): return payload
    completed=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=width,height","-of","json",str(path)],capture_output=True,text=True)
    if completed.returncode != 0:
        payload["readable"]=False;return payload
    data=json.loads(completed.stdout);stream=next((item for item in data.get("streams",[]) if "width" in item),{});payload.update({"readable":True,"width_px":int(stream.get("width",0)),"height_px":int(stream.get("height",0)),"duration_s":float(data.get("format",{}).get("duration",0.0))});return payload


def _visual_manifest(artifacts: Phase1015Artifacts, visual: dict[str, Any]) -> dict[str, Any]:
    r=visual["render"]; expected_frames=int(r["frames"]); expected_duration=float(r["expected_duration_s"]); min_w=int(r["minimum_width_px"]);min_h=int(r["minimum_height_px"])
    media=[artifacts.validated_gif,artifacts.validated_mp4,artifacts.time_limit_gif,artifacts.time_limit_mp4,artifacts.boundary_gif,artifacts.boundary_mp4,artifacts.timeline_gif,artifacts.timeline_mp4];entries=[]
    for path in media:
        item={"path":relative_to_root(path)}
        if path.suffix.lower()==".gif":
            item.update(_gif_info(path));item.update({"expected_duration_s":expected_duration,"frame_count_ok":item.get("frames")==expected_frames,"duration_ok":abs(float(item.get("duration_s",0.0))-expected_duration)<0.12,"resolution_ok":int(item.get("width_px",0))>=min_w and int(item.get("height_px",0))>=min_h})
        else:
            item.update(_mp4_info(path));item.update({"duration_ok":abs(float(item.get("duration_s",0.0))-expected_duration)<0.45,"resolution_ok":int(item.get("width_px",0))>=min_w and int(item.get("height_px",0))>=min_h-2})
        entries.append(item)
    gifs=[item for item in entries if str(item["path"]).endswith(".gif")]; mp4s=[item for item in entries if str(item["path"]).endswith(".mp4")]
    manifest={"identifier":"AQUASKIM-REF-SYS-VIS-01","entries":entries,"required_animation_count":4,"observed_animation_count":len(gifs),"required_video_count":4,"observed_video_count":len(mp4s),"all_gif_frame_counts_ok":all(bool(item.get("frame_count_ok")) for item in gifs),"all_gif_durations_ok":all(bool(item.get("duration_ok")) for item in gifs),"all_gif_resolutions_ok":all(bool(item.get("resolution_ok")) for item in gifs),"all_mp4_exist":all(bool(item.get("exists")) for item in mp4s),"all_mp4_readable":all(bool(item.get("readable")) for item in mp4s),"all_mp4_durations_ok":all(bool(item.get("duration_ok")) for item in mp4s),"all_mp4_resolutions_ok":all(bool(item.get("resolution_ok")) for item in mp4s)}
    return manifest


def _write_summary(runs: list[ScenarioRun], artifacts: Phase1015Artifacts, manifest: dict[str, Any] | None) -> dict[str, Any]:
    classes={cls:[run for run in runs if run.scenario.classification==cls] for cls in ("validated","boundary","controlled_failure")}
    check_rows=[check for run in runs for check in run.assessment.checks]
    summary={"identifier":"AQUASKIM-REF-SYS-01","status":"PASS" if all(run.assessment.accepted for run in runs) else "FAIL","non_interactive":True,"classes":{cls:{"declared":len(items),"accepted":sum(run.assessment.accepted for run in items)} for cls,items in classes.items()},"scenarios":[_scenario_row(run) for run in runs],"acceptance":{"passed":sum(check["status"]=="PASS" for check in check_rows),"total":len(check_rows)},"visual_quality":manifest,"artifacts":artifacts.as_dict()}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    validated=classes["validated"]; boundary=classes["boundary"]; failure=classes["controlled_failure"]
    lines=["# System-level scenario validation and controlled-failure evidence","","## Scope","This suite executes fixed, deterministic reference scenarios. It does not generate a Word report, delivery ZIP or release artifact. Boundary and controlled-failure runs are retained as limitations, not validated operating claims.","","## Validated scenarios",f"- Validated scenarios accepted: `{sum(run.assessment.accepted for run in validated)}/{len(validated)}`.",f"- Current limit inside this protocol: `0.020 m/s`.","","## Boundary observation",f"- `{boundary[0].scenario.title}`: `{boundary[0].assessment.status}`; termination `{boundary[0].metrics['termination_reason']}`.","","## Controlled failure evidence"]
    for run in failure: lines.append(f"- `{run.scenario.title}`: `{run.assessment.status}`; termination `{run.metrics['termination_reason']}`; minimum clearance `{_float(run.metrics,'minimum_clearance_m'):.3f} m`.")
    lines.extend(["","## Acceptance and media QA",f"- Acceptance checks passed: `{summary['acceptance']['passed']}/{summary['acceptance']['total']}`.",f"- Required GIF / observed GIF: `{(manifest or {}).get('required_animation_count','not rendered')} / {(manifest or {}).get('observed_animation_count','not rendered')}`.",f"- Required MP4 / observed MP4: `{(manifest or {}).get('required_video_count','not rendered')} / {(manifest or {}).get('observed_video_count','not rendered')}`.","","## Model boundary","These are numerical results from the documented low-speed 3-DOF sheltered-basin model. Controlled-failure and boundary replays demonstrate model and policy limits; they do not represent sea trials, physical current estimation, wave response or certification."])
    artifacts.summary_markdown.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return summary


def _record(artifacts: Phase1015Artifacts, summary: dict[str, Any]) -> Path:
    d=_dirs();run_id="phase10_15_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ");run=d["records"]/run_id;(run/"artifacts").mkdir(parents=True,exist_ok=True);(run/"inputs").mkdir(parents=True,exist_ok=True)
    for source in [project_root()/"config"/"reference_system_validation.yaml",project_root()/"config"/"reference_system_visualisation.yaml",project_root()/"config"/"reference_design.yaml"]: shutil.copy2(source,run/"inputs"/source.name)
    hashes={}
    for path in artifacts.__dict__.values():
        if isinstance(path,Path) and path.exists():
            shutil.copy2(path,run/"artifacts"/path.name);hashes[relative_to_root(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (run/"artifact_manifest.json").write_text(json.dumps({"run_id":run_id,"hashes":hashes,"summary":summary},ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    env={"python":sys.version,"executable":sys.executable,"timestamp_utc":datetime.now(timezone.utc).isoformat()}
    try: env["pip_freeze"]=subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True)
    except Exception as exc: env["pip_freeze_error"]=repr(exc)
    (run/"environment_snapshot.json").write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding="utf-8")
    handoff=d["handoffs"] / "PHASE10_15_LATEST_HANDOFF.md"
    handoff.write_text(f"# System-level scenario validation handoff\n\n- Run ID: `{run_id}`\n- Validated, boundary and controlled-failure scenarios were evaluated separately.\n- No Word report, delivery ZIP or release build was invoked.\n- Evidence: `{relative_to_root(run)}`\n",encoding="utf-8")
    return run


def prepare_phase10_15() -> tuple[Phase1015Artifacts, list[ScenarioRun], dict[str, Any], dict[str, Any]]:
    ensure_runtime_directories(); artifacts=_artifacts(); protocol=load_system_validation(); base=load_reference_configuration();runs=[]
    sample_period_s = float(protocol["logging_sample_period_s"])
    for scenario in system_scenarios(protocol):
        result, environment=run_system_scenario(scenario,base);assessment=assess_system_scenario(scenario,result)
        runs.append(ScenarioRun(scenario,_downsample_rows(result.rows, sample_period_s),result.events,dict(result.metrics),assessment,environment))
    if not all(run.assessment.accepted for run in runs):
        bad=", ".join(run.scenario.identifier for run in runs if not run.assessment.accepted); raise RuntimeError(f"System-validation protocol mismatch: {bad}")
    catalog=[{"scenario":run.scenario.identifier,"title":run.scenario.title,"classification":run.scenario.classification,"description":run.scenario.description,"current_magnitude_mps":run.scenario.current_magnitude_mps,"expected":json.dumps(run.scenario.expected,ensure_ascii=False)} for run in runs]
    _write_csv(artifacts.scenario_catalog_csv,catalog);_write_csv(artifacts.metrics_csv,[_scenario_row(run) for run in runs]);_write_csv(artifacts.checks_csv,[check for run in runs for check in run.assessment.checks]);_write_csv(artifacts.events_csv,[{"scenario":run.scenario.identifier,"classification":run.scenario.classification,**event} for run in runs for event in run.events]);_write_csv(artifacts.timeseries_csv,[{"scenario":run.scenario.identifier,"classification":run.scenario.classification,**row} for run in runs for row in run.rows]);_write_csv(artifacts.state_segments_csv,[segment for run in runs for segment in _segments(run)]);_write_csv(artifacts.acceptance_csv,[{"scenario":run.scenario.identifier,"classification":run.scenario.classification,"status":run.assessment.status,"accepted":run.assessment.accepted} for run in runs])
    _draw_static(runs,artifacts); summary=_write_summary(runs,artifacts,None);return artifacts,runs,protocol,summary


def finalize_phase10_15(*, record: bool=True) -> tuple[Phase1015Artifacts, Path | None]:
    artifacts=_artifacts(); runs,_= _load_prepared();visual=_load_visual_protocol();media=[artifacts.validated_gif,artifacts.validated_mp4,artifacts.time_limit_gif,artifacts.time_limit_mp4,artifacts.boundary_gif,artifacts.boundary_mp4,artifacts.timeline_gif,artifacts.timeline_mp4]
    if not all(path.exists() and path.stat().st_size>0 for path in media): raise FileNotFoundError("System-validation media set is incomplete; render all GIF/MP4 files before finalization.")
    manifest=_visual_manifest(artifacts,visual); artifacts.visual_quality_manifest_json.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    quality=all(bool(manifest[key]) for key in ["all_gif_frame_counts_ok","all_gif_durations_ok","all_gif_resolutions_ok","all_mp4_exist","all_mp4_readable","all_mp4_durations_ok","all_mp4_resolutions_ok"])
    if not quality: raise RuntimeError("System-validation media quality gate failed.")
    write_animation_audit_sheet([artifacts.validated_gif,artifacts.time_limit_gif,artifacts.boundary_gif,artifacts.timeline_gif],artifacts.contact_sheet_png,samples_per_animation=int(visual["render"]["contact_sheet_samples"]))
    summary=_write_summary(runs,artifacts,manifest)
    if int(summary["acceptance"]["total"]) <= 0:
        raise RuntimeError("System-validation finalization found no persisted acceptance checks.")
    if summary["status"]!="PASS": raise RuntimeError("System-validation acceptance checks failed.")
    run=_record(artifacts,summary) if record else None;return artifacts,run


def run_phase10_15(*, record: bool=True, render: bool=True) -> tuple[Phase1015Artifacts, Path | None]:
    artifacts,_,_,_=prepare_phase10_15()
    if render:
        for kind in ("validated","time_limit","boundary","timeline"): render_one(kind)
        return finalize_phase10_15(record=record)
    return artifacts,None


def print_phase10_15_summary(result: tuple[Phase1015Artifacts, Path | None] | Phase1015Artifacts) -> None:
    artifacts,run=result if isinstance(result,tuple) else (result,None)
    print("="*72);print("AquaSkim-Sim | System-level Scenario Validation");print("="*72);print(f"Scenario map  : {relative_to_root(artifacts.trajectories_png)}");print(f"Contact sheet : {relative_to_root(artifacts.contact_sheet_png)}");print(f"Visual QA     : {relative_to_root(artifacts.visual_quality_manifest_json)}");print(f"Evidence      : {relative_to_root(run) if run else 'not recorded'}");print("Status        : PASS");print("="*72)


if __name__ == "__main__":
    print_phase10_15_summary(run_phase10_15(record=True,render=True))
