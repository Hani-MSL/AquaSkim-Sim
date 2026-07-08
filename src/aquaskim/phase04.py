"""Phase 04 artifact generation: hydrodynamic resistance and twin-thruster sizing.

All numerical results are generated from the same central parameter file used
by Phases 02 and 03.  The model is deliberately explicit: equations, empirical
coefficients and operating assumptions are recorded in the generated report.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings, ResistanceState
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.propulsion import ThrusterOperatingPoint, ThrusterSettings, TwinThrusterModel
from aquaskim.visual_quality import PALETTE, FigureExport, add_figure_header, apply_engineering_style, assert_export_quality, export_figure, style_axis


@dataclass(frozen=True)
class Phase04Artifacts:
    resistance_dashboard: Path
    resistance_dashboard_svg: Path
    propulsion_envelope: Path
    propulsion_envelope_svg: Path
    current_penalty: Path
    current_penalty_svg: Path
    operating_envelope: Path
    operating_envelope_svg: Path
    resistance_curve_table: Path
    propulsion_curve_table: Path
    operating_points_table: Path
    current_penalty_table: Path
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


def _panel(ax: plt.Axes) -> None:
    ax.set_axis_off()
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.add_patch(FancyBboxPatch((0.025, 0.03), 0.95, 0.94, boxstyle="round,pad=0.018,rounding_size=0.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))


def _panel_heading(ax: plt.Axes, heading: str, subtitle: str) -> None:
    ax.text(0.08, 0.92, heading, fontsize=12.7, fontweight="bold", color=PALETTE["navy"], va="top")
    ax.text(0.08, 0.87, fill(subtitle, width=52), fontsize=8.35, color=PALETTE["gray"], va="top", linespacing=1.38)


def _metric_grid(ax: plt.Axes, rows: list[tuple[str, str, str]], *, top: float, height: float, headers: tuple[str, str, str] = ("Metric", "Value", "Unit / note")) -> None:
    x0, width = 0.08, 0.84
    col_fraction = (0.44, 0.25, 0.31)
    row_h = height / (len(rows) + 1)
    current_y = top
    for index, values in enumerate([headers, *rows]):
        y = current_y - row_h
        cursor = x0
        for col, (fraction, value) in enumerate(zip(col_fraction, values)):
            face = PALETTE["navy"] if index == 0 else (PALETTE["gray_light"] if col == 0 else PALETTE["white"])
            ax.add_patch(Rectangle((cursor, y), width * fraction, row_h, facecolor=face, edgecolor=PALETTE["grid"], linewidth=0.65))
            ax.text(cursor + (0.012 if col == 0 else width * fraction / 2), y + row_h / 2, value, ha="left" if col == 0 else "center", va="center", fontsize=7.6 if index else 7.35, fontweight="bold" if index == 0 else "normal", color=PALETTE["white"] if index == 0 else PALETTE["gray_dark"])
            cursor += width * fraction
        current_y = y


def _bullet_block(ax: plt.Axes, heading: str, bullets: list[str], *, y: float, width: int = 50) -> None:
    ax.text(0.08, y, heading, fontsize=10.1, fontweight="bold", color=PALETTE["navy"], va="top")
    current = y - 0.045
    for bullet in bullets:
        wrapped = fill(bullet, width=width)
        ax.text(0.095, current, "• " + wrapped.replace("\n", "\n  "), fontsize=8.2, color=PALETTE["gray_dark"], va="top", linespacing=1.38)
        current -= 0.030 * (wrapped.count("\n") + 1) + 0.018


def _speed_grid(settings: HydrodynamicSettings) -> np.ndarray:
    return np.linspace(0.0, settings.analysis_speed_max_mps, settings.analysis_speed_points)


def _find_speed_for_resistance(model: CatamaranResistanceModel, available_thrust_n: float, upper_mps: float = 2.5) -> float:
    """Bisection solve R(V)=available thrust for a monotonic conceptual curve."""
    if available_thrust_n <= 0.0:
        return 0.0
    low, high = 0.0, upper_mps
    while model.state_at_speed(high).total_resistance_n < available_thrust_n:
        high *= 1.5
        if high > 10.0:
            raise RuntimeError("Could not bracket theoretical top speed.")
    for _ in range(80):
        middle = 0.5 * (low + high)
        if model.state_at_speed(middle).total_resistance_n < available_thrust_n:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def _operating_row(name: str, ground_speed_mps: float, head_current_mps: float, model: CatamaranResistanceModel, thrusters: TwinThrusterModel, hotel_load_w: float) -> dict[str, object]:
    water_speed = ground_speed_mps + head_current_mps
    state = model.state_at_speed(water_speed)
    point = thrusters.symmetric_operating_point(state.total_resistance_n)
    return {
        "operating_case": name,
        "ground_speed_mps": ground_speed_mps,
        "head_current_mps": head_current_mps,
        "speed_through_water_mps": water_speed,
        "resistance_n": state.total_resistance_n,
        "rpm_per_side": point.rpm_per_side,
        "throttle_fraction": point.throttle_fraction,
        "thruster_power_w": point.total_thruster_power_w,
        "hotel_load_w": hotel_load_w,
        "total_electrical_power_w": point.total_thruster_power_w + hotel_load_w,
        "thrust_reserve_ratio": thrusters.settings.total_max_thrust_n / max(state.total_resistance_n, 1e-12),
        "feasible": point.feasible,
    }


def _draw_resistance_dashboard(states: list[ResistanceState], model: CatamaranResistanceModel, target_row: dict[str, object], output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 10.0), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.43, 0.87], left=0.055, right=0.955, bottom=0.08, top=0.875, wspace=0.16, hspace=0.32)
    resistance_ax = fig.add_subplot(grid[0, 0])
    coefficient_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Calm-Water Resistance Model", "Phase 04 • Full design payload governs sizing • ITTC-1957 friction plus explicit residual, appendage and collector terms")

    speed = [s.speed_through_water_mps for s in states]
    resistance_ax.plot(speed, [s.friction_resistance_n for s in states], color=PALETTE["blue"], linewidth=2.0, label="Friction + form")
    resistance_ax.plot(speed, [s.residual_resistance_n for s in states], color=PALETTE["green"], linewidth=2.0, label="Residual")
    resistance_ax.plot(speed, [s.appendage_resistance_n for s in states], color=PALETTE["orange"], linewidth=2.0, label="Appendage")
    resistance_ax.plot(speed, [s.collector_resistance_n for s in states], color="#9A6FB0", linewidth=2.0, label="Collector")
    resistance_ax.plot(speed, [s.total_resistance_n for s in states], color=PALETTE["navy"], linewidth=2.8, label="Total resistance")
    resistance_ax.axvline(float(target_row["speed_through_water_mps"]), color=PALETTE["gray"], linewidth=1.1, linestyle="--")
    resistance_ax.scatter([target_row["speed_through_water_mps"]], [target_row["resistance_n"]], color=PALETTE["orange"], s=45, zorder=6, label="Target cruise")
    resistance_ax.set_title("Resistance breakdown", loc="left", fontsize=12.5)
    resistance_ax.set_xlabel("Speed through water [m/s]")
    resistance_ax.set_ylabel("Resistance [N]")
    resistance_ax.legend(loc="upper left", fontsize=7.8, ncol=2)
    style_axis(resistance_ax)

    coefficient_ax.plot(speed[1:], [s.friction_coefficient for s in states[1:]], color=PALETTE["blue"], linewidth=2.1, label="ITTC-1957 Cf")
    coefficient_ax2 = coefficient_ax.twinx()
    coefficient_ax2.plot(speed[1:], [s.reynolds_number / 1e5 for s in states[1:]], color=PALETTE["green"], linewidth=1.8, label="Re / 10⁵")
    coefficient_ax.set_title("Friction correlation validity indicators", loc="left", fontsize=12.5)
    coefficient_ax.set_xlabel("Speed through water [m/s]")
    coefficient_ax.set_ylabel("Cf [-]")
    coefficient_ax2.set_ylabel("Reynolds number / 10⁵")
    style_axis(coefficient_ax)
    coefficient_ax2.spines["top"].set_visible(False)
    lines = coefficient_ax.get_lines() + coefficient_ax2.get_lines()
    coefficient_ax.legend(lines, [line.get_label() for line in lines], loc="upper right", fontsize=8.0)

    _panel(info)
    _panel_heading(info, "MODEL BASIS", "The resistance model is a transparent preliminary design model, not CFD. Coefficients remain explicit in the central YAML configuration.")
    _metric_grid(info, [
        ("Full-load mass", f"{model.hydro_case.total_mass_kg:.3f}", "kg"),
        ("Draft from Phase 03", f"{model.draft_m:.4f}", "m"),
        ("Wetted area", f"{model.wetted_surface_area_m2:.4f}", "m²"),
        ("Collector frontal area", f"{model.collector_frontal_area_m2:.4f}", "m²"),
        ("Cruise water speed", f"{target_row['speed_through_water_mps']:.3f}", "m/s"),
        ("Cruise resistance", f"{target_row['resistance_n']:.3f}", "N"),
    ], top=0.79, height=0.27)
    _bullet_block(info, "EQUATIONS", [
        "Friction: Rf = 0.5·ρ·S·Cf·V²·(1+k), using the ITTC-1957 Cf correlation.",
        "Residual, appendage and collector resistance are retained as independent, explicit quadratic terms.",
    ], y=0.43, width=49)
    _bullet_block(info, "DESIGN READING", [
        "Full payload governs sizing. The collector drag remains explicit for later energy modelling, and all coefficients can be replaced by CFD or experimental data without changing the architecture.",
    ], y=0.16, width=49)
    return export_figure(fig, output_path, dpi=320)


def _draw_propulsion_envelope(thrusters: TwinThrusterModel, resistance_states: list[ResistanceState], target_row: dict[str, object], max_theoretical_speed: float, output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 10.0), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.43, 0.87], left=0.055, right=0.955, bottom=0.08, top=0.875, wspace=0.16, hspace=0.32)
    thrust_ax = fig.add_subplot(grid[0, 0])
    power_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Twin-Thruster Propulsion Envelope", "Phase 04 • Symmetric straight-line operation • Static thrust law T = kT·RPM² • Electrical envelope P = Paux + kP·RPM³")

    rpms = np.linspace(0.0, thrusters.settings.max_rpm, 121)
    thrust_ax.plot(rpms, [thrusters.total_thrust_at_rpm(rpm) for rpm in rpms], color=PALETTE["blue"], linewidth=2.5, label="Total available thrust")
    target_rpm = float(target_row["rpm_per_side"])
    thrust_ax.scatter([target_rpm], [target_row["resistance_n"]], color=PALETTE["orange"], s=48, zorder=6, label="Target cruise demand")
    thrust_ax.axvline(thrusters.settings.max_rpm * 0.85, color=PALETTE["orange"], linestyle="--", linewidth=1.2, label="Recommended RPM ceiling")
    thrust_ax.set_title("Total thrust vs symmetric RPM", loc="left", fontsize=12.5)
    thrust_ax.set_xlabel("RPM per thruster")
    thrust_ax.set_ylabel("Total thrust [N]")
    thrust_ax.legend(loc="upper left", fontsize=8.0)
    style_axis(thrust_ax)

    power_ax.plot(rpms, [thrusters.total_electrical_power_at_rpm(rpm) for rpm in rpms], color=PALETTE["green"], linewidth=2.5, label="Thruster electrical power")
    power_ax.scatter([target_rpm], [target_row["thruster_power_w"]], color=PALETTE["orange"], s=48, zorder=6, label="Target cruise demand")
    power_ax.set_title("Electrical power vs symmetric RPM", loc="left", fontsize=12.5)
    power_ax.set_xlabel("RPM per thruster")
    power_ax.set_ylabel("Total thruster electrical power [W]")
    power_ax.legend(loc="upper left", fontsize=8.0)
    style_axis(power_ax)

    _panel(info)
    _panel_heading(info, "SIZING RESULT", "The twin-thruster model converts required total resistance into symmetric RPM, throttle and electrical power for straight-line motion.")
    _metric_grid(info, [
        ("Thruster count", str(thrusters.settings.count), "independent units"),
        ("Max thrust", f"{thrusters.settings.total_max_thrust_n:.2f}", "N total"),
        ("Max RPM", f"{thrusters.settings.max_rpm:.0f}", "per side"),
        ("Target RPM", f"{target_row['rpm_per_side']:.0f}", "per side"),
        ("Target throttle", f"{100.0 * target_row['throttle_fraction']:.1f}", "%"),
        ("Theoretical top speed", f"{max_theoretical_speed:.3f}", "m/s in calm water"),
    ], top=0.79, height=0.27)
    _bullet_block(info, "INTERPRETATION", [
        "A reserve is retained for current, turns, obstacle manoeuvres, uncertainty and degradation.",
        "This view is symmetric. Differential thrust, yaw dynamics and manoeuvring loss are intentionally deferred to the 3-DOF phase.",
    ], y=0.42, width=49)
    _bullet_block(info, "QUALITY NOTE", [
        "The theoretical top speed is only the resistance-intersection result; operational control keeps the lower 0.60 m/s limit. The configured max-thrust value and kT coefficient are cross-checked automatically.",
    ], y=0.15, width=49)
    return export_figure(fig, output_path, dpi=320)


def _draw_current_penalty(current_rows: list[dict[str, object]], output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 9.2), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.43, 0.87], left=0.055, right=0.955, bottom=0.085, top=0.875, wspace=0.16, hspace=0.33)
    thrust_ax = fig.add_subplot(grid[0, 0])
    power_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Head-Current Penalty at Cruise Speed", "Phase 04 • Ground speed remains 0.45 m/s • Through-water speed rises with opposing current")

    current = [float(row["head_current_mps"]) for row in current_rows]
    thrust_ax.plot(current, [float(row["resistance_n"]) for row in current_rows], color=PALETTE["blue"], linewidth=2.5, label="Required total thrust")
    thrust_ax.plot(current, [float(row["thrust_reserve_ratio"]) for row in current_rows], color=PALETTE["orange"], linewidth=2.0, linestyle="--", label="Reserve ratio")
    thrust_ax.set_title("Resistance and available-thrust reserve", loc="left", fontsize=12.5)
    thrust_ax.set_xlabel("Opposing current [m/s]")
    thrust_ax.set_ylabel("N / ratio")
    thrust_ax.legend(loc="upper left", fontsize=8.2)
    style_axis(thrust_ax)

    power_ax.plot(current, [float(row["total_electrical_power_w"]) for row in current_rows], color=PALETTE["green"], linewidth=2.5, label="Total electrical power")
    power_ax.plot(current, [100.0 * float(row["throttle_fraction"]) for row in current_rows], color="#9A6FB0", linewidth=2.0, linestyle="--", label="Throttle [%]")
    power_ax.set_title("Electrical penalty", loc="left", fontsize=12.5)
    power_ax.set_xlabel("Opposing current [m/s]")
    power_ax.set_ylabel("W / %")
    power_ax.legend(loc="upper left", fontsize=8.2)
    style_axis(power_ax)

    row_02 = min(current_rows, key=lambda row: abs(float(row["head_current_mps"]) - 0.20))
    _panel(info)
    _panel_heading(info, "DISTURBANCE SIZING CHECK", "This sensitivity case isolates the penalty of an opposing uniform current while holding desired ground speed constant.")
    _metric_grid(info, [
        ("Ground speed", f"{float(row_02['ground_speed_mps']):.2f}", "m/s"),
        ("Head current", f"{float(row_02['head_current_mps']):.2f}", "m/s"),
        ("Water-relative speed", f"{float(row_02['speed_through_water_mps']):.2f}", "m/s"),
        ("Required thrust", f"{float(row_02['resistance_n']):.2f}", "N"),
        ("Throttle", f"{100 * float(row_02['throttle_fraction']):.1f}", "%"),
        ("Reserve ratio", f"{float(row_02['thrust_reserve_ratio']):.2f}", "available / required"),
    ], top=0.79, height=0.27)
    _bullet_block(info, "ENGINEERING READING", [
        "Current is represented as a change in through-water speed for this steady longitudinal sizing analysis.",
        "The later 3-DOF dynamics phase will represent current as a vector disturbance in earth-fixed and body-fixed coordinates.",
        "A control policy may reduce commanded ground speed if the reserve or energy budget drops below its mission threshold.",
    ], y=0.42, width=49)
    return export_figure(fig, output_path, dpi=320)


def _draw_operating_envelope(operating_rows: list[dict[str, object]], model: CatamaranResistanceModel, thrusters: TwinThrusterModel, output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 9.2), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.43, 0.87], left=0.055, right=0.955, bottom=0.085, top=0.875, wspace=0.16, hspace=0.33)
    throttle_ax = fig.add_subplot(grid[0, 0])
    acceleration_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Operating Envelope and Surge Reserve", "Phase 04 • Full-payload steady sizing • Initial acceleration uses a transparent added-mass approximation")

    speeds = np.linspace(0.0, 0.8, 81)
    states = [model.state_at_speed(float(v)) for v in speeds]
    points = [thrusters.symmetric_operating_point(state.total_resistance_n) for state in states]
    throttle_ax.plot(speeds, [100.0 * point.throttle_fraction for point in points], color=PALETTE["blue"], linewidth=2.5, label="Required symmetric throttle")
    throttle_ax.axhline(85.0, color=PALETTE["orange"], linewidth=1.25, linestyle="--", label="Recommended ceiling")
    for row in operating_rows:
        throttle_ax.scatter([row["ground_speed_mps"]], [100.0 * row["throttle_fraction"]], s=35, zorder=6, label=str(row["operating_case"]).replace("_", " "))
    throttle_ax.set_title("Cruise command requirement", loc="left", fontsize=12.5)
    throttle_ax.set_xlabel("Ground speed in calm water [m/s]")
    throttle_ax.set_ylabel("Symmetric throttle [%]")
    throttle_ax.legend(loc="upper left", fontsize=7.0, ncol=2)
    style_axis(throttle_ax)

    craft_mass = model.hydro_case.total_mass_kg
    effective_mass = craft_mass + model.surge_added_mass_kg(craft_mass)
    acceleration = [(thrusters.settings.total_max_thrust_n - state.total_resistance_n) / effective_mass for state in states]
    acceleration_ax.plot(speeds, acceleration, color=PALETTE["green"], linewidth=2.5, label="Max-thrust surge acceleration")
    acceleration_ax.axhline(0.0, color=PALETTE["gray_dark"], linewidth=0.9)
    acceleration_ax.set_title("Maximum available surge reserve", loc="left", fontsize=12.5)
    acceleration_ax.set_xlabel("Through-water speed [m/s]")
    acceleration_ax.set_ylabel("Acceleration [m/s²]")
    acceleration_ax.legend(loc="upper right", fontsize=8.0)
    style_axis(acceleration_ax)

    target = next(row for row in operating_rows if row["operating_case"] == "cruise_calm_full_payload")
    _panel(info)
    _panel_heading(info, "OPERATING DECISION", "The controller will start from the lower operational speed limit, not the theoretical top-speed intersection.")
    _metric_grid(info, [
        ("Design cruise", f"{float(target['ground_speed_mps']):.2f}", "m/s"),
        ("Design max speed", "0.60", "m/s configured"),
        ("Target throttle", f"{100 * float(target['throttle_fraction']):.1f}", "%"),
        ("Reserve ratio", f"{float(target['thrust_reserve_ratio']):.2f}", "available / required"),
        ("Craft mass", f"{craft_mass:.2f}", "kg full payload"),
        ("Effective surge mass", f"{effective_mass:.2f}", "kg incl. added mass"),
    ], top=0.79, height=0.27)
    _bullet_block(info, "MODEL LIMIT", [
        "The acceleration curve assumes maximum symmetric thrust in a straight line; it is not a commanded acceleration profile.",
        "Later control logic will impose smooth limits on throttle, yaw rate, energy draw and safe proximity to obstacles.",
        "The added-mass fraction is a tunable conceptual parameter that will be revisited when the 3-DOF model is introduced.",
    ], y=0.42, width=49)
    return export_figure(fig, output_path, dpi=320)


def _write_summary(path: Path, settings: HydrodynamicSettings, target: dict[str, object], max_speed: float, artifacts: Phase04Artifacts) -> None:
    content = f"""# AquaSkim-Sim | Phase 04 Hydrodynamic Resistance and Propulsion Summary

## Governing condition
The full design-payload hydrostatic case is used for propulsion sizing because it has the highest draft. The target cruise speed is `{float(target['ground_speed_mps']):.3f} m/s` in calm water.

## Core result
| Metric | Value |
|---|---:|
| Water-relative cruise speed | {float(target['speed_through_water_mps']):.3f} m/s |
| Total resistance at cruise | {float(target['resistance_n']):.3f} N |
| Required RPM per thruster | {float(target['rpm_per_side']):.0f} rpm |
| Symmetric throttle | {100 * float(target['throttle_fraction']):.1f} % |
| Thruster electrical power | {float(target['thruster_power_w']):.2f} W |
| Total electrical power incl. hotel load | {float(target['total_electrical_power_w']):.2f} W |
| Available / required thrust reserve | {float(target['thrust_reserve_ratio']):.2f} |
| Theoretical calm-water top speed | {max_speed:.3f} m/s |

## Equations and assumptions
1. `Rf = 0.5 · rho · S · Cf · V² · (1+k)` with ITTC-1957 friction coefficient.
2. Residual, appendage and collector contributions are independent quadratic drag terms.
3. `T_side = kT · RPM²`; the symmetric twin-thruster operating point solves `2·T_side = R_total`.
4. Electrical power uses a cubic preliminary envelope anchored to configured maximum RPM and maximum electrical power.
5. This is a transparent preliminary sizing model. CFD, propeller open-water curves, wake interaction and dynamic manoeuvring are deferred.

## Configuration values retained explicitly
- residual coefficient: `{settings.residual_resistance_coefficient:.4f}`
- form factor: `{settings.form_factor:.3f}`
- collector drag coefficient: `{settings.collector_drag_coefficient:.3f}`
- added-mass fraction in surge: `{settings.added_mass_fraction_surge:.3f}`

## Artifact inventory
{chr(10).join(f"- `{p}`" for p in artifacts.as_dict().values())}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_phase04(config: ProjectConfiguration | None = None) -> Phase04Artifacts:
    ensure_runtime_directories()
    project_config = config or load_base_configuration()
    geometry = CatamaranGeometry.from_config(project_config.data)
    hydro_settings = HydrostaticSettings.from_config(project_config.data)
    hydro = CatamaranHydrostatics(geometry, hydro_settings)
    load_cases = build_load_cases(project_config.data)
    hydro_cases = {name: hydro.case_from_mass_properties(name, props) for name, (_, props) in load_cases.items()}
    governing_case = hydro_cases["full_design_payload"]
    settings = HydrodynamicSettings.from_config(project_config.data)
    resistance_model = CatamaranResistanceModel(geometry, settings, governing_case)
    thruster_settings = ThrusterSettings.from_config(project_config.data)
    thrusters = TwinThrusterModel(thruster_settings)
    hotel_load_w = float(project_config.data["energy"]["hotel_load_w"])
    cruise_speed = float(project_config.data["propulsion"]["limits"]["target_cruise_speed_mps"])
    max_design_speed = float(project_config.data["propulsion"]["limits"]["max_speed_mps"])

    states = [resistance_model.state_at_speed(float(speed)) for speed in _speed_grid(settings)]
    resistance_rows = [state.as_row() for state in states]
    rpm_grid = np.linspace(0.0, thruster_settings.max_rpm, 121)
    propulsion_rows = [
        {
            "rpm_per_side": float(rpm),
            "thrust_per_side_n": thrusters.thrust_per_side_at_rpm(float(rpm)),
            "total_thrust_n": thrusters.total_thrust_at_rpm(float(rpm)),
            "power_per_side_w": thrusters.electrical_power_per_side_at_rpm(float(rpm)),
            "total_thruster_power_w": thrusters.total_electrical_power_at_rpm(float(rpm)),
            "throttle_fraction": float(rpm / thruster_settings.max_rpm),
        }
        for rpm in rpm_grid
    ]

    operating_rows = [
        _operating_row("cruise_calm_full_payload", cruise_speed, 0.0, resistance_model, thrusters, hotel_load_w),
        _operating_row("design_max_speed_calm", max_design_speed, 0.0, resistance_model, thrusters, hotel_load_w),
        _operating_row("cruise_head_current_0p10", cruise_speed, 0.10, resistance_model, thrusters, hotel_load_w),
        _operating_row("cruise_head_current_0p20", cruise_speed, 0.20, resistance_model, thrusters, hotel_load_w),
        _operating_row("cruise_head_current_0p30", cruise_speed, 0.30, resistance_model, thrusters, hotel_load_w),
    ]
    current_grid = np.linspace(0.0, settings.head_current_max_mps, settings.head_current_points)
    current_rows = [
        _operating_row("cruise_current_sensitivity", cruise_speed, float(current), resistance_model, thrusters, hotel_load_w)
        for current in current_grid
    ]
    target_row = operating_rows[0]
    max_theoretical_speed = _find_speed_for_resistance(resistance_model, thruster_settings.total_max_thrust_n)
    derived_max_thrust_delta = abs(thruster_settings.derived_max_thrust_per_side_n - thruster_settings.max_thrust_per_side_n)
    checks = [
        {"check": "Full-payload target cruise is feasible", "value": bool(target_row["feasible"]), "criterion": "required thrust <= available thrust", "status": "PASS" if bool(target_row["feasible"]) else "FAIL"},
        {"check": "Target cruise thrust reserve", "value": float(target_row["thrust_reserve_ratio"]), "criterion": f">= {settings.minimum_thrust_reserve_ratio:.2f}", "status": "PASS" if float(target_row["thrust_reserve_ratio"]) >= settings.minimum_thrust_reserve_ratio else "FAIL"},
        {"check": "Target cruise RPM fraction", "value": float(target_row["throttle_fraction"]), "criterion": f"<= {settings.max_recommended_rpm_fraction:.2f}", "status": "PASS" if float(target_row["throttle_fraction"]) <= settings.max_recommended_rpm_fraction else "FAIL"},
        {"check": "0.20 m/s head-current cruise feasible", "value": bool(operating_rows[3]["feasible"]), "criterion": "required thrust <= available thrust", "status": "PASS" if bool(operating_rows[3]["feasible"]) else "FAIL"},
        {"check": "Theoretical top speed exceeds configured operational maximum", "value": max_theoretical_speed, "criterion": f">= {max_design_speed:.2f} m/s", "status": "PASS" if max_theoretical_speed >= max_design_speed else "FAIL"},
        {"check": "Configured thrust coefficient consistency", "value": derived_max_thrust_delta, "criterion": "absolute difference <= 0.05 N per side", "status": "PASS" if derived_max_thrust_delta <= 0.05 else "FAIL"},
    ]

    artifacts = Phase04Artifacts(
        resistance_dashboard=DIRECTORIES["figures"] / "phase04_resistance_dashboard.png",
        resistance_dashboard_svg=DIRECTORIES["figures"] / "phase04_resistance_dashboard.svg",
        propulsion_envelope=DIRECTORIES["figures"] / "phase04_propulsion_envelope.png",
        propulsion_envelope_svg=DIRECTORIES["figures"] / "phase04_propulsion_envelope.svg",
        current_penalty=DIRECTORIES["figures"] / "phase04_current_penalty.png",
        current_penalty_svg=DIRECTORIES["figures"] / "phase04_current_penalty.svg",
        operating_envelope=DIRECTORIES["figures"] / "phase04_operating_envelope.png",
        operating_envelope_svg=DIRECTORIES["figures"] / "phase04_operating_envelope.svg",
        resistance_curve_table=DIRECTORIES["tables"] / "phase04_resistance_curve.csv",
        propulsion_curve_table=DIRECTORIES["tables"] / "phase04_propulsion_curve.csv",
        operating_points_table=DIRECTORIES["tables"] / "phase04_operating_points.csv",
        current_penalty_table=DIRECTORIES["tables"] / "phase04_current_penalty.csv",
        acceptance_checks_table=DIRECTORIES["tables"] / "phase04_acceptance_checks.csv",
        summary_json=DIRECTORIES["logs"] / "phase04_propulsion_summary.json",
        summary_markdown=DIRECTORIES["reports"] / "phase04_hydrodynamics_and_propulsion_summary.md",
        visual_quality_manifest=DIRECTORIES["logs"] / "phase04_visual_quality_manifest.json",
    )

    exports = [
        _draw_resistance_dashboard(states, resistance_model, target_row, artifacts.resistance_dashboard),
        _draw_propulsion_envelope(thrusters, states, target_row, max_theoretical_speed, artifacts.propulsion_envelope),
        _draw_current_penalty(current_rows, artifacts.current_penalty),
        _draw_operating_envelope(operating_rows, resistance_model, thrusters, artifacts.operating_envelope),
    ]
    assert_export_quality(exports, min_width_px=4500, min_height_px=2400)
    _write_csv(artifacts.resistance_curve_table, resistance_rows)
    _write_csv(artifacts.propulsion_curve_table, propulsion_rows)
    _write_csv(artifacts.operating_points_table, operating_rows)
    _write_csv(artifacts.current_penalty_table, current_rows)
    _write_csv(artifacts.acceptance_checks_table, checks)

    summary = {
        "phase": "Phase 04 — Hydrodynamic Resistance and Propulsion",
        "configuration_file": relative_to_root(project_config.source_path),
        "governing_hydrostatic_case": governing_case.as_row(),
        "hydrodynamic_settings": settings.__dict__,
        "thruster_settings": {**thruster_settings.__dict__, "derived_max_thrust_per_side_n": thruster_settings.derived_max_thrust_per_side_n, "power_coefficient_w_per_rpm3": thruster_settings.power_coefficient_w_per_rpm3},
        "target_cruise": target_row,
        "theoretical_top_speed_calm_mps": max_theoretical_speed,
        "acceptance_checks": checks,
        "assumptions": [
            "Calm-water longitudinal steady-state model; full payload is the governing sizing case.",
            "ITTC-1957 friction is combined with transparent quadratic residual, appendage and collector terms.",
            "Twin thrusters are symmetric; differential thrust and yaw coupling are excluded until the 3-DOF phase.",
            "Electrical power uses a preliminary cubic RPM envelope anchored to configured maximum power.",
            "No propeller open-water curve, wake interaction, CFD, waves or manoeuvring loss is included in Phase 04.",
        ],
        "artifacts": artifacts.as_dict(),
    }
    artifacts.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps({
        "phase": "Phase 04 visual quality gate",
        "quality_rule": {
            "minimum_png_width_px": 4500,
            "minimum_png_height_px": 2400,
            "formats": ["PNG (report-ready raster)", "SVG (vector)"],
            "label_policy": "Plots hold only short labels; explanations and numerical reading are isolated in information panels.",
        },
        "exports": [item.as_dict() for item in exports],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(artifacts.summary_markdown, settings, target_row, max_theoretical_speed, artifacts)
    return artifacts


def print_phase04_summary(artifacts: Phase04Artifacts) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 04 Hydrodynamics and Propulsion")
    print("=" * 72)
    for name, path in artifacts.as_dict().items():
        print(f"{name:28}: {path}")
    print("=" * 72)
    print("[OK] Phase 04 resistance, propulsion, current-sensitivity and visual QA artifacts generated.")
