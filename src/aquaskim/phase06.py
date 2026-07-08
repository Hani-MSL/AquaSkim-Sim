"""Phase 06 artifact generation: 3-DOF surge-sway-yaw dynamics and manoeuvres."""
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
from aquaskim.dynamics_3dof import CraftState, DynamicsSettings, PlanarCatamaranDynamics, SimulationResult, ThrusterCommand
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import PALETTE, FigureExport, add_figure_header, apply_engineering_style, assert_export_quality, export_figure, style_axis


@dataclass(frozen=True)
class Phase06Artifacts:
    dynamics_dashboard: Path
    dynamics_dashboard_svg: Path
    trajectory_comparison: Path
    trajectory_comparison_svg: Path
    maneuver_response: Path
    maneuver_response_svg: Path
    current_disturbance: Path
    current_disturbance_svg: Path
    parameter_table: Path
    scenario_metrics_table: Path
    time_series_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)


def _panel(ax: plt.Axes) -> None:
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.025, .03), .95, .94, boxstyle="round,pad=0.018,rounding_size=0.02", facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0))


def _panel_heading(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.text(.08, .92, title, fontsize=12.2, fontweight="bold", color=PALETTE["navy"], va="top")
    ax.text(.08, .865, fill(subtitle, width=48), fontsize=8.25, color=PALETTE["gray"], va="top", linespacing=1.37)


def _metric_grid(ax: plt.Axes, rows: list[tuple[str, str, str]], *, top: float, height: float) -> None:
    x0, width, row_h = .08, .84, height/(len(rows)+1)
    fractions = (.45, .23, .32); cursor = top
    for index, values in enumerate([("Metric", "Value", "Unit / note"), *rows]):
        y = cursor-row_h; x=x0
        for col, (frac, value) in enumerate(zip(fractions,values)):
            face = PALETTE["navy"] if index == 0 else (PALETTE["gray_light"] if col == 0 else PALETTE["white"])
            ax.add_patch(Rectangle((x,y), width*frac,row_h,facecolor=face,edgecolor=PALETTE["grid"],linewidth=.65))
            ax.text(x+(.012 if col==0 else width*frac/2), y+row_h/2, value, ha="left" if col==0 else "center",va="center",fontsize=7.3 if index else 7.1,fontweight="bold" if index==0 else "normal",color=PALETTE["white"] if index==0 else PALETTE["gray_dark"])
            x += width*frac
        cursor = y


def _bullets(ax: plt.Axes, title: str, items: list[str], *, y: float, width: int=48) -> None:
    ax.text(.08,y,title,fontsize=9.9,fontweight="bold",color=PALETTE["navy"],va="top")
    cursor=y-.045
    for item in items:
        wrapped=fill(item,width=width)
        ax.text(.095,cursor,"• "+wrapped.replace("\n","\n  "),fontsize=7.9,color=PALETTE["gray_dark"],va="top",linespacing=1.36)
        cursor -= .03*(wrapped.count("\n")+1)+.017


def _build_model(config: ProjectConfiguration) -> tuple[PlanarCatamaranDynamics, float]:
    data=config.data
    geometry=CatamaranGeometry.from_config(data)
    hydro_settings=HydrostaticSettings.from_config(data)
    hydro=CatamaranHydrostatics(geometry,hydro_settings)
    cases=build_load_cases(data)
    _, full_mass=cases["full_design_payload"]
    full_case=hydro.case_from_mass_properties("full_design_payload",full_mass)
    resistance=CatamaranResistanceModel(geometry,HydrodynamicSettings.from_config(data),full_case)
    model=PlanarCatamaranDynamics(geometry=geometry,resistance=resistance,hydro_case=full_case,mass_properties=full_mass,settings=DynamicsSettings.from_config(data))
    cruise_resistance=resistance.state_at_speed(float(data["propulsion"]["limits"]["target_cruise_speed_mps"])).total_resistance_n
    return model, cruise_resistance


def _run_scenarios(model: PlanarCatamaranDynamics, cruise_force: float) -> dict[str, SimulationResult]:
    s=model.settings; delay=s.scenario_start_delay_s
    def straight(t: float) -> ThrusterCommand:
        thrust=0.0 if t<delay else .5*cruise_force*s.cruise_thrust_multiplier
        return ThrusterCommand(thrust,thrust)
    def turn(t: float) -> ThrusterCommand:
        if t<delay: return ThrusterCommand(0.0,0.0)
        if s.turn_start_s <= t <= s.turn_end_s:
            return ThrusterCommand(.5*cruise_force*s.turn_left_thrust_multiplier,.5*cruise_force*s.turn_right_thrust_multiplier)
        thrust=.5*cruise_force*s.cruise_thrust_multiplier
        return ThrusterCommand(thrust,thrust)
    results={
        "calm_straight": model.simulate(scenario="calm_straight",description="Symmetric thrust in calm water; steady-speed check against Phase 04 resistance.",command_law=straight),
        "differential_turn": model.simulate(scenario="differential_turn",description="Timed differential-thrust manoeuvre in calm water; evaluates yaw response and curved trajectory.",command_law=turn),
        "cross_current": model.simulate(scenario="cross_current",description="Symmetric thrust with 0.18 m/s earth-fixed cross-current; demonstrates disturbance-induced drift.",command_law=straight,current_earth_mps=(0.0,s.current_crossflow_mps)),
    }
    return results


def _scenario_metrics(results: dict[str, SimulationResult], target_speed: float, s: DynamicsSettings) -> list[dict[str, object]]:
    rows=[]
    for name,result in results.items():
        last=result.rows[-1]; max_r=max(abs(float(row["r_rps"])) for row in result.rows); max_v=max(abs(float(row["v_mps"])) for row in result.rows)
        rows.append({
            "scenario":name,"description":result.description,"duration_s":last["time_s"],"final_x_m":last["x_m"],"final_y_m":last["y_m"],"final_heading_deg":last["psi_deg"],"final_u_mps":last["u_mps"],"final_v_mps":last["v_mps"],"final_speed_over_ground_mps":last["speed_over_ground_mps"],"max_abs_sway_mps":max_v,"max_abs_yaw_rate_rps":max_r,"cross_track_drift_m":last["y_m"],"speed_error_to_target_mps":last["u_mps"]-target_speed,
            "current_x_mps":result.current_earth_mps[0],"current_y_mps":result.current_earth_mps[1],
            "yaw_rate_within_configured_bound":max_r <= s.maximum_expected_yaw_rate_rps,
        })
    return rows


def _draw_dashboard(model: PlanarCatamaranDynamics, cruise_force: float, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10),constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,width_ratios=[1.38,.92],left=.055,right=.955,bottom=.075,top=.875,wspace=.17,hspace=.34)
    force_ax=fig.add_subplot(grid[0,0]); schematic_ax=fig.add_subplot(grid[1,0]); info=fig.add_subplot(grid[:,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 06 — Planar 3-DOF Dynamic Model","Surge–sway–yaw • body-fixed velocities • current-relative drag • RK4 integration • full-payload case")
    speeds=np.linspace(0,.75,101); force=[model.resistance.state_at_speed(float(v)).total_resistance_n for v in speeds]
    force_ax.plot(speeds,force,color=PALETTE["blue"],linewidth=2.4,label="Phase 04 resistance reused")
    force_ax.axhline(cruise_force,color=PALETTE["orange"],linestyle="--",linewidth=1.6,label="Cruise thrust demand")
    force_ax.scatter([.45],[cruise_force],s=52,color=PALETTE["orange"],zorder=5)
    force_ax.set_title("Longitudinal force basis",loc="left",fontsize=12.5); force_ax.set_xlabel("Relative water speed [m/s]"); force_ax.set_ylabel("Resistance / thrust [N]"); force_ax.legend(loc="upper left",fontsize=8); style_axis(force_ax)
    schematic_ax.set_aspect("equal"); schematic_ax.axis("off"); schematic_ax.set_xlim(-.55,.72); schematic_ax.set_ylim(-.38,.38)
    # simple top-view geometry with force arrows
    for y in (.18,-.18): schematic_ax.add_patch(Rectangle((-.35,y-.045),.70,.09,fill=False,linewidth=1.7,edgecolor=PALETTE["navy"]))
    schematic_ax.add_patch(Rectangle((-.13,-.18),.33,.36,fill=False,linestyle="--",edgecolor=PALETTE["gray"]))
    schematic_ax.arrow(.34,.18,.20,0,width=.004,head_width=.035,head_length=.04,color=PALETTE["green"],length_includes_head=True)
    schematic_ax.arrow(.34,-.18,.20,0,width=.004,head_width=.035,head_length=.04,color=PALETTE["green"],length_includes_head=True)
    schematic_ax.arrow(-.02,0,-.22,0,width=.004,head_width=.03,head_length=.04,color=PALETTE["orange"],length_includes_head=True)
    schematic_ax.text(.55,.21,"T port",fontsize=9,color=PALETTE["green"],va="bottom"); schematic_ax.text(.55,-.21,"T starboard",fontsize=9,color=PALETTE["green"],va="top"); schematic_ax.text(-.28,.035,"hydrodynamic\ndrag",fontsize=8,color=PALETTE["orange"],ha="center")
    schematic_ax.text(0,-.31,"τz = b/2 · (Tstarboard − Tport)",fontsize=9,color=PALETTE["navy"],ha="center")
    schematic_ax.set_title("Force and moment allocation",loc="left",fontsize=12.5,pad=8)
    _panel(info); _panel_heading(info,"MODEL DEFINITION","The state is [x, y, ψ, u, v, r]. Earth position uses ENU coordinates; hydrodynamic resistance uses velocity relative to a constant current vector.")
    m=model.mass; _metric_grid(info,[
        ("Full-load rigid mass",f"{m.rigid_mass_kg:.3f}","kg"),("Effective surge mass",f"{m.surge_mass_kg:.3f}","kg"),("Effective sway mass",f"{m.sway_mass_kg:.3f}","kg"),("Effective yaw inertia",f"{m.yaw_inertia_kg_m2:.4f}","kg·m²"),("Thruster half-spacing",f"{model.thruster_half_spacing_m:.3f}","m"),("Cruise force demand",f"{cruise_force:.3f}","N total"),
    ],top=.78,height=.28)
    _bullets(info,"EQUATIONS",["m_u(du/dt − v·r) = T_port + T_starboard + X_drag.","m_v(dv/dt + u·r) = Y_drag; I_z·dr/dt = τ_z + N_drag.","Earth velocity is R(ψ)[u, v]ᵀ; drag is evaluated from [u, v]ᵀ − R(ψ)ᵀV_current."],y=.43,width=48)
    _bullets(info,"MODEL LIMITS",["Uniform current only. Waves, wind, roll/pitch/heave and a complete added-mass Coriolis matrix are omitted."],y=.16,width=48)
    return export_figure(fig,output,dpi=320)


def _draw_trajectories(results: dict[str,SimulationResult], output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.8),constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,width_ratios=[1.38,.92],left=.055,right=.955,bottom=.08,top=.875,wspace=.17,hspace=.34)
    traj=fig.add_subplot(grid[:,0]); heading=fig.add_subplot(grid[0,1]); speed=fig.add_subplot(grid[1,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 06 — Earth-Fixed Trajectory Comparison","Equal symmetric thrust; a cross-current is represented as a true vector disturbance in the dynamic equations")
    colors={"calm_straight":PALETTE["blue"],"differential_turn":PALETTE["green"],"cross_current":PALETTE["orange"]}; labels={"calm_straight":"Calm straight","differential_turn":"Differential turn","cross_current":"Cross-current"}
    for name,res in results.items():
        x=[float(r['x_m']) for r in res.rows]; y=[float(r['y_m']) for r in res.rows]; t=[float(r['time_s']) for r in res.rows]
        traj.plot(x,y,color=colors[name],linewidth=2.4,label=labels[name]); traj.scatter([x[0]],[y[0]],color=colors[name],s=28,zorder=5); traj.scatter([x[-1]],[y[-1]],color=colors[name],s=34,marker='s',zorder=5)
        heading.plot(t,[float(r['psi_deg']) for r in res.rows],color=colors[name],linewidth=2,label=labels[name]); speed.plot(t,[float(r['u_mps']) for r in res.rows],color=colors[name],linewidth=2,label=labels[name])
    traj.axhline(0,color=PALETTE['grid'],linewidth=.8); traj.axvline(0,color=PALETTE['grid'],linewidth=.8); traj.set_aspect('equal',adjustable='datalim'); traj.set_title('Earth-fixed trajectories (start: circle; finish: square)',loc='left',fontsize=12.5); traj.set_xlabel('East x [m]'); traj.set_ylabel('North y [m]'); traj.legend(loc='best',fontsize=8); style_axis(traj)
    heading.set_title('Heading response',loc='left',fontsize=12); heading.set_xlabel('Time [s]'); heading.set_ylabel('ψ [deg]'); heading.legend(loc='best',fontsize=7.5); style_axis(heading)
    speed.set_title('Surge response',loc='left',fontsize=12); speed.set_xlabel('Time [s]'); speed.set_ylabel('u [m/s]'); speed.legend(loc='best',fontsize=7.5); style_axis(speed)
    return export_figure(fig,output,dpi=320)


def _draw_maneuver(result:SimulationResult, output:Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,width_ratios=[1.35,.95],left=.055,right=.955,bottom=.08,top=.875,wspace=.17,hspace=.33)
    thrust=fig.add_subplot(grid[0,0]); response=fig.add_subplot(grid[1,0]); info=fig.add_subplot(grid[:,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 06 — Differential-Thrust Manoeuvre","Timed port/starboard thrust asymmetry; the curve isolates yaw and sway coupling before closed-loop control is introduced")
    t=[float(r['time_s']) for r in result.rows]; port=[float(r['port_thrust_n']) for r in result.rows]; star=[float(r['starboard_thrust_n']) for r in result.rows]
    thrust.plot(t,port,color=PALETTE['blue'],linewidth=2.2,label='Port thrust'); thrust.plot(t,star,color=PALETTE['green'],linewidth=2.2,label='Starboard thrust'); thrust.set_title('Commanded thruster forces',loc='left',fontsize=12.5); thrust.set_xlabel('Time [s]'); thrust.set_ylabel('Thrust [N]'); thrust.legend(loc='upper left',fontsize=8); style_axis(thrust)
    response.plot(t,[float(r['r_rps']) for r in result.rows],color=PALETTE['orange'],linewidth=2.2,label='Yaw rate r'); response.plot(t,[float(r['v_mps']) for r in result.rows],color='#9A6FB0',linewidth=2.0,label='Sway velocity v'); response.plot(t,[float(r['psi_deg'])/100.0 for r in result.rows],color=PALETTE['gray'],linestyle='--',linewidth=1.8,label='Heading ψ / 100'); response.set_title('Coupled manoeuvring response',loc='left',fontsize=12.5); response.set_xlabel('Time [s]'); response.set_ylabel('r [rad/s], v [m/s], ψ/100'); response.legend(loc='best',fontsize=8); style_axis(response)
    max_r=max(abs(float(r['r_rps'])) for r in result.rows); final=result.rows[-1]
    _panel(info); _panel_heading(info,'MANOEUVRE READING','The turn is commanded only by asymmetric thruster forces. No steering rudder is included; yaw moment derives directly from the propulsion spacing.')
    _metric_grid(info,[('Simulation duration',f"{float(t[-1]):.1f}",'s total simulation'),('Peak yaw rate',f"{max_r:.3f}",'rad/s'),('Final heading',f"{float(final['psi_deg']):.1f}",'deg'),('Final sway speed',f"{float(final['v_mps']):.3f}",'m/s'),('Peak yaw moment',f"{max(abs(float(r['yaw_moment_n_m'])) for r in result.rows):.3f}",'N·m'),('Final path x / y',f"{float(final['x_m']):.2f} / {float(final['y_m']):.2f}",'m'),],top=.78,height=.28)
    _bullets(info,'INTERPRETATION',["The apparent lateral velocity during the turn is expected: it arises from body-frame coupling and sway damping.","Closed-loop heading or path control is intentionally not applied in this phase; it will be added after environmental sensing and mission planning are defined."],y=.43,width=49)
    _bullets(info,'VALIDITY',["The result is suitable for comparative design and controller preparation, not for claiming full-scale manoeuvring certification."],y=.16,width=49)
    return export_figure(fig,output,dpi=320)


def _draw_current(result:SimulationResult, output:Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,width_ratios=[1.35,.95],left=.055,right=.955,bottom=.08,top=.875,wspace=.17,hspace=.33)
    drift=fig.add_subplot(grid[0,0]); relative=fig.add_subplot(grid[1,0]); info=fig.add_subplot(grid[:,1])
    add_figure_header(fig,"AquaSkim-Sim | Phase 06 — Cross-Current Disturbance Response","Open-loop symmetric cruise thrust; drift demonstrates why later guidance must compensate current rather than only track heading")
    t=[float(r['time_s']) for r in result.rows]; x=[float(r['x_m']) for r in result.rows]; y=[float(r['y_m']) for r in result.rows]
    drift.plot(x,y,color=PALETTE['orange'],linewidth=2.5,label='Actual trajectory'); drift.plot([0,max(x)],[0,0],color=PALETTE['gray'],linestyle='--',linewidth=1.6,label='No-drift reference'); drift.arrow(.4,.1,0,0.6,width=.008,head_width=.08,head_length=.10,color=PALETTE['blue'],length_includes_head=True); drift.text(.47,.45,'Current',color=PALETTE['blue'],fontsize=9); drift.set_aspect('equal',adjustable='datalim'); drift.set_title('Earth-fixed drift',loc='left',fontsize=12.5); drift.set_xlabel('East x [m]'); drift.set_ylabel('North y [m]'); drift.legend(loc='best',fontsize=8); style_axis(drift)
    relative.plot(t,[float(r['u_relative_water_mps']) for r in result.rows],color=PALETTE['green'],linewidth=2.1,label='u relative to water'); relative.plot(t,[float(r['v_relative_water_mps']) for r in result.rows],color=PALETTE['orange'],linewidth=2.1,label='v relative to water'); relative.plot(t,[float(r['y_m']) for r in result.rows],color=PALETTE['blue'],linestyle='--',linewidth=1.8,label='Cross-track y'); relative.set_title('Relative-water velocity and accumulated drift',loc='left',fontsize=12.5); relative.set_xlabel('Time [s]'); relative.set_ylabel('m/s or m'); relative.legend(loc='best',fontsize=8); style_axis(relative)
    last=result.rows[-1]; _panel(info); _panel_heading(info,'DISTURBANCE RESULT','Current is applied in the earth frame, rotated into the body frame at each integration step, then subtracted before hydrodynamic drag is evaluated.')
    _metric_grid(info,[('Current vector',f"[0.00, {float(last['current_y_mps']):.2f}]",'m/s ENU'),('Final x distance',f"{float(last['x_m']):.2f}",'m'),('Final y drift',f"{float(last['y_m']):.2f}",'m'),('Final heading',f"{float(last['psi_deg']):.2f}",'deg'),('Final surge speed',f"{float(last['u_mps']):.3f}",'m/s'),('Final relative sway',f"{float(last['v_relative_water_mps']):.3f}",'m/s'),],top=.78,height=.28)
    _bullets(info,'DESIGN IMPLICATION',["With no guidance controller, symmetric thrust cannot cancel cross-current drift. This scenario becomes the quantitative baseline for the path-guidance phase.","The mission planner will later use this disturbance model to maintain safe distance from obstacles and the collector path."],y=.42,width=48)
    return export_figure(fig,output,dpi=320)


def _acceptance_rows(metrics:list[dict[str,object]], s:DynamicsSettings, target_speed:float)->list[dict[str,object]]:
    calm=next(r for r in metrics if r['scenario']=='calm_straight'); turn=next(r for r in metrics if r['scenario']=='differential_turn'); current=next(r for r in metrics if r['scenario']=='cross_current')
    return [
        {'check':'Calm symmetric thrust reaches target-speed tolerance','observed':abs(float(calm['speed_error_to_target_mps'])),'criterion':s.steady_speed_tolerance_mps,'unit':'m/s','pass':abs(float(calm['speed_error_to_target_mps']))<=s.steady_speed_tolerance_mps},
        {'check':'Turn scenario produces non-zero heading change','observed':abs(float(turn['final_heading_deg'])),'criterion':5.0,'unit':'deg','pass':abs(float(turn['final_heading_deg']))>=5.0},
        {'check':'Yaw rate remains within design bound','observed':float(turn['max_abs_yaw_rate_rps']),'criterion':s.maximum_expected_yaw_rate_rps,'unit':'rad/s','pass':float(turn['max_abs_yaw_rate_rps'])<=s.maximum_expected_yaw_rate_rps},
        {'check':'Cross-current produces observable drift for guidance baseline','observed':abs(float(current['cross_track_drift_m'])),'criterion':s.straight_line_cross_track_limit_m,'unit':'m','pass':abs(float(current['cross_track_drift_m']))>=s.straight_line_cross_track_limit_m},
    ]


def _summary_markdown(path:Path,model:PlanarCatamaranDynamics,metrics:list[dict[str,object]],artifacts:Phase06Artifacts)->None:
    calm=next(r for r in metrics if r['scenario']=='calm_straight'); turn=next(r for r in metrics if r['scenario']=='differential_turn'); cross=next(r for r in metrics if r['scenario']=='cross_current')
    content=f"""# AquaSkim-Sim | Phase 06 — 3-DOF Dynamics Summary

## Model
The model integrates earth-fixed position and heading with body-fixed surge, sway and yaw rate using fourth-order Runge–Kutta. Hydrodynamic drag is evaluated from current-relative body velocity.

## Full-payload dynamic parameters
- Effective surge mass: `{model.mass.surge_mass_kg:.4f} kg`
- Effective sway mass: `{model.mass.sway_mass_kg:.4f} kg`
- Effective yaw inertia: `{model.mass.yaw_inertia_kg_m2:.5f} kg·m²`
- Thruster half-spacing: `{model.thruster_half_spacing_m:.3f} m`

## Scenario results
| Scenario | Final x [m] | Final y [m] | Final heading [deg] | Final surge [m/s] | Peak yaw rate [rad/s] |
|---|---:|---:|---:|---:|---:|
| Calm straight | {float(calm['final_x_m']):.3f} | {float(calm['final_y_m']):.3f} | {float(calm['final_heading_deg']):.2f} | {float(calm['final_u_mps']):.3f} | {float(calm['max_abs_yaw_rate_rps']):.3f} |
| Differential turn | {float(turn['final_x_m']):.3f} | {float(turn['final_y_m']):.3f} | {float(turn['final_heading_deg']):.2f} | {float(turn['final_u_mps']):.3f} | {float(turn['max_abs_yaw_rate_rps']):.3f} |
| Cross-current | {float(cross['final_x_m']):.3f} | {float(cross['final_y_m']):.3f} | {float(cross['final_heading_deg']):.2f} | {float(cross['final_u_mps']):.3f} | {float(cross['max_abs_yaw_rate_rps']):.3f} |

## Limits
- Uniform, constant current only; wave and wind forcing are excluded.
- Sway/yaw damping coefficients are transparent preliminary-design values.
- The phase prepares the plant model; autonomous guidance and feedback control are not yet applied.

## Artifacts
{chr(10).join(f'- `{value}`' for value in artifacts.as_dict().values())}
"""
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8')


def run_phase06(config:ProjectConfiguration|None=None)->Phase06Artifacts:
    ensure_runtime_directories(); cfg=config or load_base_configuration(); model,cruise_force=_build_model(cfg); results=_run_scenarios(model,cruise_force); target=float(cfg.data['propulsion']['limits']['target_cruise_speed_mps']); metrics=_scenario_metrics(results,target,model.settings)
    all_rows=[row for result in results.values() for row in result.rows]
    artifacts=Phase06Artifacts(
        dynamics_dashboard=DIRECTORIES['figures']/ 'phase06_dynamics_dashboard.png', dynamics_dashboard_svg=DIRECTORIES['figures']/ 'phase06_dynamics_dashboard.svg',
        trajectory_comparison=DIRECTORIES['figures']/ 'phase06_trajectory_comparison.png', trajectory_comparison_svg=DIRECTORIES['figures']/ 'phase06_trajectory_comparison.svg',
        maneuver_response=DIRECTORIES['figures']/ 'phase06_maneuver_response.png', maneuver_response_svg=DIRECTORIES['figures']/ 'phase06_maneuver_response.svg',
        current_disturbance=DIRECTORIES['figures']/ 'phase06_current_disturbance.png', current_disturbance_svg=DIRECTORIES['figures']/ 'phase06_current_disturbance.svg',
        parameter_table=DIRECTORIES['tables']/ 'phase06_dynamic_parameters.csv', scenario_metrics_table=DIRECTORIES['tables']/ 'phase06_scenario_metrics.csv', time_series_table=DIRECTORIES['tables']/ 'phase06_time_series.csv', acceptance_checks_table=DIRECTORIES['tables']/ 'phase06_acceptance_checks.csv',
        summary_json=DIRECTORIES['logs']/ 'phase06_dynamics_summary.json', summary_markdown=DIRECTORIES['reports']/ 'phase06_3dof_dynamics_summary.md', visual_quality_manifest=DIRECTORIES['logs']/ 'phase06_visual_quality_manifest.json',
    )
    exports=[_draw_dashboard(model,cruise_force,artifacts.dynamics_dashboard),_draw_trajectories(results,artifacts.trajectory_comparison),_draw_maneuver(results['differential_turn'],artifacts.maneuver_response),_draw_current(results['cross_current'],artifacts.current_disturbance)]
    assert_export_quality(exports)
    _write_csv(artifacts.parameter_table,[{**model.mass.as_row(), 'thruster_half_spacing_m':model.thruster_half_spacing_m, 'sway_linear_damping_n_per_mps':model.settings.sway_linear_damping_n_per_mps,'sway_quadratic_damping_n_per_mps2':model.settings.sway_quadratic_damping_n_per_mps2,'yaw_linear_damping_n_m_per_rps':model.settings.yaw_linear_damping_n_m_per_rps,'yaw_quadratic_damping_n_m_per_rps2':model.settings.yaw_quadratic_damping_n_m_per_rps2,'cruise_force_demand_n':cruise_force}])
    _write_csv(artifacts.scenario_metrics_table,metrics); _write_csv(artifacts.time_series_table,all_rows)
    checks=_acceptance_rows(metrics,model.settings,target); _write_csv(artifacts.acceptance_checks_table,checks)
    summary={'phase':'Phase 06 — 3-DOF Dynamics','configuration_file':relative_to_root(cfg.source_path),'model_basis':'Planar 3-DOF surge-sway-yaw; ground velocity state; current-relative drag; RK4 integration.','dynamic_mass':model.mass.as_row(),'cruise_force_demand_n':cruise_force,'scenario_metrics':metrics,'acceptance_checks':checks,'limitations':['Constant uniform current only.','No wave, wind, roll/pitch/heave, actuator lag or full added-mass Coriolis matrix.','Open-loop force commands only; feedback guidance/control follows in a later phase.'],'artifacts':artifacts.as_dict()}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    artifacts.visual_quality_manifest.write_text(json.dumps({'phase':'Phase 06 visual quality gate','quality_rule':{'minimum_png_width_px':3000,'minimum_png_height_px':1800,'formats':['PNG (report-ready raster)','SVG (vector)'],'layout_policy':'Technical text is isolated in fixed information panels; charts and geometry use restrained legends and non-overlapping labels.'},'exports':[e.as_dict() for e in exports]},ensure_ascii=False,indent=2),encoding='utf-8')
    _summary_markdown(artifacts.summary_markdown,model,metrics,artifacts)
    return artifacts


def print_phase06_summary(artifacts:Phase06Artifacts)->None:
    print('='*72); print('AquaSkim-Sim | Phase 06 3-DOF Dynamics'); print('='*72)
    for key,path in artifacts.as_dict().items(): print(f'{key:26}: {path}')
    print('='*72); print('[OK] Phase 06 dynamics figures, tables, report and visual-QA manifest generated.')
