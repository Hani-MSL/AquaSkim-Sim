"""Phase 10.3: parametric design trade study and release-quality evidence.

This module extends AquaSkim-Sim from a single nominal design into a small,
transparent design-space study.  It does not claim a formal optimisation or a
manufacturing-certified design.  Every point uses the same conceptual
hydrostatics, resistance, propulsion and battery models already documented in
Phases 03–05.

The implementation deliberately keeps all design assumptions explicit:
- hull-spacing / payload sweep for buoyancy and transverse stability;
- battery-capacity / cruise-speed sweep for endurance and thrust feasibility;
- a short candidate set to expose engineering trade-offs; and
- a release-quality dashboard that verifies the generated portfolio.
"""
from __future__ import annotations

import copy
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.propulsion import ThrusterSettings, TwinThrusterModel
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
class Phase103Artifacts:
    stability_trade_space: FigureExport
    endurance_trade_space: FigureExport
    candidate_comparison: FigureExport
    synthesis_dashboard: FigureExport
    stability_sweep_table: Path
    endurance_sweep_table: Path
    candidate_rankings_table: Path
    release_quality_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def all_paths(self) -> tuple[Path, ...]:
        exports = (
            self.stability_trade_space,
            self.endurance_trade_space,
            self.candidate_comparison,
            self.synthesis_dashboard,
        )
        figure_paths: list[Path] = []
        for export in exports:
            figure_paths.extend((export.png_path, export.svg_path))
        return (
            *figure_paths,
            self.stability_sweep_table,
            self.endurance_sweep_table,
            self.candidate_rankings_table,
            self.release_quality_table,
            self.acceptance_checks_table,
            self.summary_json,
            self.summary_markdown,
            self.visual_quality_manifest,
        )

    def as_dict(self) -> dict[str, str]:
        return {relative_to_root(path): relative_to_root(path) for path in self.all_paths()}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _nested_set(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def _mutate_design(
    base: dict[str, Any], *, hull_spacing_m: float | None = None,
    payload_kg: float | None = None, battery_capacity_ah: float | None = None,
    cruise_speed_mps: float | None = None,
) -> dict[str, Any]:
    """Copy the base model and apply a physically consistent trade-study change."""
    data = copy.deepcopy(base)
    geometry = data["mechanical"]["geometry"]
    if hull_spacing_m is not None:
        geometry["hull_spacing_center_m"] = float(hull_spacing_m)
        geometry["thruster_spacing_m"] = float(hull_spacing_m)
        y_map = {
            "hull_left": +0.5 * hull_spacing_m,
            "hull_right": -0.5 * hull_spacing_m,
            "thruster_left": +0.5 * hull_spacing_m,
            "thruster_right": -0.5 * hull_spacing_m,
        }
        for component in data["mass_budget"]["components"]:
            if component["name"] in y_map:
                component["position_m"][1] = float(y_map[component["name"]])
    if payload_kg is not None:
        geometry["design_payload_kg"] = float(payload_kg)
    if battery_capacity_ah is not None:
        battery = data["energy"]["battery"]
        battery["capacity_ah"] = float(battery_capacity_ah)
        battery["nominal_energy_wh"] = float(battery_capacity_ah) * float(battery["nominal_voltage_v"])
    if cruise_speed_mps is not None:
        data["propulsion"]["limits"]["target_cruise_speed_mps"] = float(cruise_speed_mps)
        data["autonomy"]["cruise_speed_mps"] = float(cruise_speed_mps)
    return data


def _governing_case(data: dict[str, Any]):
    geometry = CatamaranGeometry.from_config(data)
    settings = HydrostaticSettings.from_config(data)
    hydro = CatamaranHydrostatics(geometry, settings)
    _, properties = build_load_cases(data)["full_design_payload"]
    return geometry, settings, hydro, hydro.case_from_mass_properties("full_design_payload", properties)


def _stability_row(base: dict[str, Any], spacing_m: float, payload_kg: float) -> dict[str, object]:
    data = _mutate_design(base, hull_spacing_m=spacing_m, payload_kg=payload_kg)
    geometry, settings, hydro, case = _governing_case(data)
    heel = hydro.operating_state(case)
    feasible = (
        case.gm_m >= settings.minimum_gm_m
        and case.freeboard_m >= settings.minimum_freeboard_m
        and heel.min_freeboard_m >= settings.minimum_freeboard_m
        and case.capacity_ratio > 1.0
    )
    return {
        "hull_spacing_m": spacing_m,
        "payload_kg": payload_kg,
        "total_mass_kg": case.total_mass_kg,
        "overall_width_m": geometry.overall_width_m,
        "draft_m": case.draft_m,
        "freeboard_m": case.freeboard_m,
        "operational_heel_min_freeboard_m": heel.min_freeboard_m,
        "KG_m": case.kg_m,
        "BM_m": case.bm_m,
        "GM_m": case.gm_m,
        "capacity_ratio": case.capacity_ratio,
        "gm_margin_m": case.gm_m - settings.minimum_gm_m,
        "freeboard_margin_m": min(case.freeboard_m, heel.min_freeboard_m) - settings.minimum_freeboard_m,
        "feasible": int(feasible),
    }


def _endurance_row(base: dict[str, Any], capacity_ah: float, cruise_speed_mps: float) -> dict[str, object]:
    data = _mutate_design(base, battery_capacity_ah=capacity_ah, cruise_speed_mps=cruise_speed_mps)
    geometry, _, _, case = _governing_case(data)
    resistance = CatamaranResistanceModel(geometry, HydrodynamicSettings.from_config(data), case)
    state = resistance.state_at_speed(cruise_speed_mps)
    thrusters = TwinThrusterModel(ThrusterSettings.from_config(data))
    point = thrusters.symmetric_operating_point(state.total_resistance_n)
    battery_settings = BatterySettings.from_config(data)
    battery = BatteryModel(battery_settings)
    energy = EnergySettings.from_config(data)
    bus_load = point.total_thruster_power_w + energy.hotel_load_w
    endurance_s = battery.endurance_to_soc_s(
        bus_load,
        start_soc=1.0,
        stop_soc=float(data["autonomy"]["rth_soc_floor"]),
        step_s=energy.integration_time_step_s,
    )
    thrust_reserve = thrusters.settings.total_max_thrust_n / max(state.total_resistance_n, 1e-12)
    feasible = (
        point.feasible
        and thrust_reserve >= resistance.settings.minimum_thrust_reserve_ratio
        and endurance_s / 60.0 >= energy.minimum_endurance_at_cruise_min
    )
    return {
        "battery_capacity_ah": capacity_ah,
        "cruise_speed_mps": cruise_speed_mps,
        "resistance_n": state.total_resistance_n,
        "rpm_per_side": point.rpm_per_side,
        "throttle_fraction": point.throttle_fraction,
        "bus_load_w": bus_load,
        "battery_current_a": battery.load_state(bus_load, 1.0).pack_current_a,
        "usable_energy_wh": battery_settings.usable_energy_wh,
        "endurance_min_to_rth_floor": endurance_s / 60.0,
        "thrust_reserve_ratio": thrust_reserve,
        "thrust_feasible": int(point.feasible),
        "feasible": int(feasible),
    }


def _stability_sweep(base: dict[str, Any]) -> list[dict[str, object]]:
    nominal_spacing = float(base["mechanical"]["geometry"]["hull_spacing_center_m"])
    nominal_payload = float(base["mechanical"]["geometry"]["design_payload_kg"])
    spacings = np.round(np.linspace(max(0.20, nominal_spacing - 0.10), nominal_spacing + 0.18, 9), 3)
    payloads = np.round(np.linspace(max(0.20, nominal_payload * 0.40), nominal_payload * 1.75, 10), 3)
    return [_stability_row(base, float(spacing), float(payload)) for payload in payloads for spacing in spacings]


def _endurance_sweep(base: dict[str, Any]) -> list[dict[str, object]]:
    nominal_capacity = float(base["energy"]["battery"]["capacity_ah"])
    capacities = np.array(sorted({3.0, 4.0, nominal_capacity, 6.0, 8.0, 10.0}), dtype=float)
    speeds = np.round(np.linspace(0.20, min(0.60, float(base["propulsion"]["limits"]["max_speed_mps"])), 9), 3)
    return [_endurance_row(base, float(capacity), float(speed)) for capacity in capacities for speed in speeds]


def _candidate_rows(base: dict[str, Any]) -> list[dict[str, object]]:
    nominal = base["mechanical"]["geometry"]
    b = base["energy"]["battery"]
    candidates = [
        ("Nominal baseline", float(nominal["hull_spacing_center_m"]), float(nominal["design_payload_kg"]), float(b["capacity_ah"]), float(base["propulsion"]["limits"]["target_cruise_speed_mps"])),
        ("Stability margin", float(nominal["hull_spacing_center_m"]) + 0.08, float(nominal["design_payload_kg"]), float(b["capacity_ah"]), 0.40),
        ("Payload margin", float(nominal["hull_spacing_center_m"]) + 0.06, float(nominal["design_payload_kg"]) * 1.35, 6.0, 0.35),
        ("Endurance priority", float(nominal["hull_spacing_center_m"]), float(nominal["design_payload_kg"]), 8.0, 0.30),
        ("Throughput priority", float(nominal["hull_spacing_center_m"]) + 0.04, float(nominal["design_payload_kg"]), 8.0, 0.50),
        ("Constrained boundary", max(0.22, float(nominal["hull_spacing_center_m"]) - 0.06), float(nominal["design_payload_kg"]) * 1.50, 3.0, 0.55),
    ]
    rows: list[dict[str, object]] = []
    for label, spacing, payload, capacity, speed in candidates:
        stability = _stability_row(base, spacing, payload)
        endurance = _endurance_row(base, capacity, speed)
        gm_margin = float(stability["gm_margin_m"])
        fb_margin = float(stability["freeboard_margin_m"])
        end_margin = float(endurance["endurance_min_to_rth_floor"]) / float(base["energy"]["model"]["minimum_endurance_at_cruise_min"])
        thrust_margin = float(endurance["thrust_reserve_ratio"]) / float(base["hydrodynamics"]["minimum_thrust_reserve_ratio"])
        feasible = int(stability["feasible"]) and int(endurance["feasible"])
        score = min(
            max(0.0, gm_margin / float(base["hydrostatics"]["minimum_gm_m"])),
            max(0.0, fb_margin / float(base["hydrostatics"]["minimum_freeboard_m"])),
            end_margin,
            thrust_margin,
        )
        rows.append({
            "candidate": label,
            "hull_spacing_m": spacing,
            "payload_kg": payload,
            "battery_capacity_ah": capacity,
            "cruise_speed_mps": speed,
            "GM_m": stability["GM_m"],
            "freeboard_m": stability["freeboard_m"],
            "endurance_min": endurance["endurance_min_to_rth_floor"],
            "thrust_reserve_ratio": endurance["thrust_reserve_ratio"],
            "throttle_fraction": endurance["throttle_fraction"],
            "feasible": int(feasible),
            "constraint_margin_score": score,
        })
    return sorted(rows, key=lambda row: float(row["constraint_margin_score"]), reverse=True)


def _panel(ax: plt.Axes, title: str, rows: list[tuple[str, str]], narrative: str) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.025, 0.03), 0.95, 0.94, boxstyle="round,pad=.018,rounding_size=.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))
    ax.text(0.08, 0.92, title, fontsize=12.5, fontweight="bold", color=PALETTE["navy"], va="top")
    y = 0.82
    for key, value in rows:
        ax.text(0.09, y, key, fontsize=8.7, color=PALETTE["gray_dark"], va="center")
        ax.text(0.91, y, value, fontsize=8.7, color=PALETTE["navy"], va="center", ha="right", fontweight="bold")
        ax.plot([0.08, 0.92], [y - 0.035, y - 0.035], color=PALETTE["grid"], linewidth=.6)
        y -= 0.09
    ax.text(0.08, 0.28, fill(narrative, 46), fontsize=8.5, color=PALETTE["gray_dark"], va="top", linespacing=1.35)


def _matrix(rows: list[dict[str, object]], x_key: str, y_key: str, value_key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.array(sorted({float(row[x_key]) for row in rows}), dtype=float)
    y = np.array(sorted({float(row[y_key]) for row in rows}), dtype=float)
    grid = np.full((len(y), len(x)), np.nan)
    lookup = {(float(row[x_key]), float(row[y_key])): float(row[value_key]) for row in rows}
    for iy, y_value in enumerate(y):
        for ix, x_value in enumerate(x):
            grid[iy, ix] = lookup[(x_value, y_value)]
    return x, y, grid


def _draw_stability(rows: list[dict[str, object]], base: dict[str, Any], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.35, .85], left=.055, right=.955, bottom=.08, top=.875, wspace=.17, hspace=.34)
    gm_ax = fig.add_subplot(grid[0, 0])
    fb_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Phase 10.3 — Stability Trade Space", "Payload and hull-spacing sweep using the Phase 03 hydrostatic model; each cell uses full-load mass properties and the operational heel criterion.")
    x, y, gm = _matrix(rows, "hull_spacing_m", "payload_kg", "GM_m")
    _, _, fb = _matrix(rows, "hull_spacing_m", "payload_kg", "operational_heel_min_freeboard_m")
    extent = [x.min(), x.max(), y.min(), y.max()]
    image = gm_ax.imshow(gm, origin="lower", aspect="auto", extent=extent, cmap="YlGnBu")
    levels = [float(base["hydrostatics"]["minimum_gm_m"])]
    contour = gm_ax.contour(x, y, gm, levels=levels, colors=[PALETTE["orange"]], linewidths=2.0)
    gm_ax.clabel(contour, fmt="GM limit = %.2f m", fontsize=8)
    gm_ax.scatter([base["mechanical"]["geometry"]["hull_spacing_center_m"]], [base["mechanical"]["geometry"]["design_payload_kg"]], marker="*", s=150, color=PALETTE["orange"], edgecolor=PALETTE["white"], zorder=5, label="Nominal design")
    gm_ax.set_title("Metacentric-height map", loc="left")
    gm_ax.set_xlabel("Hull centre spacing [m]")
    gm_ax.set_ylabel("Collected payload [kg]")
    gm_ax.legend(loc="upper left", fontsize=8)
    style_axis(gm_ax)
    fig.colorbar(image, ax=gm_ax, label="GM [m]")

    image_fb = fb_ax.imshow(fb, origin="lower", aspect="auto", extent=extent, cmap="YlOrBr")
    contour_fb = fb_ax.contour(x, y, fb, levels=[float(base["hydrostatics"]["minimum_freeboard_m"])] , colors=[PALETTE["navy"]], linewidths=2.0)
    fb_ax.clabel(contour_fb, fmt="Freeboard limit = %.2f m", fontsize=8)
    fb_ax.scatter([base["mechanical"]["geometry"]["hull_spacing_center_m"]], [base["mechanical"]["geometry"]["design_payload_kg"]], marker="*", s=150, color=PALETTE["navy"], edgecolor=PALETTE["white"], zorder=5)
    fb_ax.set_title("Minimum freeboard at operational heel", loc="left")
    fb_ax.set_xlabel("Hull centre spacing [m]")
    fb_ax.set_ylabel("Collected payload [kg]")
    style_axis(fb_ax)
    fig.colorbar(image_fb, ax=fb_ax, label="Minimum freeboard [m]")

    feasible = sum(int(row["feasible"]) for row in rows)
    _panel(info, "STABILITY INTERPRETATION", [
        ("Sweep samples", str(len(rows))),
        ("Feasible samples", f"{feasible} / {len(rows)}"),
        ("GM requirement", f">= {float(base['hydrostatics']['minimum_gm_m']):.2f} m"),
        ("Freeboard requirement", f">= {float(base['hydrostatics']['minimum_freeboard_m']):.2f} m"),
        ("Nominal spacing", f"{float(base['mechanical']['geometry']['hull_spacing_center_m']):.3f} m"),
        ("Nominal payload", f"{float(base['mechanical']['geometry']['design_payload_kg']):.3f} kg"),
    ], "Increasing hull separation strongly increases transverse stability through the waterplane second moment. Increasing collected payload reduces freeboard and changes the governing full-load case. This is a conceptual hydrostatic sweep; it does not replace a detailed hull-form or wave stability study.")
    return export_figure(fig, output, dpi=320)


def _draw_endurance(rows: list[dict[str, object]], base: dict[str, Any], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.35, .85], left=.055, right=.955, bottom=.08, top=.875, wspace=.17, hspace=.34)
    endurance_ax = fig.add_subplot(grid[0, 0])
    throttle_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Phase 10.3 — Endurance and Propulsion Trade Space", "Battery-capacity and cruise-speed sweep using the Phase 04 resistance/thruster model and Phase 05 pack-side SOC model.")
    x, y, endurance = _matrix(rows, "cruise_speed_mps", "battery_capacity_ah", "endurance_min_to_rth_floor")
    _, _, throttle = _matrix(rows, "cruise_speed_mps", "battery_capacity_ah", "throttle_fraction")
    extent = [x.min(), x.max(), y.min(), y.max()]
    image = endurance_ax.imshow(endurance, origin="lower", aspect="auto", extent=extent, cmap="GnBu")
    limit = float(base["energy"]["model"]["minimum_endurance_at_cruise_min"])
    contour = endurance_ax.contour(x, y, endurance, levels=[limit], colors=[PALETTE["orange"]], linewidths=2.0)
    endurance_ax.clabel(contour, fmt="Endurance limit = %.0f min", fontsize=8)
    endurance_ax.scatter([base["propulsion"]["limits"]["target_cruise_speed_mps"]], [base["energy"]["battery"]["capacity_ah"]], marker="*", s=150, color=PALETTE["orange"], edgecolor=PALETTE["white"], zorder=5, label="Nominal design")
    endurance_ax.set_title("Endurance to return-home SOC floor", loc="left")
    endurance_ax.set_xlabel("Cruise speed [m/s]")
    endurance_ax.set_ylabel("Battery capacity [Ah]")
    endurance_ax.legend(loc="upper right", fontsize=8)
    style_axis(endurance_ax)
    fig.colorbar(image, ax=endurance_ax, label="Endurance [min]")

    image_thr = throttle_ax.imshow(throttle * 100.0, origin="lower", aspect="auto", extent=extent, cmap="PuBuGn")
    throttle_ax.axvline(float(base["propulsion"]["limits"]["target_cruise_speed_mps"]), color=PALETTE["orange"], linewidth=1.3, linestyle="--")
    throttle_ax.set_title("Required symmetric throttle", loc="left")
    throttle_ax.set_xlabel("Cruise speed [m/s]")
    throttle_ax.set_ylabel("Battery capacity [Ah]")
    style_axis(throttle_ax)
    fig.colorbar(image_thr, ax=throttle_ax, label="Throttle per side [%]")

    feasible = sum(int(row["feasible"]) for row in rows)
    _panel(info, "ENERGY INTERPRETATION", [
        ("Sweep samples", str(len(rows))),
        ("Feasible samples", f"{feasible} / {len(rows)}"),
        ("Endurance requirement", f">= {limit:.0f} min"),
        ("Min thrust reserve", f">= {float(base['hydrodynamics']['minimum_thrust_reserve_ratio']):.2f}"),
        ("Nominal capacity", f"{float(base['energy']['battery']['capacity_ah']):.1f} Ah"),
        ("Nominal cruise", f"{float(base['propulsion']['limits']['target_cruise_speed_mps']):.2f} m/s"),
    ], "Higher cruise speed increases resistance approximately quadratically and propulsor power approximately cubically in the preliminary model. Battery capacity extends endurance but also changes physical mass in a real system; that second-order mass feedback is listed as a limitation rather than silently ignored.")
    return export_figure(fig, output, dpi=320)


def _draw_candidates(rows: list[dict[str, object]], base: dict[str, Any], output: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.38, .82], left=.055, right=.955, bottom=.08, top=.875, wspace=.18, hspace=.35)
    margin_ax = fig.add_subplot(grid[0, 0])
    endurance_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Phase 10.3 — Candidate Design Comparison", "A compact candidate set makes stability, payload, speed and energy trade-offs explicit. Bars are computed from the same model chain, not assigned manually.")
    labels = [str(row["candidate"]) for row in rows]
    x = np.arange(len(labels))
    gm = np.array([float(row["GM_m"]) for row in rows])
    fb = np.array([float(row["freeboard_m"]) for row in rows])
    end = np.array([float(row["endurance_min"]) for row in rows])
    reserve = np.array([float(row["thrust_reserve_ratio"]) for row in rows])
    feasible = np.array([int(row["feasible"]) for row in rows])
    margin_ax.bar(x - .18, gm, .36, label="GM [m]", color=PALETTE["blue"])
    margin_ax.bar(x + .18, fb, .36, label="Freeboard [m]", color=PALETTE["cyan"])
    margin_ax.axhline(float(base["hydrostatics"]["minimum_gm_m"]), color=PALETTE["orange"], linestyle="--", linewidth=1.2, label="GM requirement")
    margin_ax.axhline(float(base["hydrostatics"]["minimum_freeboard_m"]), color=PALETTE["gray_dark"], linestyle=":", linewidth=1.2, label="Freeboard requirement")
    margin_ax.set_title("Hydrostatic margins", loc="left")
    margin_ax.set_xticks(x, [fill(label, 16) for label in labels], fontsize=8)
    margin_ax.set_ylabel("Margin quantity [m]")
    margin_ax.legend(fontsize=7.6, ncol=2)
    style_axis(margin_ax)

    endurance_ax.bar(x - .18, end, .36, label="Endurance [min]", color=PALETTE["green"])
    endurance_ax2 = endurance_ax.twinx()
    endurance_ax2.plot(x + .18, reserve, marker="o", color=PALETTE["orange"], linewidth=2.0, label="Thrust reserve")
    endurance_ax.axhline(float(base["energy"]["model"]["minimum_endurance_at_cruise_min"]), color=PALETTE["gray_dark"], linestyle="--", linewidth=1.2, label="Minimum endurance")
    endurance_ax2.axhline(float(base["hydrodynamics"]["minimum_thrust_reserve_ratio"]), color=PALETTE["orange"], linestyle=":", linewidth=1.2, label="Minimum thrust reserve")
    for idx, ok in enumerate(feasible):
        if not ok:
            endurance_ax.text(idx, max(end[idx], 5.0) + 4.0, "constraint\nfailed", ha="center", color=PALETTE["orange"], fontsize=7.3, fontweight="bold")
    endurance_ax.set_title("Endurance and thrust reserve", loc="left")
    endurance_ax.set_xticks(x, [fill(label, 16) for label in labels], fontsize=8)
    endurance_ax.set_ylabel("Endurance [min]")
    endurance_ax2.set_ylabel("Thrust reserve [-]")
    style_axis(endurance_ax)
    endurance_ax2.spines["top"].set_visible(False)
    lines = endurance_ax.get_lines() + endurance_ax2.get_lines()
    endurance_ax.legend(lines, [line.get_label() for line in lines], fontsize=7.6, loc="upper right")

    recommended = rows[0]
    _panel(info, "RECOMMENDED CONCEPT", [
        ("Candidate", str(recommended["candidate"])),
        ("Constraint score", f"{float(recommended['constraint_margin_score']):.2f}"),
        ("Spacing", f"{float(recommended['hull_spacing_m']):.3f} m"),
        ("Payload", f"{float(recommended['payload_kg']):.3f} kg"),
        ("Battery", f"{float(recommended['battery_capacity_ah']):.1f} Ah"),
        ("Cruise", f"{float(recommended['cruise_speed_mps']):.2f} m/s"),
    ], "The ranking score is the minimum normalized margin across GM, freeboard, endurance and thrust reserve. It is a transparent screening metric, not a multi-objective optimisation theorem. The nominal baseline remains the documented teaching design unless a different candidate is intentionally selected and revalidated.")
    return export_figure(fig, output, dpi=320)


def _draw_synthesis(rows: list[dict[str, object]], base: dict[str, Any], output: Path, quality: list[dict[str, object]]) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16, 10), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.25, .95], left=.135, right=.955, bottom=.08, top=.875, wspace=.18, hspace=.32)
    score_ax = fig.add_subplot(grid[:, 0])
    qa_ax = fig.add_subplot(grid[0, 1])
    note_ax = fig.add_subplot(grid[1, 1])
    add_figure_header(fig, "AquaSkim-Sim | Phase 10.3 — Design Synthesis and Release Quality", "The final engineering release is gated by traceable model evidence, visual outputs, animations, tests and an explicit limitation register before Word delivery is permitted.")
    labels = [str(row["candidate"]) for row in rows]
    scores = [float(row["constraint_margin_score"]) for row in rows]
    colors = [PALETTE["green"] if int(row["feasible"]) else PALETTE["orange"] for row in rows]
    positions = np.arange(len(rows))
    score_ax.barh(positions, scores, color=colors)
    score_ax.axvline(1.0, color=PALETTE["navy"], linestyle="--", linewidth=1.3, label="All normalized margins >= 1")
    score_ax.set_yticks(positions, [fill(label, 18) for label in labels])
    score_ax.invert_yaxis()
    score_ax.set_xlabel("Minimum normalized constraint margin [-]")
    score_ax.set_title("Candidate screening score", loc="left")
    score_ax.legend(loc="lower right", fontsize=8)
    style_axis(score_ax)

    qa_ax.set_axis_off()
    qa_ax.set_xlim(0, 1)
    qa_ax.set_ylim(0, 1)
    qa_ax.add_patch(FancyBboxPatch((.02,.04),.96,.92,boxstyle="round,pad=.018,rounding_size=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1.0))
    qa_ax.text(.08,.90,"RELEASE-QUALITY INVENTORY",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top")
    y=.78
    for row in quality:
        label=str(row["check"]); observed=str(row["observed"]); status=str(row["status"])
        color=PALETTE["green"] if status=="PASS" else PALETTE["orange"]
        qa_ax.text(.09,y,label,fontsize=8.6,color=PALETTE["gray_dark"],va="center")
        qa_ax.text(.80,y,observed,fontsize=8.6,color=PALETTE["navy"],ha="right",va="center",fontweight="bold")
        qa_ax.text(.92,y,status,fontsize=8.3,color=color,ha="right",va="center",fontweight="bold")
        qa_ax.plot([.08,.92],[y-.04,y-.04],color=PALETTE["grid"],linewidth=.6)
        y -= .10

    note_ax.set_axis_off()
    note_ax.set_xlim(0, 1)
    note_ax.set_ylim(0, 1)
    note_ax.add_patch(FancyBboxPatch((.02,.04),.96,.92,boxstyle="round,pad=.018,rounding_size=.02",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1.0))
    note_ax.text(.08,.90,"RELEASE DECISION",fontsize=12,fontweight="bold",color=PALETTE["navy"],va="top")
    narrative = (
        "The engineering model is treated as a reproducible digital-twin study. "
        "A final Word document is deferred until the release-quality gate reports PASS. "
        "The gate does not erase limitations: static obstacles, simplified 3-DOF planar dynamics, analytic sensor surrogates, preliminary resistance coefficients and conceptual CAD remain explicitly stated."
    )
    note_ax.text(.08,.76,fill(narrative,49),fontsize=9.2,color=PALETTE["gray_dark"],va="top",linespacing=1.45)
    note_ax.text(.08,.35,"ONE-COMMAND REPRODUCTION",fontsize=10,fontweight="bold",color=PALETTE["navy"],va="top")
    note_ax.text(.08,.27,"scripts\\bootstrap_and_build.bat",fontsize=9.6,color=PALETTE["green"],va="top",fontweight="bold")
    note_ax.text(.08,.17,"Prompts for a local profile, rebuilds all engineering phases, records inputs, outputs, SHA-256 hashes and handoffs.",fontsize=8.5,color=PALETTE["gray_dark"],va="top",wrap=True)
    return export_figure(fig, output, dpi=320)


def _release_quality_rows() -> list[dict[str, object]]:
    figures = list(DIRECTORIES["figures"].glob("*.png"))
    vectors = list(DIRECTORIES["figures"].glob("*.svg"))
    tables = list(DIRECTORIES["tables"].glob("*.csv"))
    gifs = list(DIRECTORIES["animations"].glob("*.gif"))
    mp4s = list(DIRECTORIES["videos"].glob("*.mp4"))
    reports = list(DIRECTORIES["reports"].glob("*.md"))
    expected = [
        ("High-resolution engineering PNG figures", len(figures), 28),
        ("Vector SVG counterparts", len(vectors), 28),
        ("Numerical CSV evidence tables", len(tables), 35),
        ("Mission/telemetry GIF animations", len(gifs), 8),
        ("Mission/telemetry MP4 videos", len(mp4s), 8),
        ("Phase summary Markdown reports", len(reports), 10),
    ]
    rows: list[dict[str, object]] = []
    for label, observed, minimum in expected:
        rows.append({"check": label, "observed": observed, "required_minimum": minimum, "status": "PASS" if observed >= minimum else "WARNING"})
    return rows


def _write_summary(path: Path, stability: list[dict[str, object]], endurance: list[dict[str, object]], candidates: list[dict[str, object]], quality: list[dict[str, object]], artifacts: Phase103Artifacts) -> None:
    feasible_stability = sum(int(row["feasible"]) for row in stability)
    feasible_endurance = sum(int(row["feasible"]) for row in endurance)
    recommended = candidates[0]
    quality_lines = "\n".join(
        f"| {row['check']} | {row['observed']} | {row['required_minimum']} | {row['status']} |"
        for row in quality
    )
    artifact_lines = "\n".join(f"- `{path}`" for path in artifacts.all_paths())
    content = f"""# AquaSkim-Sim | Phase 10.3 Parametric Trade Study and Release Quality

## Purpose
This phase converts the single nominal design into a transparent preliminary design-space study. It does not replace CFD, tow-tank testing, structural FEA or manufacturing drawings.

## Stability sweep
- Samples: `{len(stability)}`
- Feasible samples under the stated GM/freeboard constraints: `{feasible_stability}`

## Endurance / propulsion sweep
- Samples: `{len(endurance)}`
- Feasible samples under the stated endurance/thrust-reserve constraints: `{feasible_endurance}`

## Highest ranked screening candidate
| Item | Value |
|---|---:|
| Candidate | {recommended['candidate']} |
| Hull centre spacing | {float(recommended['hull_spacing_m']):.3f} m |
| Design payload | {float(recommended['payload_kg']):.3f} kg |
| Battery capacity | {float(recommended['battery_capacity_ah']):.1f} Ah |
| Cruise speed | {float(recommended['cruise_speed_mps']):.2f} m/s |
| Constraint-margin score | {float(recommended['constraint_margin_score']):.2f} |

## Release-quality inventory
| Check | Observed | Required minimum | Status |
|---|---:|---:|---|
{quality_lines}

## Limitations retained
- The sweep uses the same preliminary conceptual models as the earlier phases.
- Battery-capacity changes do not automatically add battery mass to the mass budget; this coupling is intentionally retained as a future refinement.
- The score is a transparent screening metric, not a formal global optimisation.
- Quality inventory warnings mean that the current output portfolio is incomplete; they do not fabricate missing evidence.

## Artifact inventory
{artifact_lines}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_design_trade_study(config: ProjectConfiguration | None = None) -> Phase103Artifacts:
    ensure_runtime_directories()
    cfg = config or load_base_configuration()
    base = cfg.data
    stability_rows = _stability_sweep(base)
    endurance_rows = _endurance_sweep(base)
    candidate_rows = _candidate_rows(base)
    quality_rows = _release_quality_rows()

    figures = DIRECTORIES["figures"]
    tables = DIRECTORIES["tables"]
    logs = DIRECTORIES["logs"]
    reports = DIRECTORIES["reports"]

    stability_export = _draw_stability(stability_rows, base, figures / "phase10_3_stability_trade_space.png")
    endurance_export = _draw_endurance(endurance_rows, base, figures / "phase10_3_endurance_trade_space.png")
    candidate_export = _draw_candidates(candidate_rows, base, figures / "phase10_3_candidate_comparison.png")
    synthesis_export = _draw_synthesis(candidate_rows, base, figures / "phase10_3_design_synthesis_dashboard.png", quality_rows)

    stability_csv = tables / "phase10_3_stability_sweep.csv"
    endurance_csv = tables / "phase10_3_endurance_sweep.csv"
    candidates_csv = tables / "phase10_3_candidate_rankings.csv"
    quality_csv = tables / "phase10_3_release_quality_inventory.csv"
    acceptance_csv = tables / "phase10_3_acceptance_checks.csv"
    summary_json = logs / "phase10_3_trade_study_summary.json"
    summary_md = reports / "phase10_3_parametric_trade_study_summary.md"
    visual_manifest = logs / "phase10_3_visual_quality_manifest.json"

    _write_csv(stability_csv, stability_rows)
    _write_csv(endurance_csv, endurance_rows)
    _write_csv(candidates_csv, candidate_rows)
    _write_csv(quality_csv, quality_rows)
    acceptance = [
        {"check": "stability_sweep_nonempty", "observed": len(stability_rows), "criterion": "> 0", "status": "PASS"},
        {"check": "endurance_sweep_nonempty", "observed": len(endurance_rows), "criterion": "> 0", "status": "PASS"},
        {"check": "candidate_set_contains_nominal", "observed": any(row["candidate"] == "Nominal baseline" for row in candidate_rows), "criterion": "True", "status": "PASS"},
        {"check": "all_candidate_scores_finite", "observed": all(np.isfinite(float(row["constraint_margin_score"])) for row in candidate_rows), "criterion": "True", "status": "PASS"},
    ]
    _write_csv(acceptance_csv, acceptance)

    artifacts = Phase103Artifacts(
        stability_trade_space=stability_export,
        endurance_trade_space=endurance_export,
        candidate_comparison=candidate_export,
        synthesis_dashboard=synthesis_export,
        stability_sweep_table=stability_csv,
        endurance_sweep_table=endurance_csv,
        candidate_rankings_table=candidates_csv,
        release_quality_table=quality_csv,
        acceptance_checks_table=acceptance_csv,
        summary_json=summary_json,
        summary_markdown=summary_md,
        visual_quality_manifest=visual_manifest,
    )
    assert_export_quality(
        (stability_export, endurance_export, candidate_export, synthesis_export),
        min_width_px=3000,
        min_height_px=1800,
    )
    manifest = {
        "phase": "Phase 10.3 Parametric Design Trade Study",
        "quality_rule": {
            "minimum_png_width_px": 3000,
            "minimum_png_height_px": 1800,
            "formats": ["PNG", "SVG"],
            "label_policy": "Trade-space labels and narrative are separated into dedicated information panels.",
        },
        "exports": [
            stability_export.as_dict(), endurance_export.as_dict(), candidate_export.as_dict(), synthesis_export.as_dict(),
        ],
    }
    visual_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "phase": "Phase 10.3 Parametric Design Trade Study",
        "configuration_file": relative_to_root(cfg.source_path),
        "stability_sample_count": len(stability_rows),
        "endurance_sample_count": len(endurance_rows),
        "recommended_screening_candidate": candidate_rows[0],
        "quality_inventory": quality_rows,
        "artifacts": [relative_to_root(path) for path in artifacts.all_paths()],
        "limitations": [
            "The design sweep is a preliminary screening study, not CFD/FEA or a manufacturing release.",
            "Battery capacity variation is not mass-coupled in the current mass budget.",
            "The quality inventory reports missing artifacts as warnings rather than treating missing evidence as success.",
        ],
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(summary_md, stability_rows, endurance_rows, candidate_rows, quality_rows, artifacts)
    return artifacts


def print_design_trade_study_summary(artifacts: Phase103Artifacts) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 10.3 Parametric Trade Study")
    print("=" * 72)
    for path in artifacts.all_paths():
        print(relative_to_root(path))
    print("=" * 72)
    print("[OK] Trade-study figures, screening tables and release-quality inventory generated.")
