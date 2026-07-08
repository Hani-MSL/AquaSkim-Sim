from __future__ import annotations

import copy

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.phase09_2 import _contract_for_base, _load_plan, _scenario_status


def test_phase09_2_catalog_has_validated_protective_and_boundary_classes() -> None:
    scenarios, contract = _load_plan()
    assert len(scenarios) == 6
    assert {item.scenario_class for item in scenarios} == {"validated", "boundary"}
    assert contract["monte_carlo_trials"] >= 8
    assert any(item.expected_outcome == "proactive_return" for item in scenarios)


def test_phase09_2_profile_validation_contract_can_override_defaults() -> None:
    base = load_base_configuration()
    data = copy.deepcopy(base.data)
    data.setdefault("validation", {}).setdefault("phase09_2", {})["monte_carlo_trials"] = 8
    _, base_contract = _load_plan()
    contract = _contract_for_base(ProjectConfiguration(base.source_path, data), base_contract)
    assert contract["monte_carlo_trials"] == 8


def test_phase09_2_outcome_classifier_retains_boundary_limits() -> None:
    class Result:
        metrics = {"mission_success": 0, "energy_return_triggered": 0, "final_state": "TRANSIT_TO_DEBRIS"}
    assert _scenario_status(Result(), "time_limited_boundary") == "BOUNDARY_LIMIT"
