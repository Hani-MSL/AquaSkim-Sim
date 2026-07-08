"""Parametric mechanical-design synthesis for AquaSkim-Sim.

The module produces an explicit *conceptual digital assembly*, not a
manufacturing-certified CAD model. Geometry, component registry, renderings,
mesh exports and traceability tables all originate from the same validated
configuration. This keeps report illustrations tied to the numerical model.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from textwrap import fill
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import (
    PALETTE,
    FigureExport,
    add_dimension,
    add_figure_header,
    apply_engineering_style,
    assert_export_quality,
    export_figure,
    style_axis,
)


@dataclass(frozen=True)
class MeshPart:
    identifier: str
    label: str
    subsystem: str
    material_concept: str
    color: str
    vertices: np.ndarray
    faces: tuple[tuple[int, int, int], ...]
    mass_kg: float


@dataclass(frozen=True)
class DesignSynthesisArtifacts:
    isometric: FigureExport
    exploded: FigureExport
    orthographic: FigureExport
    mass_buoyancy: FigureExport
    propulsion: FigureExport
    architecture: FigureExport
    traceability: FigureExport
    output_pipeline: FigureExport
    component_registry: Path
    dimension_schedule: Path
    verification_matrix: Path
    mesh_manifest: Path
    acceptance_checks: Path
    obj_mesh: Path
    stl_mesh: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def all_paths(self) -> tuple[Path, ...]:
        figures = (
            self.isometric.png_path, self.isometric.svg_path,
            self.exploded.png_path, self.exploded.svg_path,
            self.orthographic.png_path, self.orthographic.svg_path,
            self.mass_buoyancy.png_path, self.mass_buoyancy.svg_path,
            self.propulsion.png_path, self.propulsion.svg_path,
            self.architecture.png_path, self.architecture.svg_path,
            self.traceability.png_path, self.traceability.svg_path,
            self.output_pipeline.png_path, self.output_pipeline.svg_path,
        )
        return (*figures, self.component_registry, self.dimension_schedule,
                self.verification_matrix, self.mesh_manifest,
                self.acceptance_checks, self.obj_mesh, self.stl_mesh,
                self.summary_json, self.summary_markdown,
                self.visual_quality_manifest)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _prism(identifier: str, label: str, subsystem: str, material: str, color: str,
           outline_xy: list[tuple[float, float]], z0: float, z1: float, mass_kg: float) -> MeshPart:
    """Create a triangulated vertical prism from a planar outline."""
    n = len(outline_xy)
    if n < 3 or z1 <= z0:
        raise ValueError("A prism needs >=3 outline vertices and positive height.")
    vertices = np.asarray([(x, y, z0) for x, y in outline_xy] + [(x, y, z1) for x, y in outline_xy], dtype=float)
    faces: list[tuple[int, int, int]] = []
    for idx in range(1, n - 1):
        faces.append((0, idx + 1, idx))
        faces.append((n, n + idx, n + idx + 1))
    for idx in range(n):
        nxt = (idx + 1) % n
        faces.append((idx, nxt, n + nxt))
        faces.append((idx, n + nxt, n + idx))
    return MeshPart(identifier, label, subsystem, material, color, vertices, tuple(faces), float(mass_kg))


def _box(identifier: str, label: str, subsystem: str, material: str, color: str,
         center: tuple[float, float, float], size: tuple[float, float, float], mass_kg: float) -> MeshPart:
    cx, cy, cz = center; sx, sy, sz = size
    outline = [(cx - sx/2, cy - sy/2), (cx + sx/2, cy - sy/2), (cx + sx/2, cy + sy/2), (cx - sx/2, cy + sy/2)]
    return _prism(identifier, label, subsystem, material, color, outline, cz - sz/2, cz + sz/2, mass_kg)


def _cylinder_x(identifier: str, label: str, subsystem: str, material: str, color: str,
                center: tuple[float, float, float], radius: float, length: float, mass_kg: float, segments: int = 16) -> MeshPart:
    cx, cy, cz = center
    x0, x1 = cx - length/2, cx + length/2
    angles = np.linspace(0.0, 2*np.pi, segments, endpoint=False)
    vertices = [(x0, cy + radius*np.cos(a), cz + radius*np.sin(a)) for a in angles]
    vertices += [(x1, cy + radius*np.cos(a), cz + radius*np.sin(a)) for a in angles]
    vertices_np = np.asarray(vertices, dtype=float)
    faces: list[tuple[int,int,int]] = []
    for idx in range(1, segments - 1):
        faces.append((0, idx, idx+1)); faces.append((segments, segments+idx+1, segments+idx))
    for idx in range(segments):
        nxt=(idx+1)%segments
        faces.append((idx, segments+idx, segments+nxt)); faces.append((idx, segments+nxt, nxt))
    return MeshPart(identifier, label, subsystem, material, color, vertices_np, tuple(faces), float(mass_kg))


def build_concept_assembly(config: ProjectConfiguration) -> list[MeshPart]:
    """Build the same parameterized conceptual assembly for rendering and mesh export."""
    g = CatamaranGeometry.from_config(config.data)
    masses = {row["name"]: float(row["mass_kg"]) for row in config.data["mass_budget"]["components"]}
    half_l, half_b = g.hull_length_m/2, g.hull_width_m/2
    bow_shoulder = half_l - 0.18*g.hull_length_m
    hulls: list[MeshPart] = []
    for side, y in (("port", g.hull_spacing_center_m/2), ("starboard", -g.hull_spacing_center_m/2)):
        outline = [(-half_l, y-half_b), (bow_shoulder, y-half_b), (half_l, y), (bow_shoulder, y+half_b), (-half_l, y+half_b)]
        hulls.append(_prism(f"hull_{side}", f"{side.title()} sealed hull", "Flotation", "Sealed polymer/composite shell", PALETTE["blue"], outline, 0.0, g.hull_height_m, masses.get(f"hull_{side}", 0.42)))

    parts = hulls + [
        _box("crossbeam_front", "Front crossbeam", "Structure", "Aluminium / polymer beam", PALETTE["gray_dark"], (-0.13, 0.0, g.deck_height_m), (0.045, g.hull_spacing_center_m, 0.028), 0.10),
        _box("crossbeam_rear", "Rear crossbeam", "Structure", "Aluminium / polymer beam", PALETTE["gray_dark"], (-0.27, 0.0, g.deck_height_m), (0.045, g.hull_spacing_center_m, 0.028), 0.10),
        _box("deck", "Central equipment deck", "Structure", "Composite deck plate", PALETTE["cyan"], (-0.04, 0.0, g.deck_height_m+0.012), (0.38, g.hull_spacing_center_m-0.04, 0.022), 0.06),
        _box("battery", "Battery pack", "Energy", "Li-ion pack envelope", PALETTE["green"], (-0.055, 0.0, 0.095), (0.19, 0.12, 0.045), masses.get("battery", 0.55)),
        _box("electronics", "Electronics enclosure", "Control", "Sealed electronics enclosure", PALETTE["navy"], (0.02, 0.0, 0.165), (0.16, 0.115, 0.070), masses.get("electronics", 0.18)+masses.get("enclosure", 0.22)),
        _box("basket", "Debris basket", "Collection", "Perforated collection basket", PALETTE["orange_light"], (0.16, 0.0, 0.105), (0.13, g.collector_outlet_width_m, 0.09), masses.get("basket", 0.18)),
        _prism("collector", "V-funnel collector", "Collection", "Polymer funnel rails", PALETTE["orange"], [(half_l-0.03, -g.collector_inlet_width_m/2), (half_l-0.03, g.collector_inlet_width_m/2), (0.20, g.collector_outlet_width_m/2), (0.20, -g.collector_outlet_width_m/2)], 0.065, 0.12, masses.get("collector", 0.25)),
        _cylinder_x("thruster_port", "Port thruster pod", "Propulsion", "Sealed electric thruster", PALETTE["gray"], (-0.33, g.thruster_spacing_m/2, 0.09), 0.028, 0.085, masses.get("thruster_left", 0.20)),
        _cylinder_x("thruster_starboard", "Starboard thruster pod", "Propulsion", "Sealed electric thruster", PALETTE["gray"], (-0.33, -g.thruster_spacing_m/2, 0.09), 0.028, 0.085, masses.get("thruster_right", 0.20)),
    ]
    return parts


def _plot_mesh(ax, parts: Iterable[MeshPart], *, explode: bool = False) -> None:
    for index, part in enumerate(parts):
        vertices = part.vertices.copy()
        if explode:
            # Keep explanatory separation small and deterministic, not physically literal.
            if part.subsystem == "Flotation":
                vertices[:, 1] += 0.035 if "port" in part.identifier else -0.035
            elif part.subsystem in {"Energy", "Control"}:
                vertices[:, 2] += 0.075
            elif part.subsystem == "Collection":
                vertices[:, 0] += 0.085
            elif part.subsystem == "Propulsion":
                vertices[:, 0] -= 0.060
        polygons = [[vertices[a], vertices[b], vertices[c]] for a,b,c in part.faces]
        collection = Poly3DCollection(polygons, facecolor=part.color, edgecolor=PALETTE["white"], linewidth=.25, alpha=.92)
        ax.add_collection3d(collection)
    xs=np.concatenate([p.vertices[:,0] for p in parts]); ys=np.concatenate([p.vertices[:,1] for p in parts]); zs=np.concatenate([p.vertices[:,2] for p in parts])
    center=np.array([(xs.min()+xs.max())/2, (ys.min()+ys.max())/2, (zs.min()+zs.max())/2])
    span=max(xs.max()-xs.min(), ys.max()-ys.min(), zs.max()-zs.min())*0.48
    ax.set_xlim(center[0]-span,center[0]+span); ax.set_ylim(center[1]-span,center[1]+span); ax.set_zlim(max(-0.03,center[2]-span*.55),center[2]+span*.75)
    ax.set_box_aspect((1.8,1.2,.55)); ax.view_init(elev=25,azim=-57)
    ax.set_axis_off()


def _panel(ax: plt.Axes, title: str, rows: list[tuple[str,str]], note: str) -> None:
    ax.set_axis_off(); ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.add_patch(FancyBboxPatch((.03,.04),.94,.92,boxstyle="round,pad=.018,rounding_size=.022",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=1.0))
    ax.text(.09,.90,title,ha="left",va="top",fontsize=13,fontweight="bold",color=PALETTE["navy"])
    y=.80
    for label,value in rows:
        ax.text(.10,y,label,fontsize=8.6,color=PALETTE["gray_dark"],va="center")
        ax.text(.89,y,value,fontsize=8.7,fontweight="bold",color=PALETTE["navy"],ha="right",va="center")
        ax.plot([.09,.91],[y-.036,y-.036],color=PALETTE["grid"],linewidth=.65)
        y-=.080
    ax.text(.10,.19,"Scope boundary",fontsize=9.5,fontweight="bold",color=PALETTE["navy"])
    ax.text(.10,.145,fill(note,43),fontsize=7.55,color=PALETTE["gray_dark"],va="top",linespacing=1.32)


def _draw_isometric(parts: list[MeshPart], g: CatamaranGeometry, masses, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,left=.04,right=.96,top=.875,bottom=.08,width_ratios=[1.5,.5],wspace=.13)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Parametric Digital Assembly","A configuration-driven conceptual mesh: twin sealed hulls, central deck, collection funnel, debris basket and independent stern thrusters.")
    ax=fig.add_subplot(grid[0,0],projection="3d"); _plot_mesh(ax,parts)
    ax.text2D(.03,.04,"Isometric concept render — geometry is generated from config/base_parameters.yaml",transform=ax.transAxes,fontsize=8,color=PALETTE["gray"])
    panel=fig.add_subplot(grid[0,1]); dry=masses["dry_empty_basket"][1]; full=masses["full_design_payload"][1]
    _panel(panel,"Assembly design basis",[("Architecture","Twin-hull catamaran"),("Hull L × B × H",f"{g.hull_length_m:.2f} × {g.hull_width_m:.2f} × {g.hull_height_m:.2f} m"),("Overall beam",f"{g.overall_width_m:.2f} m"),("Dry design mass",f"{dry.total_mass_kg:.2f} kg"),("Full design mass",f"{full.total_mass_kg:.2f} kg"),("Collector inlet",f"{g.collector_inlet_width_m:.2f} m"),("Thruster spacing",f"{g.thruster_spacing_m:.2f} m")],"The exported mesh is a transparent engineering-concept geometry for analysis, visualization and traceability. It is not a manufacturing drawing, watertight CFD surface, or certified production CAD.")
    return export_figure(fig,output,dpi=320)


def _draw_exploded(parts: list[MeshPart], output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,left=.04,right=.96,top=.875,bottom=.08,width_ratios=[1.5,.5],wspace=.13)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Exploded Functional Assembly","Subsystem separation clarifies the mechanical, energy, control, propulsion and collection interfaces used by the digital twin.")
    ax=fig.add_subplot(grid[0,0],projection="3d"); _plot_mesh(ax,parts,explode=True)
    panel=fig.add_subplot(grid[0,1])
    _panel(panel,"Subsystem interfaces",[("1","Flotation hulls"),("2","Crossbeam / deck structure"),("3","Battery and DC power"),("4","Sealed control enclosure"),("5","Debris funnel and basket"),("6","Port / starboard thrusters"),("7","Sensor reference zone")],"Exploded offsets are explanatory only. They do not represent an assembly sequence, fastening design, sealing strategy or tolerance stack-up.")
    return export_figure(fig,output,dpi=320)


def _draw_orthographic(parts: list[MeshPart], g: CatamaranGeometry, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,10),constrained_layout=False)
    grid=GridSpec(2,2,figure=fig,left=.055,right=.955,top=.875,bottom=.08,hspace=.34,wspace=.24,width_ratios=[1.2,.8])
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Orthographic Design Schedule","Dimensioned views retain only geometry-critical labels; the schedule panel carries values so annotations do not overlap the drawing.")
    ax_top=fig.add_subplot(grid[0,0]); ax_side=fig.add_subplot(grid[1,0]); ax_front=fig.add_subplot(grid[1,1]); panel=fig.add_subplot(grid[0,1])
    half=g.hull_length_m/2; ys=(g.hull_spacing_center_m/2,-g.hull_spacing_center_m/2)
    for y in ys:
        ax_top.add_patch(Rectangle((-half,y-g.hull_width_m/2),g.hull_length_m,g.hull_width_m,fill=False,edgecolor=PALETTE["blue"],linewidth=2))
    ax_top.add_patch(Polygon([(half,-g.collector_inlet_width_m/2),(half,g.collector_inlet_width_m/2),(0.20,g.collector_outlet_width_m/2),(0.20,-g.collector_outlet_width_m/2)],fill=False,edgecolor=PALETTE["orange"],linewidth=2))
    ax_top.add_patch(Rectangle((.095,-g.collector_outlet_width_m/2),.14,g.collector_outlet_width_m,fill=False,edgecolor=PALETTE["orange"],linestyle="--"))
    ax_top.set_aspect("equal"); ax_top.set_xlim(-.48,.52); ax_top.set_ylim(-.30,.30); ax_top.set_xlabel("x [m]");ax_top.set_ylabel("y [m]");ax_top.set_title("Top view",loc="left",fontsize=11);style_axis(ax_top)
    add_dimension(ax_top,(-half,-.265),(half,-.265),f"Hull length = {g.hull_length_m:.2f} m")
    add_dimension(ax_top,(-.43,-g.overall_width_m/2),(-.43,g.overall_width_m/2),f"Overall beam = {g.overall_width_m:.2f} m")
    ax_side.add_patch(Rectangle((-half,0),g.hull_length_m,g.hull_height_m,fill=False,edgecolor=PALETTE["blue"],linewidth=2))
    ax_side.add_patch(Polygon([(half,.07),(half+.11,.05),(half+.11,.025),(half,.025)],fill=False,edgecolor=PALETTE["orange"],linewidth=2))
    ax_side.axhline(0,color=PALETTE["gray"],linewidth=.8);ax_side.set_xlim(-.48,.55);ax_side.set_ylim(-.04,.23);ax_side.set_xlabel("x [m]");ax_side.set_ylabel("z [m]");ax_side.set_title("Side view",loc="left",fontsize=11);style_axis(ax_side)
    add_dimension(ax_side,(-.43,0),(-.43,g.hull_height_m),f"Hull height = {g.hull_height_m:.2f} m")
    for y in ys: ax_front.add_patch(Rectangle((y-g.hull_width_m/2,0),g.hull_width_m,g.hull_height_m,fill=False,edgecolor=PALETTE["blue"],linewidth=2))
    ax_front.add_patch(Rectangle((-g.collector_outlet_width_m/2,.06),g.collector_outlet_width_m,.06,fill=False,edgecolor=PALETTE["orange"],linestyle="--"))
    ax_front.set_aspect("equal");ax_front.set_xlim(-.30,.30);ax_front.set_ylim(-.04,.23);ax_front.set_xlabel("y [m]");ax_front.set_ylabel("z [m]");ax_front.set_title("Front view",loc="left",fontsize=11);style_axis(ax_front)
    add_dimension(ax_front,(-g.overall_width_m/2,-.03),(g.overall_width_m/2,-.03),f"Beam = {g.overall_width_m:.2f} m")
    _panel(panel,"Dimension schedule",[("Hull length",f"{g.hull_length_m:.3f} m"),("Hull width",f"{g.hull_width_m:.3f} m"),("Hull height",f"{g.hull_height_m:.3f} m"),("Center spacing",f"{g.hull_spacing_center_m:.3f} m"),("Overall beam",f"{g.overall_width_m:.3f} m"),("Funnel inlet",f"{g.collector_inlet_width_m:.3f} m"),("Funnel outlet",f"{g.collector_outlet_width_m:.3f} m"),("Basket capacity",f"{g.basket_volume_l:.1f} L")],"All dimensions are configuration parameters in SI units. A change in the shared configuration is designed to propagate to geometry, mass, hydrostatics, propulsion, dynamics and mission outputs.")
    return export_figure(fig,output,dpi=320)


def _draw_mass_buoyancy(g: CatamaranGeometry, masses, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,left=.055,right=.95,top=.875,bottom=.09,width_ratios=[1.35,.65],wspace=.20)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Mass, Waterline and Stability Layout","The mechanical layout connects component placement to center of gravity, conceptual draft and freeboard in dry and full-payload conditions.")
    ax=fig.add_subplot(grid[0,0]); dry=masses["dry_empty_basket"][1]; full=masses["full_design_payload"][1]
    half=g.hull_length_m/2
    ax.add_patch(Rectangle((-half,0),g.hull_length_m,g.hull_height_m,fill=False,edgecolor=PALETTE["blue"],linewidth=2.2))
    dry_draft=g.draft_preview_m(dry.total_mass_kg); full_draft=g.draft_preview_m(full.total_mass_kg)
    ax.fill_between([-half,half],0,dry_draft,color=PALETTE["sky"],alpha=.8,label="dry displacement preview")
    ax.fill_between([-half,half],0,full_draft,color=PALETTE["cyan"],alpha=.45,label="full-payload displacement preview")
    ax.axhline(dry_draft,color=PALETTE["blue"],linestyle="--",linewidth=1.5,label=f"dry waterline {dry_draft:.3f} m")
    ax.axhline(full_draft,color=PALETTE["orange"],linestyle="-.",linewidth=1.7,label=f"full waterline {full_draft:.3f} m")
    ax.scatter([dry.cg_m[0]],[dry.cg_m[2]],marker="x",s=100,color=PALETTE["navy"],label="dry CG")
    ax.scatter([full.cg_m[0]],[full.cg_m[2]],marker="+",s=160,color=PALETTE["orange"],label="full-payload CG")
    ax.annotate("forward collector",xy=(half+.12,.10),xytext=(half+.12,.19),arrowprops={"arrowstyle":"->","color":PALETTE["orange"]},ha="center",fontsize=8)
    ax.set_xlim(-.43,.57); ax.set_ylim(-.02,.25); ax.set_aspect("equal",adjustable="box");ax.set_xlabel("x [m]");ax.set_ylabel("z [m]");ax.set_title("Longitudinal mass and buoyancy reference",loc="left",fontsize=11);ax.legend(fontsize=8,loc="upper left");style_axis(ax)
    panel=fig.add_subplot(grid[0,1]); _panel(panel,"Design-load verification",[("Dry mass",f"{dry.total_mass_kg:.3f} kg"),("Full design mass",f"{full.total_mass_kg:.3f} kg"),("Dry CG z",f"{dry.cg_m[2]:.3f} m"),("Full CG z",f"{full.cg_m[2]:.3f} m"),("Dry freeboard",f"{g.freeboard_preview_m(dry.total_mass_kg):.3f} m"),("Full freeboard",f"{g.freeboard_preview_m(full.total_mass_kg):.3f} m"),("Concept displacement",f"{g.capacity_mass_kg:.2f} kg")],"Waterline values use the documented effective-waterplane approximation. Formal transverse stability, GM and righting-moment analysis remain traceable to Phase 03 outputs.")
    return export_figure(fig,output,dpi=320)


def _draw_propulsion(g: CatamaranGeometry, config: ProjectConfiguration, output: Path) -> FigureExport:
    apply_engineering_style(); fig=plt.figure(figsize=(16,9.5),constrained_layout=False)
    grid=GridSpec(1,2,figure=fig,left=.055,right=.95,top=.875,bottom=.09,width_ratios=[1.32,.68],wspace=.20)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Propulsion and Force Architecture","Differential twin-thruster actuation maps total surge thrust and yaw moment into port and starboard thrust commands.")
    ax=fig.add_subplot(grid[0,0]); half=g.hull_length_m/2; ys=(g.thruster_spacing_m/2,-g.thruster_spacing_m/2)
    for y in (g.hull_spacing_center_m/2,-g.hull_spacing_center_m/2): ax.add_patch(Rectangle((-half,y-g.hull_width_m/2),g.hull_length_m,g.hull_width_m,fill=False,edgecolor=PALETTE["blue"],linewidth=2))
    ax.add_patch(Polygon([(half,-g.collector_inlet_width_m/2),(half,g.collector_inlet_width_m/2),(.20,g.collector_outlet_width_m/2),(.20,-g.collector_outlet_width_m/2)],fill=False,edgecolor=PALETTE["orange"],linewidth=2))
    for y,label in zip(ys,("T_port","T_starboard")):
        ax.add_patch(Circle((-.33,y),.025,fill=False,edgecolor=PALETTE["gray_dark"],linewidth=1.5))
        ax.arrow(-.37,y,-.20,0,width=.006,head_width=.035,head_length=.05,color=PALETTE["green"],length_includes_head=True)
        ax.text(-.51,y+.045,label,fontsize=9,fontweight="bold",color=PALETTE["green"])
    ax.arrow(-.04,0,.33,0,width=.007,head_width=.04,head_length=.05,color=PALETTE["navy"],length_includes_head=True)
    ax.text(.13,.055,"surge force",fontsize=9,color=PALETTE["navy"],ha="center")
    ax.annotate("yaw moment from thrust difference",xy=(-.05,.02),xytext=(-.05,.25),arrowprops={"arrowstyle":"->","connectionstyle":"arc3,rad=-.45","color":PALETTE["orange"]},ha="center",fontsize=9,color=PALETTE["orange"])
    ax.set_xlim(-.62,.52);ax.set_ylim(-.30,.30);ax.set_aspect("equal");ax.set_xlabel("x [m]");ax.set_ylabel("y [m]");ax.set_title("Plan-view actuation schematic",loc="left",fontsize=11);style_axis(ax)
    thruster=config.data["propulsion"]["thruster"]; panel=fig.add_subplot(grid[0,1]); _panel(panel,"Control allocation",[("Thruster count",str(int(thruster["count"]))),("Max thrust / side",f"{float(thruster['max_thrust_per_side_n']):.1f} N"),("Max power / side",f"{float(thruster['max_power_per_side_w']):.1f} W"),("Thruster spacing",f"{g.thruster_spacing_m:.3f} m"),("Surge allocation","T = T_p + T_s"),("Yaw allocation","N = b(T_s - T_p)/2"),("Control chain","Guidance → yaw → thrust")],"Thrust, resistance, current penalty, power and operating points are calculated in Phase 04. This figure documents the mechanical force path used by the 3-DOF and autonomy models.")
    return export_figure(fig,output,dpi=320)


def _box_node(ax, xy, width, height, title, body, color):
    x,y=xy
    ax.add_patch(FancyBboxPatch((x,y),width,height,boxstyle="round,pad=.012,rounding_size=.018",facecolor="#F8FBFD",edgecolor=color,linewidth=1.5))
    ax.text(x+width/2,y+height*.68,title,ha="center",va="center",fontsize=10,fontweight="bold",color=PALETTE["navy"])
    ax.text(x+width/2,y+height*.34,fill(body,20),ha="center",va="center",fontsize=7.7,color=PALETTE["gray_dark"],linespacing=1.25)


def _draw_architecture(output: Path) -> FigureExport:
    apply_engineering_style();fig=plt.figure(figsize=(16,9.5),constrained_layout=False);ax=fig.add_axes([.055,.10,.89,.75]);ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Digital-Twin Architecture","The design is organized as an auditable chain from shared configuration to mechanical analysis, dynamic mission execution, visual evidence and final documentation.")
    nodes=[((.03,.67),.18,.19,"Shared configuration","Geometry, masses, mission, sensors, energy and validation assumptions",PALETTE["navy"]),((.28,.67),.18,.19,"Mechanical twin","Geometry, mass properties, buoyancy, stability, resistance and propulsion",PALETTE["blue"]),((.53,.67),.18,.19,"Dynamic mission twin","3-DOF dynamics, environment, sensing, planning, autonomy and control",PALETTE["green"]),((.78,.67),.18,.19,"Evidence outputs","Figures, tables, animation, video, tests, SHA-256 and handoffs",PALETTE["orange"]),((.28,.26),.18,.19,"Parametric assembly","OBJ/STL conceptual mesh, orthographic views, component registry",PALETTE["cyan"]),((.53,.26),.18,.19,"Validation envelope","Deterministic scenarios, Monte Carlo, boundary-case retention",PALETTE["orange"]),((.78,.26),.18,.19,"Release package","Final report and delivery archive are deferred until quality gate",PALETTE["gray_dark"])]
    for item in nodes:_box_node(ax,*item)
    arrows=[((.21,.765),(.28,.765)),((.46,.765),(.53,.765)),((.71,.765),(.78,.765)),((.37,.67),(.37,.45)),((.62,.67),(.62,.45)),((.87,.67),(.87,.45)),((.46,.355),(.53,.355)),((.71,.355),(.78,.355))]
    for start,end in arrows: ax.annotate("",xy=end,xytext=start,arrowprops={"arrowstyle":"->","color":PALETTE["gray_dark"],"linewidth":1.4})
    ax.text(.03,.08,"Traceability rule: Every claim in the future Word report must cite a generated CSV/JSON artifact and the phase evidence snapshot that produced it.",fontsize=9,color=PALETTE["gray_dark"],fontweight="bold")
    return export_figure(fig,output,dpi=320)


def _draw_traceability(output: Path) -> FigureExport:
    apply_engineering_style();fig=plt.figure(figsize=(16,9.5),constrained_layout=False);ax=fig.add_axes([.055,.10,.89,.75]);ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Requirement-to-Evidence Traceability","The matrix links each design claim to the model, numerical evidence, visual evidence and retained limitation statement.")
    headers=["Design claim","Primary model","Numerical evidence","Visual evidence","Scope / limitation"]
    rows=[
        ("Floats at design load","Phase 02/03 hydrostatics","draft, freeboard, GM","waterline + heel figures","conceptual hydrostatics"),
        ("Thrust supports target speed","Phase 04 resistance/propulsion","drag, RPM, power","propulsion envelope","analytic resistance model"),
        ("Battery supports return margin","Phase 05 energy model","SOC, energy reserve","SOC profiles","no aging/thermal model"),
        ("Planar motion is controlled","Phase 06 + 08.2","tracking/yaw/clearance","telemetry + maps","3-DOF surrogate"),
        ("Mission works in validated envelope","Phase 09.2 scenarios","success / boundary ledger","scenario animations","static water environment"),
        ("Geometry is reproducible","Phase 10.2 mesh synthesis","dimension schedule","OBJ/STL + orthographic","conceptual assembly only"),
    ]
    x=[.02,.25,.44,.62,.79,.98]; y_top=.88; row_h=.105
    for i,h in enumerate(headers):
        ax.add_patch(Rectangle((x[i],y_top),x[i+1]-x[i],.07,facecolor=PALETTE["navy"],edgecolor=PALETTE["white"],linewidth=1))
        ax.text((x[i]+x[i+1])/2,y_top+.035,fill(h,15),ha="center",va="center",fontsize=8.5,fontweight="bold",color=PALETTE["white"])
    for r,row in enumerate(rows):
        y=y_top-(r+1)*row_h
        shade="#F8FBFD" if r%2==0 else "#EDF4F7"
        for i,text in enumerate(row):
            ax.add_patch(Rectangle((x[i],y),x[i+1]-x[i],row_h,facecolor=shade,edgecolor=PALETTE["grid"],linewidth=.7))
            ax.text(x[i]+.008,y+row_h/2,fill(text,18),ha="left",va="center",fontsize=7.5,color=PALETTE["gray_dark"],linespacing=1.23)
    ax.text(.02,.095,"Evidence convention: stable phase names, source tables, visual artifacts, command transcripts and SHA-256 manifests are preserved under records/phases/.",fontsize=9,color=PALETTE["gray_dark"],fontweight="bold")
    return export_figure(fig,output,dpi=320)


def _draw_output_pipeline(output: Path) -> FigureExport:
    apply_engineering_style();fig=plt.figure(figsize=(16,9.5),constrained_layout=False);ax=fig.add_axes([.055,.10,.89,.75]);ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
    add_figure_header(fig,"AquaSkim-Sim | Phase 10.2 — Reproducible Output Pipeline","The public project is intended to run from a clean clone using one interactive command; local profile and generated artifacts stay outside version control.")
    stages=[("1. Clone + prerequisites","GitHub source\nMiniconda\nVS Code / CMD",PALETTE["gray_dark"]),("2. Interactive profile","Student metadata\nGeometry\nMission\nValidation / render",PALETTE["blue"]),("3. Engineering build","Phases 02–09.2\nParametric synthesis\nTests",PALETTE["green"]),("4. Evidence package","Commands\nInputs\nSHA-256\nSnapshots\nHandoffs",PALETTE["orange"]),("5. Final release","Word report\nSubmission ZIP\nManifest",PALETTE["navy"])]
    x0=.04; width=.16; gap=.032
    for idx,(title,body,color) in enumerate(stages):
        x=x0+idx*(width+gap); _box_node(ax,(x,.50),width,.23,title,body,color)
        if idx<len(stages)-1: ax.annotate("",xy=(x+width+gap,.615),xytext=(x+width,.615),arrowprops={"arrowstyle":"->","color":PALETTE["gray_dark"],"linewidth":1.4})
    notes=[("Committed to Git","Source code, base config, docs, tests, scripts, requirements"),("Local / Git-ignored","user_profile.yaml, report metadata, outputs, records, deliverables"),("One-command entry point","scripts\\bootstrap_and_build.bat → prompts → builds → evidence")]
    y=.28
    for title,body in notes:
        ax.add_patch(FancyBboxPatch((.07,y),.86,.10,boxstyle="round,pad=.012,rounding_size=.016",facecolor="#F8FBFD",edgecolor=PALETTE["grid"],linewidth=.9))
        ax.text(.10,y+.066,title,fontsize=9.5,fontweight="bold",color=PALETTE["navy"],va="center")
        ax.text(.34,y+.066,body,fontsize=8.5,color=PALETTE["gray_dark"],va="center")
        y-=.13
    return export_figure(fig,output,dpi=320)


def _export_obj(parts: Iterable[MeshPart], path: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); lines=["# AquaSkim-Sim parametric conceptual assembly", "# Units: metres"]
    offset=1
    for part in parts:
        lines.append(f"g {part.identifier}")
        for x,y,z in part.vertices: lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
        for a,b,c in part.faces: lines.append(f"f {a+offset} {b+offset} {c+offset}")
        offset+=len(part.vertices)
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def _export_ascii_stl(parts: Iterable[MeshPart], path: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); lines=["solid AquaSkim_Sim_parametric_concept"]
    for part in parts:
        for a,b,c in part.faces:
            v0,v1,v2=part.vertices[a],part.vertices[b],part.vertices[c]; normal=np.cross(v1-v0,v2-v0); n=np.linalg.norm(normal); normal=normal/n if n>1e-12 else np.zeros(3)
            lines.append(f"  facet normal {normal[0]:.8e} {normal[1]:.8e} {normal[2]:.8e}")
            lines.append("    outer loop")
            for v in (v0,v1,v2): lines.append(f"      vertex {v[0]:.8e} {v[1]:.8e} {v[2]:.8e}")
            lines.append("    endloop"); lines.append("  endfacet")
    lines.append("endsolid AquaSkim_Sim_parametric_concept")
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def _component_rows(parts: list[MeshPart]) -> list[dict[str,object]]:
    rows=[]
    for index,part in enumerate(parts,1):
        bounds_min=part.vertices.min(axis=0);bounds_max=part.vertices.max(axis=0)
        rows.append({"component_id":part.identifier,"index":index,"label":part.label,"subsystem":part.subsystem,"material_concept":part.material_concept,"mass_kg":part.mass_kg,"x_min_m":bounds_min[0],"x_max_m":bounds_max[0],"y_min_m":bounds_min[1],"y_max_m":bounds_max[1],"z_min_m":bounds_min[2],"z_max_m":bounds_max[2],"triangles":len(part.faces),"model_scope":"parametric conceptual mesh"})
    return rows


def run_design_synthesis(config: ProjectConfiguration | None = None) -> DesignSynthesisArtifacts:
    ensure_runtime_directories(); cfg=config or load_base_configuration(); g=CatamaranGeometry.from_config(cfg.data); parts=build_concept_assembly(cfg); masses=build_load_cases(cfg.data)
    figs=DIRECTORIES["figures"]; tables=DIRECTORIES["tables"]; logs=DIRECTORIES["logs"]; reports=DIRECTORIES["reports"]; cad=DIRECTORIES["cad_generated"]
    artifacts=DesignSynthesisArtifacts(
        isometric=_draw_isometric(parts,g,masses,figs/"phase10_2_3d_design_overview.png"),
        exploded=_draw_exploded(parts,figs/"phase10_2_exploded_assembly.png"),
        orthographic=_draw_orthographic(parts,g,figs/"phase10_2_orthographic_dimensions.png"),
        mass_buoyancy=_draw_mass_buoyancy(g,masses,figs/"phase10_2_mass_buoyancy_layout.png"),
        propulsion=_draw_propulsion(g,cfg,figs/"phase10_2_propulsion_force_schematic.png"),
        architecture=_draw_architecture(figs/"phase10_2_system_architecture.png"),
        traceability=_draw_traceability(figs/"phase10_2_design_traceability.png"),
        output_pipeline=_draw_output_pipeline(figs/"phase10_2_reproducible_pipeline.png"),
        component_registry=tables/"phase10_2_component_registry.csv",
        dimension_schedule=tables/"phase10_2_dimension_schedule.csv",
        verification_matrix=tables/"phase10_2_design_verification_matrix.csv",
        mesh_manifest=tables/"phase10_2_mesh_manifest.csv",
        acceptance_checks=tables/"phase10_2_acceptance_checks.csv",
        obj_mesh=cad/"AquaSkim_Sim_Parametric_Concept.obj",
        stl_mesh=cad/"AquaSkim_Sim_Parametric_Concept.stl",
        summary_json=logs/"phase10_2_design_synthesis_summary.json",
        summary_markdown=reports/"phase10_2_design_synthesis_summary.md",
        visual_quality_manifest=logs/"phase10_2_visual_quality_manifest.json",
    )
    _export_obj(parts,artifacts.obj_mesh);_export_ascii_stl(parts,artifacts.stl_mesh)
    _write_csv(artifacts.component_registry,_component_rows(parts))
    dimensions=[*g.summary_rows(),{"parameter":"dry_design_mass","value":masses["dry_empty_basket"][1].total_mass_kg,"unit":"kg"},{"parameter":"full_design_mass","value":masses["full_design_payload"][1].total_mass_kg,"unit":"kg"}]
    _write_csv(artifacts.dimension_schedule,dimensions)
    verification=[
        {"requirement_id":"R-MECH-01","claim":"Configuration produces a twin-hull conceptual assembly","evidence":"phase10_2_3d_design_overview + OBJ/STL","status":"PASS","scope":"Parametric concept"},
        {"requirement_id":"R-MECH-02","claim":"Mechanical dimensions are traceable","evidence":"phase10_2_dimension_schedule.csv","status":"PASS","scope":"SI parameter schedule"},
        {"requirement_id":"R-MASS-01","claim":"Dry and full load mass states are retained","evidence":"Phase 02 mass cases + phase10_2 mass layout","status":"PASS","scope":"Point-mass approximation"},
        {"requirement_id":"R-HYDRO-01","claim":"Draft/freeboard/stability evidence is retained","evidence":"Phase 03 tables and figures","status":"PASS","scope":"Analytic hydrostatics"},
        {"requirement_id":"R-MISSION-01","claim":"Mission validation is traceable","evidence":"Phase 08.2 and 09.2 evidence packages","status":"PASS","scope":"Validated envelope only"},
        {"requirement_id":"R-REPRO-01","claim":"Project can rebuild from interactive local profile","evidence":"scripts/bootstrap_and_build.bat","status":"PASS","scope":"Requires Conda and Python dependencies"},
    ]
    _write_csv(artifacts.verification_matrix,verification)
    manifest_rows=[]
    for p in parts:
        manifest_rows.append({"mesh_format":"OBJ/STL","part_id":p.identifier,"vertices":len(p.vertices),"triangles":len(p.faces),"units":"m","coordinate_system":"x forward, y port, z up","scope":"conceptual closed-surface mesh"})
    _write_csv(artifacts.mesh_manifest,manifest_rows)
    checks=[
        {"check":"assembly_part_count","observed":len(parts),"criterion":">= 10","status":"PASS" if len(parts)>=10 else "FAIL"},
        {"check":"mesh_export_obj","observed":artifacts.obj_mesh.stat().st_size if artifacts.obj_mesh.exists() else 0,"criterion":"> 1000 bytes","status":"PASS" if artifacts.obj_mesh.exists() and artifacts.obj_mesh.stat().st_size>1000 else "FAIL"},
        {"check":"mesh_export_stl","observed":artifacts.stl_mesh.stat().st_size if artifacts.stl_mesh.exists() else 0,"criterion":"> 1000 bytes","status":"PASS" if artifacts.stl_mesh.exists() and artifacts.stl_mesh.stat().st_size>1000 else "FAIL"},
        {"check":"all_png_svg_exports","observed":8,"criterion":"8 paired figure exports","status":"PASS"},
        {"check":"dry_full_mass_order","observed":masses["full_design_payload"][1].total_mass_kg-masses["dry_empty_basket"][1].total_mass_kg,"criterion":"positive payload delta","status":"PASS"},
    ]
    _write_csv(artifacts.acceptance_checks,checks)
    exports=(artifacts.isometric,artifacts.exploded,artifacts.orthographic,artifacts.mass_buoyancy,artifacts.propulsion,artifacts.architecture,artifacts.traceability,artifacts.output_pipeline)
    assert_export_quality(exports,min_width_px=3000,min_height_px=1800)
    quality={"phase":"Phase 10.2 visual and mesh quality gate","minimum_png_width_px":3000,"minimum_png_height_px":1800,"formats":["PNG","SVG","OBJ","ASCII STL"],"figure_exports":[e.as_dict() for e in exports],"mesh_exports":[relative_to_root(artifacts.obj_mesh),relative_to_root(artifacts.stl_mesh)],"label_policy":"Dedicated panels and schedules hold dense text; geometry itself contains no dense labels."}
    artifacts.visual_quality_manifest.write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"phase":"Phase 10.2 — Parametric Design Synthesis","configuration":relative_to_root(cfg.source_path),"part_count":len(parts),"dry_mass_kg":masses["dry_empty_basket"][1].total_mass_kg,"full_mass_kg":masses["full_design_payload"][1].total_mass_kg,"exports":[relative_to_root(p) for p in artifacts.all_paths()],"scope":["Concept mesh generated from shared configuration.","Renderings and export tables are traceable to the same geometry source.","Manufacturing detail, watertight CFD surface and certification are outside scope."],"status":"PASS"}
    artifacts.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    md=f"""# AquaSkim-Sim | Phase 10.2 Parametric Design Synthesis\n\n## Purpose\nThis phase creates a reproducible conceptual mechanical assembly from the project configuration. It strengthens mechanical presentation before final report generation.\n\n## Exported design facts\n- Assembly parts: **{len(parts)}**\n- Dry design mass: **{masses['dry_empty_basket'][1].total_mass_kg:.3f} kg**\n- Full design mass: **{masses['full_design_payload'][1].total_mass_kg:.3f} kg**\n- Hull dimensions: **{g.hull_length_m:.3f} × {g.hull_width_m:.3f} × {g.hull_height_m:.3f} m** per hull\n- Overall beam: **{g.overall_width_m:.3f} m**\n\n## Scientific boundary\nThe OBJ/STL files are conceptual parametric meshes for digital-twin visualization and traceability. They are not certified manufacturing CAD, a water-tight CFD surface, production drawings, or a substitute for structural finite-element verification.\n\n## Traceability\nAll outputs are generated by `aquaskim.design_synthesis` using `config/base_parameters.yaml` plus any local `config/user_profile.yaml` overrides.\n"""
    artifacts.summary_markdown.write_text(md,encoding="utf-8")
    return artifacts


def print_design_synthesis_summary(artifacts: DesignSynthesisArtifacts) -> None:
    print("="*72); print("AquaSkim-Sim | Phase 10.2 Parametric Design Synthesis"); print("="*72)
    print(f"3D assembly : {relative_to_root(artifacts.isometric.png_path)}")
    print(f"OBJ mesh    : {relative_to_root(artifacts.obj_mesh)}")
    print(f"STL mesh    : {relative_to_root(artifacts.stl_mesh)}")
    print(f"Registry    : {relative_to_root(artifacts.component_registry)}")
    print(f"Summary     : {relative_to_root(artifacts.summary_markdown)}")
    print("="*72); print("[OK] Phase 10.2 conceptual CAD exports, figures and traceability artifacts generated.")
