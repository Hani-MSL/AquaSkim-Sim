"""Formal Phase 03 hydrostatic and transverse-stability model.

The catamaran is represented by two identical effective waterplane strips.  The
small-angle result uses standard hydrostatics (KB, BM, KG and GM).  A separate
numerical strip-integration model evaluates finite heel, clips emerged or
submerged strips to the hull height, and produces a transparent nonlinear GZ
curve suitable for this conceptual design stage.

This is deliberately not a CFD model.  It is a reproducible hydrostatic model
for calm water.  Every simplification is recorded in the phase documentation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import radians, sin, cos, tan
from typing import Any, Iterable

import numpy as np

from aquaskim.geometry import CatamaranGeometry
from aquaskim.mass_properties import MassProperties


class HydrostaticsError(ValueError):
    """Raised when hydrostatic inputs cannot form a physical case."""


@dataclass(frozen=True)
class HydrostaticSettings:
    water_density_kg_m3: float
    gravity_mps2: float
    kb_draft_fraction: float
    transverse_strip_count_per_hull: int
    analysis_heel_max_deg: float
    analysis_heel_step_deg: float
    linear_model_valid_to_deg: float
    operational_heel_limit_deg: float
    minimum_gm_m: float
    minimum_freeboard_m: float
    emergence_draft_tolerance_m: float
    payload_envelope_points: int

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "HydrostaticSettings":
        source = data["hydrostatics"]
        settings = cls(
            water_density_kg_m3=float(source["water_density_kg_m3"]),
            gravity_mps2=float(source["gravity_mps2"]),
            kb_draft_fraction=float(source["kb_draft_fraction"]),
            transverse_strip_count_per_hull=int(source["transverse_strip_count_per_hull"]),
            analysis_heel_max_deg=float(source["analysis_heel_max_deg"]),
            analysis_heel_step_deg=float(source["analysis_heel_step_deg"]),
            linear_model_valid_to_deg=float(source["linear_model_valid_to_deg"]),
            operational_heel_limit_deg=float(source["operational_heel_limit_deg"]),
            minimum_gm_m=float(source["minimum_gm_m"]),
            minimum_freeboard_m=float(source["minimum_freeboard_m"]),
            emergence_draft_tolerance_m=float(source["emergence_draft_tolerance_m"]),
            payload_envelope_points=int(source["payload_envelope_points"]),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        positive = {
            "water_density_kg_m3": self.water_density_kg_m3,
            "gravity_mps2": self.gravity_mps2,
            "analysis_heel_max_deg": self.analysis_heel_max_deg,
            "analysis_heel_step_deg": self.analysis_heel_step_deg,
            "operational_heel_limit_deg": self.operational_heel_limit_deg,
            "minimum_gm_m": self.minimum_gm_m,
            "minimum_freeboard_m": self.minimum_freeboard_m,
            "emergence_draft_tolerance_m": self.emergence_draft_tolerance_m,
        }
        for name, value in positive.items():
            if value <= 0.0:
                raise HydrostaticsError(f"{name} must be positive.")
        if not 0.0 < self.kb_draft_fraction <= 1.0:
            raise HydrostaticsError("kb_draft_fraction must be in (0, 1].")
        if self.transverse_strip_count_per_hull < 21:
            raise HydrostaticsError("transverse_strip_count_per_hull must be at least 21.")
        if self.payload_envelope_points < 3:
            raise HydrostaticsError("payload_envelope_points must be at least 3.")
        if self.linear_model_valid_to_deg > self.analysis_heel_max_deg:
            raise HydrostaticsError("linear_model_valid_to_deg must not exceed analysis_heel_max_deg.")


@dataclass(frozen=True)
class HydrostaticCase:
    name: str
    total_mass_kg: float
    displacement_volume_m3: float
    draft_m: float
    freeboard_m: float
    kb_m: float
    kg_m: float
    transverse_waterplane_moment_m4: float
    bm_m: float
    gm_m: float
    capacity_ratio: float

    def as_row(self) -> dict[str, object]:
        return {
            "load_case": self.name,
            "total_mass_kg": self.total_mass_kg,
            "displacement_volume_m3": self.displacement_volume_m3,
            "draft_m": self.draft_m,
            "freeboard_m": self.freeboard_m,
            "KB_m": self.kb_m,
            "KG_m": self.kg_m,
            "I_T_waterplane_m4": self.transverse_waterplane_moment_m4,
            "BM_m": self.bm_m,
            "GM_m": self.gm_m,
            "capacity_ratio": self.capacity_ratio,
        }


@dataclass(frozen=True)
class HeelState:
    heel_deg: float
    equilibrium_draft_m: float
    port_mean_draft_m: float
    starboard_mean_draft_m: float
    port_min_draft_m: float
    starboard_min_draft_m: float
    port_max_draft_m: float
    starboard_max_draft_m: float
    min_freeboard_m: float
    cb_y_m: float
    cb_z_m: float
    gz_nonlinear_m: float
    gz_linear_m: float
    righting_moment_n_m: float
    hull_partially_emerged: bool

    def as_row(self, case_name: str) -> dict[str, object]:
        return {
            "load_case": case_name,
            "heel_deg": self.heel_deg,
            "equilibrium_draft_m": self.equilibrium_draft_m,
            "port_mean_draft_m": self.port_mean_draft_m,
            "starboard_mean_draft_m": self.starboard_mean_draft_m,
            "port_min_draft_m": self.port_min_draft_m,
            "starboard_min_draft_m": self.starboard_min_draft_m,
            "port_max_draft_m": self.port_max_draft_m,
            "starboard_max_draft_m": self.starboard_max_draft_m,
            "min_freeboard_m": self.min_freeboard_m,
            "CB_y_m": self.cb_y_m,
            "CB_z_m": self.cb_z_m,
            "GZ_nonlinear_m": self.gz_nonlinear_m,
            "GZ_linear_m": self.gz_linear_m,
            "righting_moment_n_m": self.righting_moment_n_m,
            "hull_partially_emerged": self.hull_partially_emerged,
        }


class CatamaranHydrostatics:
    """Hydrostatic calculations for the parametric two-hull concept."""

    def __init__(self, geometry: CatamaranGeometry, settings: HydrostaticSettings):
        self.geometry = geometry
        self.settings = settings
        self._effective_width_m = geometry.hull_width_m * geometry.waterplane_shape_factor
        self._half_effective_width_m = self._effective_width_m / 2.0
        self._port_center_y_m, self._starboard_center_y_m = geometry.hull_centerlines_y_m()

    @property
    def waterplane_area_per_hull_m2(self) -> float:
        return self.geometry.hull_length_m * self._effective_width_m

    @property
    def total_waterplane_area_m2(self) -> float:
        return 2.0 * self.waterplane_area_per_hull_m2

    @property
    def transverse_waterplane_moment_m4(self) -> float:
        """I_T about the longitudinal centreline using parallel-axis theorem."""
        local_moment = (
            self.geometry.hull_length_m * self._effective_width_m**3 / 12.0
        )
        per_hull = local_moment + self.waterplane_area_per_hull_m2 * self._port_center_y_m**2
        return 2.0 * per_hull

    @property
    def maximum_strip_displacement_m3(self) -> float:
        return self.total_waterplane_area_m2 * self.geometry.hull_height_m

    def case_from_mass_properties(self, name: str, mass_properties: MassProperties) -> HydrostaticCase:
        mass = mass_properties.total_mass_kg
        displacement = mass / self.settings.water_density_kg_m3
        if displacement <= 0.0:
            raise HydrostaticsError("Displacement volume must be positive.")
        if displacement >= self.maximum_strip_displacement_m3:
            raise HydrostaticsError(
                "Requested displacement exceeds the conceptual strip-model capacity."
            )
        draft = displacement / self.total_waterplane_area_m2
        freeboard = self.geometry.hull_height_m - draft
        kb = self.settings.kb_draft_fraction * draft
        kg = mass_properties.cg_m[2]
        bm = self.transverse_waterplane_moment_m4 / displacement
        gm = kb + bm - kg
        return HydrostaticCase(
            name=name,
            total_mass_kg=mass,
            displacement_volume_m3=displacement,
            draft_m=draft,
            freeboard_m=freeboard,
            kb_m=kb,
            kg_m=kg,
            transverse_waterplane_moment_m4=self.transverse_waterplane_moment_m4,
            bm_m=bm,
            gm_m=gm,
            capacity_ratio=self.geometry.capacity_mass_kg / mass,
        )

    def _hull_strip_y(self, center_y_m: float) -> np.ndarray:
        return np.linspace(
            center_y_m - self._half_effective_width_m,
            center_y_m + self._half_effective_width_m,
            self.settings.transverse_strip_count_per_hull,
        )

    def _integrate_at_level(self, heel_rad: float, level_draft_m: float) -> dict[str, float | np.ndarray]:
        """Integrate displaced volume and first moments across both hull strips.

        Positive heel is defined as port-down.  The local draft is clipped to
        [0, hull_height], which gives a finite-heel warning when one hull begins
        to emerge or the immersed side approaches deck height.
        """
        all_y = []
        all_depth = []
        hull_metrics: dict[str, float] = {}
        for label, center_y in (("port", self._port_center_y_m), ("starboard", self._starboard_center_y_m)):
            y = self._hull_strip_y(center_y)
            local_depth = np.clip(
                level_draft_m + y * tan(heel_rad),
                0.0,
                self.geometry.hull_height_m,
            )
            volume = float(np.trapezoid(self.geometry.hull_length_m * local_depth, y))
            moment_y = float(np.trapezoid(self.geometry.hull_length_m * local_depth * y, y))
            moment_z = float(np.trapezoid(self.geometry.hull_length_m * 0.5 * local_depth**2, y))
            hull_metrics[f"{label}_volume"] = volume
            hull_metrics[f"{label}_moment_y"] = moment_y
            hull_metrics[f"{label}_moment_z"] = moment_z
            hull_metrics[f"{label}_mean_draft"] = float(np.mean(local_depth))
            hull_metrics[f"{label}_min_draft"] = float(np.min(local_depth))
            hull_metrics[f"{label}_max_draft"] = float(np.max(local_depth))
            all_y.append(y)
            all_depth.append(local_depth)

        volume_total = hull_metrics["port_volume"] + hull_metrics["starboard_volume"]
        moment_y_total = hull_metrics["port_moment_y"] + hull_metrics["starboard_moment_y"]
        moment_z_total = hull_metrics["port_moment_z"] + hull_metrics["starboard_moment_z"]
        return {
            **hull_metrics,
            "total_volume": volume_total,
            "total_moment_y": moment_y_total,
            "total_moment_z": moment_z_total,
            "all_y": np.concatenate(all_y),
            "all_depth": np.concatenate(all_depth),
        }

    def _solve_equilibrium_level_draft(self, heel_rad: float, displacement_m3: float) -> float:
        """Solve water level at a heel angle while preserving displacement."""
        lower = -self.geometry.hull_height_m
        upper = 2.0 * self.geometry.hull_height_m
        for _ in range(56):
            mid = (lower + upper) / 2.0
            volume = float(self._integrate_at_level(heel_rad, mid)["total_volume"])
            if volume < displacement_m3:
                lower = mid
            else:
                upper = mid
        result = (lower + upper) / 2.0
        residual = abs(float(self._integrate_at_level(heel_rad, result)["total_volume"]) - displacement_m3)
        if residual > max(1e-9, displacement_m3 * 1e-6):
            raise HydrostaticsError(f"Equilibrium-draft solver residual too large: {residual}")
        return result

    def heel_state(self, case: HydrostaticCase, heel_deg: float) -> HeelState:
        heel_rad = radians(heel_deg)
        level_draft = self._solve_equilibrium_level_draft(heel_rad, case.displacement_volume_m3)
        integrated = self._integrate_at_level(heel_rad, level_draft)
        volume = float(integrated["total_volume"])
        cb_y = float(integrated["total_moment_y"]) / volume
        cb_z = float(integrated["total_moment_z"]) / volume
        # Relative horizontal separation between the vertical buoyancy and weight
        # lines after roll.  For small heel this converges to GM*sin(phi).
        gz = cb_y * cos(heel_rad) + (cb_z - case.kg_m) * sin(heel_rad)
        gz_linear = case.gm_m * sin(heel_rad)
        righting = case.total_mass_kg * self.settings.gravity_mps2 * gz
        min_draft = min(float(integrated["port_min_draft"]), float(integrated["starboard_min_draft"]))
        max_draft = max(float(integrated["port_max_draft"]), float(integrated["starboard_max_draft"]))
        return HeelState(
            heel_deg=heel_deg,
            equilibrium_draft_m=level_draft,
            port_mean_draft_m=float(integrated["port_mean_draft"]),
            starboard_mean_draft_m=float(integrated["starboard_mean_draft"]),
            port_min_draft_m=float(integrated["port_min_draft"]),
            starboard_min_draft_m=float(integrated["starboard_min_draft"]),
            port_max_draft_m=float(integrated["port_max_draft"]),
            starboard_max_draft_m=float(integrated["starboard_max_draft"]),
            min_freeboard_m=self.geometry.hull_height_m - max_draft,
            cb_y_m=cb_y,
            cb_z_m=cb_z,
            gz_nonlinear_m=gz,
            gz_linear_m=gz_linear,
            righting_moment_n_m=righting,
            hull_partially_emerged=min_draft <= self.settings.emergence_draft_tolerance_m,
        )

    def heel_curve(self, case: HydrostaticCase) -> list[HeelState]:
        steps = int(round(self.settings.analysis_heel_max_deg / self.settings.analysis_heel_step_deg))
        return [
            self.heel_state(case, index * self.settings.analysis_heel_step_deg)
            for index in range(steps + 1)
        ]

    def first_emergence_angle_deg(self, curve: Iterable[HeelState]) -> float | None:
        for state in curve:
            if state.hull_partially_emerged:
                return state.heel_deg
        return None

    def first_freeboard_limit_angle_deg(self, curve: Iterable[HeelState]) -> float | None:
        for state in curve:
            if state.min_freeboard_m < self.settings.minimum_freeboard_m:
                return state.heel_deg
        return None

    def operating_state(self, case: HydrostaticCase) -> HeelState:
        return self.heel_state(case, self.settings.operational_heel_limit_deg)

    def payload_envelope(self, dry_mass_properties: MassProperties, payload_position_m: tuple[float, float, float], max_payload_kg: float) -> list[dict[str, float]]:
        """Build draft/freeboard/GM envelope as basket payload rises from zero to design load."""
        if max_payload_kg < 0.0:
            raise HydrostaticsError("max_payload_kg cannot be negative.")
        payloads = np.linspace(0.0, max_payload_kg, self.settings.payload_envelope_points)
        rows: list[dict[str, float]] = []
        dry_mass = dry_mass_properties.total_mass_kg
        dry_cg = np.asarray(dry_mass_properties.cg_m, dtype=float)
        payload_position = np.asarray(payload_position_m, dtype=float)
        for payload in payloads:
            total_mass = dry_mass + float(payload)
            cg = (dry_mass * dry_cg + float(payload) * payload_position) / total_mass
            proxy = MassProperties(total_mass, tuple(float(v) for v in cg), dry_mass_properties.inertia_kg_m2)
            case = self.case_from_mass_properties(f"payload_{payload:.3f}", proxy)
            rows.append(
                {
                    "payload_kg": float(payload),
                    "total_mass_kg": total_mass,
                    "draft_m": case.draft_m,
                    "freeboard_m": case.freeboard_m,
                    "KG_m": case.kg_m,
                    "BM_m": case.bm_m,
                    "GM_m": case.gm_m,
                    "capacity_ratio": case.capacity_ratio,
                }
            )
        return rows
