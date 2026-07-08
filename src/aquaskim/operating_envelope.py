"""Deterministic operating-envelope helpers for the fixed reference mission.

This module separates a validated sheltered-basin envelope from deliberately
out-of-envelope boundary observations.  It does not read local user profiles,
invoke report generation or classify a boundary limitation as a release pass.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any

import yaml

from aquaskim.config import ProjectConfiguration, validate_base_configuration
from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.mission_quality import QualityMissionResult, run_quality_mission
from aquaskim.phase10_6 import _settings
from aquaskim.project_profile import deep_merge
from aquaskim.reference_design import load_reference_configuration, project_root


class OperatingEnvelopeError(ValueError):
    """Raised when the versioned operating-envelope protocol is inconsistent."""


@dataclass(frozen=True)
class EnvelopeScenario:
    identifier: str
    title: str
    classification: str
    description: str
    overrides: dict[str, Any]
    expected: dict[str, Any]

    @property
    def current_magnitude_mps(self) -> float:
        values = self.overrides.get("autonomy", {}).get("current_earth_mps", [0.0, 0.0])
        return hypot(float(values[0]), float(values[1]))


@dataclass(frozen=True)
class ScenarioAssessment:
    scenario_id: str
    classification: str
    status: str
    accepted: bool
    checks: list[dict[str, Any]]
    metrics: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise OperatingEnvelopeError(f"Operating-envelope file must be a mapping: {path}")
    return parsed


def load_operating_envelope(path: Path | None = None) -> dict[str, Any]:
    source = path or (project_root() / "config" / "reference_operating_envelope.yaml")
    parsed = _read_yaml(source)
    protocol = parsed.get("reference_operating_envelope")
    if not isinstance(protocol, dict):
        raise OperatingEnvelopeError("reference_operating_envelope.yaml requires a reference_operating_envelope mapping.")
    scenarios = protocol.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise OperatingEnvelopeError("Operating envelope requires a non-empty scenarios list.")
    limit = float(protocol.get("validated_current_limit_mps", 0.0))
    if limit <= 0.0:
        raise OperatingEnvelopeError("validated_current_limit_mps must be positive.")
    ids: set[str] = set()
    validated = 0
    boundary = 0
    for item in scenarios:
        scenario = scenario_from_mapping(item)
        if scenario.identifier in ids:
            raise OperatingEnvelopeError(f"Duplicate scenario identifier: {scenario.identifier}")
        ids.add(scenario.identifier)
        if scenario.classification == "validated":
            validated += 1
            if scenario.current_magnitude_mps > limit + 1e-9:
                raise OperatingEnvelopeError(
                    f"Validated scenario {scenario.identifier} exceeds the current limit {limit:.3f} m/s."
                )
        elif scenario.classification == "boundary":
            boundary += 1
        else:
            raise OperatingEnvelopeError(f"Unsupported scenario class: {scenario.classification}")
    if validated < 4 or boundary < 1:
        raise OperatingEnvelopeError("Envelope requires at least four validated cases and one boundary case.")
    return protocol


def scenario_from_mapping(item: Any) -> EnvelopeScenario:
    if not isinstance(item, dict):
        raise OperatingEnvelopeError("Each operating-envelope scenario must be a mapping.")
    required = ("id", "title", "class", "description", "overrides", "expected")
    missing = [key for key in required if key not in item]
    if missing:
        raise OperatingEnvelopeError(f"Scenario is missing required keys: {missing}")
    if not isinstance(item["overrides"], dict) or not isinstance(item["expected"], dict):
        raise OperatingEnvelopeError("Scenario overrides and expected sections must be mappings.")
    return EnvelopeScenario(
        identifier=str(item["id"]),
        title=str(item["title"]),
        classification=str(item["class"]),
        description=str(item["description"]),
        overrides=deepcopy(item["overrides"]),
        expected=deepcopy(item["expected"]),
    )


def envelope_scenarios(protocol: dict[str, Any] | None = None) -> list[EnvelopeScenario]:
    active = protocol if protocol is not None else load_operating_envelope()
    return [scenario_from_mapping(item) for item in active["scenarios"]]


def configuration_for_scenario(base: ProjectConfiguration, scenario: EnvelopeScenario) -> ProjectConfiguration:
    data = deep_merge(deepcopy(base.data), scenario.overrides)
    validate_base_configuration(data)
    return ProjectConfiguration(source_path=base.source_path, data=data)


def run_envelope_scenario(scenario: EnvelopeScenario, base: ProjectConfiguration | None = None) -> tuple[QualityMissionResult, Any]:
    config = configuration_for_scenario(base or load_reference_configuration(), scenario)
    model, environment, _, battery, battery_settings, energy_settings = build_digital_twin_plant(config)
    result = run_quality_mission(
        model=model,
        environment=environment,
        battery=battery,
        battery_settings=battery_settings,
        energy_settings=energy_settings,
        settings=_settings(config.data),
        debris=environment.generate_debris(),
    )
    return result, environment


def assess_scenario(scenario: EnvelopeScenario, result: QualityMissionResult) -> ScenarioAssessment:
    metrics = dict(result.metrics)
    expected = scenario.expected
    checks: list[dict[str, Any]] = []

    def check(name: str, observed: Any, criterion: str, passed: bool) -> None:
        checks.append({"scenario": scenario.identifier, "check": name, "observed": observed, "criterion": criterion, "status": "PASS" if passed else "FAIL"})

    required_success = bool(expected.get("mission_success", True))
    success_observed = bool(int(metrics.get("mission_success", 0)))
    check("mission success expectation", success_observed, f"mission_success == {required_success}", success_observed == required_success)

    fragment = str(expected.get("termination_contains", ""))
    termination = str(metrics.get("termination_reason", ""))
    if fragment:
        check("termination reason", termination, f"contains '{fragment}'", fragment.lower() in termination.lower())

    if "minimum_coverage_fraction" in expected:
        minimum = float(expected["minimum_coverage_fraction"])
        observed = float(metrics.get("coverage_fraction", 0.0))
        check("coverage fraction", observed, f">= {minimum:.3f}", observed + 1e-9 >= minimum)

    if "minimum_clearance_m" in expected:
        minimum = float(expected["minimum_clearance_m"])
        observed = float(metrics.get("minimum_clearance_m", float("-inf")))
        check("minimum clearance", observed, f">= {minimum:.3f} m", observed + 1e-9 >= minimum)

    if "maximum_home_error_m" in expected:
        maximum = float(expected["maximum_home_error_m"])
        observed = float(metrics.get("final_distance_home_m", float("inf")))
        check("home docking error", observed, f"<= {maximum:.3f} m", observed <= maximum + 1e-9)

    # A boundary case is accepted when it is observed as its declared limited
    # behaviour and remains non-colliding. It is never folded into the
    # validated-success rate.
    accepted = all(row["status"] == "PASS" for row in checks)
    if scenario.classification == "boundary":
        status = "BOUNDARY_OBSERVED" if accepted else "BOUNDARY_MISMATCH"
    else:
        status = "VALIDATED_PASS" if accepted else "VALIDATED_FAIL"
    return ScenarioAssessment(scenario.identifier, scenario.classification, status, accepted, checks, metrics)
