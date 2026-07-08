"""Deterministic system-level scenario validation for the fixed reference craft.

The protocol deliberately separates validated missions from boundary observations
and controlled failures.  A controlled failure is accepted only when the declared
supervisory termination occurs without collision; it is never counted as a
validated operating success.
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


class SystemScenarioError(ValueError):
    """Raised when the system-level protocol is malformed."""


@dataclass(frozen=True)
class SystemScenario:
    identifier: str
    title: str
    classification: str
    description: str
    overrides: dict[str, Any]
    expected: dict[str, Any]

    @property
    def current_magnitude_mps(self) -> float:
        current = self.overrides.get("autonomy", {}).get("current_earth_mps", [0.0, 0.0])
        return hypot(float(current[0]), float(current[1]))


@dataclass(frozen=True)
class SystemAssessment:
    scenario_id: str
    classification: str
    status: str
    accepted: bool
    checks: list[dict[str, Any]]
    metrics: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise SystemScenarioError(f"System-validation file must be a mapping: {path}")
    return parsed


def load_system_validation(path: Path | None = None) -> dict[str, Any]:
    source = path or (project_root() / "config" / "reference_system_validation.yaml")
    parsed = _read_yaml(source)
    protocol = parsed.get("reference_system_validation")
    if not isinstance(protocol, dict):
        raise SystemScenarioError("reference_system_validation.yaml requires a reference_system_validation mapping.")
    raw_scenarios = protocol.get("scenarios")
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) < 6:
        raise SystemScenarioError("System-validation protocol requires at least six scenarios.")
    accepted_classes = {str(value) for value in protocol.get("accepted_classes", [])}
    if accepted_classes != {"validated", "boundary", "controlled_failure"}:
        raise SystemScenarioError("accepted_classes must contain validated, boundary and controlled_failure exactly.")
    identifiers: set[str] = set()
    counts = {key: 0 for key in accepted_classes}
    limit = float(protocol.get("validated_current_limit_mps", 0.0))
    if limit <= 0.0:
        raise SystemScenarioError("validated_current_limit_mps must be positive.")
    if float(protocol.get("logging_sample_period_s", 0.0)) <= 0.0:
        raise SystemScenarioError("logging_sample_period_s must be positive.")
    for raw in raw_scenarios:
        scenario = scenario_from_mapping(raw)
        if scenario.identifier in identifiers:
            raise SystemScenarioError(f"Duplicate system scenario: {scenario.identifier}")
        identifiers.add(scenario.identifier)
        if scenario.classification not in accepted_classes:
            raise SystemScenarioError(f"Unsupported system scenario class: {scenario.classification}")
        counts[scenario.classification] += 1
        if scenario.classification == "validated" and scenario.current_magnitude_mps > limit + 1e-9:
            raise SystemScenarioError("Validated system scenario exceeds the versioned current limit.")
    if counts["validated"] < 4 or counts["boundary"] < 1 or counts["controlled_failure"] < 2:
        raise SystemScenarioError("Protocol requires >=4 validated, >=1 boundary and >=2 controlled-failure scenarios.")
    return protocol


def scenario_from_mapping(raw: Any) -> SystemScenario:
    if not isinstance(raw, dict):
        raise SystemScenarioError("Each system scenario must be a mapping.")
    required = ("id", "title", "class", "description", "overrides", "expected")
    missing = [key for key in required if key not in raw]
    if missing:
        raise SystemScenarioError(f"System scenario is missing keys: {missing}")
    if not isinstance(raw["overrides"], dict) or not isinstance(raw["expected"], dict):
        raise SystemScenarioError("System scenario overrides and expected must be mappings.")
    return SystemScenario(
        identifier=str(raw["id"]),
        title=str(raw["title"]),
        classification=str(raw["class"]),
        description=str(raw["description"]),
        overrides=deepcopy(raw["overrides"]),
        expected=deepcopy(raw["expected"]),
    )


def system_scenarios(protocol: dict[str, Any] | None = None) -> list[SystemScenario]:
    active = protocol or load_system_validation()
    return [scenario_from_mapping(raw) for raw in active["scenarios"]]


def configuration_for_system_scenario(base: ProjectConfiguration, scenario: SystemScenario) -> ProjectConfiguration:
    data = deep_merge(deepcopy(base.data), scenario.overrides)
    validate_base_configuration(data)
    return ProjectConfiguration(source_path=base.source_path, data=data)


def run_system_scenario(
    scenario: SystemScenario,
    base: ProjectConfiguration | None = None,
) -> tuple[QualityMissionResult, Any]:
    config = configuration_for_system_scenario(base or load_reference_configuration(), scenario)
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


def assess_system_scenario(scenario: SystemScenario, result: QualityMissionResult) -> SystemAssessment:
    metrics = dict(result.metrics)
    expected = scenario.expected
    checks: list[dict[str, Any]] = []

    def add(name: str, observed: Any, criterion: str, passed: bool) -> None:
        checks.append({
            "scenario": scenario.identifier,
            "classification": scenario.classification,
            "check": name,
            "observed": observed,
            "criterion": criterion,
            "status": "PASS" if passed else "FAIL",
        })

    expected_success = bool(expected.get("mission_success", True))
    observed_success = bool(int(metrics.get("mission_success", 0)))
    add("mission-success expectation", observed_success, f"mission_success == {expected_success}", observed_success == expected_success)

    termination = str(metrics.get("termination_reason", ""))
    fragment = str(expected.get("termination_contains", ""))
    if fragment:
        add("declared termination", termination, f"contains '{fragment}'", fragment.lower() in termination.lower())

    if "minimum_clearance_m" in expected:
        minimum = float(expected["minimum_clearance_m"])
        observed = float(metrics.get("minimum_clearance_m", float("-inf")))
        add("minimum clearance", observed, f">= {minimum:.3f} m", observed + 1e-9 >= minimum)

    if "minimum_coverage_fraction" in expected:
        minimum = float(expected["minimum_coverage_fraction"])
        observed = float(metrics.get("coverage_fraction", 0.0))
        add("coverage completion", observed, f">= {minimum:.3f}", observed + 1e-9 >= minimum)

    if "maximum_coverage_fraction" in expected:
        maximum = float(expected["maximum_coverage_fraction"])
        observed = float(metrics.get("coverage_fraction", 0.0))
        add("coverage remains intentionally incomplete", observed, f"<= {maximum:.3f}", observed <= maximum + 1e-9)

    if "maximum_home_error_m" in expected:
        maximum = float(expected["maximum_home_error_m"])
        observed = float(metrics.get("final_distance_home_m", float("inf")))
        add("home-docking error", observed, f"<= {maximum:.3f} m", observed <= maximum + 1e-9)

    if "minimum_collected_count" in expected:
        minimum = int(expected["minimum_collected_count"])
        observed = int(metrics.get("collected_count", 0))
        add("collection result", observed, f">= {minimum}", observed >= minimum)

    if bool(expected.get("quota_absent", False)):
        event_reasons = " ".join(str(item.get("reason", "")) for item in result.events)
        quota_absent = "quota" not in (termination + " " + event_reasons).lower()
        add("quota absent from reference termination", quota_absent, "no quota-derived termination or transition", quota_absent)

    accepted = all(check["status"] == "PASS" for check in checks)
    status_by_class = {
        "validated": "VALIDATED_PASS" if accepted else "VALIDATED_FAIL",
        "boundary": "BOUNDARY_OBSERVED" if accepted else "BOUNDARY_MISMATCH",
        "controlled_failure": "CONTROLLED_FAILURE_OBSERVED" if accepted else "CONTROLLED_FAILURE_MISMATCH",
    }
    return SystemAssessment(scenario.identifier, scenario.classification, status_by_class[scenario.classification], accepted, checks, metrics)
