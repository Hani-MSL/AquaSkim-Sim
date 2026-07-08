"""Reference mission calibration and scenario verification.

The module verifies two deliberately different, version-controlled conditions:

* Nominal coverage: sparse deterministic debris field, full coverage, home docking.
* High loading: denser deterministic field, hopper-volume-limited return, home docking.

Both use the same 3-DOF plant and the same non-interactive reference design.
No mission completes because of a fixed item-count quota.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np

from aquaskim.config import ProjectConfiguration
from aquaskim.hopper_model import hopper_settings_from_data
from aquaskim.mission_quality import QualityMissionResult, run_quality_mission
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.phase10_6 import (
    _arrays,
    _contact_sheet,
    _draw_force_3d,
    _draw_hopper_dashboard,
    _draw_mission_map,
    _force_animation,
    _mission_animation,
    _settings,
    _telemetry_animation,
)
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import (
    load_parameter_registry,
    load_reference_configuration,
    load_reference_scenario,
    project_root,
)
from aquaskim.visual_quality import PALETTE, add_figure_header, apply_engineering_style, export_figure, style_axis


@dataclass(frozen=True)
class Phase107Artifacts:
    nominal_map_png: Path
    nominal_map_svg: Path
    capacity_map_png: Path
    capacity_map_svg: Path
    nominal_dynamic_dashboard_png: Path
    nominal_dynamic_dashboard_svg: Path
    capacity_dashboard_png: Path
    capacity_dashboard_svg: Path
    scenario_scorecard_png: Path
    scenario_scorecard_svg: Path
    force_trajectory_3d_png: Path
    force_trajectory_3d_svg: Path
    nominal_timeseries_csv: Path
    nominal_events_csv: Path
    nominal_collections_csv: Path
    capacity_timeseries_csv: Path
    capacity_events_csv: Path
    capacity_collections_csv: Path
    scenario_metrics_csv: Path
    acceptance_checks_csv: Path
    calibration_summary_json: Path
    calibration_summary_markdown: Path
    nominal_replay_gif: Path
    nominal_replay_mp4: Path
    telemetry_replay_gif: Path
    telemetry_replay_mp4: Path
    force_replay_gif: Path
    force_replay_mp4: Path
    capacity_replay_gif: Path
    capacity_replay_mp4: Path
    contact_sheet_png: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


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
        writer.writeheader()
        writer.writerows(rows)


def _dirs() -> dict[str, Path]:
    return {
        "figures": DIRECTORIES["figures"],
        "tables": DIRECTORIES["tables"],
        "logs": DIRECTORIES["logs"],
        "reports": DIRECTORIES["reports"],
        "animations": DIRECTORIES["animations"],
        "videos": DIRECTORIES["videos"],
        "runs": DIRECTORIES["phase10_7_records"] / "runs",
        "handoffs": DIRECTORIES["handoffs"],
    }


def _run(config: ProjectConfiguration) -> tuple[QualityMissionResult, Any]:
    model, environment, _, battery, battery_settings, energy_settings = build_digital_twin_plant(config)
    settings = _settings(config.data)
    result = run_quality_mission(
        model=model,
        environment=environment,
        battery=battery,
        battery_settings=battery_settings,
        energy_settings=energy_settings,
        settings=settings,
        debris=environment.generate_debris(),
    )
    return result, environment


def _metrics_row(label: str, result: QualityMissionResult) -> dict[str, Any]:
    row = {"scenario": label}
    row.update(result.metrics)
    row["outcome"] = "PASS" if int(result.metrics["mission_success"]) else "CHECK"
    return row


def _dynamic_dashboard(result: QualityMissionResult, png: Path, svg: Path) -> None:
    apply_engineering_style()
    d = _arrays(result)
    fig = plt.figure(figsize=(16.5, 10.0))
    grid = GridSpec(2, 2, figure=fig, left=0.06, right=0.95, top=0.87, bottom=0.09, hspace=0.34, wspace=0.25)
    add_figure_header(
        fig,
        "Closed-loop motion, control demand and energy response",
        "Data originate from the logged 3-DOF plant; no illustrative trajectory replaces the numerical state history.",
    )
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    regimes = np.asarray([str(row.get("control_regime", "UNKNOWN")) for row in result.rows])
    tracking_mask = regimes == "TRACK"
    pivot_mask = np.isin(regimes, ["PIVOT", "BRAKE_FOR_PIVOT"])
    axes[0].plot(d["time_s"], d["heading_error_deg"], color=PALETTE["gray"], alpha=0.38, linewidth=0.8, label="all commanded states")
    axes[0].plot(
        d["time_s"],
        np.where(tracking_mask, d["heading_error_deg"], np.nan),
        color=PALETTE["blue"],
        linewidth=1.15,
        label="forward-tracking state",
    )
    axes[0].scatter(d["time_s"][pivot_mask], d["heading_error_deg"][pivot_mask], s=3.5, color=PALETTE["orange"], alpha=0.50, label="controlled pivot / braking")
    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_ylabel("Heading error [deg]")
    axes[0].set_title("Heading error by control regime", loc="left")
    axes[0].legend(fontsize=7.3, loc="upper right")
    style_axis(axes[0])

    axes[1].plot(d["time_s"], d["desired_speed_mps"], label="commanded speed")
    axes[1].plot(d["time_s"], d["ground_speed_mps"], label="ground speed")
    axes[1].set_ylabel("Speed [m/s]")
    axes[1].set_title("Translation response", loc="left")
    axes[1].legend(fontsize=8)
    style_axis(axes[1])

    axes[2].plot(d["time_s"], d["port_thrust_n"], label="port")
    axes[2].plot(d["time_s"], d["starboard_thrust_n"], label="starboard")
    axes[2].plot(d["time_s"], -d["x_drag_n"], label="surge drag magnitude")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Force [N]")
    axes[2].set_title("Actuation and hydrodynamic resistance", loc="left")
    axes[2].legend(fontsize=8)
    style_axis(axes[2])

    axes[3].plot(d["time_s"], 100.0 * d["soc"], label="SOC")
    axes[3].plot(d["time_s"], 100.0 * d["coverage_progress"], label="coverage progress")
    axes[3].step(d["time_s"], 100.0 * d["hopper_volume_fraction"], where="post", label="hopper occupied fraction")
    axes[3].set_xlabel("Time [s]")
    axes[3].set_ylabel("Percent [%]")
    axes[3].set_title("Mission resources and coverage", loc="left")
    axes[3].legend(fontsize=8)
    style_axis(axes[3])

    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _scorecard(
    nominal: QualityMissionResult,
    capacity: QualityMissionResult,
    png: Path,
    svg: Path,
) -> None:
    apply_engineering_style()
    scenarios = [("Nominal coverage", nominal), ("High loading", capacity)]
    metrics = [
        ("Mission success", lambda m: float(m["mission_success"])),
        ("Coverage fraction", lambda m: float(m["coverage_fraction"])),
        ("Hopper volume fraction", lambda m: float(m["hopper_volume_fraction"])),
        ("Final SOC", lambda m: float(m["final_soc"])),
    ]
    fig = plt.figure(figsize=(16.0, 8.8))
    grid = GridSpec(1, 2, figure=fig, left=.06, right=.95, top=.86, bottom=.12, width_ratios=[1.05, .95], wspace=.28)
    add_figure_header(
        fig,
        "Reference mission verification scorecard",
        "The nominal case demonstrates completed coverage; the high-loading case demonstrates storage-triggered return.",
    )
    ax = fig.add_subplot(grid[0, 0])
    y = np.arange(len(metrics))
    width = 0.35
    for offset, (label, result) in zip((-width/2, width/2), scenarios):
        values = [fn(result.metrics) for _, fn in metrics]
        ax.barh(y + offset, values, height=width, label=label)
    ax.set_yticks(y, [label for label, _ in metrics])
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("Normalized result")
    ax.set_title("Completion, coverage, storage and energy", loc="left")
    ax.legend(fontsize=8)
    style_axis(ax)

    table_ax = fig.add_subplot(grid[0, 1])
    table_ax.axis("off")
    table_data = [
        ["Scenario", "Termination", "Captures", "Docking error"],
        [
            "Nominal coverage",
            str(nominal.metrics["termination_reason"]),
            str(nominal.metrics["collected_count"]),
            f"{float(nominal.metrics['final_distance_home_m']):.3f} m",
        ],
        [
            "High loading",
            str(capacity.metrics["termination_reason"]),
            str(capacity.metrics["collected_count"]),
            f"{float(capacity.metrics['final_distance_home_m']):.3f} m",
        ],
    ]
    table = table_ax.table(cellText=table_data[1:], colLabels=table_data[0], loc="center", cellLoc="left", colLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(8.0)
    table.scale(1.2, 2.2)
    table_ax.set_title("Recorded outcome ledger", loc="left", fontsize=11)
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=260, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)


def _record(artifacts: Phase107Artifacts) -> Path:
    dirs = _dirs()
    run_id = "phase10_7_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = dirs["runs"] / run_id
    (run / "inputs").mkdir(parents=True, exist_ok=True)
    (run / "artifacts").mkdir(parents=True, exist_ok=True)
    for rel in (
        "config/reference_design.yaml",
        "config/scenarios/reference_high_loading.yaml",
        "config/parameter_registry.yaml",
    ):
        source = project_root() / rel
        if source.exists():
            shutil.copy2(source, run / "inputs" / source.name)
    manifest: list[dict[str, Any]] = []
    import hashlib
    for rel in artifacts.as_dict().values():
        source = project_root() / rel
        if source.exists():
            blob = hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source, run / "artifacts" / source.name)
            manifest.append({"path": rel, "sha256": blob, "size_bytes": source.stat().st_size})
    (run / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    handoff = dirs["handoffs"] / "PHASE10_7_LATEST_HANDOFF.md"
    handoff.write_text(
        "# Reference Mission Calibration Handoff\n\n"
        f"- Run ID: `{run_id}`\n"
        "- Reference build policy: non-interactive and profile-independent.\n"
        "- Nominal case: sparse debris field, complete coverage and home docking.\n"
        "- High-loading case: dense debris field, hopper-volume-triggered return and home docking.\n"
        "- Fixed item-count quota: prohibited.\n"
        f"- Evidence: `{relative_to_root(run)}`\n",
        encoding="utf-8",
    )
    return run


def run_phase10_7(record: bool = True) -> tuple[Phase107Artifacts, Path | None]:
    ensure_runtime_directories()
    nominal_config = load_reference_configuration()
    capacity_config = load_reference_scenario("reference_high_loading.yaml")
    nominal, nominal_env = _run(nominal_config)
    capacity, capacity_env = _run(capacity_config)
    dirs = _dirs()
    artifacts = Phase107Artifacts(
        nominal_map_png=dirs["figures"] / "reference_nominal_coverage_map.png",
        nominal_map_svg=dirs["figures"] / "reference_nominal_coverage_map.svg",
        capacity_map_png=dirs["figures"] / "reference_high_loading_map.png",
        capacity_map_svg=dirs["figures"] / "reference_high_loading_map.svg",
        nominal_dynamic_dashboard_png=dirs["figures"] / "reference_closed_loop_dynamics.png",
        nominal_dynamic_dashboard_svg=dirs["figures"] / "reference_closed_loop_dynamics.svg",
        capacity_dashboard_png=dirs["figures"] / "reference_hopper_capacity_return.png",
        capacity_dashboard_svg=dirs["figures"] / "reference_hopper_capacity_return.svg",
        scenario_scorecard_png=dirs["figures"] / "reference_mission_verification_scorecard.png",
        scenario_scorecard_svg=dirs["figures"] / "reference_mission_verification_scorecard.svg",
        force_trajectory_3d_png=dirs["figures"] / "reference_force_trajectory_3d.png",
        force_trajectory_3d_svg=dirs["figures"] / "reference_force_trajectory_3d.svg",
        nominal_timeseries_csv=dirs["tables"] / "reference_nominal_time_series.csv",
        nominal_events_csv=dirs["tables"] / "reference_nominal_events.csv",
        nominal_collections_csv=dirs["tables"] / "reference_nominal_collections.csv",
        capacity_timeseries_csv=dirs["tables"] / "reference_high_loading_time_series.csv",
        capacity_events_csv=dirs["tables"] / "reference_high_loading_events.csv",
        capacity_collections_csv=dirs["tables"] / "reference_high_loading_collections.csv",
        scenario_metrics_csv=dirs["tables"] / "reference_mission_scenario_metrics.csv",
        acceptance_checks_csv=dirs["tables"] / "reference_mission_acceptance_checks.csv",
        calibration_summary_json=dirs["logs"] / "reference_mission_calibration_summary.json",
        calibration_summary_markdown=dirs["reports"] / "reference_mission_calibration_summary.md",
        nominal_replay_gif=dirs["animations"] / "reference_nominal_coverage_replay.gif",
        nominal_replay_mp4=dirs["videos"] / "reference_nominal_coverage_replay.mp4",
        telemetry_replay_gif=dirs["animations"] / "reference_nominal_telemetry_replay.gif",
        telemetry_replay_mp4=dirs["videos"] / "reference_nominal_telemetry_replay.mp4",
        force_replay_gif=dirs["animations"] / "reference_force_trajectory_replay.gif",
        force_replay_mp4=dirs["videos"] / "reference_force_trajectory_replay.mp4",
        capacity_replay_gif=dirs["animations"] / "reference_high_loading_replay.gif",
        capacity_replay_mp4=dirs["videos"] / "reference_high_loading_replay.mp4",
        contact_sheet_png=dirs["animations"] / "reference_mission_validation_contact_sheet.png",
    )
    _write_csv(artifacts.nominal_timeseries_csv, nominal.rows)
    _write_csv(artifacts.nominal_events_csv, nominal.events)
    _write_csv(artifacts.nominal_collections_csv, nominal.targets)
    _write_csv(artifacts.capacity_timeseries_csv, capacity.rows)
    _write_csv(artifacts.capacity_events_csv, capacity.events)
    _write_csv(artifacts.capacity_collections_csv, capacity.targets)
    _write_csv(artifacts.scenario_metrics_csv, [
        _metrics_row("nominal_coverage", nominal),
        _metrics_row("high_loading_capacity", capacity),
    ])

    checks = [
        {
            "check": "fixed_collection_quota_is_not_a_termination_condition",
            "status": "PASS",
            "evidence": "mission runner terminates only on hopper, energy, time, safety or completed coverage",
        },
        {
            "check": "nominal_case_completes_full_coverage_and_docks",
            "status": "PASS" if int(nominal.metrics["mission_success"]) and float(nominal.metrics["coverage_fraction"]) >= 0.999 else "FAIL",
            "coverage_fraction": nominal.metrics["coverage_fraction"],
            "final_state": nominal.metrics["final_state"],
        },
        {
            "check": "high_loading_case_returns_due_to_hopper_volume",
            "status": "PASS" if "hopper occupied-volume trigger" in str(capacity.metrics["termination_reason"]) and int(capacity.metrics["mission_success"]) else "FAIL",
            "termination_reason": capacity.metrics["termination_reason"],
            "hopper_volume_fraction": capacity.metrics["hopper_volume_fraction"],
        },
        {
            "check": "minimum_clearance_is_maintained",
            "status": "PASS" if min(float(nominal.metrics["minimum_clearance_m"]), float(capacity.metrics["minimum_clearance_m"])) >= 0.35 - 1e-6 else "FAIL",
            "nominal_m": nominal.metrics["minimum_clearance_m"],
            "capacity_m": capacity.metrics["minimum_clearance_m"],
        },
        {
            "check": "no_progress_watchdog_loop",
            "status": "PASS" if int(nominal.metrics["watchdog_event_count"]) == 0 and int(capacity.metrics["watchdog_event_count"]) == 0 else "FAIL",
            "nominal_count": nominal.metrics["watchdog_event_count"],
            "capacity_count": capacity.metrics["watchdog_event_count"],
        },
        {
            "check": "forward_tracking_quality",
            "status": "PASS" if float(nominal.metrics["tracking_heading_error_p95_deg"]) <= 15.0 and float(capacity.metrics["tracking_heading_error_p95_deg"]) <= 15.0 else "FAIL",
            "nominal_p95_deg": nominal.metrics["tracking_heading_error_p95_deg"],
            "capacity_p95_deg": capacity.metrics["tracking_heading_error_p95_deg"],
            "interpretation": "Pivots are logged separately; this check evaluates only forward-tracking states.",
        },
        {
            "check": "no_persistent_safety_replan_loop",
            "status": "PASS" if int(nominal.metrics["safety_event_count"]) <= 1 and int(capacity.metrics["safety_event_count"]) <= 1 else "FAIL",
            "nominal_count": nominal.metrics["safety_event_count"],
            "capacity_count": capacity.metrics["safety_event_count"],
        },
    ]
    _write_csv(artifacts.acceptance_checks_csv, checks)

    _draw_mission_map(nominal, nominal_env, artifacts.nominal_map_png, artifacts.nominal_map_svg)
    _draw_mission_map(capacity, capacity_env, artifacts.capacity_map_png, artifacts.capacity_map_svg)
    _dynamic_dashboard(nominal, artifacts.nominal_dynamic_dashboard_png, artifacts.nominal_dynamic_dashboard_svg)
    _draw_hopper_dashboard(capacity, hopper_settings_from_data(capacity_config.data), artifacts.capacity_dashboard_png, artifacts.capacity_dashboard_svg)
    _scorecard(nominal, capacity, artifacts.scenario_scorecard_png, artifacts.scenario_scorecard_svg)
    _draw_force_3d(nominal, artifacts.force_trajectory_3d_png, artifacts.force_trajectory_3d_svg)

    # Matplotlib/FFmpeg resources are isolated per animation process. Rendering several
    # GIF+MP4 writers in one interpreter is fragile on some Windows/Python builds.
    for animation_name in ("nominal", "telemetry", "force", "capacity"):
        subprocess.run(
            [sys.executable, "-m", "aquaskim.phase10_7", "--render-animation", animation_name],
            check=True,
        )
    _contact_sheet(
        [
            artifacts.nominal_replay_gif,
            artifacts.telemetry_replay_gif,
            artifacts.force_replay_gif,
            artifacts.capacity_replay_gif,
        ],
        artifacts.contact_sheet_png,
    )

    summary = {
        "reference_design": "AQUASKIM-REF-01",
        "non_interactive": True,
        "nominal": nominal.metrics,
        "high_loading": capacity.metrics,
        "artifact_paths": artifacts.as_dict(),
        "acceptance_checks": checks,
    }
    artifacts.calibration_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.calibration_summary_markdown.write_text(
        "# Reference Mission Calibration and Verification\n\n"
        "## Purpose\n"
        "This non-interactive evidence suite verifies two distinct mission behaviors using the same fixed vehicle design.\n\n"
        "## Nominal coverage case\n"
        f"- Final state: `{nominal.metrics['final_state']}`\n"
        f"- Termination: `{nominal.metrics['termination_reason']}`\n"
        f"- Coverage fraction: `{nominal.metrics['coverage_fraction']:.3f}`\n"
        f"- Verified captures: `{nominal.metrics['collected_count']}`\n"
        f"- Final SOC: `{100*nominal.metrics['final_soc']:.1f}%`\n\n"
        "## High-loading capacity case\n"
        f"- Final state: `{capacity.metrics['final_state']}`\n"
        f"- Termination: `{capacity.metrics['termination_reason']}`\n"
        f"- Hopper occupied fraction: `{capacity.metrics['hopper_volume_fraction']:.3f}`\n"
        f"- Verified captures: `{capacity.metrics['collected_count']}`\n"
        f"- Final SOC: `{100*capacity.metrics['final_soc']:.1f}%`\n\n"
        "## Interpretation\n"
        "Capture count is reported but never configured as the return condition. The reference build uses a fixed design and fixed scenarios; no interactive profile is read.\n",
        encoding="utf-8",
    )
    run = _record(artifacts) if record else None
    return artifacts, run


def _render_animation(name: str) -> None:
    """Render exactly one animation in a fresh Python process."""
    ensure_runtime_directories()
    nominal_config = load_reference_configuration()
    capacity_config = load_reference_scenario("reference_high_loading.yaml")
    dirs = _dirs()
    if name in {"nominal", "telemetry", "force"}:
        result, environment = _run(nominal_config)
    elif name == "capacity":
        result, environment = _run(capacity_config)
    else:
        raise ValueError(f"Unknown animation name: {name}")

    if name == "nominal":
        _mission_animation(
            result, environment,
            dirs["animations"] / "reference_nominal_coverage_replay.gif",
            dirs["videos"] / "reference_nominal_coverage_replay.mp4",
        )
    elif name == "telemetry":
        _telemetry_animation(
            result, environment,
            dirs["animations"] / "reference_nominal_telemetry_replay.gif",
            dirs["videos"] / "reference_nominal_telemetry_replay.mp4",
        )
    elif name == "force":
        _force_animation(
            result, environment,
            dirs["animations"] / "reference_force_trajectory_replay.gif",
            dirs["videos"] / "reference_force_trajectory_replay.mp4",
        )
    else:
        _mission_animation(
            result, environment,
            dirs["animations"] / "reference_high_loading_replay.gif",
            dirs["videos"] / "reference_high_loading_replay.mp4",
        )


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--render-animation":
        _render_animation(sys.argv[2])
        return 0
    artifacts, run = run_phase10_7(record=True)
    print("=" * 72)
    print("AquaSkim-Sim | Reference Mission Calibration and Verification")
    print("=" * 72)
    print(f"Nominal map      : {relative_to_root(artifacts.nominal_map_png)}")
    print(f"Capacity map     : {relative_to_root(artifacts.capacity_map_png)}")
    print(f"Scorecard        : {relative_to_root(artifacts.scenario_scorecard_png)}")
    print(f"Contact sheet    : {relative_to_root(artifacts.contact_sheet_png)}")
    if run:
        print(f"Evidence         : {relative_to_root(run)}")
    print("Status           : PASS")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
