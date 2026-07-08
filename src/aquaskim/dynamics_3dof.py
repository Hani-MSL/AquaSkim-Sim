"""Phase 06 planar 3-DOF marine dynamics for AquaSkim-Sim.

The model uses body-fixed surge (u), sway (v) and yaw rate (r), while position
and heading are integrated in the earth-fixed ENU frame.  Hydrodynamic drag is
computed from velocity relative to the water; a constant earth-fixed current is
therefore a genuine disturbance rather than a post-processing offset.

This is a transparent preliminary manoeuvring model.  It reuses the Phase 04
longitudinal resistance model and adds explicit sway/yaw damping terms.  It is
not a replacement for captive-model tests, CFD or a full added-mass Coriolis
model; those limitations are retained in the phase record.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, sqrt
from typing import Any, Callable

import numpy as np

from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel
from aquaskim.hydrostatics import HydrostaticCase
from aquaskim.mass_properties import MassProperties


class DynamicsError(ValueError):
    """Raised when a dynamics configuration or state is not physically valid."""


@dataclass(frozen=True)
class DynamicsSettings:
    added_mass_fraction_sway: float
    added_yaw_inertia_fraction: float
    sway_linear_damping_n_per_mps: float
    sway_quadratic_damping_n_per_mps2: float
    yaw_linear_damping_n_m_per_rps: float
    yaw_quadratic_damping_n_m_per_rps2: float
    max_simulation_time_s: float
    integration_time_step_s: float
    trajectory_sample_interval_s: float
    current_crossflow_mps: float
    cruise_thrust_multiplier: float
    turn_left_thrust_multiplier: float
    turn_right_thrust_multiplier: float
    turn_start_s: float
    turn_end_s: float
    scenario_start_delay_s: float
    straight_line_cross_track_limit_m: float
    maximum_expected_yaw_rate_rps: float
    steady_speed_tolerance_mps: float

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "DynamicsSettings":
        source = data["dynamics_3dof"]
        result = cls(**{name: float(source[name]) for name in cls.__dataclass_fields__})
        result.validate()
        return result

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if value <= 0.0:
                raise DynamicsError(f"dynamics_3dof.{name} must be positive.")
        if self.turn_end_s <= self.turn_start_s:
            raise DynamicsError("turn_end_s must exceed turn_start_s.")
        if self.trajectory_sample_interval_s < self.integration_time_step_s:
            raise DynamicsError("trajectory_sample_interval_s must be >= integration_time_step_s.")


@dataclass(frozen=True)
class DynamicMass:
    rigid_mass_kg: float
    surge_added_mass_kg: float
    sway_added_mass_kg: float
    rigid_yaw_inertia_kg_m2: float
    yaw_added_inertia_kg_m2: float

    @property
    def surge_mass_kg(self) -> float:
        return self.rigid_mass_kg + self.surge_added_mass_kg

    @property
    def sway_mass_kg(self) -> float:
        return self.rigid_mass_kg + self.sway_added_mass_kg

    @property
    def yaw_inertia_kg_m2(self) -> float:
        return self.rigid_yaw_inertia_kg_m2 + self.yaw_added_inertia_kg_m2

    def as_row(self) -> dict[str, float]:
        return {
            "rigid_mass_kg": self.rigid_mass_kg,
            "surge_added_mass_kg": self.surge_added_mass_kg,
            "sway_added_mass_kg": self.sway_added_mass_kg,
            "effective_surge_mass_kg": self.surge_mass_kg,
            "effective_sway_mass_kg": self.sway_mass_kg,
            "rigid_yaw_inertia_kg_m2": self.rigid_yaw_inertia_kg_m2,
            "yaw_added_inertia_kg_m2": self.yaw_added_inertia_kg_m2,
            "effective_yaw_inertia_kg_m2": self.yaw_inertia_kg_m2,
        }


@dataclass(frozen=True)
class CraftState:
    x_m: float = 0.0
    y_m: float = 0.0
    psi_rad: float = 0.0
    u_mps: float = 0.0
    v_mps: float = 0.0
    r_rps: float = 0.0

    def as_vector(self) -> np.ndarray:
        return np.asarray([self.x_m, self.y_m, self.psi_rad, self.u_mps, self.v_mps, self.r_rps], dtype=float)

    @classmethod
    def from_vector(cls, vector: np.ndarray) -> "CraftState":
        return cls(*[float(value) for value in vector])


@dataclass(frozen=True)
class ThrusterCommand:
    port_thrust_n: float
    starboard_thrust_n: float

    @property
    def total_thrust_n(self) -> float:
        return self.port_thrust_n + self.starboard_thrust_n


@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    description: str
    current_earth_mps: tuple[float, float]
    rows: list[dict[str, float | str]]

    def metric(self, name: str) -> float:
        return float(self.rows[-1][name])


CommandLaw = Callable[[float], ThrusterCommand]


def wrap_to_pi(angle_rad: float) -> float:
    return float((angle_rad + np.pi) % (2.0 * np.pi) - np.pi)


def rotation_body_to_earth(psi_rad: float) -> np.ndarray:
    return np.asarray([[cos(psi_rad), -sin(psi_rad)], [sin(psi_rad), cos(psi_rad)]], dtype=float)


class PlanarCatamaranDynamics:
    """3-DOF body-fixed manoeuvring model driven by twin-thruster forces."""

    def __init__(
        self,
        *,
        geometry: CatamaranGeometry,
        resistance: CatamaranResistanceModel,
        hydro_case: HydrostaticCase,
        mass_properties: MassProperties,
        settings: DynamicsSettings,
    ) -> None:
        self.geometry = geometry
        self.resistance = resistance
        self.hydro_case = hydro_case
        self.settings = settings
        rigid_mass = hydro_case.total_mass_kg
        self.mass = DynamicMass(
            rigid_mass_kg=rigid_mass,
            surge_added_mass_kg=resistance.surge_added_mass_kg(rigid_mass),
            sway_added_mass_kg=settings.added_mass_fraction_sway * rigid_mass,
            rigid_yaw_inertia_kg_m2=mass_properties.inertia_kg_m2[2],
            yaw_added_inertia_kg_m2=settings.added_yaw_inertia_fraction * mass_properties.inertia_kg_m2[2],
        )
        if self.mass.yaw_inertia_kg_m2 <= 0.0:
            raise DynamicsError("Effective yaw inertia must be positive.")

    @property
    def thruster_half_spacing_m(self) -> float:
        return self.geometry.thruster_spacing_m / 2.0

    def relative_water_velocity_body(self, state: CraftState, current_earth_mps: tuple[float, float]) -> tuple[float, float]:
        earth_to_body = rotation_body_to_earth(state.psi_rad).T
        current_body = earth_to_body @ np.asarray(current_earth_mps, dtype=float)
        return state.u_mps - float(current_body[0]), state.v_mps - float(current_body[1])

    def hydrodynamic_forces(self, state: CraftState, current_earth_mps: tuple[float, float]) -> tuple[float, float, float]:
        u_rel, v_rel = self.relative_water_velocity_body(state, current_earth_mps)
        speed_rel = sqrt(u_rel * u_rel + v_rel * v_rel)
        # ITTC-1957 is not defined at vanishing Reynolds number.  During a
        # deliberate stop-turn-go manoeuvre the craft legitimately passes through
        # this region, so use a continuous low-speed linear extension matched at
        # 0.02 m/s rather than asking the resistance correlation to extrapolate.
        low_speed_reference_mps = 0.02
        if speed_rel <= 1e-12:
            x_drag = 0.0
        elif speed_rel < low_speed_reference_mps:
            reference_drag = self.resistance.state_at_speed(low_speed_reference_mps).total_resistance_n
            x_drag = -(reference_drag / low_speed_reference_mps) * u_rel
        else:
            resistance = self.resistance.state_at_speed(speed_rel).total_resistance_n
            x_drag = -resistance * (u_rel / speed_rel)
        y_drag = -(
            self.settings.sway_linear_damping_n_per_mps * v_rel
            + self.settings.sway_quadratic_damping_n_per_mps2 * abs(v_rel) * v_rel
        )
        n_drag = -(
            self.settings.yaw_linear_damping_n_m_per_rps * state.r_rps
            + self.settings.yaw_quadratic_damping_n_m_per_rps2 * abs(state.r_rps) * state.r_rps
        )
        return x_drag, y_drag, n_drag

    def derivatives(self, state: CraftState, command: ThrusterCommand, current_earth_mps: tuple[float, float]) -> CraftState:
        x_drag, y_drag, n_drag = self.hydrodynamic_forces(state, current_earth_mps)
        tau_u = command.total_thrust_n
        tau_n = self.thruster_half_spacing_m * (command.starboard_thrust_n - command.port_thrust_n)
        # Rigid-body body-frame acceleration with effective added masses. The
        # u*r and v*r terms preserve the planar body-frame coupling explicitly.
        u_dot = (tau_u + x_drag + self.mass.sway_mass_kg * state.v_mps * state.r_rps) / self.mass.surge_mass_kg
        v_dot = (y_drag - self.mass.surge_mass_kg * state.u_mps * state.r_rps) / self.mass.sway_mass_kg
        r_dot = (tau_n + n_drag) / self.mass.yaw_inertia_kg_m2
        rot = rotation_body_to_earth(state.psi_rad)
        earth_velocity = rot @ np.asarray([state.u_mps, state.v_mps], dtype=float)
        return CraftState(
            x_m=float(earth_velocity[0]), y_m=float(earth_velocity[1]), psi_rad=state.r_rps,
            u_mps=float(u_dot), v_mps=float(v_dot), r_rps=float(r_dot),
        )

    @staticmethod
    def _add(state: CraftState, derivative: CraftState, scale: float) -> CraftState:
        return CraftState.from_vector(state.as_vector() + scale * derivative.as_vector())

    def rk4_step(self, state: CraftState, command: ThrusterCommand, current_earth_mps: tuple[float, float], dt_s: float) -> CraftState:
        if dt_s <= 0.0:
            raise DynamicsError("dt_s must be positive.")
        k1 = self.derivatives(state, command, current_earth_mps)
        k2 = self.derivatives(self._add(state, k1, 0.5 * dt_s), command, current_earth_mps)
        k3 = self.derivatives(self._add(state, k2, 0.5 * dt_s), command, current_earth_mps)
        k4 = self.derivatives(self._add(state, k3, dt_s), command, current_earth_mps)
        vector = state.as_vector() + (dt_s / 6.0) * (k1.as_vector() + 2.0*k2.as_vector() + 2.0*k3.as_vector() + k4.as_vector())
        vector[2] = wrap_to_pi(float(vector[2]))
        return CraftState.from_vector(vector)

    def simulate(
        self,
        *,
        scenario: str,
        description: str,
        command_law: CommandLaw,
        current_earth_mps: tuple[float, float] = (0.0, 0.0),
        initial_state: CraftState = CraftState(),
        duration_s: float | None = None,
    ) -> SimulationResult:
        duration = duration_s if duration_s is not None else self.settings.max_simulation_time_s
        if duration <= 0.0:
            raise DynamicsError("duration_s must be positive.")
        dt = self.settings.integration_time_step_s
        sample_every = max(1, int(round(self.settings.trajectory_sample_interval_s / dt)))
        state = initial_state
        rows: list[dict[str, float | str]] = []
        steps = int(round(duration / dt))
        for step in range(steps + 1):
            time_s = step * dt
            command = command_law(time_s)
            u_rel, v_rel = self.relative_water_velocity_body(state, current_earth_mps)
            x_drag, y_drag, n_drag = self.hydrodynamic_forces(state, current_earth_mps)
            if step % sample_every == 0 or step == steps:
                rows.append({
                    "scenario": scenario, "time_s": float(time_s), "x_m": state.x_m, "y_m": state.y_m,
                    "psi_rad": state.psi_rad, "psi_deg": float(np.degrees(state.psi_rad)),
                    "u_mps": state.u_mps, "v_mps": state.v_mps, "r_rps": state.r_rps,
                    "speed_over_ground_mps": float(sqrt(state.u_mps**2 + state.v_mps**2)),
                    "u_relative_water_mps": u_rel, "v_relative_water_mps": v_rel,
                    "port_thrust_n": command.port_thrust_n, "starboard_thrust_n": command.starboard_thrust_n,
                    "total_thrust_n": command.total_thrust_n,
                    "yaw_moment_n_m": self.thruster_half_spacing_m * (command.starboard_thrust_n-command.port_thrust_n),
                    "x_drag_n": x_drag, "y_drag_n": y_drag, "yaw_drag_n_m": n_drag,
                    "current_x_mps": current_earth_mps[0], "current_y_mps": current_earth_mps[1],
                })
            if step < steps:
                state = self.rk4_step(state, command, current_earth_mps, dt)
        return SimulationResult(scenario=scenario, description=description, current_earth_mps=current_earth_mps, rows=rows)
