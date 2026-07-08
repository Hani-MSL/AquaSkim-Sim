from __future__ import annotations

from aquaskim.operating_envelope import assess_scenario, envelope_scenarios, load_operating_envelope, run_envelope_scenario


def test_reference_cross_current_case_completes_with_current_aware_guidance() -> None:
    scenario = next(item for item in envelope_scenarios(load_operating_envelope()) if item.identifier == "north_current_0_02")
    result, _ = run_envelope_scenario(scenario)
    assessment = assess_scenario(scenario, result)
    assert assessment.status == "VALIDATED_PASS"
    assert int(result.metrics["mission_success"]) == 1
    assert result.metrics["termination_reason"] == "all coverage lanes completed"
    assert float(result.metrics["minimum_clearance_m"]) >= 0.35 - 1e-9
