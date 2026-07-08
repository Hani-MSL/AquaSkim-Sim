"""Mass budget, CG and point-mass inertia calculations for Phase 02."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
import numpy as np

class MassPropertyError(ValueError):
    pass

@dataclass(frozen=True)
class PointMass:
    name: str
    mass_kg: float
    position_m: tuple[float, float, float]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "PointMass":
        pos = data.get("position_m")
        if not isinstance(pos, list) or len(pos) != 3:
            raise MassPropertyError(f"{data.get('name', '<unnamed>')} needs position_m=[x,y,z].")
        result = cls(str(data["name"]), float(data["mass_kg"]), tuple(float(v) for v in pos))
        if result.mass_kg <= 0:
            raise MassPropertyError(f"{result.name} must have positive mass.")
        return result

@dataclass(frozen=True)
class MassProperties:
    total_mass_kg: float
    cg_m: tuple[float, float, float]
    inertia_kg_m2: tuple[float, float, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "total_mass_kg": self.total_mass_kg,
            "center_of_gravity_m": {"x": self.cg_m[0], "y": self.cg_m[1], "z": self.cg_m[2]},
            "inertia_about_cg_kg_m2": {"Ixx": self.inertia_kg_m2[0], "Iyy": self.inertia_kg_m2[1], "Izz": self.inertia_kg_m2[2]},
            "method": "Point-mass approximation about computed CG",
        }

def components_from_config(data: dict[str, Any]) -> list[PointMass]:
    return [PointMass.from_mapping(x) for x in data["mass_budget"]["components"]]

def compute_mass_properties(components: Iterable[PointMass]) -> MassProperties:
    items = list(components)
    if not items:
        raise MassPropertyError("At least one component is required.")
    masses = np.array([x.mass_kg for x in items], dtype=float)
    positions = np.array([x.position_m for x in items], dtype=float)
    total = float(masses.sum())
    cg = (masses[:, None] * positions).sum(axis=0) / total
    rel = positions - cg
    ixx = float(np.sum(masses * (rel[:, 1]**2 + rel[:, 2]**2)))
    iyy = float(np.sum(masses * (rel[:, 0]**2 + rel[:, 2]**2)))
    izz = float(np.sum(masses * (rel[:, 0]**2 + rel[:, 1]**2)))
    return MassProperties(total, tuple(float(x) for x in cg), (ixx, iyy, izz))

def build_load_cases(data: dict[str, Any]) -> dict[str, tuple[list[PointMass], MassProperties]]:
    base = components_from_config(data)
    dry = compute_mass_properties(base)
    basket = next((x for x in base if x.name == "basket"), None)
    if basket is None:
        raise MassPropertyError("Basket component is required.")
    payload = PointMass("collected_debris_payload", float(data["mechanical"]["geometry"]["design_payload_kg"]), basket.position_m)
    full_components = [*base, payload]
    return {
        "dry_empty_basket": (base, dry),
        "full_design_payload": (full_components, compute_mass_properties(full_components)),
    }

def mass_rows(components: Iterable[PointMass]) -> list[dict[str, object]]:
    return [
        {"component": c.name, "mass_kg": c.mass_kg, "x_m": c.position_m[0], "y_m": c.position_m[1], "z_m": c.position_m[2]}
        for c in components
    ]
