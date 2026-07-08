"""Registry of historical quota-based modules retained for traceability.

The listed modules are preserved because their figures, logs and tests document
an earlier development branch.  They must never be called by the fixed
non-interactive reference build.  The current reference path is explicitly
limited to ``mission_plant``, ``mission_quality``, ``reference_design``,
``phase10_7`` and ``phase10_8``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyModule:
    module: str
    reason: str
    allowed_use: str


QUOTA_BASED_LEGACY_MODULES: tuple[LegacyModule, ...] = (
    LegacyModule(
        module="aquaskim.autonomy",
        reason="State machine can terminate on max_collections.",
        allowed_use="Historical Phase 08/09 replay and source traceability only.",
    ),
    LegacyModule(
        module="aquaskim.phase08",
        reason="Uses the quota-based autonomy branch for legacy artefacts.",
        allowed_use="Historical artefact regeneration only; its physical-plant helper is now wrapped around mission_plant.",
    ),
    LegacyModule(
        module="aquaskim.phase08_2",
        reason="Extends the quota-based legacy demonstration.",
        allowed_use="Historical analysis only.",
    ),
    LegacyModule(
        module="aquaskim.phase09",
        reason="Scenario validation over the legacy quota mission policy.",
        allowed_use="Historical analysis only.",
    ),
    LegacyModule(
        module="aquaskim.phase09_2",
        reason="Scenario validation over the legacy quota mission policy.",
        allowed_use="Historical analysis only.",
    ),
    LegacyModule(
        module="aquaskim.phase10_4",
        reason="Legacy visual package whose scenario terminology retains target quotas.",
        allowed_use="Historical visual evidence only.",
    ),
)

REFERENCE_ALLOWED_MODULES: tuple[str, ...] = (
    "aquaskim.config",
    "aquaskim.geometry",
    "aquaskim.mass_properties",
    "aquaskim.hydrostatics",
    "aquaskim.hydrodynamics",
    "aquaskim.energy_model",
    "aquaskim.dynamics_3dof",
    "aquaskim.environment",
    "aquaskim.hopper_model",
    "aquaskim.mission_plant",
    "aquaskim.mission_quality",
    "aquaskim.reference_design",
    "aquaskim.maneuver_validation",
    "aquaskim.phase10_6",
    "aquaskim.phase10_7",
    "aquaskim.phase10_8",
    "aquaskim.reference_fidelity",
    "aquaskim.phase10_11",
)


def legacy_module_names() -> set[str]:
    return {entry.module for entry in QUOTA_BASED_LEGACY_MODULES}
