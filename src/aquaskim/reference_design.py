"""Fixed, non-interactive reference-design configuration loader."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from aquaskim.config import ProjectConfiguration, validate_base_configuration
from aquaskim.project_profile import deep_merge


class ReferenceDesignError(ValueError):
    """Raised when reference design definitions are missing or inconsistent."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ReferenceDesignError(f"Reference design file is missing: {path}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ReferenceDesignError(f"Reference design must be a YAML mapping: {path}")
    return parsed


def load_reference_configuration() -> ProjectConfiguration:
    """Load base_parameters.yaml plus the versioned reference overlay.

    Local user_profile.yaml files are intentionally ignored.  This guarantees
    that a clean GitHub clone and the official project report use the same
    reference configuration.
    """
    base_path = project_root() / "config" / "base_parameters.yaml"
    base = _read_yaml(base_path)
    overlay_path = project_root() / "config" / "reference_design.yaml"
    overlay = _read_yaml(overlay_path)
    if "overrides" not in overlay or not isinstance(overlay["overrides"], dict):
        raise ReferenceDesignError("reference_design.yaml requires an overrides mapping.")

    data = deep_merge(deepcopy(base), overlay["overrides"])

    # ``max_collections`` belongs to the historical autonomy branch.  The
    # fixed reference mission never receives this compatibility field: it
    # terminates only on capacity, energy, time, safety or coverage.  The base
    # configuration retains the key for Legacy replays, while the official
    # non-interactive reference path removes it before validation.
    autonomy = data.get("autonomy")
    if isinstance(autonomy, dict):
        autonomy.pop("max_collections", None)

    # The fixed reference policy is intentionally stored beside the physical
    # override block so it remains readable in the design document. Merge it
    # explicitly into the effective configuration; otherwise the mission
    # runner silently falls back to generic defaults instead of the versioned
    # stop-turn-go, low-speed current-compensation and fidelity policy.
    reference_mission = overlay.get("reference_mission")
    if reference_mission is not None:
        if not isinstance(reference_mission, dict):
            raise ReferenceDesignError("reference_design.yaml reference_mission must be a mapping.")
        data["reference_mission"] = deepcopy(reference_mission)

    debris_field = data.get("experiment_model", {}).get("debris_field", {})
    environment = data["mission"]["environment"]
    density = float(debris_field.get("areal_density_items_m2", 0.40))
    count = int(round(float(environment["length_m"]) * float(environment["width_m"]) * density))
    count = max(3, min(120, count))
    data.setdefault("environment_model", {}).setdefault("debris", {})["count"] = count
    data.setdefault("experiment_model", {}).setdefault("debris_field", {})[
        "derived_discrete_item_count"
    ] = count

    validate_base_configuration(data)
    return ProjectConfiguration(source_path=overlay_path, data=data)


def load_parameter_registry() -> dict[str, Any]:
    return _read_yaml(project_root() / "config" / "parameter_registry.yaml")


def load_reference_scenario(name: str) -> ProjectConfiguration:
    """Load the fixed reference design and a versioned scenario overlay.

    This function never reads config/user_profile.yaml. Scenario names are
    intentionally file-based and version controlled; this is the reproducible
    alternative to an interactive configuration wizard.
    """
    scenario_path = project_root() / "config" / "scenarios" / name
    scenario = _read_yaml(scenario_path)
    overrides = scenario.get("overrides")
    if not isinstance(overrides, dict):
        raise ReferenceDesignError(f"Scenario requires an overrides mapping: {scenario_path}")
    reference = load_reference_configuration()
    data = deep_merge(deepcopy(reference.data), overrides)
    validate_base_configuration(data)
    return ProjectConfiguration(source_path=scenario_path, data=data)
