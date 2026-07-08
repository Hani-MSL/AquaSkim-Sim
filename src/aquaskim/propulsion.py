"""Twin-thruster static envelope and preliminary electrical power model."""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any


class PropulsionError(ValueError):
    """Raised when a thruster operating point is infeasible."""


@dataclass(frozen=True)
class ThrusterSettings:
    count: int
    max_thrust_per_side_n: float
    max_power_per_side_w: float
    max_rpm: float
    thrust_coefficient_n_per_rpm2: float
    static_auxiliary_power_per_side_w: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "ThrusterSettings":
        source = data["propulsion"]["thruster"]
        result = cls(
            count=int(source["count"]),
            max_thrust_per_side_n=float(source["max_thrust_per_side_n"]),
            max_power_per_side_w=float(source["max_power_per_side_w"]),
            max_rpm=float(source["max_rpm"]),
            thrust_coefficient_n_per_rpm2=float(source["thrust_coefficient_n_per_rpm2"]),
            static_auxiliary_power_per_side_w=float(source.get("static_auxiliary_power_per_side_w", 0.0)),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.count != 2:
            raise PropulsionError("AquaSkim-Sim Phase 04 assumes exactly two thrusters.")
        for name, value in self.__dict__.items():
            if name == "count":
                continue
            if float(value) <= 0.0 and name != "static_auxiliary_power_per_side_w":
                raise PropulsionError(f"{name} must be positive.")

    @property
    def derived_max_thrust_per_side_n(self) -> float:
        return self.thrust_coefficient_n_per_rpm2 * self.max_rpm**2

    @property
    def power_coefficient_w_per_rpm3(self) -> float:
        return (self.max_power_per_side_w - self.static_auxiliary_power_per_side_w) / self.max_rpm**3

    @property
    def total_max_thrust_n(self) -> float:
        return self.count * self.max_thrust_per_side_n


@dataclass(frozen=True)
class ThrusterOperatingPoint:
    requested_total_thrust_n: float
    thrust_per_side_n: float
    rpm_per_side: float
    throttle_fraction: float
    electrical_power_per_side_w: float
    total_thruster_power_w: float
    feasible: bool

    def as_row(self) -> dict[str, float | bool]:
        return {
            "requested_total_thrust_n": self.requested_total_thrust_n,
            "thrust_per_side_n": self.thrust_per_side_n,
            "rpm_per_side": self.rpm_per_side,
            "throttle_fraction": self.throttle_fraction,
            "electrical_power_per_side_w": self.electrical_power_per_side_w,
            "total_thruster_power_w": self.total_thruster_power_w,
            "feasible": self.feasible,
        }


class TwinThrusterModel:
    def __init__(self, settings: ThrusterSettings):
        self.settings = settings

    def thrust_per_side_at_rpm(self, rpm: float) -> float:
        if rpm < 0.0:
            raise PropulsionError("rpm cannot be negative.")
        return self.settings.thrust_coefficient_n_per_rpm2 * rpm**2

    def electrical_power_per_side_at_rpm(self, rpm: float) -> float:
        if rpm < 0.0:
            raise PropulsionError("rpm cannot be negative.")
        if rpm == 0.0:
            return 0.0
        return self.settings.static_auxiliary_power_per_side_w + self.settings.power_coefficient_w_per_rpm3 * rpm**3

    def total_thrust_at_rpm(self, rpm: float) -> float:
        return self.settings.count * self.thrust_per_side_at_rpm(rpm)

    def total_electrical_power_at_rpm(self, rpm: float) -> float:
        return self.settings.count * self.electrical_power_per_side_at_rpm(rpm)

    def symmetric_operating_point(self, requested_total_thrust_n: float) -> ThrusterOperatingPoint:
        if requested_total_thrust_n < 0.0:
            raise PropulsionError("requested_total_thrust_n cannot be negative.")
        per_side = requested_total_thrust_n / self.settings.count
        rpm = sqrt(per_side / self.settings.thrust_coefficient_n_per_rpm2) if per_side > 0.0 else 0.0
        throttle = rpm / self.settings.max_rpm
        feasible = (
            per_side <= self.settings.max_thrust_per_side_n + 1e-12
            and rpm <= self.settings.max_rpm + 1e-12
        )
        power_side = self.electrical_power_per_side_at_rpm(min(rpm, self.settings.max_rpm))
        return ThrusterOperatingPoint(
            requested_total_thrust_n=requested_total_thrust_n,
            thrust_per_side_n=per_side,
            rpm_per_side=rpm,
            throttle_fraction=throttle,
            electrical_power_per_side_w=power_side,
            total_thruster_power_w=self.settings.count * power_side,
            feasible=feasible,
        )
