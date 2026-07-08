"""Shared non-legacy digital-twin plant assembly.

Reference missions and manoeuvre verification use this module to assemble the
common 3-DOF plant.  It deliberately does not import the legacy quota-based
autonomy state machine.  Older Phase 08/09 modules may wrap this function for
historical replay compatibility, but the fixed reference path must not depend
on those policy modules.
"""
from __future__ import annotations

from aquaskim.config import ProjectConfiguration
from aquaskim.dynamics_3dof import DynamicsSettings, PlanarCatamaranDynamics
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings
from aquaskim.environment import EnvironmentSettings, SensorSettings
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrodynamics import CatamaranResistanceModel, HydrodynamicSettings
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases


def build_digital_twin_plant(
    config: ProjectConfiguration,
) -> tuple[
    PlanarCatamaranDynamics,
    EnvironmentSettings,
    SensorSettings,
    BatteryModel,
    BatterySettings,
    EnergySettings,
]:
    """Create the versioned physical plant shared by reference simulations.

    The full-payload hydrostatic case is used as a conservative design mass
    state for the planar dynamics.  This selection is documented and does not
    impose any collection-count mission termination policy.
    """
    data = config.data
    geometry = CatamaranGeometry.from_config(data)
    hydro = CatamaranHydrostatics(geometry, HydrostaticSettings.from_config(data))
    _, full_mass = build_load_cases(data)["full_design_payload"]
    full_case = hydro.case_from_mass_properties("full_design_payload", full_mass)
    resistance = CatamaranResistanceModel(
        geometry,
        HydrodynamicSettings.from_config(data),
        full_case,
    )
    model = PlanarCatamaranDynamics(
        geometry=geometry,
        resistance=resistance,
        hydro_case=full_case,
        mass_properties=full_mass,
        settings=DynamicsSettings.from_config(data),
    )
    battery_settings = BatterySettings.from_config(data)
    return (
        model,
        EnvironmentSettings.from_config(data),
        SensorSettings.from_config(data),
        BatteryModel(battery_settings),
        battery_settings,
        EnergySettings.from_config(data),
    )
