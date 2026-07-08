"""Phase 09: deterministic scenario validation and seeded Monte Carlo robustness study.

This phase intentionally reuses the exact Phase 08 closed-loop mission chain.
It changes only declared configuration parameters, records each trial and makes
no claim beyond the sampled design envelope.
"""
from __future__ import annotations

import copy
import csv
import json
import math
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
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.phase08 import _run_mission
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
    scenario_id: str
    title: str
    description: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class ScenarioRun:
    definition: ScenarioDefinition
    result: MissionResult
    metrics: dict[str, object]


@dataclass(frozen=True)
class Phase09Artifacts:
    scenario_trajectories: Path
    scenario_trajectories_svg: Path
    mission_scorecard: Path
    mission_scorecard_svg: Path
    monte_carlo_robustness: Path
    monte_carlo_robustness_svg: Path
    sensitivity_heatmap: Path
    sensitivity_heatmap_svg: Path
    scenario_reel_gif: Path
    scenario_reel_mp4: Path
    scenario_catalog_table: Path
    deterministic_metrics_table: Path
    monte_carlo_trials_table: Path
    monte_carlo_summary_table: Path
    scenario_time_series_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


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


def _load_scenario_plan() -> tuple[list[ScenarioDefinition], dict[str, Any]]:
    path = DIRECTORIES["config"] / "phase09_scenarios.yaml"
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    scenarios = [
        ScenarioDefinition(
            scenario_id=str(item["id"]),
            title=str(item["title"]),
            description=str(item["description"]),
            overrides=dict(item["overrides"]),
        )
        for item in document["deterministic_scenarios"]
    ]
    return scenarios, dict(document["quality_contract"])


def _current_magnitude(current: object) -> float:
    vector = list(current)  # list or tuple
    return float(math.hypot(float(vector[0]), float(vector[1])))


def _scenario_metrics(result: MissionResult, scenario_id: str, title: str, config: ProjectConfiguration) -> dict[str, object]:
    metrics = dict(result.metrics)
    current = config.data["autonomy"]["current_earth_mps"]
    final_state = str(metrics["final_state"])
    min_clearance = float(metrics["minimum_hazard_distance_m"])
    home_error = float(metrics["final_distance_home_m"])
    collected = int(metrics["collected_count"])
    success = bool(int(metrics["mission_success"])) and final_state == AgentState.MISSION_COMPLETE.value and collected >= 1 and min_clearance >= 0.0 and home_error <= 0.30
    return {
        "scenario_id": scenario_id,
        "title": title,
        "current_x_mps": float(current[0]),
        "current_y_mps": float(current[1]),
        "current_magnitude_mps": _current_magnitude(current),
        "initial_soc": float(config.data["autonomy"]["initial_soc"]),
        "max_collections": int(config.data["autonomy"]["max_collections"]),
        "mission_success": int(success),
        "final_state": final_state,
        "duration_s": float(metrics["duration_s"]),
        "collected_count": collected,
        "collected_mass_kg": float(metrics["collected_mass_kg"]),
        "final_soc": float(metrics["final_soc"]),
        "final_home_error_m": home_error,
        "minimum_clearance_m": min_clearance,
        "state_transition_count": int(metrics["state_transition_count"]),
        "planned_route_count": int(metrics["planned_route_count"]),
        "planned_route_length_m": float(metrics["total_planned_length_m"]),
    }


def _run_deterministic_scenarios(base: ProjectConfiguration) -> tuple[list[ScenarioRun], dict[str, Any]]:
    definitions, quality = _load_scenario_plan()
    runs: list[ScenarioRun] = []
    for definition in definitions:
        scenario_config = _scenario_config(base, definition.overrides)
        result, _, _ = _run_mission(scenario_config)
        metrics = _scenario_metrics(result, definition.scenario_id, definition.title, scenario_config)
        runs.append(ScenarioRun(definition, result, metrics))
    return runs, quality


def _run_monte_carlo(base: ProjectConfiguration, contract: dict[str, Any]) -> list[dict[str, object]]:
    trial_count = int(contract["monte_carlo_trials"])
    maximum_current = float(contract["current_speed_max_mps"])
    soc_min, soc_max = [float(value) for value in contract["initial_soc_range"]]
    rng = np.random.default_rng(90909)
    rows: list[dict[str, object]] = []
    for trial in range(trial_count):
        magnitude = float(rng.uniform(0.0, maximum_current))
        direction_rad = float(rng.uniform(0.0, 2.0 * math.pi))
        initial_soc = float(rng.uniform(soc_min, soc_max))
        overrides = {
            "autonomy": {
                "current_earth_mps": [magnitude * math.cos(direction_rad), magnitude * math.sin(direction_rad)],
                "initial_soc": initial_soc,
                "max_collections": 2,
                "mission_duration_s": 300.0,
                "random_seed": 8026,
            },
            "environment_model": {"debris": {"seed": 7107}},
        }
        config = _scenario_config(base, overrides)
        result, _, _ = _run_mission(config)
        row = _scenario_metrics(result, f"mc_{trial + 1:02d}", "Monte Carlo", config)
        row.update({
            "trial_index": trial + 1,
            "current_direction_deg": (math.degrees(direction_rad) + 360.0) % 360.0,
            "autonomy_seed": 8026,
            "debris_seed": 7107,
        })
        rows.append(row)
    return rows


def _summary_rows(monte_carlo: list[dict[str, object]]) -> list[dict[str, object]]:
    numerical = lambda key: np.asarray([float(row[key]) for row in monte_carlo], dtype=float)
    return [
        {"metric": "trial_count", "value": len(monte_carlo), "unit": "trials", "interpretation": "Seeded Monte Carlo samples"},
        {"metric": "success_rate", "value": float(numerical("mission_success").mean()), "unit": "fraction", "interpretation": "Complete mission + collection + safety + docking"},
        {"metric": "mean_collected_count", "value": float(numerical("collected_count").mean()), "unit": "items", "interpretation": "Average confirmed collections"},
        {"metric": "median_duration", "value": float(np.median(numerical("duration_s"))), "unit": "s", "interpretation": "Median completed / terminated mission duration"},
        {"metric": "p05_final_soc", "value": float(np.quantile(numerical("final_soc"), 0.05)), "unit": "fraction", "interpretation": "5th percentile terminal state-of-charge"},
        {"metric": "minimum_clearance", "value": float(numerical("minimum_clearance_m").min()), "unit": "m", "interpretation": "Worst signed hazard margin among trials"},
        {"metric": "mean_home_error", "value": float(numerical("final_home_error_m").mean()), "unit": "m", "interpretation": "Average final docking error"},
    ]


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            ax.add_patch(Circle(obstacle.center_m, obstacle.radius_m, facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.9, zorder=4))
        elif isinstance(obstacle, RectangleObstacle):
            ax.add_patch(Rectangle((obstacle.center_m[0] - obstacle.half_x_m, obstacle.center_m[1] - obstacle.half_y_m), obstacle.size_m[0], obstacle.size_m[1], facecolor=PALETTE["orange"], edgecolor=PALETTE["orange"], alpha=0.9, zorder=4))


def _trajectory_arrays(result: MissionResult) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray([float(row["x_m"]) for row in result.rows])
    y = np.asarray([float(row["y_m"]) for row in result.rows])
    time = np.asarray([float(row["time_s"]) for row in result.rows])
    return time, x, y


def _draw_scenario_trajectories(runs: list[ScenarioRun], environment: EnvironmentSettings, output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 11), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.88, bottom=.08, hspace=.28, wspace=.18)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09 — Deterministic Scenario Trajectories", "Closed-loop mission traces; static obstacles are shown in orange. Start/home is marked by a square and collected target endpoints are implicit in agent events.")
    for index, run in enumerate(runs):
        ax = fig.add_subplot(grid[index // 2, index % 2])
        _draw_obstacles(ax, environment)
        time, x, y = _trajectory_arrays(run.result)
        ax.plot(x, y, linewidth=2.0, color=PALETTE["blue"], label="closed-loop trajectory", zorder=3)
        ax.scatter([x[0]], [y[0]], marker="s", s=60, color=PALETTE["green"], label="home / start", zorder=6)
        ax.scatter([x[-1]], [y[-1]], marker="X", s=60, color=PALETTE["navy"], label="final", zorder=6)
        metrics = run.metrics
        caption = f"{run.definition.title}\ncurrent={metrics['current_magnitude_mps']:.2f} m/s • collected={metrics['collected_count']} • final SOC={metrics['final_soc']:.3f} • clearance={metrics['minimum_clearance_m']:.2f} m"
        ax.set_title(fill(caption, width=62), fontsize=10.0, loc="left", pad=10)
        ax.set_xlim(0.0, environment.length_m); ax.set_ylim(0.0, environment.width_m)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]")
        style_axis(ax)
        if index == 0:
            ax.legend(loc="upper left", fontsize=7.6)
    return export_figure(fig, output, dpi=320)


def _card(ax: plt.Axes, x: float, y: float, w: float, h: float, title: str, value: str, note: str) -> None:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=.012,rounding_size=.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))
    ax.text(x+.025, y+h-.055, title, fontsize=8.3, color=PALETTE["gray"], va="top")
    ax.text(x+.025, y+h-.145, value, fontsize=15.0, fontweight="bold", color=PALETTE["navy"], va="top")
    ax.text(x+.025, y+.052, fill(note, width=30), fontsize=6.65, color=PALETTE["gray_dark"], va="bottom", linespacing=1.20)


def _draw_scorecard(runs: list[ScenarioRun], summary: list[dict[str, object]], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.875, bottom=.09, height_ratios=[1.05, .95], hspace=.36, wspace=.28)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09 — Mission Scorecard", "Deterministic mission outcomes and seeded Monte Carlo aggregate metrics. Values are outputs of the same Phase 08 autonomy and 3-DOF plant chain.")
    ax1 = fig.add_subplot(grid[0, 0]); ax2 = fig.add_subplot(grid[0, 1]); ax3 = fig.add_subplot(grid[1, :])
    labels = [run.definition.scenario_id.replace("_", "\n") for run in runs]
    counts = [int(run.metrics["collected_count"]) for run in runs]
    soc = [float(run.metrics["final_soc"]) for run in runs]
    x = np.arange(len(labels))
    ax1.bar(x-.18, counts, width=.34, label="collected items", color=PALETTE["green"])
    ax1.bar(x+.18, soc, width=.34, label="final SOC", color=PALETTE["blue"])
    ax1.set_xticks(x, labels, fontsize=8)
    ax1.set_ylim(0, max(2.5, max(counts) + .5)); ax1.set_ylabel("Items / fraction")
    ax1.set_title("Deterministic performance", loc="left", fontsize=11)
    style_axis(ax1); ax1.legend(fontsize=8)

    ax2.set_axis_off(); ax2.set_xlim(0, 1); ax2.set_ylim(0, 1)
    lookup = {str(row["metric"]): row for row in summary}
    _card(ax2, .03, .55, .43, .35, "Monte Carlo success rate", f"{100*float(lookup['success_rate']['value']):.1f}%", "Complete mission, >=1 collection, safe clearance and docking error <=0.30 m.")
    _card(ax2, .54, .55, .43, .35, "Worst clearance", f"{float(lookup['minimum_clearance']['value']):.3f} m", "Worst signed separation from the safety-inflated hazard boundary.")
    _card(ax2, .03, .12, .43, .32, "Median duration", f"{float(lookup['median_duration']['value']):.1f} s", "Median end time among all seeded trials.")
    _card(ax2, .54, .12, .43, .32, "P05 terminal SOC", f"{float(lookup['p05_final_soc']['value']):.3f}", "Fifth-percentile terminal state of charge.")

    rows = [(run.definition.title, run.metrics) for run in runs]
    col_labels = ["Scenario", "State", "Collect", "Time [s]", "Final SOC", "Home err. [m]", "Min clr. [m]"]
    cell_text = [[title, str(metric["final_state"]), str(metric["collected_count"]), f"{float(metric['duration_s']):.1f}", f"{float(metric['final_soc']):.3f}", f"{float(metric['final_home_error_m']):.3f}", f"{float(metric['minimum_clearance_m']):.3f}"] for title, metric in rows]
    table = ax3.table(cellText=cell_text, colLabels=col_labels, colLoc="center", cellLoc="center", bbox=[0, .03, 1, .84], colWidths=[.27,.17,.09,.11,.12,.13,.11])
    table.auto_set_font_size(False); table.set_fontsize(8.2)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(PALETTE["grid"]); cell.set_linewidth(.55)
        if row == 0:
            cell.set_facecolor(PALETTE["navy"]); cell.set_text_props(color="white", fontweight="bold")
        elif col == 0:
            cell.set_facecolor(PALETTE["gray_light"])
    ax3.set_axis_off(); ax3.set_title("Named-scenario validation table", loc="left", fontsize=11, pad=8)
    return export_figure(fig, output, dpi=320)


def _draw_monte_carlo(trials: list[dict[str, object]], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10.4), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, left=.06, right=.95, top=.875, bottom=.09, hspace=.32, wspace=.24)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09 — Seeded Monte Carlo Robustness", "Twenty reproducible trials vary current magnitude/direction and initial SOC; fixed perception/debris seeds isolate the controller calibration envelope.")
    current = np.asarray([float(row["current_magnitude_mps"]) for row in trials]); duration = np.asarray([float(row["duration_s"]) for row in trials]); soc0 = np.asarray([float(row["initial_soc"]) for row in trials]); socf = np.asarray([float(row["final_soc"]) for row in trials]); clear = np.asarray([float(row["minimum_clearance_m"]) for row in trials]); collected = np.asarray([float(row["collected_count"]) for row in trials]); success = np.asarray([int(row["mission_success"]) for row in trials])
    ax1 = fig.add_subplot(grid[0,0]); ax2 = fig.add_subplot(grid[0,1]); ax3 = fig.add_subplot(grid[1,0]); ax4 = fig.add_subplot(grid[1,1])
    ax1.scatter(current, duration, c=np.where(success > 0, PALETTE["green"], PALETTE["orange"]), s=55, edgecolors="white", linewidths=.7)
    ax1.set_xlabel("Current magnitude [m/s]"); ax1.set_ylabel("Mission duration [s]"); ax1.set_title("Current vs mission duration", loc="left", fontsize=11); style_axis(ax1)
    ax2.scatter(soc0, socf, c=collected, cmap="viridis", s=58, edgecolors="white", linewidths=.7)
    ax2.plot([soc0.min(), soc0.max()], [soc0.min(), soc0.max()], linestyle="--", color=PALETTE["gray"], linewidth=1)
    ax2.set_xlabel("Initial SOC"); ax2.set_ylabel("Final SOC"); ax2.set_title("Energy use across trials", loc="left", fontsize=11); style_axis(ax2)
    ax3.hist(clear, bins=8, color=PALETTE["blue"], edgecolor="white")
    ax3.axvline(0.0, color=PALETTE["orange"], linestyle="--", linewidth=1.3, label="safety threshold")
    ax3.set_xlabel("Minimum signed clearance [m]"); ax3.set_ylabel("Trial count"); ax3.set_title("Safety-margin distribution", loc="left", fontsize=11); style_axis(ax3); ax3.legend(fontsize=8)
    counts = [int(np.sum(success==0)), int(np.sum(success==1))]
    ax4.bar(["not successful", "successful"], counts, color=[PALETTE["orange"], PALETTE["green"]], width=.58)
    for index, value in enumerate(counts): ax4.text(index, value+.18, str(value), ha="center", fontsize=10, fontweight="bold")
    ax4.set_ylim(0, max(counts)+2); ax4.set_ylabel("Trials"); ax4.set_title("Mission success classification", loc="left", fontsize=11); style_axis(ax4)
    return export_figure(fig, output, dpi=320)


def _draw_sensitivity_heatmap(trials: list[dict[str, object]], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 9.5), constrained_layout=False)
    grid = GridSpec(1, 2, figure=fig, left=.06, right=.95, top=.875, bottom=.11, width_ratios=[1.15,.85], wspace=.23)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09 — Sensitivity Envelope", "Binned empirical outcomes from the seeded Monte Carlo set. Empty bins are intentionally marked as no sample rather than interpolated.")
    ax = fig.add_subplot(grid[0,0]); panel = fig.add_subplot(grid[0,1])
    current = np.asarray([float(row["current_magnitude_mps"]) for row in trials]); soc = np.asarray([float(row["initial_soc"]) for row in trials]); success = np.asarray([float(row["mission_success"]) for row in trials]); collected = np.asarray([float(row["collected_count"]) for row in trials])
    current_edges = np.linspace(0, max(.02, float(current.max()) + 1e-6), 5); soc_edges = np.linspace(.31, .48, 5)
    rate = np.full((4,4), np.nan); mean_collected = np.full((4,4), np.nan); sample_count=np.zeros((4,4),dtype=int)
    for i in range(4):
        for j in range(4):
            mask = (current >= current_edges[i]) & (current < current_edges[i+1] if i<3 else current <= current_edges[i+1]) & (soc >= soc_edges[j]) & (soc < soc_edges[j+1] if j<3 else soc <= soc_edges[j+1])
            if np.any(mask):
                rate[j,i] = success[mask].mean(); mean_collected[j,i] = collected[mask].mean(); sample_count[j,i]=mask.sum()
    image=ax.imshow(rate, origin="lower", aspect="auto", interpolation="nearest", extent=[current_edges[0],current_edges[-1],soc_edges[0],soc_edges[-1]], vmin=0, vmax=1, cmap="YlGn")
    cbar=fig.colorbar(image, ax=ax, fraction=.046, pad=.04); cbar.set_label("Empirical success rate")
    for j in range(4):
        for i in range(4):
            x=(current_edges[i]+current_edges[i+1])/2; y=(soc_edges[j]+soc_edges[j+1])/2
            label="n=0" if sample_count[j,i]==0 else f"n={sample_count[j,i]}\nrate={rate[j,i]:.2f}\ncollect={mean_collected[j,i]:.1f}"
            ax.text(x,y,label,ha="center",va="center",fontsize=8,color=PALETTE["gray_dark"])
    ax.set_xlabel("Current magnitude [m/s]"); ax.set_ylabel("Initial SOC"); ax.set_title("Binned robustness envelope",loc="left",fontsize=11); style_axis(ax, grid=False)
    panel.set_axis_off(); panel.set_xlim(0,1); panel.set_ylim(0,1)
    panel.add_patch(FancyBboxPatch((.03,.04),.94,.90,boxstyle="round,pad=.018,rounding_size=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1.0))
    panel.text(.08,.88,"Interpretation rules",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top")
    bullet_rows = [
        (.80, "Each cell reports observed outcomes only; empty cells are not interpolated."),
        (.66, "Current direction is randomized independently, so this compact map is not a complete response surface."),
        (.51, "Success requires completion, at least one collection, non-negative margin and home error <=0.30 m."),
        (.35, "Validation is bounded to the controller-calibration envelope: current <=0.02 m/s and initial SOC 0.31–0.48."),
    ]
    for y, item in bullet_rows:
        wrapped=fill(item,width=43)
        panel.text(.09,y,"• "+wrapped.replace("\n","\n  "),fontsize=8.25,color=PALETTE["gray_dark"],va="top",linespacing=1.28)
    panel.text(.08,.185,"Engineering limitation",fontsize=9.8,fontweight="bold",color=PALETTE["navy"])
    panel.text(.09,.14,fill("This seeded computational experiment supports sensitivity analysis inside the stated model assumptions. It does not replace field testing, physical-parameter uncertainty analysis, or safety certification.",width=47),fontsize=7.8,color=PALETTE["gray_dark"],va="top",linespacing=1.28)
    return export_figure(fig, output, dpi=320)


def _draw_reel(runs: list[ScenarioRun], environment: EnvironmentSettings, gif_path: Path, mp4_path: Path) -> None:
    apply_engineering_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=False)
    fig.subplots_adjust(left=.06, right=.96, top=.87, bottom=.08, hspace=.30, wspace=.22)
    add_figure_header(fig, "AquaSkim-Sim | Phase 09 — Comparative Mission Reel", "Four closed-loop trajectories reveal simultaneously; each panel uses the same safety-inflated static environment.")
    artists=[]
    trajectory_data=[]
    for ax, run in zip(axes.flat, runs):
        _draw_obstacles(ax, environment)
        time, x, y = _trajectory_arrays(run.result)
        line,=ax.plot([], [], color=PALETTE["blue"], linewidth=2.0)
        point=ax.scatter([], [], marker="o", s=32, color=PALETTE["green"], zorder=6)
        ax.scatter([environment.home_position_m[0]],[environment.home_position_m[1]],marker="s",s=45,color=PALETTE["navy"],zorder=6)
        ax.set_xlim(0,environment.length_m); ax.set_ylim(0,environment.width_m); ax.set_aspect("equal",adjustable="box")
        ax.set_title(fill(run.definition.title,width=32),fontsize=9.2,loc="left",pad=7)
        ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); style_axis(ax)
        trajectory_data.append((x,y)); artists.append((line,point))
    frame_count=36
    def update(frame: int):
        changed=[]
        for (x,y),(line,point) in zip(trajectory_data,artists):
            index=min(len(x)-1, int(round(frame/(frame_count-1)*(len(x)-1))))
            line.set_data(x[:index+1],y[:index+1]); point.set_offsets(np.asarray([[x[index],y[index]]]))
            changed.extend([line,point])
        return changed
    animation=FuncAnimation(fig,update,frames=frame_count,interval=70,blit=True)
    gif_path.parent.mkdir(parents=True,exist_ok=True); mp4_path.parent.mkdir(parents=True,exist_ok=True)
    animation.save(gif_path,writer=PillowWriter(fps=12),dpi=80)
    try:
        animation.save(mp4_path,writer=FFMpegWriter(fps=12,bitrate=1200),dpi=90)
    except Exception:
        # The project has ffmpeg in its conda environment; retaining GIF still preserves a visual deliverable if a local runtime lacks it.
        mp4_path.write_bytes(b"")
    plt.close(fig)


def _markdown_summary(runs: list[ScenarioRun], summary: list[dict[str, object]], artifacts: Phase09Artifacts) -> str:
    success_rate = next(float(row["value"]) for row in summary if row["metric"] == "success_rate")
    scenario_lines = "\n".join(
        f"| {run.definition.scenario_id} | {int(run.metrics['mission_success'])} | {run.metrics['final_state']} | {int(run.metrics['collected_count'])} | {float(run.metrics['duration_s']):.1f} | {float(run.metrics['final_soc']):.3f} | {float(run.metrics['minimum_clearance_m']):.3f} |"
        for run in runs
    )
    artifact_lines = "\n".join(f"- `{value}`" for value in artifacts.as_dict().values())
    return f"""# AquaSkim-Sim | Phase 09 Scenario Validation Summary

## Scope
This phase re-runs the Phase 08 closed-loop autonomy chain over four named scenarios and twenty seeded Monte Carlo trials. It evaluates the model only within declared current and initial-SOC ranges.

## Deterministic scenarios
| Scenario | Success | Final state | Collected | Duration [s] | Final SOC | Min clearance [m] |
|---|---:|---|---:|---:|---:|---:|
{scenario_lines}

## Monte Carlo result
- Trial count: `{len(summary) and int(next(row['value'] for row in summary if row['metric']=='trial_count'))}`
- Success rate: `{100.0*success_rate:.1f}%`
- Result validity: seeded computational robustness study; not a field certification.

## Evidence and outputs
{artifact_lines}
"""


def run_phase09(*, render_animation: bool = True) -> Phase09Artifacts:
    ensure_runtime_directories()
    base = load_base_configuration()
    runs, contract = _run_deterministic_scenarios(base)
    monte_carlo = _run_monte_carlo(base, contract)
    summary_rows = _summary_rows(monte_carlo)
    environment = EnvironmentSettings.from_config(base.data)

    artifacts = Phase09Artifacts(
        scenario_trajectories=DIRECTORIES["figures"] / "phase09_scenario_trajectories.png",
        scenario_trajectories_svg=DIRECTORIES["figures"] / "phase09_scenario_trajectories.svg",
        mission_scorecard=DIRECTORIES["figures"] / "phase09_mission_scorecard.png",
        mission_scorecard_svg=DIRECTORIES["figures"] / "phase09_mission_scorecard.svg",
        monte_carlo_robustness=DIRECTORIES["figures"] / "phase09_monte_carlo_robustness.png",
        monte_carlo_robustness_svg=DIRECTORIES["figures"] / "phase09_monte_carlo_robustness.svg",
        sensitivity_heatmap=DIRECTORIES["figures"] / "phase09_sensitivity_heatmap.png",
        sensitivity_heatmap_svg=DIRECTORIES["figures"] / "phase09_sensitivity_heatmap.svg",
        scenario_reel_gif=DIRECTORIES["animations"] / "phase09_scenario_reel.gif",
        scenario_reel_mp4=DIRECTORIES["videos"] / "phase09_scenario_reel.mp4",
        scenario_catalog_table=DIRECTORIES["tables"] / "phase09_scenario_catalog.csv",
        deterministic_metrics_table=DIRECTORIES["tables"] / "phase09_deterministic_metrics.csv",
        monte_carlo_trials_table=DIRECTORIES["tables"] / "phase09_monte_carlo_trials.csv",
        monte_carlo_summary_table=DIRECTORIES["tables"] / "phase09_monte_carlo_summary.csv",
        scenario_time_series_table=DIRECTORIES["tables"] / "phase09_scenario_time_series.csv",
        acceptance_checks_table=DIRECTORIES["tables"] / "phase09_acceptance_checks.csv",
        summary_json=DIRECTORIES["logs"] / "phase09_validation_summary.json",
        summary_markdown=DIRECTORIES["reports"] / "phase09_scenario_validation_summary.md",
        visual_quality_manifest=DIRECTORIES["logs"] / "phase09_visual_quality_manifest.json",
    )

    exports = [
        _draw_scenario_trajectories(runs, environment, artifacts.scenario_trajectories),
        _draw_scorecard(runs, summary_rows, artifacts.mission_scorecard),
        _draw_monte_carlo(monte_carlo, artifacts.monte_carlo_robustness),
        _draw_sensitivity_heatmap(monte_carlo, artifacts.sensitivity_heatmap),
    ]
    assert_export_quality(exports)
    if render_animation:
        _draw_reel(runs, environment, artifacts.scenario_reel_gif, artifacts.scenario_reel_mp4)

    catalog_rows=[]
    for run in runs:
        catalog_rows.append({"scenario_id":run.definition.scenario_id,"title":run.definition.title,"description":run.definition.description,"overrides_json":json.dumps(run.definition.overrides,ensure_ascii=False,sort_keys=True)})
    deterministic_rows=[dict(run.metrics) for run in runs]
    time_series=[]
    for run in runs:
        for row in run.result.rows[::2]:
            time_series.append({"scenario_id":run.definition.scenario_id, **row})
    success_rate=float(next(row["value"] for row in summary_rows if row["metric"]=="success_rate"))
    acceptance=[
        {"check":"deterministic_nominal_success","criterion":"nominal_calm mission passes full criteria","actual":int(next(run.metrics["mission_success"] for run in runs if run.definition.scenario_id=="nominal_calm")),"passed":int(next(run.metrics["mission_success"] for run in runs if run.definition.scenario_id=="nominal_calm")==1)},
        {"check":"deterministic_clearance","criterion":"all named scenarios retain non-negative signed clearance","actual":min(float(run.metrics["minimum_clearance_m"]) for run in runs),"passed":int(min(float(run.metrics["minimum_clearance_m"]) for run in runs)>=0.0)},
        {"check":"monte_carlo_success_rate","criterion":f">= {float(contract['required_success_rate']):.2f}","actual":success_rate,"passed":int(success_rate>=float(contract['required_success_rate']))},
        {"check":"visual_exports","criterion":"4 high-resolution PNG+SVG pairs","actual":len(exports),"passed":int(len(exports)==4)},
        {"check":"animation_exports","criterion":"GIF and MP4 report assets","actual":f"gif={artifacts.scenario_reel_gif.exists()}, mp4={artifacts.scenario_reel_mp4.exists() and artifacts.scenario_reel_mp4.stat().st_size>0}","passed":int(artifacts.scenario_reel_gif.exists() and artifacts.scenario_reel_mp4.exists() and artifacts.scenario_reel_mp4.stat().st_size>0) if render_animation else 1},
    ]
    _write_csv(artifacts.scenario_catalog_table,catalog_rows)
    _write_csv(artifacts.deterministic_metrics_table,deterministic_rows)
    _write_csv(artifacts.monte_carlo_trials_table,monte_carlo)
    _write_csv(artifacts.monte_carlo_summary_table,summary_rows)
    _write_csv(artifacts.scenario_time_series_table,time_series)
    _write_csv(artifacts.acceptance_checks_table,acceptance)

    manifest={
        "phase":"Phase 09 visual quality gate",
        "quality_rule":{"minimum_png_width_px":3000,"minimum_png_height_px":1800,"formats":["PNG (report-ready raster)","SVG (vector)","GIF / MP4 (presentation animation)"],"label_policy":"Trajectories and metrics are separated into dedicated panels and tables; dense labels are not placed on paths."},
        "exports":[export.as_dict() for export in exports],
        "animation_exports":[{"gif":relative_to_root(artifacts.scenario_reel_gif),"gif_bytes":artifacts.scenario_reel_gif.stat().st_size if artifacts.scenario_reel_gif.exists() else 0,"mp4":relative_to_root(artifacts.scenario_reel_mp4),"mp4_bytes":artifacts.scenario_reel_mp4.stat().st_size if artifacts.scenario_reel_mp4.exists() else 0,"generated":render_animation}],
    }
    artifacts.visual_quality_manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={
        "phase":"Phase 09 — Scenario validation and Monte Carlo robustness",
        "scenario_config":relative_to_root(DIRECTORIES["config"] / "phase09_scenarios.yaml"),
        "deterministic_scenarios":deterministic_rows,
        "monte_carlo_summary":summary_rows,
        "acceptance_checks":acceptance,
        "limitations":["Constant spatially uniform current per trial.","Static obstacles and no independently drifting debris.","Monte Carlo claims are bounded by sampled ranges and deterministic pseudo-random seeds.","No field-validation or safety-certification claim."],
        "artifacts":artifacts.as_dict(),
    }
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    artifacts.summary_markdown.write_text(_markdown_summary(runs,summary_rows,artifacts),encoding="utf-8")
    return artifacts


def print_phase09_summary(artifacts: Phase09Artifacts) -> None:
    print("="*72)
    print("AquaSkim-Sim | Phase 09 Scenario Validation and Robustness")
    print("="*72)
    for name,path in artifacts.as_dict().items(): print(f"{name:29}: {path}")
    print("="*72)
    print("[OK] Phase 09 scenarios, Monte Carlo study, figures, reel and evidence inputs generated.")
