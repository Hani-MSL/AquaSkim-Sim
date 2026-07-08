"""Phase 04 calm-water resistance model for AquaSkim-Sim.

The model deliberately separates frictional, residual, appendage and collector
resistance. It is a transparent preliminary-design model: useful for sizing
propulsion and demonstrating engineering reasoning, but not a substitute for a
tow-tank test or CFD validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log10, sqrt
from typing import Any

from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrostatics import HydrostaticCase


class HydrodynamicsError(ValueError):
    """Raised when a hydrodynamic calculation receives an invalid input."""


@dataclass(frozen=True)
class HydrodynamicSettings:
    water_density_kg_m3: float
    kinematic_viscosity_m2ps: float
    wetted_surface_shape_factor: float
    form_factor: float
    residual_resistance_coefficient: float
    appendage_drag_area_m2: float
    appendage_drag_coefficient: float
    collector_immersed_depth_m: float
    collector_drag_coefficient: float
    added_mass_fraction_surge: float
    analysis_speed_max_mps: float
    analysis_speed_points: int
    head_current_max_mps: float
    head_current_points: int
    minimum_thrust_reserve_ratio: float
    max_recommended_rpm_fraction: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "HydrodynamicSettings":
        source = data["hydrodynamics"]
        result = cls(
            water_density_kg_m3=float(source["water_density_kg_m3"]),
            kinematic_viscosity_m2ps=float(source["kinematic_viscosity_m2ps"]),
            wetted_surface_shape_factor=float(source["wetted_surface_shape_factor"]),
            form_factor=float(source["form_factor"]),
            residual_resistance_coefficient=float(source["residual_resistance_coefficient"]),
            appendage_drag_area_m2=float(source["appendage_drag_area_m2"]),
            appendage_drag_coefficient=float(source["appendage_drag_coefficient"]),
            collector_immersed_depth_m=float(source["collector_immersed_depth_m"]),
            collector_drag_coefficient=float(source["collector_drag_coefficient"]),
            added_mass_fraction_surge=float(source["added_mass_fraction_surge"]),
            analysis_speed_max_mps=float(source["analysis_speed_max_mps"]),
            analysis_speed_points=int(source["analysis_speed_points"]),
            head_current_max_mps=float(source["head_current_max_mps"]),
            head_current_points=int(source["head_current_points"]),
            minimum_thrust_reserve_ratio=float(source["minimum_thrust_reserve_ratio"]),
            max_recommended_rpm_fraction=float(source["max_recommended_rpm_fraction"]),
        )
        result.validate()
        return result

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if name.endswith("points"):
                if int(value) < 3:
                    raise HydrodynamicsError(f"{name} must be at least 3.")
            elif float(value) <= 0.0:
                raise HydrodynamicsError(f"{name} must be positive.")
        if self.max_recommended_rpm_fraction > 1.0:
            raise HydrodynamicsError("max_recommended_rpm_fraction must not exceed 1.")


@dataclass(frozen=True)
class ResistanceState:
    speed_through_water_mps: float
    reynolds_number: float
    froude_number: float
    friction_coefficient: float
    wetted_surface_area_m2: float
    friction_resistance_n: float
    residual_resistance_n: float
    appendage_resistance_n: float
    collector_resistance_n: float
    total_resistance_n: float

    def as_row(self) -> dict[str, float]:
        return {
            "speed_through_water_mps": self.speed_through_water_mps,
            "Reynolds_number": self.reynolds_number,
            "Froude_number": self.froude_number,
            "ITTC_1957_Cf": self.friction_coefficient,
            "wetted_surface_area_m2": self.wetted_surface_area_m2,
            "friction_resistance_n": self.friction_resistance_n,
            "residual_resistance_n": self.residual_resistance_n,
            "appendage_resistance_n": self.appendage_resistance_n,
            "collector_resistance_n": self.collector_resistance_n,
            "total_resistance_n": self.total_resistance_n,
        }


class CatamaranResistanceModel:
    """Preliminary resistance model evaluated at a specified displacement draft."""

    def __init__(self, geometry: CatamaranGeometry, settings: HydrodynamicSettings, hydro_case: HydrostaticCase):
        self.geometry = geometry
        self.settings = settings
        self.hydro_case = hydro_case
        self.draft_m = hydro_case.draft_m
        if self.draft_m <= 0.0:
            raise HydrodynamicsError("Hydrostatic draft must be positive.")

    @property
    def effective_hull_beam_m(self) -> float:
        return self.geometry.hull_width_m * self.geometry.waterplane_shape_factor

    @property
    def wetted_surface_area_m2(self) -> float:
        """Two-hull wetted surface approximation excluding the deck.

        For each hull, the geometric prism estimate includes bottom, two sides,
        and transom terms. `wetted_surface_shape_factor` makes the estimate
        consistent with rounded/streamlined conceptual hull geometry.
        """
        per_hull_prism = (
            self.geometry.hull_length_m * self.effective_hull_beam_m
            + 2.0 * self.geometry.hull_length_m * self.draft_m
            + 2.0 * self.effective_hull_beam_m * self.draft_m
        )
        return 2.0 * self.settings.wetted_surface_shape_factor * per_hull_prism

    @property
    def collector_frontal_area_m2(self) -> float:
        return self.geometry.collector_inlet_width_m * self.settings.collector_immersed_depth_m

    def reynolds_number(self, speed_mps: float) -> float:
        return speed_mps * self.geometry.hull_length_m / self.settings.kinematic_viscosity_m2ps

    def froude_number(self, speed_mps: float, gravity_mps2: float = 9.80665) -> float:
        return speed_mps / sqrt(gravity_mps2 * self.geometry.hull_length_m)

    def ittc_1957_friction_coefficient(self, speed_mps: float) -> float:
        if speed_mps <= 0.0:
            return 0.0
        re = self.reynolds_number(speed_mps)
        if re <= 100.0:
            raise HydrodynamicsError("Reynolds number is too small for the ITTC-1957 correlation.")
        return 0.075 / (log10(re) - 2.0) ** 2

    def state_at_speed(self, speed_mps: float) -> ResistanceState:
        if speed_mps < 0.0:
            raise HydrodynamicsError("speed_mps cannot be negative.")
        if speed_mps == 0.0:
            return ResistanceState(0.0, 0.0, 0.0, 0.0, self.wetted_surface_area_m2, 0.0, 0.0, 0.0, 0.0, 0.0)

        rho = self.settings.water_density_kg_m3
        v2 = speed_mps**2
        cf = self.ittc_1957_friction_coefficient(speed_mps)
        wetted = self.wetted_surface_area_m2
        friction = 0.5 * rho * wetted * cf * v2 * (1.0 + self.settings.form_factor)
        residual = 0.5 * rho * wetted * self.settings.residual_resistance_coefficient * v2
        appendage = 0.5 * rho * self.settings.appendage_drag_coefficient * self.settings.appendage_drag_area_m2 * v2
        collector = 0.5 * rho * self.settings.collector_drag_coefficient * self.collector_frontal_area_m2 * v2
        return ResistanceState(
            speed_through_water_mps=speed_mps,
            reynolds_number=self.reynolds_number(speed_mps),
            froude_number=self.froude_number(speed_mps),
            friction_coefficient=cf,
            wetted_surface_area_m2=wetted,
            friction_resistance_n=friction,
            residual_resistance_n=residual,
            appendage_resistance_n=appendage,
            collector_resistance_n=collector,
            total_resistance_n=friction + residual + appendage + collector,
        )

    def surge_added_mass_kg(self, craft_mass_kg: float) -> float:
        if craft_mass_kg <= 0.0:
            raise HydrodynamicsError("craft_mass_kg must be positive.")
        return self.settings.added_mass_fraction_surge * craft_mass_kg
