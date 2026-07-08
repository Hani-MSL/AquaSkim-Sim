from __future__ import annotations

from aquaskim.mission_quality import QualityMissionResult
from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration
from aquaskim.system_scenario_validation import (
    assess_system_scenario,
    configuration_for_system_scenario,
    load_system_validation,
    system_scenarios,
)


def test_system_validation_protocol_has_required_segregated_classes() -> None:
    protocol = load_system_validation()
    scenarios = system_scenarios(protocol)
    classes = [scenario.classification for scenario in scenarios]
    assert classes.count("validated") >= 4
    assert classes.count("boundary") >= 1
    assert classes.count("controlled_failure") >= 2
    assert all("max_collections" not in str(scenario.overrides).lower() for scenario in scenarios)
    assert all("target_quota" not in str(scenario.overrides).lower() for scenario in scenarios)


def test_uncompensated_crossflow_is_an_explicit_versioned_policy_override() -> None:
    scenario = next(item for item in system_scenarios() if item.identifier == "uncompensated_diagonal_crossflow")
    config = configuration_for_system_scenario(load_reference_configuration(), scenario)
    assert config.data["reference_mission"]["validated_control_policy"]["current_compensation_enabled"] is False
    assert _settings(config.data).current_compensation_enabled is False


def test_controlled_failure_is_accepted_only_for_declared_noncolliding_termination() -> None:
    scenario = next(item for item in system_scenarios() if item.identifier == "scheduled_time_limit")
    result = QualityMissionResult(
        rows=[], events=[], routes=[], targets=[],
        metrics={
            "mission_success": 0,
            "termination_reason": "mission time limit reached",
            "minimum_clearance_m": 0.52,
            "coverage_fraction": 0.0,
            "final_distance_home_m": 7.0,
        },
    )
    assessment = assess_system_scenario(scenario, result)
    assert assessment.accepted is True
    assert assessment.status == "CONTROLLED_FAILURE_OBSERVED"
