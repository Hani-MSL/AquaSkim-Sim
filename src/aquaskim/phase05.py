"""Phase 05 artifact generation: energy, battery SOC and return-home policy."""
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
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.propulsion import ThrusterSettings, TwinThrusterModel
from aquaskim.visual_quality import PALETTE, FigureExport, add_figure_header, apply_engineering_style, assert_export_quality, export_figure, style_axis


@dataclass(frozen=True)
class Phase05Artifacts:
    energy_dashboard: Path
    energy_dashboard_svg: Path
    mission_soc_profiles: Path
    mission_soc_profiles_svg: Path
    return_home_envelope: Path
    return_home_envelope_svg: Path
    energy_operating_envelope: Path
    energy_operating_envelope_svg: Path
    operating_points_table: Path
    mission_profiles_table: Path
    soc_time_series_table: Path
    return_home_table: Path
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
        writer.writeheader(); writer.writerows(rows)


def _panel(ax: plt.Axes) -> None:
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.025, 0.03), 0.95, 0.94, boxstyle="round,pad=0.018,rounding_size=0.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))


def _heading(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.text(0.08, 0.92, title, fontsize=12.4, fontweight="bold", color=PALETTE["navy"], va="top")
    ax.text(0.08, 0.87, fill(subtitle, width=52), fontsize=8.3, color=PALETTE["gray"], va="top", linespacing=1.38)


def _metric_table(ax: plt.Axes, rows: list[tuple[str, str, str]], *, top: float, height: float) -> None:
    x0, width = 0.08, 0.84; fractions = (0.44, 0.25, 0.31); row_h = height / (len(rows) + 1); y_cursor = top
    for index, values in enumerate([("Metric", "Value", "Unit / note"), *rows]):
        y = y_cursor - row_h; x = x0
        for col, (fraction, value) in enumerate(zip(fractions, values)):
            face = PALETTE["navy"] if index == 0 else (PALETTE["gray_light"] if col == 0 else PALETTE["white"])
            ax.add_patch(Rectangle((x, y), width*fraction, row_h, facecolor=face, edgecolor=PALETTE["grid"], linewidth=.65))
            ax.text(x + (.012 if col == 0 else width*fraction/2), y+row_h/2, value, ha="left" if col == 0 else "center", va="center", fontsize=7.5 if index else 7.25, fontweight="bold" if index == 0 else "normal", color=PALETTE["white"] if index == 0 else PALETTE["gray_dark"])
            x += width*fraction
        y_cursor = y


def _bullets(ax: plt.Axes, heading: str, bullets: list[str], *, y: float, width: int=51) -> None:
    ax.text(0.08, y, heading, fontsize=10.0, fontweight="bold", color=PALETTE["navy"], va="top")
    current = y - .045
    for item in bullets:
        wrapped = fill(item, width=width)
        ax.text(.095, current, "• " + wrapped.replace("\n", "\n  "), fontsize=8.05, color=PALETTE["gray_dark"], va="top", linespacing=1.38)
        current -= .030*(wrapped.count("\n")+1)+.018


def _operating_point(name: str, ground_speed_mps: float, head_current_mps: float, model: CatamaranResistanceModel, thrusters: TwinThrusterModel, battery: BatteryModel, energy: EnergySettings, return_soc_threshold: float) -> dict[str, object]:
    water_speed = ground_speed_mps + head_current_mps
    state = model.state_at_speed(water_speed)
    point = thrusters.symmetric_operating_point(state.total_resistance_n)
    bus_w = point.total_thruster_power_w + energy.hotel_load_w
    load = battery.load_state(bus_w, 1.0)
    endurance_s = battery.endurance_to_soc_s(bus_w, 1.0, return_soc_threshold, energy.integration_time_step_s)
    soc_60 = battery.soc_after_interval(1.0, bus_w, energy.analysis_duration_s)
    return {
        "operating_case": name,
        "ground_speed_mps": ground_speed_mps,
        "head_current_mps": head_current_mps,
        "speed_through_water_mps": water_speed,
        "resistance_n": state.total_resistance_n,
        "rpm_per_side": point.rpm_per_side,
        "throttle_fraction": point.throttle_fraction,
        "thruster_power_w": point.total_thruster_power_w,
        "hotel_load_w": energy.hotel_load_w,
        "bus_power_w": bus_w,
        "battery_power_w": load.battery_power_w,
        "pack_current_a": load.pack_current_a,
        "pack_voltage_start_v": load.pack_voltage_v,
        "peukert_multiplier": load.peukert_multiplier,
        "endurance_to_rth_threshold_min": endurance_s / 60.0,
        "soc_after_nominal_mission": soc_60,
        "feasible": point.feasible,
    }


def _profile_definition() -> list[dict[str, object]]:
    return [
        {"name": "coverage_calm", "label": "Coverage / calm water", "segments": [(0.65, .45, .00), (.20, .20, .00), (.15, .12, .00)]},
        {"name": "coverage_head_current", "label": "Coverage / 0.20 m/s head current", "segments": [(0.65, .45, .20), (.20, .20, .10), (.15, .12, .00)]},
        {"name": "conservative", "label": "Conservative mission", "segments": [(0.65, .35, .00), (.20, .18, .00), (.15, .10, .00)]},
        {"name": "high_demand", "label": "High-demand mission", "segments": [(0.70, .60, .10), (.15, .30, .05), (.15, .12, .00)]},
    ]


def _profile_bus_power(profile: dict[str, object], model: CatamaranResistanceModel, thrusters: TwinThrusterModel, energy: EnergySettings) -> float:
    weighted = 0.0
    for fraction, speed, current in profile["segments"]:  # type: ignore[index]
        state = model.state_at_speed(float(speed)+float(current))
        point = thrusters.symmetric_operating_point(state.total_resistance_n)
        weighted += float(fraction) * (point.total_thruster_power_w + energy.hotel_load_w)
    return weighted


def _simulate_profile(profile: dict[str, object], model: CatamaranResistanceModel, thrusters: TwinThrusterModel, battery: BatteryModel, energy: EnergySettings, return_soc_threshold: float) -> tuple[dict[str, object], list[dict[str, object]]]:
    bus_w = _profile_bus_power(profile, model, thrusters, energy)
    dt = energy.integration_time_step_s; duration = energy.analysis_duration_s
    soc = 1.0; rows: list[dict[str, object]] = []
    for t in np.arange(0.0, duration + dt/2.0, dt):
        load = battery.load_state(bus_w, soc)
        rows.append({"profile": profile["name"], "time_s": float(t), "time_min": float(t/60.0), "soc": soc, "usable_energy_remaining_wh": soc*battery.settings.usable_energy_wh, "pack_voltage_v": load.pack_voltage_v, "battery_power_w": load.battery_power_w, "pack_current_a": load.pack_current_a})
        if t < duration:
            soc = battery.soc_after_interval(soc, bus_w, dt)
    endurance = battery.endurance_to_soc_s(bus_w, 1.0, return_soc_threshold, dt)
    summary = {"profile": profile["name"], "label": profile["label"], "average_bus_power_w": bus_w, "average_battery_power_w": rows[0]["battery_power_w"], "average_pack_current_a": rows[0]["pack_current_a"], "soc_after_nominal_mission": rows[-1]["soc"], "remaining_energy_after_nominal_wh": rows[-1]["usable_energy_remaining_wh"], "endurance_to_rth_threshold_min": endurance/60.0, "return_triggered_during_nominal_mission": bool(rows[-1]["soc"] <= return_soc_threshold)}
    return summary, rows


def _return_home_rows(model: CatamaranResistanceModel, thrusters: TwinThrusterModel, battery: BatteryModel, energy: EnergySettings, threshold: float) -> list[dict[str, object]]:
    rows=[]
    for current in energy.current_sensitivity_values_mps:
        state=model.state_at_speed(energy.return_speed_mps+current)
        point=thrusters.symmetric_operating_point(state.total_resistance_n)
        bus_w=point.total_thruster_power_w+energy.hotel_load_w
        load=battery.load_state(bus_w, 1.0)
        for distance in np.linspace(0.0, energy.return_distance_max_m, energy.return_distance_points):
            travel_s=0.0 if distance==0.0 else float(distance/energy.return_speed_mps)
            travel_energy=load.battery_power_w*travel_s/3600.0*load.peukert_multiplier
            required_soc=(travel_energy+energy.safety_reserve_energy_wh)/battery.settings.usable_energy_wh
            command_soc=max(threshold, required_soc)
            rows.append({"head_current_mps": current, "return_distance_m": float(distance), "return_speed_mps": energy.return_speed_mps, "return_bus_power_w": bus_w, "return_battery_power_w": load.battery_power_w, "return_travel_time_s": travel_s, "return_trip_energy_wh": travel_energy, "reserve_energy_wh": energy.safety_reserve_energy_wh, "energy_based_minimum_soc": required_soc, "configured_rth_soc_threshold": threshold, "commanded_return_soc": command_soc, "feasible": bool(point.feasible)})
    return rows


def _draw_dashboard(battery: BatteryModel, energy: EnergySettings, cruise: dict[str, object], return_row: dict[str, object], output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    gs=GridSpec(2,2,figure=fig,width_ratios=[1.43,.87],left=.055,right=.955,bottom=.08,top=.875,wspace=.16,hspace=.32)
    ax_power=fig.add_subplot(gs[0,0]); ax_voltage=fig.add_subplot(gs[1,0]); info=fig.add_subplot(gs[:,1])
    add_figure_header(fig,"AquaSkim-Sim | Battery and Energy Design Basis","Phase 05 • Pack-side power is derived from Phase 04 bus demand through DC efficiency • SOC references usable, derated pack energy")
    labels=["Hotel", "Thrusters", "DC losses"]; values=[float(cruise['hotel_load_w']), float(cruise['thruster_power_w']), float(cruise['battery_power_w'])-float(cruise['bus_power_w'])]
    ax_power.bar(labels,values,color=[PALETTE['gray'],PALETTE['blue'],PALETTE['orange']]); ax_power.set_ylabel('Power [W]'); ax_power.set_title('Cruise power allocation',loc='left',fontsize=12.5); style_axis(ax_power)
    for i,v in enumerate(values): ax_power.text(i,v+max(values)*.035,f'{v:.2f} W',ha='center',fontsize=8.8)
    soc=np.linspace(0,1,101); voltage=[battery.pack_voltage_v(float(s)) for s in soc]
    ax_voltage.plot(soc*100,voltage,color=PALETTE['green'],linewidth=2.5); ax_voltage.axvline(25,color=PALETTE['orange'],linestyle='--',linewidth=1.2,label='Configured RTH threshold'); ax_voltage.set_xlabel('Usable SOC [%]'); ax_voltage.set_ylabel('Conceptual pack OCV [V]'); ax_voltage.set_title('Conceptual open-circuit voltage curve',loc='left',fontsize=12.5); ax_voltage.legend(loc='lower right',fontsize=8); style_axis(ax_voltage)
    _panel(info); _heading(info,'ENERGY MODEL BASIS','All values are directly derived from the central YAML configuration and Phase 04 operating power.')
    _metric_table(info,[('Chemistry',battery.settings.chemistry,'configured'),('Nominal energy',f'{battery.settings.nominal_energy_wh:.1f}','Wh'),('Usable derated energy',f'{battery.settings.usable_energy_wh:.1f}','Wh'),('Cruise bus demand',f"{float(cruise['bus_power_w']):.2f}",'W'),('Cruise pack demand',f"{float(cruise['battery_power_w']):.2f}",'W'),('Cruise current',f"{float(cruise['pack_current_a']):.2f}",'A'),('RTH reserve',f'{energy.safety_reserve_energy_wh:.1f}','Wh'),('Return power / 0.10 current',f"{float(return_row['return_battery_power_w']):.2f}",'W')],top=.79,height=.36)
    _bullets(info,'EQUATIONS',["Ppack = Pbus / ηDC. The battery-side load is therefore larger than the DC-bus demand by the conversion loss.","SOC is integrated from usable, derated energy; a mild Peukert multiplier penalizes currents above the configured reference current."],y=.37)
    _bullets(info,'LIMITS',["This is a mission-energy model, not a cell electrochemistry, thermal or BMS model. Voltage is a transparent conceptual curve used only for current estimation."],y=.11)
    return export_figure(fig,output,dpi=320)


def _draw_soc_profiles(profile_rows: list[dict[str, object]], summaries: list[dict[str, object]], threshold: float, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False)
    gs=GridSpec(2,2,figure=fig,width_ratios=[1.43,.87],left=.055,right=.955,bottom=.08,top=.875,wspace=.16,hspace=.32)
    ax_soc=fig.add_subplot(gs[0,0]); ax_energy=fig.add_subplot(gs[1,0]); info=fig.add_subplot(gs[:,1]); add_figure_header(fig,'AquaSkim-Sim | Mission SOC Profiles','Phase 05 • 60-minute nominal mission • Fixed duty-cycle profiles built from Phase 04 power operating points')
    for summary in summaries:
        rows=[r for r in profile_rows if r['profile']==summary['profile']]
        ax_soc.plot([r['time_min'] for r in rows],[100*r['soc'] for r in rows],linewidth=2.0,label=str(summary['label']))
        ax_energy.plot([r['time_min'] for r in rows],[r['usable_energy_remaining_wh'] for r in rows],linewidth=2.0,label=str(summary['label']))
    ax_soc.axhline(threshold*100,color=PALETTE['orange'],linestyle='--',linewidth=1.2,label='RTH threshold'); ax_soc.set_ylabel('Usable SOC [%]'); ax_soc.set_title('SOC through the nominal mission',loc='left',fontsize=12.5); ax_soc.legend(loc='best',fontsize=7.6); style_axis(ax_soc)
    ax_energy.axhline(0,color=PALETTE['gray'],linewidth=.8); ax_energy.set_xlabel('Mission time [min]'); ax_energy.set_ylabel('Usable energy remaining [Wh]'); ax_energy.set_title('Remaining usable energy',loc='left',fontsize=12.5); style_axis(ax_energy)
    _panel(info); _heading(info,'NOMINAL MISSION READING','Each profile mixes transit, collection and low-speed manoeuvring. The duty cycles are explicit in the code and saved in the summary JSON.')
    rows=[(str(s['profile']),f"{float(s['average_battery_power_w']):.1f}",f"SOC@60 = {100*float(s['soc_after_nominal_mission']):.1f}%") for s in summaries]
    _metric_table(info,rows,top=.79,height=.29)
    _bullets(info,'DECISION LOGIC',[f"The configured return threshold is {threshold*100:.0f}% usable SOC. A profile triggers return if SOC falls to this boundary.","Endurance estimates are reported to the RTH boundary, leaving energy for return and the configured fixed reserve."],y=.43)
    _bullets(info,'INTERPRETATION',["The head-current profile is deliberately more demanding because through-water speed, resistance, propeller RPM and electrical power all increase."],y=.18)
    return export_figure(fig,output,dpi=320)


def _draw_return_envelope(rows: list[dict[str, object]], threshold: float, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False); gs=GridSpec(2,2,figure=fig,width_ratios=[1.43,.87],left=.055,right=.955,bottom=.08,top=.875,wspace=.16,hspace=.32)
    ax_soc=fig.add_subplot(gs[0,0]); ax_energy=fig.add_subplot(gs[1,0]); info=fig.add_subplot(gs[:,1]); add_figure_header(fig,'AquaSkim-Sim | Return-to-Home Energy Envelope','Phase 05 • Return policy compares instantaneous usable SOC with return-trip energy plus a fixed engineering reserve')
    currents=sorted({float(r['head_current_mps']) for r in rows})
    for current in currents:
        subset=[r for r in rows if float(r['head_current_mps'])==current]
        ax_soc.plot([r['return_distance_m'] for r in subset],[100*r['energy_based_minimum_soc'] for r in subset],linewidth=2.1,label=f'Energy-only, head current {current:.2f} m/s')
        ax_energy.plot([r['return_distance_m'] for r in subset],[r['return_trip_energy_wh'] for r in subset],linewidth=2.1,label=f'Head current {current:.2f} m/s')
    ax_soc.axhline(threshold*100,color=PALETTE['orange'],linestyle='--',linewidth=1.5,label='Configured return trigger'); ax_soc.set_ylabel('Minimum usable SOC [%]'); ax_soc.set_title('Energy-only return requirement vs configured trigger',loc='left',fontsize=12.5); ax_soc.legend(loc='upper left',fontsize=7.3); style_axis(ax_soc)
    ax_energy.set_xlabel('Distance to home [m]'); ax_energy.set_ylabel('Return-trip battery energy [Wh]'); ax_energy.set_title('Return-trip energy before fixed reserve',loc='left',fontsize=12.5); ax_energy.legend(loc='upper left',fontsize=7.3); style_axis(ax_energy)
    max_row=max(rows,key=lambda r: float(r['return_trip_energy_wh']))
    _panel(info); _heading(info,'RETURN POLICY','The commanded return threshold is the maximum of the configured SOC floor and the distance/current-specific energy requirement.')
    _metric_table(info,[('Configured SOC trigger',f'{threshold*100:.1f}','% usable SOC'),('Fixed reserve',f"{float(max_row['reserve_energy_wh']):.1f}",'Wh'),('Envelope distance',f"{max(float(r['return_distance_m']) for r in rows):.1f}",'m'),('Worst return energy',f"{float(max_row['return_trip_energy_wh']):.3f}",'Wh'),('Worst energy-only SOC',f"{100*float(max_row['energy_based_minimum_soc']):.2f}",'%'),('Commanded threshold',f"{100*float(max_row['commanded_return_soc']):.1f}",'%')],top=.79,height=.28)
    _bullets(info,'ENGINEERING READING',["For this small pool-scale map, the fixed reserve and configured 25% RTH floor govern more strongly than the physical travel energy. This is an intentional conservative policy.","Later autonomy phases will evaluate this envelope continuously from the estimated distance-to-home and current estimate."],y=.43)
    return export_figure(fig,output,dpi=320)


def _draw_operating_envelope(rows: list[dict[str, object]], battery: BatteryModel, current_limit: float, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10), constrained_layout=False); gs=GridSpec(2,2,figure=fig,width_ratios=[1.43,.87],left=.055,right=.955,bottom=.08,top=.875,wspace=.16,hspace=.32)
    ax_power=fig.add_subplot(gs[0,0]); ax_end=fig.add_subplot(gs[1,0]); info=fig.add_subplot(gs[:,1]); add_figure_header(fig,'AquaSkim-Sim | Energy Operating Envelope','Phase 05 • Battery-side demand and endurance to the return-home SOC boundary')
    labels=[str(r['operating_case']).replace('_','\n') for r in rows]; x=np.arange(len(rows)); power=[float(r['battery_power_w']) for r in rows]; current=[float(r['pack_current_a']) for r in rows]; endurance=[float(r['endurance_to_rth_threshold_min']) for r in rows]
    ax_power.bar(x-.18,power,.36,color=PALETTE['blue'],label='Battery power [W]'); axp=ax_power.twinx(); axp.bar(x+.18,current,.36,color=PALETTE['green'],label='Pack current [A]'); axp.axhline(current_limit,color=PALETTE['orange'],linestyle='--',linewidth=1.2,label='Continuous-current limit'); ax_power.set_xticks(x,labels,fontsize=7.3); ax_power.set_ylabel('Battery power [W]'); axp.set_ylabel('Pack current [A]'); ax_power.set_title('Battery-side operating demand',loc='left',fontsize=12.5); style_axis(ax_power); lines=ax_power.get_legend_handles_labels()[0]+axp.get_legend_handles_labels()[0]; labs=ax_power.get_legend_handles_labels()[1]+axp.get_legend_handles_labels()[1]; ax_power.legend(lines,labs,loc='upper left',fontsize=7.2)
    ax_end.bar(x,endurance,color=PALETTE['green']); ax_end.set_xticks(x,labels,fontsize=7.3); ax_end.set_ylabel('Time to RTH threshold [min]'); ax_end.set_title('Endurance to configured RTH threshold',loc='left',fontsize=12.5); style_axis(ax_end)
    for i,v in enumerate(endurance): ax_end.text(i,v+max(endurance)*.02,f'{v:.0f}',ha='center',fontsize=8)
    cruise=next(r for r in rows if r['operating_case']=='cruise_calm_full_payload')
    _panel(info); _heading(info,'OPERATING ENVELOPE','Every bar is traceable to a Phase 04 thrust requirement and the same battery model used for SOC integration.')
    _metric_table(info,[('Cruise pack power',f"{float(cruise['battery_power_w']):.2f}",'W'),('Cruise pack current',f"{float(cruise['pack_current_a']):.2f}",'A'),('Continuous current limit',f'{current_limit:.1f}','A'),('Cruise endurance to RTH',f"{float(cruise['endurance_to_rth_threshold_min']):.1f}",'min'),('SOC after 60 min',f"{100*float(cruise['soc_after_nominal_mission']):.1f}",'%'),('Usable battery energy',f'{battery.settings.usable_energy_wh:.1f}','Wh')],top=.79,height=.29)
    _bullets(info,'USE IN FOLLOWING PHASES',["The 3-DOF simulator will query instantaneous thrust commands, convert them to electrical demand, then update SOC using the same battery model and current limits."],y=.42)
    return export_figure(fig,output,dpi=320)


def _write_summary(path: Path, battery: BatteryModel, energy: EnergySettings, cruise: dict[str, object], profiles: list[dict[str, object]], threshold: float, artifacts: Phase05Artifacts) -> None:
    lines = [
        "# AquaSkim-Sim | Phase 05 Energy and Battery Summary", "",
        "## Design basis",
        f"- Battery: `{battery.settings.chemistry}`",
        f"- Nominal stored energy: `{battery.settings.nominal_energy_wh:.2f} Wh`",
        f"- Usable derated energy: `{battery.settings.usable_energy_wh:.2f} Wh`",
        f"- DC bus efficiency: `{battery.settings.dc_bus_efficiency:.3f}`",
        f"- Return-home trigger: `{threshold*100:.1f}%` usable SOC",
        f"- Fixed return reserve: `{energy.safety_reserve_energy_wh:.2f} Wh`", "",
        "## Governing calm-water cruise",
        f"- Battery power: `{float(cruise['battery_power_w']):.3f} W`",
        f"- Pack current: `{float(cruise['pack_current_a']):.3f} A`",
        f"- Endurance to RTH threshold: `{float(cruise['endurance_to_rth_threshold_min']):.1f} min`",
        f"- SOC after 60 min: `{100*float(cruise['soc_after_nominal_mission']):.1f}%`", "",
        "## Mission-profile result", "",
        "| Profile | Average battery power [W] | SOC after 60 min | Time to RTH [min] |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item['profile']} | {float(item['average_battery_power_w']):.2f} | "
        f"{100*float(item['soc_after_nominal_mission']):.1f}% | "
        f"{float(item['endurance_to_rth_threshold_min']):.1f} |"
        for item in profiles
    )
    lines.extend([
        "", "## Explicit limitations", "",
        "- No electrochemical cell dynamics, temperature model, BMS cut-off transient, ageing or charge model is included.",
        "- The voltage curve is conceptual and only supports pack-current estimation.",
        "- The current return envelope assumes known head-current magnitude and constant return speed.",
        "", "## Artifact inventory", "",
    ])
    lines.extend(f"- `{value}`" for value in artifacts.as_dict().values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase05(config: ProjectConfiguration | None=None) -> Phase05Artifacts:
    ensure_runtime_directories(); project=config or load_base_configuration(); geometry=CatamaranGeometry.from_config(project.data); hydro_settings=HydrostaticSettings.from_config(project.data); hydro=CatamaranHydrostatics(geometry,hydro_settings); _, full=build_load_cases(project.data)['full_design_payload']; full_case=hydro.case_from_mass_properties('full_design_payload',full)
    resistance=CatamaranResistanceModel(geometry,HydrodynamicSettings.from_config(project.data),full_case); thrusters=TwinThrusterModel(ThrusterSettings.from_config(project.data)); battery=BatteryModel(BatterySettings.from_config(project.data)); energy=EnergySettings.from_config(project.data); threshold=float(project.data['mission']['mission_limits']['return_soc_threshold']); cruise_speed=float(project.data['propulsion']['limits']['target_cruise_speed_mps']); max_speed=float(project.data['propulsion']['limits']['max_speed_mps'])
    operating=[_operating_point('low_speed_collection',.20,.0,resistance,thrusters,battery,energy,threshold),_operating_point('cruise_calm_full_payload',cruise_speed,.0,resistance,thrusters,battery,energy,threshold),_operating_point('cruise_head_current_0p20',cruise_speed,.20,resistance,thrusters,battery,energy,threshold),_operating_point('return_home_0p10_current',energy.return_speed_mps,energy.return_head_current_mps,resistance,thrusters,battery,energy,threshold),_operating_point('design_max_speed_calm',max_speed,.0,resistance,thrusters,battery,energy,threshold)]
    profiles=[]; soc_rows=[]
    for definition in _profile_definition():
        summary, rows=_simulate_profile(definition,resistance,thrusters,battery,energy,threshold); profiles.append(summary); soc_rows.extend(rows)
    rth_rows=_return_home_rows(resistance,thrusters,battery,energy,threshold); cruise=next(row for row in operating if row['operating_case']=='cruise_calm_full_payload'); return_row=next(row for row in rth_rows if float(row['head_current_mps'])==energy.return_head_current_mps and abs(float(row['return_distance_m'])-energy.return_distance_max_m)<1e-9)
    checks=[
        {'check':'Calm cruise is propulsion-feasible','value':bool(cruise['feasible']),'criterion':'required thrust <= available thrust','status':'PASS' if bool(cruise['feasible']) else 'FAIL'},
        {'check':'Cruise current below continuous battery limit','value':float(cruise['pack_current_a']),'criterion':f"<= {battery.settings.max_continuous_discharge_current_a:.2f} A",'status':'PASS' if float(cruise['pack_current_a'])<=battery.settings.max_continuous_discharge_current_a else 'FAIL'},
        {'check':'Calm cruise endurance to RTH threshold','value':float(cruise['endurance_to_rth_threshold_min']),'criterion':f">= {energy.minimum_endurance_at_cruise_min:.1f} min",'status':'PASS' if float(cruise['endurance_to_rth_threshold_min'])>=energy.minimum_endurance_at_cruise_min else 'FAIL'},
        {'check':'Calm coverage SOC after nominal mission','value':float(next(p for p in profiles if p['profile']=='coverage_calm')['soc_after_nominal_mission']),'criterion':f">= {energy.minimum_soc_after_nominal_mission:.2f}",'status':'PASS' if float(next(p for p in profiles if p['profile']=='coverage_calm')['soc_after_nominal_mission'])>=energy.minimum_soc_after_nominal_mission else 'FAIL'},
        {'check':'All return-envelope cases propulsion-feasible','value':all(bool(r['feasible']) for r in rth_rows),'criterion':'all cases feasible','status':'PASS' if all(bool(r['feasible']) for r in rth_rows) else 'FAIL'},
        {'check':'Configured RTH threshold exceeds worst energy-only RTH requirement','value':threshold,'criterion':f">= {max(float(r['energy_based_minimum_soc']) for r in rth_rows):.4f}",'status':'PASS' if threshold>=max(float(r['energy_based_minimum_soc']) for r in rth_rows) else 'FAIL'},
    ]
    artifacts=Phase05Artifacts(energy_dashboard=DIRECTORIES['figures']/ 'phase05_energy_dashboard.png',energy_dashboard_svg=DIRECTORIES['figures']/ 'phase05_energy_dashboard.svg',mission_soc_profiles=DIRECTORIES['figures']/ 'phase05_mission_soc_profiles.png',mission_soc_profiles_svg=DIRECTORIES['figures']/ 'phase05_mission_soc_profiles.svg',return_home_envelope=DIRECTORIES['figures']/ 'phase05_return_home_envelope.png',return_home_envelope_svg=DIRECTORIES['figures']/ 'phase05_return_home_envelope.svg',energy_operating_envelope=DIRECTORIES['figures']/ 'phase05_energy_operating_envelope.png',energy_operating_envelope_svg=DIRECTORIES['figures']/ 'phase05_energy_operating_envelope.svg',operating_points_table=DIRECTORIES['tables']/ 'phase05_energy_operating_points.csv',mission_profiles_table=DIRECTORIES['tables']/ 'phase05_mission_profiles.csv',soc_time_series_table=DIRECTORIES['tables']/ 'phase05_soc_time_series.csv',return_home_table=DIRECTORIES['tables']/ 'phase05_return_home_envelope.csv',acceptance_checks_table=DIRECTORIES['tables']/ 'phase05_acceptance_checks.csv',summary_json=DIRECTORIES['logs']/ 'phase05_energy_summary.json',summary_markdown=DIRECTORIES['reports']/ 'phase05_energy_and_battery_summary.md',visual_quality_manifest=DIRECTORIES['logs']/ 'phase05_visual_quality_manifest.json')
    exports=[_draw_dashboard(battery,energy,cruise,return_row,artifacts.energy_dashboard),_draw_soc_profiles(soc_rows,profiles,threshold,artifacts.mission_soc_profiles),_draw_return_envelope(rth_rows,threshold,artifacts.return_home_envelope),_draw_operating_envelope(operating,battery,battery.settings.max_continuous_discharge_current_a,artifacts.energy_operating_envelope)]
    assert_export_quality(exports,min_width_px=4500,min_height_px=2400)
    _write_csv(artifacts.operating_points_table,operating); _write_csv(artifacts.mission_profiles_table,profiles); _write_csv(artifacts.soc_time_series_table,soc_rows); _write_csv(artifacts.return_home_table,rth_rows); _write_csv(artifacts.acceptance_checks_table,checks)
    summary={'phase':'Phase 05 — Energy, Battery SOC and Return-to-Home Policy','configuration_file':relative_to_root(project.source_path),'battery_settings':battery.settings.__dict__,'energy_settings':{**energy.__dict__,'current_sensitivity_values_mps':list(energy.current_sensitivity_values_mps)},'full_payload_hydrostatic_case':full_case.as_row(),'operating_points':operating,'mission_profiles':profiles,'acceptance_checks':checks,'assumptions':['Pack-side power equals DC-bus load divided by configured conversion efficiency.','SOC refers to usable, derated pack energy and uses a mild Peukert-style current multiplier.','Mission profiles are deterministic duty-cycle abstractions; 3-DOF manoeuvring load enters in Phase 06.','Return envelope assumes a known constant head current and fixed return speed.'],'artifacts':artifacts.as_dict()}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); artifacts.visual_quality_manifest.write_text(json.dumps({'phase':'Phase 05 visual quality gate','quality_rule':{'minimum_png_width_px':4500,'minimum_png_height_px':2400,'formats':['PNG (report-ready raster)','SVG (vector)'],'label_policy':'Dense calculations and long explanations are isolated in dedicated information panels and machine-readable tables.'},'exports':[item.as_dict() for item in exports]},ensure_ascii=False,indent=2),encoding='utf-8'); _write_summary(artifacts.summary_markdown,battery,energy,cruise,profiles,threshold,artifacts); return artifacts


def print_phase05_summary(artifacts: Phase05Artifacts) -> None:
    print('='*72); print('AquaSkim-Sim | Phase 05 Energy and Battery'); print('='*72)
    for name,path in artifacts.as_dict().items(): print(f'{name:30}: {path}')
    print('='*72); print('[OK] Phase 05 energy, SOC, endurance and return-home artifacts generated.')
