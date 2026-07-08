"""Parametric conceptual geometry for the AquaSkim-Sim catamaran."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

WATER_DENSITY_KG_M3 = 1000.0

class GeometryError(ValueError):
    pass

@dataclass(frozen=True)
class CatamaranGeometry:
    hull_length_m: float
    hull_width_m: float
    hull_height_m: float
    hull_spacing_center_m: float
    hull_shape_factor: float
    waterplane_shape_factor: float
    deck_height_m: float
    collector_inlet_width_m: float
    collector_outlet_width_m: float
    collector_length_m: float
    collector_opening_angle_deg: float
    basket_volume_l: float
    thruster_spacing_m: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "CatamaranGeometry":
        g = data["mechanical"]["geometry"]
        obj = cls(
            hull_length_m=float(g["hull_length_m"]),
            hull_width_m=float(g["hull_width_m"]),
            hull_height_m=float(g["hull_height_m"]),
            hull_spacing_center_m=float(g["hull_spacing_center_m"]),
            hull_shape_factor=float(g["hull_shape_factor"]),
            waterplane_shape_factor=float(g.get("waterplane_shape_factor", 0.88)),
            deck_height_m=float(g["deck_height_m"]),
            collector_inlet_width_m=float(g["collector_inlet_width_m"]),
            collector_outlet_width_m=float(g["collector_outlet_width_m"]),
            collector_length_m=float(g["collector_length_m"]),
            collector_opening_angle_deg=float(g["collector_opening_angle_deg"]),
            basket_volume_l=float(g["basket_volume_l"]),
            thruster_spacing_m=float(g["thruster_spacing_m"]),
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        vals = self.__dict__
        for name in (
            "hull_length_m", "hull_width_m", "hull_height_m", "hull_spacing_center_m",
            "deck_height_m", "collector_inlet_width_m", "collector_outlet_width_m",
            "collector_length_m", "basket_volume_l", "thruster_spacing_m",
        ):
            if vals[name] <= 0:
                raise GeometryError(f"{name} must be positive.")
        for name in ("hull_shape_factor", "waterplane_shape_factor"):
            if not 0 < vals[name] <= 1:
                raise GeometryError(f"{name} must be in (0, 1].")
        if self.hull_spacing_center_m <= self.hull_width_m:
            raise GeometryError("Hull centre spacing must exceed hull width.")
        if self.collector_outlet_width_m > self.collector_inlet_width_m:
            raise GeometryError("Collector outlet width cannot exceed inlet width.")
        if self.thruster_spacing_m > self.hull_spacing_center_m + 1e-12:
            raise GeometryError("Thruster spacing cannot exceed hull centre spacing.")

    @property
    def overall_width_m(self) -> float:
        return self.hull_spacing_center_m + self.hull_width_m

    @property
    def effective_volume_per_hull_m3(self) -> float:
        return self.hull_length_m * self.hull_width_m * self.hull_height_m * self.hull_shape_factor

    @property
    def displacement_volume_m3(self) -> float:
        return 2 * self.effective_volume_per_hull_m3

    @property
    def capacity_mass_kg(self) -> float:
        return WATER_DENSITY_KG_M3 * self.displacement_volume_m3

    @property
    def waterplane_area_m2(self) -> float:
        return 2 * self.hull_length_m * self.hull_width_m * self.waterplane_shape_factor

    @property
    def collector_planform_area_m2(self) -> float:
        return 0.5 * (self.collector_inlet_width_m + self.collector_outlet_width_m) * self.collector_length_m

    def draft_preview_m(self, mass_kg: float) -> float:
        if mass_kg < 0:
            raise GeometryError("Mass cannot be negative.")
        return mass_kg / (WATER_DENSITY_KG_M3 * self.waterplane_area_m2)

    def freeboard_preview_m(self, mass_kg: float) -> float:
        return self.hull_height_m - self.draft_preview_m(mass_kg)

    def hull_centerlines_y_m(self) -> tuple[float, float]:
        h = self.hull_spacing_center_m / 2
        return h, -h

    def summary_rows(self) -> list[dict[str, object]]:
        return [
            {"parameter": "hull_length", "value": self.hull_length_m, "unit": "m"},
            {"parameter": "hull_width", "value": self.hull_width_m, "unit": "m"},
            {"parameter": "hull_height", "value": self.hull_height_m, "unit": "m"},
            {"parameter": "hull_spacing_center", "value": self.hull_spacing_center_m, "unit": "m"},
            {"parameter": "overall_width", "value": self.overall_width_m, "unit": "m"},
            {"parameter": "effective_displacement_volume", "value": self.displacement_volume_m3, "unit": "m^3"},
            {"parameter": "conceptual_capacity", "value": self.capacity_mass_kg, "unit": "kg"},
            {"parameter": "effective_waterplane_area", "value": self.waterplane_area_m2, "unit": "m^2"},
            {"parameter": "collector_planform_area", "value": self.collector_planform_area_m2, "unit": "m^2"},
            {"parameter": "basket_volume", "value": self.basket_volume_l, "unit": "L"},
        ]
