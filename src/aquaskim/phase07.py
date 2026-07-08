"""Phase 07: environment, obstacles, debris and virtual sensor products."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Wedge
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.environment import (
    CircleObstacle,
    DebrisObject,
    EnvironmentSettings,
    GridMap,
    RectangleObstacle,
    SensorSettings,
    forward_range_measurements,
    simulate_sensor_demo,
)
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
class Phase07Artifacts:
    environment_map: Path
    environment_map_svg: Path
    occupancy_grid: Path
    occupancy_grid_svg: Path
    sensor_model: Path
    sensor_model_svg: Path
    perception_dashboard: Path
    perception_dashboard_svg: Path
    environment_objects_table: Path
    occupancy_grid_table: Path
    sensor_specifications_table: Path
    sensor_demo_log_table: Path
    detection_summary_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def as_dict(self) -> dict[str, str]:
        return {key: relative_to_root(value) for key, value in asdict(self).items()}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _draw_obstacles(ax: plt.Axes, environment: EnvironmentSettings, *, inflated: bool = False) -> None:
    for obstacle in environment.obstacles:
        if isinstance(obstacle, CircleObstacle):
            radius = obstacle.radius_m + (environment.robot_safety_radius_m if inflated else 0.0)
            ax.add_patch(Circle(obstacle.center_m, radius, facecolor=(PALETTE["orange_light"] if inflated else PALETTE["orange"]), edgecolor=PALETTE["orange"], alpha=(0.38 if inflated else 0.92), linewidth=1.2))
        elif isinstance(obstacle, RectangleObstacle):
            offset = environment.robot_safety_radius_m if inflated else 0.0
            width = obstacle.size_m[0] + 2.0 * offset
            height = obstacle.size_m[1] + 2.0 * offset
            ax.add_patch(Rectangle((obstacle.center_m[0] - width/2.0, obstacle.center_m[1] - height/2.0), width, height, facecolor=(PALETTE["orange_light"] if inflated else PALETTE["orange"]), edgecolor=PALETTE["orange"], alpha=(0.38 if inflated else 0.92), linewidth=1.2))


def _draw_environment_map(environment: EnvironmentSettings, debris: list[DebrisObject], truth_rows: list[dict[str, float]], output_path: Path) -> FigureExport:
    apply_engineering_style()
    figure = plt.figure(figsize=(16.0, 10.0))
    add_figure_header(figure, "Phase 07 | Operational Environment and Object Layout", "Analytic basin geometry, safety-inflated hazards, deterministic debris population and non-autonomous sensor-demonstration route.")
    ax = figure.add_axes([0.06, 0.12, 0.62, 0.75])
    panel = figure.add_axes([0.72, 0.12, 0.23, 0.75]); panel.axis("off")
    ax.add_patch(Rectangle((0.0, 0.0), environment.length_m, environment.width_m, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=1.5, zorder=0))
    _draw_obstacles(ax, environment, inflated=True)
    _draw_obstacles(ax, environment, inflated=False)
    ax.scatter([item.position_m[0] for item in debris], [item.position_m[1] for item in debris], s=20, marker="o", color=PALETTE["green"], edgecolors=PALETTE["white"], linewidths=0.35, label="Floating debris", zorder=5)
    ax.scatter([environment.home_position_m[0]], [environment.home_position_m[1]], marker="*", s=210, color=PALETTE["navy"], label="Home station", zorder=6)
    ax.plot([row["truth_x_m"] for row in truth_rows], [row["truth_y_m"] for row in truth_rows], color=PALETTE["blue"], linewidth=1.4, linestyle="--", label="Sensor demonstration route", zorder=4)
    ax.set_xlim(-0.2, environment.length_m + 0.2); ax.set_ylim(-0.2, environment.width_m + 0.2); ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); ax.legend(loc="upper right", fontsize=8.5); style_axis(ax)
    lines = [
        "ENVIRONMENT KEY",
        "",
        f"Basin plan: {environment.length_m:.1f} m × {environment.width_m:.1f} m",
        f"Water depth: {environment.water_depth_m:.2f} m",
        f"Robot safety radius: {environment.robot_safety_radius_m:.2f} m",
        f"Occupancy resolution: {environment.occupancy_resolution_m:.2f} m",
        f"Analytic obstacles: {len(environment.obstacles)}",
        f"Deterministic debris objects: {len(debris)}",
        "",
        "INTERPRETATION",
        "Orange solid geometry is the physical hazard. Pale orange is the configuration-space inflation used to account for vessel radius and safety margin. Green markers are candidate floating-litter targets. The dashed blue polyline is a repeatable sensor demonstration route, not an autonomy result.",
    ]
    y = 0.98
    for line in lines:
        weight = "bold" if line in {"ENVIRONMENT KEY", "INTERPRETATION"} else "normal"
        color = PALETTE["navy"] if weight == "bold" else PALETTE["gray_dark"]
        panel.text(0.0, y, line, ha="left", va="top", fontsize=10.0 if weight == "bold" else 9.1, fontweight=weight, color=color, wrap=True)
        y -= 0.055 if line else 0.03
    return export_figure(figure, output_path, dpi=320)


def _draw_occupancy_grid(environment: EnvironmentSettings, grid: GridMap, debris: list[DebrisObject], output_path: Path) -> FigureExport:
    apply_engineering_style()
    figure = plt.figure(figsize=(16.0, 10.0))
    add_figure_header(figure, "Phase 07 | Occupancy Grid and Configuration-Space Safety Inflation", "Grid occupancy is generated directly from analytic basin boundaries and obstacle signed-distance functions.")
    ax = figure.add_axes([0.06, 0.12, 0.64, 0.75])
    panel = figure.add_axes([0.74, 0.12, 0.21, 0.75]); panel.axis("off")
    extent = [0.0, environment.length_m, 0.0, environment.width_m]
    ax.imshow(grid.occupied.astype(float), extent=extent, origin="lower", interpolation="nearest", cmap="Blues", alpha=0.88, aspect="auto")
    _draw_obstacles(ax, environment, inflated=False)
    ax.scatter([item.position_m[0] for item in debris], [item.position_m[1] for item in debris], s=13, color=PALETTE["green"], edgecolors=PALETTE["white"], linewidths=0.25, zorder=5)
    ax.scatter([environment.home_position_m[0]], [environment.home_position_m[1]], marker="*", s=180, color=PALETTE["navy"], zorder=6)
    ax.set_xlim(0.0, environment.length_m); ax.set_ylim(0.0, environment.width_m); ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); style_axis(ax, grid=False)
    stats = [
        "GRID SPECIFICATION",
        "",
        f"Cell resolution: {grid.resolution_m:.2f} m",
        f"Grid dimensions: {grid.shape[1]} columns × {grid.shape[0]} rows",
        f"Total cells: {grid.occupied.size}",
        f"Occupied cells: {int(np.sum(grid.occupied))}",
        f"Occupied fraction: {100.0*grid.occupied_fraction:.1f}%",
        f"Safety inflation: {grid.clearance_m:.2f} m",
        "",
        "CELL MEANING",
        "Dark cells are prohibited configuration-space locations. This includes the basin boundary buffer plus each obstacle inflated by the robot safety radius. The planner in the next phase will use this exact grid as a reproducible navigation input.",
    ]
    y = 0.98
    for line in stats:
        is_header = line in {"GRID SPECIFICATION", "CELL MEANING"}
        panel.text(0.0, y, line, ha="left", va="top", fontsize=10.0 if is_header else 9.1, fontweight="bold" if is_header else "normal", color=PALETTE["navy"] if is_header else PALETTE["gray_dark"], wrap=True)
        y -= 0.055 if line else 0.03
    return export_figure(figure, output_path, dpi=320)


def _draw_sensor_model(environment: EnvironmentSettings, settings: SensorSettings, debris: list[DebrisObject], output_path: Path) -> FigureExport:
    apply_engineering_style()
    figure = plt.figure(figsize=(16.0, 10.0))
    add_figure_header(figure, "Phase 07 | Virtual Sensor Geometry at a Representative Pose", "Range beams, debris-detector field of view, GNSS uncertainty and compass uncertainty are explicit simulation interfaces.")
    ax = figure.add_axes([0.06, 0.12, 0.62, 0.75])
    panel = figure.add_axes([0.72, 0.12, 0.23, 0.75]); panel.axis("off")
    pose_x, pose_y, heading_deg = 3.6, 1.55, 42.0
    heading_rad = math.radians(heading_deg)
    ax.add_patch(Rectangle((0.0, 0.0), environment.length_m, environment.width_m, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=1.4))
    _draw_obstacles(ax, environment, inflated=False)
    visible_debris = debris[:]
    ax.scatter([item.position_m[0] for item in visible_debris], [item.position_m[1] for item in visible_debris], s=24, color=PALETTE["green"], edgecolors=PALETTE["white"], linewidths=0.3, zorder=5)
    wedge = Wedge((pose_x, pose_y), settings.debris_detection_range_m, heading_deg - settings.debris_detection_fov_deg/2.0, heading_deg + settings.debris_detection_fov_deg/2.0, facecolor=PALETTE["green_light"], edgecolor=PALETTE["green"], alpha=0.45, linewidth=1.2, zorder=2)
    ax.add_patch(wedge)
    beams = forward_range_measurements(environment, pose_x, pose_y, heading_rad, settings)
    for offset_deg, distance_m in beams:
        angle = heading_rad + math.radians(offset_deg)
        ax.plot([pose_x, pose_x + distance_m*math.cos(angle)], [pose_y, pose_y + distance_m*math.sin(angle)], color=PALETTE["orange"], linewidth=1.0, zorder=4)
    ax.add_patch(Circle((pose_x, pose_y), 0.18, facecolor=PALETTE["navy"], edgecolor=PALETTE["white"], linewidth=1.0, zorder=6))
    ax.arrow(pose_x, pose_y, 0.45*math.cos(heading_rad), 0.45*math.sin(heading_rad), width=0.028, head_width=0.15, head_length=0.13, color=PALETTE["navy"], length_includes_head=True, zorder=7)
    gps_ring = Circle((pose_x, pose_y), 2.0*settings.gps_position_std_m, fill=False, linestyle="--", linewidth=1.2, edgecolor=PALETTE["blue"], zorder=5)
    ax.add_patch(gps_ring)
    ax.set_xlim(0.0, 7.5); ax.set_ylim(0.0, 5.6); ax.set_aspect("equal", adjustable="box"); ax.set_xlabel("East x [m]"); ax.set_ylabel("North y [m]"); style_axis(ax)
    lines = [
        "SENSOR INTERFACES",
        "",
        f"GNSS/UWB noise σ: {settings.gps_position_std_m:.3f} m",
        f"Compass noise σ: {settings.compass_heading_std_deg:.1f}°",
        f"Range sensor: {settings.range_sensor_beam_count} beams / {settings.range_sensor_fov_deg:.0f}° / {settings.range_sensor_max_range_m:.1f} m",
        f"Debris detector: {settings.debris_detection_fov_deg:.0f}° / {settings.debris_detection_range_m:.1f} m",
        "",
        "VISUAL LEGEND",
        "Orange lines: range beams. Green sector: debris-detection field of view. Dashed blue circle: two-sigma GNSS uncertainty radius. Navy disc and arrow: vessel reference pose and heading.",
        "",
        "MODELLING LIMIT",
        "Sensors are analytic virtual instruments. Occlusion by obstacles is intentionally not enabled in this phase; it is a documented future extension.",
    ]
    y = 0.98
    for line in lines:
        is_header = line in {"SENSOR INTERFACES", "VISUAL LEGEND", "MODELLING LIMIT"}
        panel.text(0.0, y, line, ha="left", va="top", fontsize=10.0 if is_header else 9.1, fontweight="bold" if is_header else "normal", color=PALETTE["navy"] if is_header else PALETTE["gray_dark"], wrap=True)
        y -= 0.055 if line else 0.03
    return export_figure(figure, output_path, dpi=320)


def _draw_perception_dashboard(sensor_rows: list[dict[str, object]], detection_rows: list[dict[str, object]], settings: SensorSettings, output_path: Path) -> FigureExport:
    apply_engineering_style()
    figure = plt.figure(figsize=(16.0, 10.0))
    add_figure_header(figure, "Phase 07 | Sensor-Demo Perception Dashboard", "Truth-versus-measurement diagnostics and deterministic debris-detection outcomes generated for downstream autonomy development.")
    ax_position = figure.add_axes([0.06, 0.54, 0.39, 0.30])
    ax_heading = figure.add_axes([0.53, 0.54, 0.39, 0.30])
    ax_range = figure.add_axes([0.06, 0.12, 0.39, 0.30])
    ax_detect = figure.add_axes([0.53, 0.12, 0.39, 0.30])
    time = np.asarray([float(row["time_s"]) for row in sensor_rows])
    truth_x = np.asarray([float(row["truth_x_m"]) for row in sensor_rows]); truth_y = np.asarray([float(row["truth_y_m"]) for row in sensor_rows])
    gps_x = np.asarray([float(row["gps_x_m"]) for row in sensor_rows]); gps_y = np.asarray([float(row["gps_y_m"]) for row in sensor_rows])
    ax_position.plot(truth_x, truth_y, color=PALETTE["navy"], linewidth=1.8, label="Truth path")
    ax_position.scatter(gps_x[::10], gps_y[::10], s=10, color=PALETTE["blue"], alpha=0.65, label="GNSS/UWB surrogate")
    ax_position.set_title("Position measurement scatter", loc="left"); ax_position.set_xlabel("x [m]"); ax_position.set_ylabel("y [m]"); ax_position.legend(fontsize=8); ax_position.set_aspect("equal", adjustable="box"); style_axis(ax_position)
    heading_error = np.asarray([float(row["compass_heading_deg"]) - float(row["truth_heading_deg"]) for row in sensor_rows])
    heading_error = (heading_error + 180.0) % 360.0 - 180.0
    ax_heading.plot(time, heading_error, color=PALETTE["orange"], linewidth=1.0)
    ax_heading.axhline(0.0, color=PALETTE["gray"], linewidth=0.8)
    ax_heading.axhline(settings.compass_heading_std_deg, color=PALETTE["gray"], linestyle="--", linewidth=0.8)
    ax_heading.axhline(-settings.compass_heading_std_deg, color=PALETTE["gray"], linestyle="--", linewidth=0.8)
    ax_heading.set_title("Compass heading error", loc="left"); ax_heading.set_xlabel("time [s]"); ax_heading.set_ylabel("error [deg]"); style_axis(ax_heading)
    beam_indices = sorted({int(str(key).split("_")[2]) for key in sensor_rows[0] if key.startswith("range_beam_") and key.endswith("_m")})
    for index in beam_indices:
        ax_range.plot(time, [float(row[f"range_beam_{index}_m"]) for row in sensor_rows], linewidth=0.9, label=f"beam {index}")
    ax_range.set_title("Forward range measurements", loc="left"); ax_range.set_xlabel("time [s]"); ax_range.set_ylabel("range [m]"); ax_range.legend(ncol=3, fontsize=7, loc="upper right"); style_axis(ax_range)
    in_fov = [row for row in detection_rows if int(row["in_fov"]) == 1]
    detected = [row for row in in_fov if int(row["detected"]) == 1]
    ax_detect.scatter([float(row["truth_distance_m"]) for row in in_fov], [float(row["detection_probability"]) for row in in_fov], s=8, color=PALETTE["green"], alpha=0.32, label="Eligible observations")
    ax_detect.scatter([float(row["truth_distance_m"]) for row in detected], [float(row["detection_probability"]) for row in detected], s=14, marker="x", color=PALETTE["navy"], label="Detected")
    ax_detect.set_title("Debris detection outcome", loc="left"); ax_detect.set_xlabel("truth range [m]"); ax_detect.set_ylabel("model probability"); ax_detect.set_ylim(-0.03, 1.03); ax_detect.legend(fontsize=8); style_axis(ax_detect)
    return export_figure(figure, output_path, dpi=320)


def _detection_summary(detection_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_id: dict[str, list[dict[str, object]]] = {}
    for row in detection_rows:
        by_id.setdefault(str(row["debris_id"]), []).append(row)
    rows: list[dict[str, object]] = []
    for debris_id, rows_for_id in sorted(by_id.items()):
        in_fov = [row for row in rows_for_id if int(row["in_fov"]) == 1]
        detected = [row for row in in_fov if int(row["detected"]) == 1]
        rows.append({
            "debris_id": debris_id,
            "eligible_observations": len(in_fov),
            "detections": len(detected),
            "ever_detected": int(bool(detected)),
            "minimum_truth_range_m": min(float(row["truth_distance_m"]) for row in rows_for_id),
            "mean_probability_when_eligible": (float(np.mean([float(row["detection_probability"]) for row in in_fov])) if in_fov else 0.0),
        })
    return rows


def _acceptance_rows(environment: EnvironmentSettings, grid: GridMap, debris: list[DebrisObject], sensor_rows: list[dict[str, object]], detection_summary: list[dict[str, object]]) -> list[dict[str, object]]:
    gps_errors = [math.hypot(float(row["gps_x_m"]) - float(row["truth_x_m"]), float(row["gps_y_m"]) - float(row["truth_y_m"])) for row in sensor_rows]
    heading_errors = [((float(row["compass_heading_deg"]) - float(row["truth_heading_deg"]) + 180.0) % 360.0 - 180.0) for row in sensor_rows]
    truth_route_safe = all(environment.point_is_navigable(float(row["truth_x_m"]), float(row["truth_y_m"]), clearance_m=environment.robot_safety_radius_m) for row in sensor_rows)
    return [
        {"check": "home_position_is_navigable", "value": int(environment.point_is_navigable(*environment.home_position_m, clearance_m=environment.robot_safety_radius_m)), "criterion": "must equal 1", "status": "PASS" if environment.point_is_navigable(*environment.home_position_m, clearance_m=environment.robot_safety_radius_m) else "FAIL"},
        {"check": "all_debris_outside_inflated_hazards", "value": int(all(environment.point_is_navigable(*item.position_m, clearance_m=item.radius_m + environment.debris_clearance_m) for item in debris)), "criterion": "must equal 1", "status": "PASS" if all(environment.point_is_navigable(*item.position_m, clearance_m=item.radius_m + environment.debris_clearance_m) for item in debris) else "FAIL"},
        {"check": "demo_route_safe_for_robot_radius", "value": int(truth_route_safe), "criterion": "must equal 1", "status": "PASS" if truth_route_safe else "FAIL"},
        {"check": "occupancy_grid_contains_prohibited_cells", "value": int(np.sum(grid.occupied)), "criterion": "must be > 0", "status": "PASS" if np.sum(grid.occupied) > 0 else "FAIL"},
        {"check": "gps_rms_error_m", "value": float(np.sqrt(np.mean(np.square(gps_errors)))), "criterion": "must be < 0.20 m", "status": "PASS" if float(np.sqrt(np.mean(np.square(gps_errors)))) < 0.20 else "FAIL"},
        {"check": "compass_rms_error_deg", "value": float(np.sqrt(np.mean(np.square(heading_errors)))), "criterion": "must be < 8 deg", "status": "PASS" if float(np.sqrt(np.mean(np.square(heading_errors)))) < 8.0 else "FAIL"},
        {"check": "at_least_one_debris_detection", "value": int(sum(int(row["ever_detected"]) for row in detection_summary)), "criterion": "must be >= 1", "status": "PASS" if sum(int(row["ever_detected"]) for row in detection_summary) >= 1 else "FAIL"},
    ]


def _write_summary_markdown(path: Path, environment: EnvironmentSettings, grid: GridMap, debris: list[DebrisObject], sensor_settings: SensorSettings, acceptance: list[dict[str, object]], artifacts: Phase07Artifacts) -> None:
    passed = sum(1 for row in acceptance if row["status"] == "PASS")
    content = f"""# AquaSkim-Sim | Phase 07 Environment, Sensors and Debris Summary

## Operational world
- Basin plan: `{environment.length_m:.2f} × {environment.width_m:.2f} m`
- Analytic obstacles: `{len(environment.obstacles)}`
- Robot safety radius: `{environment.robot_safety_radius_m:.2f} m`
- Grid resolution: `{grid.resolution_m:.2f} m`
- Occupied configuration-space cells: `{int(np.sum(grid.occupied))} / {grid.occupied.size}`
- Deterministically placed debris objects: `{len(debris)}`

## Virtual sensors
- Position surrogate σ: `{sensor_settings.gps_position_std_m:.3f} m`
- Compass surrogate σ: `{sensor_settings.compass_heading_std_deg:.2f}°`
- Range sensor: `{sensor_settings.range_sensor_beam_count}` beams, `{sensor_settings.range_sensor_fov_deg:.0f}°` FOV, `{sensor_settings.range_sensor_max_range_m:.2f} m` maximum range
- Debris detector: `{sensor_settings.debris_detection_fov_deg:.0f}°` FOV, `{sensor_settings.debris_detection_range_m:.2f} m` maximum range

## Acceptance checks
- Passed: `{passed}/{len(acceptance)}`

| Check | Value | Criterion | Status |
|---|---:|---|---|
{chr(10).join(f"| {row['check']} | {row['value']} | {row['criterion']} | {row['status']} |" for row in acceptance)}

## Explicit modelling limitations
- Obstacles are analytic, static circles or axis-aligned rectangles.
- Virtual range beams stop on basin boundaries and obstacle geometry; debris is not currently modelled as an occluder.
- Debris detection uses an explicit probabilistic surrogate; no camera image or neural detector is claimed.
- The demonstration path is a deterministic data-generation route, not a closed-loop autonomy result.

## Phase 08 handoff
The occupancy grid, object map, sensor log and detection summary provide fixed, auditable inputs for planning, state estimation, reactive safety and the autonomy state machine.

## Artifact inventory
{chr(10).join(f"- `{path_value}`" for path_value in artifacts.as_dict().values())}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_phase07(config: ProjectConfiguration | None = None) -> Phase07Artifacts:
    ensure_runtime_directories()
    cfg = config or load_base_configuration()
    environment = EnvironmentSettings.from_config(cfg.data)
    sensor_settings = SensorSettings.from_config(cfg.data)
    debris = environment.generate_debris()
    grid = environment.occupancy_grid()
    cruise_speed = float(cfg.data["propulsion"]["limits"]["target_cruise_speed_mps"])
    sensor_rows, detection_rows, truth_rows = simulate_sensor_demo(environment, sensor_settings, debris, cruise_speed_mps=cruise_speed, random_seed=int(cfg.data["project"]["random_seed"]) + 700)
    detection_summary = _detection_summary(detection_rows)
    artifacts = Phase07Artifacts(
        environment_map=DIRECTORIES["figures"] / "phase07_environment_map.png",
        environment_map_svg=DIRECTORIES["figures"] / "phase07_environment_map.svg",
        occupancy_grid=DIRECTORIES["figures"] / "phase07_occupancy_grid.png",
        occupancy_grid_svg=DIRECTORIES["figures"] / "phase07_occupancy_grid.svg",
        sensor_model=DIRECTORIES["figures"] / "phase07_sensor_model.png",
        sensor_model_svg=DIRECTORIES["figures"] / "phase07_sensor_model.svg",
        perception_dashboard=DIRECTORIES["figures"] / "phase07_perception_dashboard.png",
        perception_dashboard_svg=DIRECTORIES["figures"] / "phase07_perception_dashboard.svg",
        environment_objects_table=DIRECTORIES["tables"] / "phase07_environment_objects.csv",
        occupancy_grid_table=DIRECTORIES["tables"] / "phase07_occupancy_grid.csv",
        sensor_specifications_table=DIRECTORIES["tables"] / "phase07_sensor_specifications.csv",
        sensor_demo_log_table=DIRECTORIES["tables"] / "phase07_sensor_demo_log.csv",
        detection_summary_table=DIRECTORIES["tables"] / "phase07_detection_summary.csv",
        acceptance_checks_table=DIRECTORIES["tables"] / "phase07_acceptance_checks.csv",
        summary_json=DIRECTORIES["logs"] / "phase07_environment_summary.json",
        summary_markdown=DIRECTORIES["reports"] / "phase07_environment_sensors_and_debris_summary.md",
        visual_quality_manifest=DIRECTORIES["logs"] / "phase07_visual_quality_manifest.json",
    )
    exports = [
        _draw_environment_map(environment, debris, truth_rows, artifacts.environment_map),
        _draw_occupancy_grid(environment, grid, debris, artifacts.occupancy_grid),
        _draw_sensor_model(environment, sensor_settings, debris, artifacts.sensor_model),
        _draw_perception_dashboard(sensor_rows, detection_rows, sensor_settings, artifacts.perception_dashboard),
    ]
    assert_export_quality(exports)
    _write_csv(artifacts.environment_objects_table, environment.object_rows(debris))
    _write_csv(artifacts.occupancy_grid_table, grid.occupancy_rows())
    _write_csv(artifacts.sensor_specifications_table, [spec.as_row() for spec in sensor_settings.specifications()])
    _write_csv(artifacts.sensor_demo_log_table, sensor_rows)
    _write_csv(artifacts.detection_summary_table, detection_summary)
    acceptance = _acceptance_rows(environment, grid, debris, sensor_rows, detection_summary)
    _write_csv(artifacts.acceptance_checks_table, acceptance)
    summary: dict[str, Any] = {
        "phase": "Phase 07 — Environment, Sensors and Debris",
        "configuration_file": relative_to_root(cfg.source_path),
        "environment": {
            "length_m": environment.length_m,
            "width_m": environment.width_m,
            "water_depth_m": environment.water_depth_m,
            "home_position_m": environment.home_position_m,
            "safety_radius_m": environment.robot_safety_radius_m,
            "obstacle_count": len(environment.obstacles),
            "debris_count": len(debris),
        },
        "occupancy_grid": {
            "resolution_m": grid.resolution_m,
            "shape": list(grid.shape),
            "occupied_cells": int(np.sum(grid.occupied)),
            "occupied_fraction": grid.occupied_fraction,
        },
        "sensor_demo": {
            "samples": len(sensor_rows),
            "detection_observations": len(detection_rows),
            "detected_debris_count": int(sum(int(row["ever_detected"]) for row in detection_summary)),
        },
        "acceptance_checks": acceptance,
        "limitations": [
            "Static analytic obstacles only; no moving obstacles, waves or wind fields in this phase.",
            "Virtual sensors use transparent Gaussian and probability models, not camera imagery or trained AI.",
            "The sensor demo route is deterministic and not yet generated by autonomous planning/control.",
        ],
        "artifacts": artifacts.as_dict(),
    }
    artifacts.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps({
        "phase": "Phase 07 visual quality gate",
        "quality_rule": {
            "minimum_png_width_px": 3000,
            "minimum_png_height_px": 1800,
            "formats": ["PNG (report-ready raster)", "SVG (vector)"],
            "layout_policy": "Object geometry, legends and explanatory text are separated into dedicated information panels; technical charts use fixed axes and restrained labels.",
        },
        "exports": [export.as_dict() for export in exports],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_markdown(artifacts.summary_markdown, environment, grid, debris, sensor_settings, acceptance, artifacts)
    return artifacts


def print_phase07_summary(artifacts: Phase07Artifacts) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 07 Environment, Sensors and Debris")
    print("=" * 72)
    for key, path in artifacts.as_dict().items():
        print(f"{key:28}: {path}")
    print("=" * 72)
    print("[OK] Phase 07 environment, grid, sensor and perception artifacts generated.")
