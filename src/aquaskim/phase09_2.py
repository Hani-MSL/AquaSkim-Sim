"""Phase 09.2: comprehensive scenario validation, uncertainty study, and visual evidence.

This phase is intentionally explicit about model validity. It separates:
- validated operating cases, which are counted in acceptance statistics;
- protective energy-return cases, which demonstrate conservative behavior; and
- boundary cases, which expose the current limitations of the simplified plant
  and controller without being mislabeled as successful missions.

All numerical outputs are generated from the actual closed-loop model in Phase
08/08.2. No values are manually authored for the report.
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
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
import numpy as np
import yaml

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
class ScenarioDefinition:
    identifier: str
    title: str
    scenario_class: str
    expected_outcome: str
    description: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class ScenarioRun:
    definition: ScenarioDefinition
    config: ProjectConfiguration
    result: MissionResult
    metrics: dict[str, object]


@dataclass(frozen=True)
class Phase092Artifacts:
    scenario_matrix: Path
    scenario_matrix_svg: Path
    scorecard: Path
    scorecard_svg: Path
    operating_envelope: Path
    operating_envelope_svg: Path
    sensitivity_heatmap: Path
    sensitivity_heatmap_svg: Path
    safety_energy_dashboard: Path
    safety_energy_dashboard_svg: Path
    control_performance: Path
    control_performance_svg: Path
    coverage_collection: Path
    coverage_collection_svg: Path
    state_distribution: Path
    state_distribution_svg: Path
    scenario_catalog_table: Path
    deterministic_metrics_table: Path
    scenario_time_series_table: Path
    event_ledger_table: Path
    monte_carlo_trials_table: Path
    monte_carlo_summary_table: Path
    envelope_table: Path
    acceptance_checks_table: Path
    animation_manifest_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path
    scenario_reel_gif: Path
    scenario_reel_mp4: Path
    nominal_telemetry_gif: Path
    nominal_telemetry_mp4: Path
    energy_return_gif: Path
    energy_return_mp4: Path
    safety_replan_gif: Path
    safety_replan_mp4: Path
    monte_carlo_gif: Path
    monte_carlo_mp4: Path
    boundary_case_gif: Path
    boundary_case_mp4: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


STATE_INDEX = {
    AgentState.INIT.value: 0,
    AgentState.SEARCH.value: 1,
    AgentState.TRANSIT_TO_DEBRIS.value: 2,
    AgentState.COLLECT.value: 3,
    AgentState.RETURN_HOME.value: 4,
    AgentState.DOCK.value: 5,
    AgentState.MISSION_COMPLETE.value: 6,
    AgentState.EMERGENCY_STOP.value: 7,
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _deep_merge(destination: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(destination.get(key), dict):
            _deep_merge(destination[key], value)
        else:
            destination[key] = copy.deepcopy(value)
    return destination


def _scenario_config(base: ProjectConfiguration, overrides: dict[str, Any]) -> ProjectConfiguration:
    data = copy.deepcopy(base.data)
    _deep_merge(data, overrides)
    return ProjectConfiguration(source_path=base.source_path, data=data)


def _load_plan() -> tuple[list[ScenarioDefinition], dict[str, Any]]:
    path = DIRECTORIES["config"] / "phase09_2_scenarios.yaml"
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    definitions = [
        ScenarioDefinition(
            identifier=str(item["id"]),
            title=str(item["title"]),
            scenario_class=str(item["class"]),
            expected_outcome=str(item["expected_outcome"]),
            description=str(item["description"]),
            overrides=dict(item["overrides"]),
        )
        for item in document["deterministic_scenarios"]
    ]
    return definitions, dict(document["validation_contract"])


def _current_vector(config: ProjectConfiguration) -> tuple[float, float]:
    source = config.data["autonomy"]["current_earth_mps"]
    return float(source[0]), float(source[1])


def _current_magnitude(config: ProjectConfiguration) -> float:
    x, y = _current_vector(config)
    return float(math.hypot(x, y))


def _scenario_status(result: MissionResult, expected: str) -> str:
    m = result.metrics
    if expected == "proactive_return":
        return "PROTECTIVE_RETURN" if int(m["energy_return_triggered"]) == 1 else "UNEXPECTED"
    if expected == "time_limited_boundary":
        return "BOUNDARY_LIMIT" if int(m["mission_success"]) == 0 else "BOUNDARY_EXCEEDED_EXPECTATION"
    if int(m["mission_success"]) == 1 and str(m["final_state"]) == AgentState.MISSION_COMPLETE.value:
        return "VALIDATED_SUCCESS"
    return "UNEXPECTED"


def _metrics(result: MissionResult, scenario: ScenarioDefinition, config: ProjectConfiguration) -> dict[str, object]:
    m = result.metrics
    current_x, current_y = _current_vector(config)
    events = result.event_rows
    energy_event = next((row for row in events if "return-energy" in str(row["reason"])), None)
    collection_efficiency = int(m["collected_count"]) / max(1e-9, float(m["total_planned_length_m"]))
    safety_ok = float(m["minimum_hazard_distance_m"]) >= 0.0
    return {
        "scenario_id": scenario.identifier,
        "title": scenario.title,
        "scenario_class": scenario.scenario_class,
        "expected_outcome": scenario.expected_outcome,
        "observed_outcome": _scenario_status(result, scenario.expected_outcome),
        "current_x_mps": current_x,
        "current_y_mps": current_y,
        "current_magnitude_mps": _current_magnitude(config),
        "initial_soc": float(config.data["autonomy"]["initial_soc"]),
        "max_collections": int(config.data["autonomy"]["max_collections"]),
        "mission_time_limit_s": float(config.data["autonomy"]["mission_duration_s"]),
        "mission_success": int(m["mission_success"]),
        "final_state": str(m["final_state"]),
        "duration_s": float(m["duration_s"]),
        "collected_count": int(m["collected_count"]),
        "collected_mass_kg": float(m["collected_mass_kg"]),
        "final_soc": float(m["final_soc"]),
        "final_home_error_m": float(m["final_distance_home_m"]),
        "minimum_clearance_m": float(m["minimum_hazard_distance_m"]),
        "safety_intervention_count": int(m["safety_intervention_count"]),
        "replan_count": int(m["replan_count"]),
        "energy_return_triggered": int(m["energy_return_triggered"]),
        "energy_return_time_s": float(energy_event["time_s"]) if energy_event else float("nan"),
        "planned_route_length_m": float(m["total_planned_length_m"]),
        "collection_efficiency_items_per_m": collection_efficiency,
        "state_transition_count": int(m["state_transition_count"]),
    }


def _contract_for_base(base: ProjectConfiguration, contract: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(contract)
    profile_contract = base.data.get("validation", {}).get("phase09_2", {})
    if isinstance(profile_contract, dict):
        _deep_merge(merged, profile_contract)
    return merged


def _run_deterministic(base: ProjectConfiguration) -> tuple[list[ScenarioRun], dict[str, Any]]:
    definitions, contract = _load_plan()
    contract = _contract_for_base(base, contract)
    runs: list[ScenarioRun] = []
    for definition in definitions:
        scenario_config = _scenario_config(base, definition.overrides)
        result, _, _ = _run_mission(scenario_config)
        runs.append(ScenarioRun(definition, scenario_config, result, _metrics(result, definition, scenario_config)))
    return runs, contract


def _mc_rows(base: ProjectConfiguration, contract: dict[str, Any]) -> list[dict[str, object]]:
    trials = int(contract["monte_carlo_trials"])
    seed = int(contract["monte_carlo_seed"])
    rng = np.random.default_rng(seed)
    current_levels = (0.0, 0.05, 0.10, 0.15, 0.20)
    soc_levels = (0.24, 0.42, 0.72)
    directions = (0.0, 90.0)
    design = [(magnitude, soc, direction) for magnitude in current_levels for soc in soc_levels for direction in directions]
    order = rng.permutation(len(design))[:trials]
    records: list[dict[str, object]] = []
    for index, design_index in enumerate(order, start=1):
        magnitude, initial_soc, direction_deg = design[int(design_index)]
        angle = math.radians(direction_deg)
        definition = ScenarioDefinition(
            identifier=f"mc_{index:02d}",
            title="Monte Carlo envelope sample",
            scenario_class="sample",
            expected_outcome="envelope_sample",
            description="Seeded stratified current/SOC sample.",
            overrides={},
        )
        overrides = {
            "autonomy": {
                "mission_duration_s": float(contract["scenario_time_limit_s"]),
                "max_collections": 3,
                "initial_soc": initial_soc,
                "rth_soc_floor": 0.18,
                "current_earth_mps": [magnitude * math.cos(angle), magnitude * math.sin(angle)],
                "random_seed": 8026,
            },
            "environment_model": {"debris": {"seed": 7107}},
        }
        config = _scenario_config(base, overrides)
        result, _, _ = _run_mission(config)
        row = _metrics(result, definition, config)
        row.update({
            "trial_index": index,
            "current_direction_deg": direction_deg,
            "rng_seed": seed,
            "inside_validated_envelope": int(magnitude <= float(contract["valid_current_limit_mps"]) and initial_soc >= float(contract["valid_soc_floor"])),
        })
        records.append(row)
    return records


def _summary_rows(rows: list[dict[str, object]], contract: dict[str, Any]) -> list[dict[str, object]]:
    valid = [row for row in rows if int(row["inside_validated_envelope"]) == 1]
    all_rows = rows
    def mean(values: list[dict[str, object]], name: str) -> float:
        return float(np.mean([float(item[name]) for item in values])) if values else float("nan")
    def minimum(values: list[dict[str, object]], name: str) -> float:
        return float(np.min([float(item[name]) for item in values])) if values else float("nan")
    return [
        {"metric": "trial_count", "value": len(all_rows), "unit": "trials", "scope": "all sampled conditions", "interpretation": "Seeded stratified sample count."},
        {"metric": "validated_envelope_trial_count", "value": len(valid), "unit": "trials", "scope": "current <= valid limit and SOC >= valid floor", "interpretation": "Subset counted for acceptance."},
        {"metric": "validated_envelope_success_rate", "value": mean(valid, "mission_success"), "unit": "fraction", "scope": "validated envelope", "interpretation": "Closed-loop completion with docking."},
        {"metric": "validated_envelope_minimum_clearance", "value": minimum(valid, "minimum_clearance_m"), "unit": "m", "scope": "validated envelope", "interpretation": "Worst signed configuration-space clearance."},
        {"metric": "mean_collection_efficiency", "value": mean(valid, "collection_efficiency_items_per_m"), "unit": "items/m", "scope": "validated envelope", "interpretation": "Confirmed captures per planned route meter."},
        {"metric": "p05_final_soc", "value": float(np.quantile([float(row["final_soc"]) for row in all_rows], 0.05)), "unit": "fraction", "scope": "all sampled conditions", "interpretation": "Low-tail terminal SOC across scenario envelope."},
        {"metric": "boundary_limit_count", "value": sum(int(row["mission_success"]) == 0 for row in all_rows), "unit": "trials", "scope": "all sampled conditions", "interpretation": "Failures are retained as operating-envelope evidence rather than omitted."},
    ]


def _run_lookup(runs: list[ScenarioRun]) -> dict[str, ScenarioRun]:
    return {run.definition.identifier: run for run in runs}


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings, *, inflated: bool = False) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            if inflated:
                ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m + environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.45, zorder=1))
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.9, zorder=3))
        elif isinstance(obstacle, RectangleObstacle):
            if inflated:
                ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m - environment.robot_safety_radius_m, obstacle.center_m[1] - obstacle.half_y_m - environment.robot_safety_radius_m), obstacle.size_m[0] + 2 * environment.robot_safety_radius_m, obstacle.size_m[1] + 2 * environment.robot_safety_radius_m, facecolor=PALETTE["orange_light"], edgecolor="none", alpha=0.45, zorder=1))
            ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m, obstacle.center_m[1] - obstacle.half_y_m), obstacle.size_m[0], obstacle.size_m[1], facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.9, zorder=3))


def _map_axis(ax: plt.Axes, env: EnvironmentSettings, title: str) -> None:
    ax.set_xlim(0.0, env.length_m); ax.set_ylim(0.0, env.width_m)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, loc="left", fontsize=10.5)
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]")
    style_axis(ax)


def _arrays(result: MissionResult) -> dict[str, np.ndarray]:
    keys = (
        "time_s", "x_m", "y_m", "psi_deg", "u_mps", "v_mps", "r_rps",
        "hazard_distance_m", "soc", "bus_load_w", "battery_current_a",
        "port_thrust_n", "starboard_thrust_n", "heading_error_rad", "desired_speed_mps",
        "yaw_moment_command_n_m", "collected_count", "distance_home_m",
    )
    return {key: np.asarray([float(row.get(key, 0.0)) for row in result.rows], dtype=float) for key in keys}


def _draw_scenario_matrix(runs: list[ScenarioRun], env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(18, 13), constrained_layout=False)
    grid = GridSpec(2, 3, figure=fig, left=.055, right=.955, top=.885, bottom=.075, hspace=.29, wspace=.22)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Comprehensive Scenario Matrix", "Validated operating cases, protective energy behavior, and deliberately exposed boundary conditions are visually separated.")
    for index, run in enumerate(runs):
        ax = fig.add_subplot(grid[index // 3, index % 3])
        _draw_obstacles(ax, env, inflated=True)
        data = _arrays(run.result)
        ax.plot(data["x_m"], data["y_m"], linewidth=1.9, color=PALETTE["blue"], zorder=5)
        ax.scatter([data["x_m"][0]], [data["y_m"][0]], marker="s", s=42, color=PALETTE["navy"], zorder=7)
        ax.scatter([data["x_m"][-1]], [data["y_m"][-1]], marker="X", s=52, color=PALETTE["green"] if int(run.metrics["mission_success"]) else "#A74E4E", zorder=7)
        for target in run.result.target_rows:
            ax.scatter([float(target["x_m"])], [float(target["y_m"])], marker="*", s=90, color=PALETTE["green"], zorder=8)
        status = str(run.metrics["observed_outcome"])
        caption = f"{run.definition.title}\n{status} • current={float(run.metrics['current_magnitude_mps']):.2f} m/s • captures={int(run.metrics['collected_count'])}"
        _map_axis(ax, env, fill(caption, width=46))
    return export_figure(fig, output, dpi=280)


def _draw_scorecard(runs: list[ScenarioRun], output: Path) -> FigureExport:
    apply_engineering_style()
    labels = [run.definition.identifier.replace("_", "\n") for run in runs]
    duration = [float(run.metrics["duration_s"]) for run in runs]
    capture = [int(run.metrics["collected_count"]) for run in runs]
    soc = [100 * float(run.metrics["final_soc"]) for run in runs]
    clearance = [float(run.metrics["minimum_clearance_m"]) for run in runs]
    fig = plt.figure(figsize=(17, 11), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.95, top=.88, bottom=.18, hspace=.38, wspace=.27)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Mission Performance Scorecard", "The scorecard makes successful, protective, and boundary outcomes directly comparable without hiding non-success observations.")
    charts = [("Mission duration", duration, "s"), ("Confirmed captures", capture, "items"), ("Terminal state of charge", soc, "%"), ("Minimum signed clearance", clearance, "m")]
    for ax, (title, values, unit) in zip([fig.add_subplot(grid[i // 2, i % 2]) for i in range(4)], charts):
        ax.bar(np.arange(len(labels)), values)
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_ylabel(unit); ax.set_xticks(np.arange(len(labels))); ax.set_xticklabels(labels, fontsize=7.2)
        style_axis(ax)
        for idx, value in enumerate(values): ax.text(idx, value, f"{value:.2f}" if isinstance(value, float) else str(value), ha="center", va="bottom", fontsize=7.2)
    return export_figure(fig, output, dpi=280)


def _draw_operating_envelope(mc: list[dict[str, object]], contract: dict[str, Any], output: Path) -> FigureExport:
    apply_engineering_style()
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    fig.subplots_adjust(left=.07, right=.95, top=.84, bottom=.14, wspace=.28)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Current/SOC Operating Envelope", "Stratified Monte Carlo samples distinguish the validated envelope from exploratory boundary samples.")
    current = np.asarray([float(row["current_magnitude_mps"]) for row in mc]); soc = np.asarray([float(row["initial_soc"]) for row in mc]); success = np.asarray([int(row["mission_success"]) for row in mc])
    valid = np.asarray([int(row["inside_validated_envelope"]) for row in mc])
    axes[0].axvspan(0.0, float(contract["valid_current_limit_mps"]), alpha=.12)
    axes[0].axhspan(float(contract["valid_soc_floor"]), 1.0, alpha=.12)
    for flag, marker, label in ((1, "o", "mission complete"), (0, "X", "not complete")):
        selector = success == flag
        axes[0].scatter(current[selector], soc[selector], marker=marker, s=65, label=label)
    axes[0].axvline(float(contract["valid_current_limit_mps"]), linestyle="--", linewidth=1.0)
    axes[0].axhline(float(contract["valid_soc_floor"]), linestyle="--", linewidth=1.0)
    axes[0].set_xlabel("Current magnitude [m/s]"); axes[0].set_ylabel("Initial SOC [-]"); axes[0].set_title("Sample outcome map", loc="left", fontsize=11); axes[0].legend(fontsize=8); style_axis(axes[0])
    clearance = np.asarray([float(row["minimum_clearance_m"]) for row in mc])
    axes[1].scatter(current, clearance, s=70, marker="o")
    axes[1].axhline(0.0, linestyle="--", linewidth=1.0)
    axes[1].axvline(float(contract["valid_current_limit_mps"]), linestyle="--", linewidth=1.0)
    axes[1].set_xlabel("Current magnitude [m/s]"); axes[1].set_ylabel("Minimum signed clearance [m]"); axes[1].set_title("Safety margin by current", loc="left", fontsize=11); style_axis(axes[1])
    return export_figure(fig, output, dpi=280)


def _draw_sensitivity_heatmap(mc: list[dict[str, object]], output: Path) -> FigureExport:
    apply_engineering_style()
    current_levels = sorted({round(float(row["current_magnitude_mps"]), 2) for row in mc})
    soc_levels = sorted({round(float(row["initial_soc"]), 2) for row in mc})
    matrix = np.full((len(soc_levels), len(current_levels)), np.nan)
    for i, soc in enumerate(soc_levels):
        for j, current in enumerate(current_levels):
            values = [int(row["mission_success"]) for row in mc if round(float(row["initial_soc"]), 2) == soc and round(float(row["current_magnitude_mps"]), 2) == current]
            if values: matrix[i, j] = float(np.mean(values))
    fig, ax = plt.subplots(figsize=(11, 7.8))
    fig.subplots_adjust(left=.12, right=.90, top=.84, bottom=.14)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Success Sensitivity Heatmap", "Cell values report completion fraction across seeded direction variants; blank cells were not sampled.")
    image = ax.imshow(matrix, origin="lower", aspect="auto", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(current_levels))); ax.set_xticklabels([f"{value:.2f}" for value in current_levels])
    ax.set_yticks(range(len(soc_levels))); ax.set_yticklabels([f"{value:.2f}" for value in soc_levels])
    ax.set_xlabel("Current magnitude [m/s]"); ax.set_ylabel("Initial SOC [-]"); ax.set_title("Closed-loop mission-completion fraction", loc="left", fontsize=11)
    for i in range(len(soc_levels)):
        for j in range(len(current_levels)):
            if not np.isnan(matrix[i, j]): ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center", fontsize=10, fontweight="bold")
    fig.colorbar(image, ax=ax, label="completion fraction")
    return export_figure(fig, output, dpi=280)


def _draw_safety_energy(runs: list[ScenarioRun], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(17, 10.2), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.95, top=.88, bottom=.11, hspace=.34, wspace=.27)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Safety and Energy Decision Evidence", "Each panel is derived from the closed-loop telemetry and state-event ledger.")
    selected = _run_lookup(runs)
    safety = selected["mild_east_current_safety_replan"]
    energy = selected["proactive_energy_return"]
    for ax, run, key in ((fig.add_subplot(grid[0,0]), safety, "hazard_distance_m"), (fig.add_subplot(grid[0,1]), safety, "soc"), (fig.add_subplot(grid[1,0]), energy, "distance_home_m"), (fig.add_subplot(grid[1,1]), energy, "soc")):
        data = _arrays(run.result)
        time = data["time_s"]
        if key == "soc": values = 100 * data[key]; label = "SOC [%]"
        elif key == "hazard_distance_m": values = data[key]; label = "Signed clearance [m]"
        else: values = data[key]; label = "Distance to home [m]"
        ax.plot(time, values, linewidth=1.9)
        for event in run.result.event_rows:
            if "safety shield" in str(event["reason"]) or "return-energy" in str(event["reason"]): ax.axvline(float(event["time_s"]), linestyle="--", linewidth=1.0)
        ax.set_title(run.definition.title, loc="left", fontsize=10.2); ax.set_xlabel("Time [s]"); ax.set_ylabel(label); style_axis(ax)
    return export_figure(fig, output, dpi=280)


def _draw_control_performance(runs: list[ScenarioRun], output: Path) -> FigureExport:
    apply_engineering_style()
    run = _run_lookup(runs)["nominal_multitarget"]
    data = _arrays(run.result); time = data["time_s"]
    fig = plt.figure(figsize=(17, 10.2), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.07, right=.95, top=.88, bottom=.11, hspace=.34, wspace=.27)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Nominal Closed-Loop Control Performance", "Heading, surge speed, differential thrust and yaw command are plotted from the actual controller telemetry.")
    plots = [
        ("Heading error", np.degrees(data["heading_error_rad"]), "deg"),
        ("Ground-plane speed", np.hypot(data["u_mps"], data["v_mps"]), "m/s"),
        ("Port / starboard thrust", None, "N"),
        ("Yaw-moment command", data["yaw_moment_command_n_m"], "N m"),
    ]
    axes = [fig.add_subplot(grid[i//2, i%2]) for i in range(4)]
    for ax, (title, values, unit) in zip(axes, plots):
        ax.set_title(title, loc="left", fontsize=10.5); ax.set_xlabel("Time [s]"); ax.set_ylabel(unit); style_axis(ax)
        if values is None:
            ax.plot(time, data["port_thrust_n"], label="port")
            ax.plot(time, data["starboard_thrust_n"], label="starboard")
            ax.legend(fontsize=8)
        else: ax.plot(time, values, linewidth=1.7)
    return export_figure(fig, output, dpi=280)


def _grid_coverage_fraction(result: MissionResult, env: EnvironmentSettings, resolution: float = 0.25) -> float:
    cells: set[tuple[int, int]] = set()
    for row in result.rows:
        x, y = float(row["x_m"]), float(row["y_m"])
        if 0 <= x <= env.length_m and 0 <= y <= env.width_m: cells.add((int(x/resolution), int(y/resolution)))
    return len(cells) / max(1, int(math.ceil(env.length_m/resolution)) * int(math.ceil(env.width_m/resolution)))


def _draw_coverage_collection(runs: list[ScenarioRun], env: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style()
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    fig.subplots_adjust(left=.07,right=.95,top=.84,bottom=.15,wspace=.28)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Coverage and Collection Efficiency", "Efficiency is shown as confirmed captures per planned meter; coverage is a sampled path-footprint proxy, not a swept-area CFD result.")
    labels = [run.definition.identifier.replace("_", "\n") for run in runs]
    coverage = [_grid_coverage_fraction(run.result, env) for run in runs]
    efficiency = [float(run.metrics["collection_efficiency_items_per_m"]) for run in runs]
    axes[0].bar(np.arange(len(labels)), coverage); axes[0].set_title("Sampled path-footprint coverage", loc="left", fontsize=11); axes[0].set_ylabel("fraction of basin grid"); axes[0].set_xticks(np.arange(len(labels))); axes[0].set_xticklabels(labels, fontsize=7.2); style_axis(axes[0])
    axes[1].bar(np.arange(len(labels)), efficiency); axes[1].set_title("Collection efficiency", loc="left", fontsize=11); axes[1].set_ylabel("verified items / planned meter"); axes[1].set_xticks(np.arange(len(labels))); axes[1].set_xticklabels(labels, fontsize=7.2); style_axis(axes[1])
    return export_figure(fig, output, dpi=280)


def _draw_state_distribution(runs: list[ScenarioRun], output: Path) -> FigureExport:
    apply_engineering_style()
    fig, ax = plt.subplots(figsize=(15, 8))
    fig.subplots_adjust(left=.08,right=.95,top=.84,bottom=.19)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Agent-State Time Distribution", "State occupancy is obtained from the time-stepped mission ledger, not inferred from static routes.")
    states = [AgentState.SEARCH.value, AgentState.TRANSIT_TO_DEBRIS.value, AgentState.COLLECT.value, AgentState.RETURN_HOME.value, AgentState.DOCK.value]
    bottom = np.zeros(len(runs))
    positions = np.arange(len(runs))
    for state in states:
        values = []
        for run in runs:
            dt = float(run.config.data["autonomy"]["integration_time_step_s"])
            values.append(sum(1 for row in run.result.rows if str(row["state"]) == state) * dt)
        ax.bar(positions, values, bottom=bottom, label=state)
        bottom += np.asarray(values)
    ax.set_xticks(positions); ax.set_xticklabels([run.definition.identifier.replace("_", "\n") for run in runs], fontsize=7.4)
    ax.set_ylabel("Approximate state time [s]"); ax.set_title("Mission-state occupancy", loc="left", fontsize=11); ax.legend(ncol=3, fontsize=8, loc="upper right"); style_axis(ax)
    return export_figure(fig, output, dpi=280)


def _frame_indices(length: int, count: int) -> np.ndarray:
    return np.unique(np.linspace(0, length - 1, min(length, count), dtype=int))


def _save_animation(animation: FuncAnimation, gif_path: Path, mp4_path: Path, *, fps: int = 10, dpi: int = 78) -> None:
    gif_path.parent.mkdir(parents=True, exist_ok=True); mp4_path.parent.mkdir(parents=True, exist_ok=True)
    animation.save(gif_path, writer=PillowWriter(fps=fps), dpi=dpi)
    animation.save(mp4_path, writer=FFMpegWriter(fps=fps, bitrate=1700), dpi=dpi)


def _animate_scenario_reel(runs: list[ScenarioRun], env: EnvironmentSettings, gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style()
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.subplots_adjust(left=.06,right=.96,top=.88,bottom=.08,hspace=.30,wspace=.22)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09.2 — Scenario Reel", "Synchronous mission progress across validated, protective and boundary cases.")
    arrays = [_arrays(run.result) for run in runs]
    indices = [_frame_indices(len(data["time_s"]), frames) for data in arrays]
    lines=[]; craft=[]
    for ax, run in zip(axes.ravel(), runs):
        _draw_obstacles(ax, env, inflated=True); _map_axis(ax, env, fill(run.definition.title, width=34));
        line, = ax.plot([], [], linewidth=1.6); dot = ax.scatter([], [], s=44, marker="o")
        lines.append(line); craft.append(dot)
    def update(frame: int):
        artists=[]
        progress=frame/max(1,frames-1)
        for data, idxs, line, dot in zip(arrays,indices,lines,craft):
            idx = idxs[min(len(idxs)-1, int(progress*(len(idxs)-1)))]
            line.set_data(data["x_m"][:idx+1], data["y_m"][:idx+1]); dot.set_offsets([[data["x_m"][idx], data["y_m"][idx]]]); artists.extend([line,dot])
        return artists
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=True,cache_frame_data=False); _save_animation(animation,gif,mp4,fps=fps); plt.close(fig)


def _animate_nominal_telemetry(run: ScenarioRun, env: EnvironmentSettings, gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style(); data=_arrays(run.result); idxs=_frame_indices(len(data["time_s"]),frames)
    fig=plt.figure(figsize=(14,8.5));grid=GridSpec(2,2,figure=fig,left=.07,right=.96,top=.86,bottom=.10,hspace=.33,wspace=.27);add_figure_header(fig,"AquaSkim-Sim | Phase 09.2 — Nominal Telemetry Replay","Map, SOC, clearance and twin-thruster commands evolve together.")
    map_ax=fig.add_subplot(grid[:,0]);soc_ax=fig.add_subplot(grid[0,1]);safe_ax=fig.add_subplot(grid[1,1]);_draw_obstacles(map_ax,env,inflated=True);_map_axis(map_ax,env,"Nominal mission map");path,=map_ax.plot([],[],linewidth=1.8);craft=map_ax.scatter([],[],s=54)
    for ax,title,y,label in ((soc_ax,"State of charge",100*data["soc"],"SOC [%]"),(safe_ax,"Signed clearance",data["hazard_distance_m"],"m")):
        ax.set_title(title,loc="left",fontsize=10.5);ax.set_xlabel("Time [s]");ax.set_ylabel(label);ax.plot(data["time_s"],y,alpha=.25);style_axis(ax)
    soc_line,=soc_ax.plot([],[],linewidth=1.8);safe_line,=safe_ax.plot([],[],linewidth=1.8)
    def update(frame:int):
        idx=idxs[frame];path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);soc_line.set_data(data["time_s"][:idx+1],100*data["soc"][:idx+1]);safe_line.set_data(data["time_s"][:idx+1],data["hazard_distance_m"][:idx+1]);return [path,craft,soc_line,safe_line]
    animation=FuncAnimation(fig,update,frames=len(idxs),interval=1000/fps,blit=True,cache_frame_data=False);_save_animation(animation,gif,mp4,fps=fps);plt.close(fig)


def _animate_energy_return(run: ScenarioRun, env: EnvironmentSettings, gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(run.result);idxs=_frame_indices(len(data["time_s"]),frames)
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.8));fig.subplots_adjust(left=.07,right=.96,top=.84,bottom=.13,wspace=.27);add_figure_header(fig,"AquaSkim-Sim | Phase 09.2 — Proactive Energy Return","The conservative energy gate commands return before an unserviceable outbound leg is accepted.")
    ax, timeline=axes;_draw_obstacles(ax,env,inflated=True);_map_axis(ax,env,"Energy-return geometry");craft=ax.scatter([],[],s=55);path,=ax.plot([],[],linewidth=1.8)
    states=[STATE_INDEX.get(str(row["state"]),0) for row in run.result.rows];timeline.set_title("State and SOC",loc="left",fontsize=10.5);timeline.set_xlabel("Time [s]");timeline.set_ylabel("State index / SOC [%]");timeline.plot(data["time_s"],states,alpha=.25);timeline.plot(data["time_s"],100*data["soc"],alpha=.25);style_axis(timeline);l1,=timeline.plot([],[],linewidth=1.8);l2,=timeline.plot([],[],linewidth=1.8)
    def update(frame:int):
        idx=idxs[frame];path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);l1.set_data(data["time_s"][:idx+1],states[:idx+1]);l2.set_data(data["time_s"][:idx+1],100*data["soc"][:idx+1]);return [path,craft,l1,l2]
    animation=FuncAnimation(fig,update,frames=len(idxs),interval=1000/fps,blit=True,cache_frame_data=False);_save_animation(animation,gif,mp4,fps=fps);plt.close(fig)


def _animate_safety_replan(run: ScenarioRun, env: EnvironmentSettings, gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(run.result);idxs=_frame_indices(len(data["time_s"]),frames)
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.8));fig.subplots_adjust(left=.07,right=.96,top=.84,bottom=.13,wspace=.27);add_figure_header(fig,"AquaSkim-Sim | Phase 09.2 — Safety Shield and A* Replanning","The trace reveals clearance reduction, numerical projection and a recorded route replan.")
    ax,clearance=axes;_draw_obstacles(ax,env,inflated=True);_map_axis(ax,env,"Safety-replan geometry");path,=ax.plot([],[],linewidth=1.8);craft=ax.scatter([],[],s=55);markers=ax.scatter([],[],marker="X",s=85)
    clearance.set_title("Signed clearance",loc="left",fontsize=10.5);clearance.set_xlabel("Time [s]");clearance.set_ylabel("m");clearance.plot(data["time_s"],data["hazard_distance_m"],alpha=.25);clearance.axhline(.35,linestyle="--",linewidth=1.0);line,=clearance.plot([],[],linewidth=1.8);events=[event for event in run.result.event_rows if "safety shield" in str(event["reason"])]
    def update(frame:int):
        idx=idxs[frame];t=data["time_s"][idx];path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);line.set_data(data["time_s"][:idx+1],data["hazard_distance_m"][:idx+1]);pts=[[float(e["x_m"]),float(e["y_m"])] for e in events if float(e["time_s"])<=t];markers.set_offsets(np.asarray(pts) if pts else np.empty((0,2)));return [path,craft,line,markers]
    animation=FuncAnimation(fig,update,frames=len(idxs),interval=1000/fps,blit=True,cache_frame_data=False);_save_animation(animation,gif,mp4,fps=fps);plt.close(fig)


def _animate_monte_carlo(mc: list[dict[str, object]], gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style();fig,ax=plt.subplots(figsize=(11,7.5));fig.subplots_adjust(left=.11,right=.94,top=.84,bottom=.14);add_figure_header(fig,"AquaSkim-Sim | Phase 09.2 — Monte Carlo Envelope Replay","Seeded stratified current/SOC samples accumulate while success status remains visible.")
    ax.set_xlim(-.01,.22);ax.set_ylim(.18,.78);ax.set_xlabel("Current magnitude [m/s]");ax.set_ylabel("Initial SOC [-]");ax.set_title("Sample outcome map",loc="left",fontsize=11);style_axis(ax);success=ax.scatter([],[],s=70,marker="o",label="mission complete");failure=ax.scatter([],[],s=80,marker="X",label="not complete");ax.legend(fontsize=8)
    def update(frame:int):
        count=max(1,int((frame+1)/frames*len(mc)));done=[row for row in mc[:count] if int(row["mission_success"])==1];bad=[row for row in mc[:count] if int(row["mission_success"])==0];success.set_offsets(np.asarray([[float(r["current_magnitude_mps"]),float(r["initial_soc"])] for r in done]) if done else np.empty((0,2)));failure.set_offsets(np.asarray([[float(r["current_magnitude_mps"]),float(r["initial_soc"])] for r in bad]) if bad else np.empty((0,2)));ax.set_title(f"Sample outcome map — {count}/{len(mc)} trials",loc="left",fontsize=11);return [success,failure]
    animation=FuncAnimation(fig,update,frames=frames,interval=1000/fps,blit=False,cache_frame_data=False);_save_animation(animation,gif,mp4,fps=fps);plt.close(fig)


def _animate_boundary(run: ScenarioRun, env: EnvironmentSettings, gif: Path, mp4: Path, frames: int, fps: int) -> None:
    apply_engineering_style();data=_arrays(run.result);idxs=_frame_indices(len(data["time_s"]),frames)
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.8));fig.subplots_adjust(left=.07,right=.96,top=.84,bottom=.13,wspace=.27);add_figure_header(fig,"AquaSkim-Sim | Phase 09.2 — Boundary Case Replay","This is an intentionally retained limitation case, not a validated success claim.")
    ax,plot=axes;_draw_obstacles(ax,env,inflated=True);_map_axis(ax,env,"High-current boundary route");path,=ax.plot([],[],linewidth=1.8);craft=ax.scatter([],[],s=55)
    plot.set_title("Speed and clearance",loc="left",fontsize=10.5);plot.set_xlabel("Time [s]");plot.set_ylabel("m/s or m");plot.plot(data["time_s"],np.hypot(data["u_mps"],data["v_mps"]),alpha=.25);plot.plot(data["time_s"],data["hazard_distance_m"],alpha=.25);style_axis(plot);l1,=plot.plot([],[],linewidth=1.8);l2,=plot.plot([],[],linewidth=1.8)
    def update(frame:int):
        idx=idxs[frame];path.set_data(data["x_m"][:idx+1],data["y_m"][:idx+1]);craft.set_offsets([[data["x_m"][idx],data["y_m"][idx]]]);l1.set_data(data["time_s"][:idx+1],np.hypot(data["u_mps"][:idx+1],data["v_mps"][:idx+1]));l2.set_data(data["time_s"][:idx+1],data["hazard_distance_m"][:idx+1]);return [path,craft,l1,l2]
    animation=FuncAnimation(fig,update,frames=len(idxs),interval=1000/fps,blit=True,cache_frame_data=False);_save_animation(animation,gif,mp4,fps=fps);plt.close(fig)


def _acceptance(runs: list[ScenarioRun], mc: list[dict[str, object]], contract: dict[str, Any]) -> list[dict[str, object]]:
    lookup = _run_lookup(runs)
    valid_mc = [row for row in mc if int(row["inside_validated_envelope"]) == 1]
    rate = float(np.mean([int(row["mission_success"]) for row in valid_mc])) if valid_mc else 0.0
    clearance = min(float(row["minimum_clearance_m"]) for row in valid_mc) if valid_mc else float("-inf")
    checks = [
        ("nominal_multitarget_completion", int(lookup["nominal_multitarget"].metrics["mission_success"]) == 1, "Nominal three-target mission completes and docks."),
        ("safety_replan_evidence", int(lookup["mild_east_current_safety_replan"].metrics["replan_count"]) >= 1, "Safety shield and replanning are explicitly evidenced."),
        ("north_current_completion", int(lookup["north_current_operating_case"].metrics["mission_success"]) == 1, "Validated north-current case completes."),
        ("proactive_energy_return", int(lookup["proactive_energy_return"].metrics["energy_return_triggered"]) == 1, "Energy gate commands a protective return."),
        ("boundary_case_retained", int(lookup["high_current_boundary"].metrics["mission_success"]) == 0, "High-current boundary remains visible as a limitation case."),
        ("mc_valid_envelope_rate", rate >= float(contract["required_valid_envelope_success_rate"]), "Validated-envelope Monte Carlo completion rate meets threshold."),
        ("mc_valid_envelope_clearance", clearance >= 0.0, "All validated-envelope samples retain nonnegative signed clearance."),
    ]
    return [{"check": name, "passed": int(passed), "criterion": criterion} for name, passed, criterion in checks]


def _markdown(runs: list[ScenarioRun], summary: list[dict[str, object]], artifacts: Phase092Artifacts) -> str:
    rows = "\n".join(
        f"| {run.definition.title} | {run.metrics['scenario_class']} | {run.metrics['observed_outcome']} | {run.metrics['collected_count']} | {float(run.metrics['final_soc']):.3f} | {float(run.metrics['minimum_clearance_m']):.3f} |"
        for run in runs
    )
    summary_lines = "\n".join(f"- **{row['metric']}**: {float(row['value']):.3f} {row['unit']} — {row['interpretation']}" for row in summary)
    artifacts_list = "\n".join(f"- `{path}`" for path in artifacts.as_dict().values())
    return f"""# AquaSkim-Sim | Phase 09.2 Comprehensive Validation Summary

## Design intent
This validation separates *validated operating conditions*, *protective energy behavior*, and *boundary-limitation demonstrations*. Boundary outcomes are preserved in the evidence rather than silently excluded from the study.

## Deterministic scenarios
| Scenario | Class | Observed outcome | Captures | Final SOC | Minimum clearance [m] |
|---|---|---|---:|---:|---:|
{rows}

## Monte Carlo envelope
{summary_lines}

## Interpretation
- The validated envelope is intentionally bounded by the documented current and SOC contract.
- The proactive-energy-return case demonstrates that the agent can decline a mission leg before entering an unserviceable energy state.
- Boundary cases are not counted as validated successes. Their trajectories, state traces, and final conditions remain available for limitation analysis.
- All figures, tables, GIFs, MP4 files and numerical ledgers are generated from the same scenario runs.

## Generated artifacts
{artifacts_list}
"""


def _animation_manifest(artifacts: Phase092Artifacts, contract: dict[str, Any]) -> list[dict[str, object]]:
    pairs = [
        ("scenario_reel", artifacts.scenario_reel_gif, artifacts.scenario_reel_mp4, "Synchronous comparison of all deterministic scenarios."),
        ("nominal_telemetry", artifacts.nominal_telemetry_gif, artifacts.nominal_telemetry_mp4, "Map, SOC and clearance for nominal mission."),
        ("energy_return", artifacts.energy_return_gif, artifacts.energy_return_mp4, "Protective energy-gate replay."),
        ("safety_replan", artifacts.safety_replan_gif, artifacts.safety_replan_mp4, "Safety-shield clearance and replanning replay."),
        ("monte_carlo", artifacts.monte_carlo_gif, artifacts.monte_carlo_mp4, "Stratified uncertainty envelope accumulation."),
        ("boundary_case", artifacts.boundary_case_gif, artifacts.boundary_case_mp4, "High-current limitation replay."),
    ]
    return [{"animation": name, "gif": relative_to_root(gif), "mp4": relative_to_root(mp4), "frames_target": int(contract["animation_frames"]), "fps": int(contract["animation_fps"]), "purpose": purpose} for name, gif, mp4, purpose in pairs]


def run_phase09_2(config: ProjectConfiguration | None = None, *, render_animations: bool = True) -> Phase092Artifacts:
    ensure_runtime_directories()
    base = config or load_base_configuration()
    runs, contract = _run_deterministic(base)
    mc = _mc_rows(base, contract)
    env = EnvironmentSettings.from_config(base.data)
    fig = DIRECTORIES["figures"]; tables = DIRECTORIES["tables"]; logs = DIRECTORIES["logs"]; reports = DIRECTORIES["reports"]; anim = DIRECTORIES["animations"]; videos = DIRECTORIES["videos"]
    artifacts = Phase092Artifacts(
        scenario_matrix=fig/"phase09_2_scenario_matrix.png", scenario_matrix_svg=fig/"phase09_2_scenario_matrix.svg",
        scorecard=fig/"phase09_2_mission_scorecard.png", scorecard_svg=fig/"phase09_2_mission_scorecard.svg",
        operating_envelope=fig/"phase09_2_operating_envelope.png", operating_envelope_svg=fig/"phase09_2_operating_envelope.svg",
        sensitivity_heatmap=fig/"phase09_2_sensitivity_heatmap.png", sensitivity_heatmap_svg=fig/"phase09_2_sensitivity_heatmap.svg",
        safety_energy_dashboard=fig/"phase09_2_safety_energy_dashboard.png", safety_energy_dashboard_svg=fig/"phase09_2_safety_energy_dashboard.svg",
        control_performance=fig/"phase09_2_control_performance.png", control_performance_svg=fig/"phase09_2_control_performance.svg",
        coverage_collection=fig/"phase09_2_coverage_collection.png", coverage_collection_svg=fig/"phase09_2_coverage_collection.svg",
        state_distribution=fig/"phase09_2_state_distribution.png", state_distribution_svg=fig/"phase09_2_state_distribution.svg",
        scenario_catalog_table=tables/"phase09_2_scenario_catalog.csv", deterministic_metrics_table=tables/"phase09_2_deterministic_metrics.csv", scenario_time_series_table=tables/"phase09_2_scenario_time_series.csv", event_ledger_table=tables/"phase09_2_event_ledger.csv", monte_carlo_trials_table=tables/"phase09_2_monte_carlo_trials.csv", monte_carlo_summary_table=tables/"phase09_2_monte_carlo_summary.csv", envelope_table=tables/"phase09_2_envelope_definition.csv", acceptance_checks_table=tables/"phase09_2_acceptance_checks.csv", animation_manifest_table=tables/"phase09_2_animation_manifest.csv",
        summary_json=logs/"phase09_2_validation_summary.json", summary_markdown=reports/"phase09_2_comprehensive_validation_summary.md", visual_quality_manifest=logs/"phase09_2_visual_quality_manifest.json",
        scenario_reel_gif=anim/"phase09_2_scenario_reel.gif", scenario_reel_mp4=videos/"phase09_2_scenario_reel.mp4", nominal_telemetry_gif=anim/"phase09_2_nominal_telemetry.gif", nominal_telemetry_mp4=videos/"phase09_2_nominal_telemetry.mp4", energy_return_gif=anim/"phase09_2_energy_return.gif", energy_return_mp4=videos/"phase09_2_energy_return.mp4", safety_replan_gif=anim/"phase09_2_safety_replan.gif", safety_replan_mp4=videos/"phase09_2_safety_replan.mp4", monte_carlo_gif=anim/"phase09_2_monte_carlo.gif", monte_carlo_mp4=videos/"phase09_2_monte_carlo.mp4", boundary_case_gif=anim/"phase09_2_boundary_case.gif", boundary_case_mp4=videos/"phase09_2_boundary_case.mp4",
    )
    exports = [
        _draw_scenario_matrix(runs, env, artifacts.scenario_matrix),
        _draw_scorecard(runs, artifacts.scorecard),
        _draw_operating_envelope(mc, contract, artifacts.operating_envelope),
        _draw_sensitivity_heatmap(mc, artifacts.sensitivity_heatmap),
        _draw_safety_energy(runs, artifacts.safety_energy_dashboard),
        _draw_control_performance(runs, artifacts.control_performance),
        _draw_coverage_collection(runs, env, artifacts.coverage_collection),
        _draw_state_distribution(runs, artifacts.state_distribution),
    ]
    assert_export_quality(exports)
    catalog = [{"scenario_id": run.definition.identifier, "title": run.definition.title, "class": run.definition.scenario_class, "expected_outcome": run.definition.expected_outcome, "description": run.definition.description, "overrides_json": json.dumps(run.definition.overrides, ensure_ascii=False)} for run in runs]
    deterministic = [run.metrics for run in runs]
    time_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for run in runs:
        for row in run.result.rows: time_rows.append({"scenario_id": run.definition.identifier, **row})
        for row in run.result.event_rows: event_rows.append({"scenario_id": run.definition.identifier, **row})
    summary = _summary_rows(mc, contract)
    acceptance = _acceptance(runs, mc, contract)
    _write_csv(artifacts.scenario_catalog_table, catalog); _write_csv(artifacts.deterministic_metrics_table, deterministic); _write_csv(artifacts.scenario_time_series_table, time_rows); _write_csv(artifacts.event_ledger_table, event_rows); _write_csv(artifacts.monte_carlo_trials_table, mc); _write_csv(artifacts.monte_carlo_summary_table, summary)
    envelope_rows = [{"parameter": key, "value": value, "unit_or_note": "validation contract"} for key, value in contract.items()]; _write_csv(artifacts.envelope_table, envelope_rows); _write_csv(artifacts.acceptance_checks_table, acceptance)
    manifest_rows = _animation_manifest(artifacts, contract); _write_csv(artifacts.animation_manifest_table, manifest_rows)
    if render_animations:
        for name in ("scenario_reel", "nominal_telemetry", "energy_return", "safety_replan", "monte_carlo", "boundary_case"):
            completed = subprocess.run([sys.executable, "-m", "aquaskim.phase09_2", "--render-animation", name], check=False)
            if completed.returncode != 0: raise RuntimeError(f"Phase 09.2 animation renderer failed: {name}")
    summary_json = {
        "phase": "Phase 09.2 — Comprehensive scenario validation and operating envelope",
        "configuration_file": relative_to_root(base.source_path),
        "validation_contract": contract,
        "deterministic_metrics": deterministic,
        "monte_carlo_summary": summary,
        "acceptance_checks": acceptance,
        "artifacts": artifacts.as_dict(),
        "limitations": [
            "Boundary cases remain evidence of model/controller limits; they are not validated performance claims.",
            "Safety shield is a numerical supervisory barrier, not impact-contact physics.",
            "No waves, wind, spatially varying current, moving obstacles, SLAM, or hardware-in-the-loop tests are represented.",
        ],
    }
    artifacts.summary_json.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.summary_markdown.write_text(_markdown(runs, summary, artifacts), encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps({"phase": "Phase 09.2 visual quality gate", "exports": [item.as_dict() for item in exports], "animation_contract": {"gif_count": 6, "mp4_count": 6, "target_frames": int(contract["animation_frames"]), "fps": int(contract["animation_fps"])}, "label_policy": "Dense scenario descriptions are retained in CSV/Markdown tables; map labels remain short and non-overlapping."}, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifacts


def print_phase09_2_summary(artifacts: Phase092Artifacts) -> None:
    print("=" * 72); print("AquaSkim-Sim | Phase 09.2 Comprehensive Validation"); print("=" * 72)
    for name, path in artifacts.as_dict().items(): print(f"{name:28}: {path}")
    print("=" * 72); print("[OK] Phase 09.2 scenario, Monte Carlo, plots and animation artifacts generated.")


def _render_single_animation(name: str) -> int:
    base = load_base_configuration(); runs, contract = _run_deterministic(base); mc = _mc_rows(base, contract); env = EnvironmentSettings.from_config(base.data); lookup = _run_lookup(runs); frames=int(contract["animation_frames"]);fps=int(contract["animation_fps"])
    if name == "scenario_reel": _animate_scenario_reel(runs, env, DIRECTORIES["animations"] / "phase09_2_scenario_reel.gif", DIRECTORIES["videos"] / "phase09_2_scenario_reel.mp4", frames, fps)
    elif name == "nominal_telemetry": _animate_nominal_telemetry(lookup["nominal_multitarget"], env, DIRECTORIES["animations"] / "phase09_2_nominal_telemetry.gif", DIRECTORIES["videos"] / "phase09_2_nominal_telemetry.mp4", frames, fps)
    elif name == "energy_return": _animate_energy_return(lookup["proactive_energy_return"], env, DIRECTORIES["animations"] / "phase09_2_energy_return.gif", DIRECTORIES["videos"] / "phase09_2_energy_return.mp4", frames, fps)
    elif name == "safety_replan": _animate_safety_replan(lookup["mild_east_current_safety_replan"], env, DIRECTORIES["animations"] / "phase09_2_safety_replan.gif", DIRECTORIES["videos"] / "phase09_2_safety_replan.mp4", frames, fps)
    elif name == "monte_carlo": _animate_monte_carlo(mc, DIRECTORIES["animations"] / "phase09_2_monte_carlo.gif", DIRECTORIES["videos"] / "phase09_2_monte_carlo.mp4", frames, fps)
    elif name == "boundary_case": _animate_boundary(lookup["high_current_boundary"], env, DIRECTORIES["animations"] / "phase09_2_boundary_case.gif", DIRECTORIES["videos"] / "phase09_2_boundary_case.mp4", frames, fps)
    else: raise ValueError(f"Unknown animation: {name}")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--render-animation", choices=("scenario_reel", "nominal_telemetry", "energy_return", "safety_replan", "monte_carlo", "boundary_case"), required=True)
    args = parser.parse_args(); raise SystemExit(_render_single_animation(args.render_animation))
