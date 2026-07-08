"""Phase 05 battery and mission-energy model.

The battery model is deliberately transparent.  It converts electrical load at
its DC bus to pack-side power through an efficiency factor, applies a capacity
derating and a mild Peukert-style current penalty, and integrates usable SOC.
It is a preliminary design model rather than an electrochemical cell model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EnergyModelError(ValueError):
    """Raised when battery or mission-energy inputs are invalid."""


@dataclass(frozen=True)
class BatterySettings:
    chemistry: str
    nominal_voltage_v: float
    capacity_ah: float
    usable_fraction: float
    nominal_energy_wh: float
    capacity_derating_factor: float
    dc_bus_efficiency: float
    peukert_exponent: float
    reference_current_a: float
    max_continuous_discharge_current_a: float
    min_pack_voltage_v: float
    max_pack_voltage_v: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "BatterySettings":
        source = data["energy"]["battery"]
        result = cls(
            chemistry=str(source["chemistry"]),
            nominal_voltage_v=float(source["nominal_voltage_v"]),
            capacity_ah=float(source["capacity_ah"]),
            usable_fraction=float(source["usable_fraction"]),
            nominal_energy_wh=float(source["nominal_energy_wh"]),
            capacity_derating_factor=float(source["capacity_derating_factor"]),
            dc_bus_efficiency=float(source["dc_bus_efficiency"]),
            peukert_exponent=float(source["peukert_exponent"]),
            reference_current_a=float(source["reference_current_a"]),
            max_continuous_discharge_current_a=float(source["max_continuous_discharge_current_a"]),
            min_pack_voltage_v=float(source["min_pack_voltage_v"]),
            max_pack_voltage_v=float(source["max_pack_voltage_v"]),
        )
        result.validate()
        return result

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if name == "chemistry":
                continue
            if float(value) <= 0.0:
                raise EnergyModelError(f"{name} must be positive.")
        if self.usable_fraction > 1.0 or self.capacity_derating_factor > 1.0 or self.dc_bus_efficiency > 1.0:
            raise EnergyModelError("Battery fractions and efficiency must not exceed one.")
        if self.peukert_exponent < 1.0:
            raise EnergyModelError("peukert_exponent must be at least one for this model.")
        if self.max_pack_voltage_v <= self.min_pack_voltage_v:
            raise EnergyModelError("max_pack_voltage_v must exceed min_pack_voltage_v.")

    @property
    def usable_energy_wh(self) -> float:
        return self.nominal_energy_wh * self.usable_fraction * self.capacity_derating_factor

    @property
    def usable_capacity_ah(self) -> float:
        return self.capacity_ah * self.usable_fraction * self.capacity_derating_factor


@dataclass(frozen=True)
class EnergySettings:
    hotel_load_w: float
    integration_time_step_s: float
    analysis_duration_s: float
    safety_reserve_energy_wh: float
    return_speed_mps: float
    return_head_current_mps: float
    return_distance_max_m: float
    return_distance_points: int
    current_sensitivity_values_mps: tuple[float, ...]
    minimum_endurance_at_cruise_min: float
    minimum_soc_after_nominal_mission: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "EnergySettings":
        source = data["energy"]
        model = source["model"]
        result = cls(
            hotel_load_w=float(source["hotel_load_w"]),
            integration_time_step_s=float(model["integration_time_step_s"]),
            analysis_duration_s=float(model["analysis_duration_s"]),
            safety_reserve_energy_wh=float(model["safety_reserve_energy_wh"]),
            return_speed_mps=float(model["return_speed_mps"]),
            return_head_current_mps=float(model["return_head_current_mps"]),
            return_distance_max_m=float(model["return_distance_max_m"]),
            return_distance_points=int(model["return_distance_points"]),
            current_sensitivity_values_mps=tuple(float(v) for v in model["current_sensitivity_values_mps"]),
            minimum_endurance_at_cruise_min=float(model["minimum_endurance_at_cruise_min"]),
            minimum_soc_after_nominal_mission=float(model["minimum_soc_after_nominal_mission"]),
        )
        result.validate()
        return result

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if name == "current_sensitivity_values_mps":
                continue
            if float(value) <= 0.0:
                raise EnergyModelError(f"{name} must be positive.")
        if self.return_distance_points < 3:
            raise EnergyModelError("return_distance_points must be at least three.")
        if not self.current_sensitivity_values_mps or min(self.current_sensitivity_values_mps) < 0.0:
            raise EnergyModelError("current_sensitivity_values_mps must be a non-empty non-negative sequence.")
        if not 0.0 < self.minimum_soc_after_nominal_mission <= 1.0:
            raise EnergyModelError("minimum_soc_after_nominal_mission must be in (0, 1].")


@dataclass(frozen=True)
class BatteryLoadState:
    bus_load_w: float
    battery_power_w: float
    pack_voltage_v: float
    pack_current_a: float
    peukert_multiplier: float

    def as_row(self) -> dict[str, float]:
        return {
            "bus_load_w": self.bus_load_w,
            "battery_power_w": self.battery_power_w,
            "pack_voltage_v": self.pack_voltage_v,
            "pack_current_a": self.pack_current_a,
            "peukert_multiplier": self.peukert_multiplier,
        }


class BatteryModel:
    def __init__(self, settings: BatterySettings):
        self.settings = settings

    def pack_voltage_v(self, soc: float) -> float:
        if not 0.0 <= soc <= 1.0:
            raise EnergyModelError("SOC must be in [0, 1].")
        # Smooth conceptual 4S Li-ion discharge curve over the usable SOC window.
        shaped_soc = 0.18 * soc + 0.82 * soc**0.55
        return self.settings.min_pack_voltage_v + (self.settings.max_pack_voltage_v - self.settings.min_pack_voltage_v) * shaped_soc

    def load_state(self, bus_load_w: float, soc: float) -> BatteryLoadState:
        if bus_load_w < 0.0:
            raise EnergyModelError("bus_load_w cannot be negative.")
        voltage = self.pack_voltage_v(soc)
        battery_power = bus_load_w / self.settings.dc_bus_efficiency
        current = battery_power / voltage
        peukert = max(1.0, current / self.settings.reference_current_a) ** (self.settings.peukert_exponent - 1.0)
        return BatteryLoadState(bus_load_w, battery_power, voltage, current, peukert)

    def soc_after_interval(self, soc: float, bus_load_w: float, duration_s: float) -> float:
        if duration_s < 0.0:
            raise EnergyModelError("duration_s cannot be negative.")
        state = self.load_state(bus_load_w, soc)
        energy_draw_wh = state.battery_power_w * duration_s / 3600.0 * state.peukert_multiplier
        return max(0.0, soc - energy_draw_wh / self.settings.usable_energy_wh)

    def endurance_to_soc_s(self, bus_load_w: float, start_soc: float, stop_soc: float, step_s: float = 5.0) -> float:
        if not 0.0 <= stop_soc < start_soc <= 1.0:
            raise EnergyModelError("Expected 0 <= stop_soc < start_soc <= 1.")
        soc = start_soc
        elapsed = 0.0
        while soc > stop_soc:
            before = soc
            soc = self.soc_after_interval(soc, bus_load_w, step_s)
            elapsed += step_s
            if soc >= before:
                raise EnergyModelError("SOC integration did not decrease under positive load.")
            if elapsed > 24.0 * 3600.0:
                raise EnergyModelError("Endurance loop exceeded 24 h; check model inputs.")
        return elapsed
