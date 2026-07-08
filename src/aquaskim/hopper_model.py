"""Mass-and-volume constrained collection hopper model.

The module deliberately avoids using a collection-count quota.  It converts each
captured debris mass to equivalent occupied hopper volume using a documented
bulk-density and packing-factor surrogate.
"""
from __future__ import annotations

from dataclasses import dataclass


class HopperModelError(ValueError):
    """Raised when hopper settings are physically invalid."""


@dataclass(frozen=True)
class HopperSettings:
    usable_volume_l: float
    payload_mass_limit_kg: float
    equivalent_bulk_density_kg_m3: float
    packing_factor: float
    return_trigger_fraction: float = 0.95

    def validate(self) -> None:
        for name, value in {
            "usable_volume_l": self.usable_volume_l,
            "payload_mass_limit_kg": self.payload_mass_limit_kg,
            "equivalent_bulk_density_kg_m3": self.equivalent_bulk_density_kg_m3,
            "packing_factor": self.packing_factor,
            "return_trigger_fraction": self.return_trigger_fraction,
        }.items():
            if value <= 0.0:
                raise HopperModelError(f"{name} must be positive.")
        if self.packing_factor > 1.0:
            raise HopperModelError("packing_factor must not exceed 1.")
        if self.return_trigger_fraction > 1.0:
            raise HopperModelError("return_trigger_fraction must not exceed 1.")

    @property
    def mass_equivalent_volume_limit_kg(self) -> float:
        """Mass that fills volume capacity at the documented bulk/packing model."""
        return (
            self.usable_volume_l / 1000.0
            * self.equivalent_bulk_density_kg_m3
            * self.packing_factor
        )

    @property
    def effective_payload_limit_kg(self) -> float:
        """The smaller of mechanical payload and effective hopper-volume limits."""
        return min(self.payload_mass_limit_kg, self.mass_equivalent_volume_limit_kg)

    def occupied_volume_l(self, captured_mass_kg: float) -> float:
        if captured_mass_kg < 0.0:
            raise HopperModelError("captured_mass_kg cannot be negative.")
        return (
            captured_mass_kg
            / (self.equivalent_bulk_density_kg_m3 * self.packing_factor)
            * 1000.0
        )


@dataclass(frozen=True)
class HopperState:
    captured_mass_kg: float = 0.0
    occupied_volume_l: float = 0.0
    captured_items: int = 0

    def add(self, mass_kg: float, settings: HopperSettings) -> "HopperState":
        if mass_kg <= 0.0:
            raise HopperModelError("Captured debris mass must be positive.")
        settings.validate()
        return HopperState(
            captured_mass_kg=self.captured_mass_kg + mass_kg,
            occupied_volume_l=settings.occupied_volume_l(self.captured_mass_kg + mass_kg),
            captured_items=self.captured_items + 1,
        )

    def mass_fraction(self, settings: HopperSettings) -> float:
        return self.captured_mass_kg / settings.payload_mass_limit_kg

    def volume_fraction(self, settings: HopperSettings) -> float:
        return self.occupied_volume_l / settings.usable_volume_l

    def limiting_fraction(self, settings: HopperSettings) -> float:
        return max(self.mass_fraction(settings), self.volume_fraction(settings))

    def can_accept(self, mass_kg: float, settings: HopperSettings) -> bool:
        proposed = self.add(mass_kg, settings)
        return (
            proposed.captured_mass_kg <= settings.payload_mass_limit_kg + 1e-12
            and proposed.occupied_volume_l <= settings.usable_volume_l + 1e-12
        )

    def return_required(self, settings: HopperSettings) -> tuple[bool, str]:
        if self.mass_fraction(settings) >= settings.return_trigger_fraction:
            return True, "hopper payload-mass trigger reached"
        if self.volume_fraction(settings) >= settings.return_trigger_fraction:
            return True, "hopper occupied-volume trigger reached"
        return False, ""


def hopper_settings_from_data(data: dict) -> HopperSettings:
    source = data.get("experiment_model", {}).get("hopper", {})
    geometry = data["mechanical"]["geometry"]
    result = HopperSettings(
        usable_volume_l=float(source.get("usable_volume_l", geometry["basket_volume_l"])),
        payload_mass_limit_kg=float(
            source.get("payload_mass_limit_kg", geometry["design_payload_kg"])
        ),
        equivalent_bulk_density_kg_m3=float(
            source.get("equivalent_bulk_density_kg_m3", 75.0)
        ),
        packing_factor=float(source.get("packing_factor", 0.62)),
        return_trigger_fraction=float(source.get("return_trigger_fraction", 0.95)),
    )
    result.validate()
    return result
