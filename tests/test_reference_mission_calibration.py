from aquaskim.phase10_7 import _run
from aquaskim.reference_design import load_reference_configuration, load_reference_scenario


def test_nominal_reference_case_completes_coverage_and_docks() -> None:
    result, _ = _run(load_reference_configuration())
    assert result.metrics["mission_success"] == 1
    assert result.metrics["final_state"] == "MISSION_COMPLETE"
    assert result.metrics["coverage_fraction"] >= 0.999
    assert result.metrics["watchdog_event_count"] == 0
    assert result.metrics["termination_reason"] == "all coverage lanes completed"


def test_high_loading_case_returns_on_hopper_volume_not_capture_quota() -> None:
    result, _ = _run(load_reference_scenario("reference_high_loading.yaml"))
    assert result.metrics["mission_success"] == 1
    assert "hopper occupied-volume trigger" in result.metrics["termination_reason"]
    assert result.metrics["hopper_volume_fraction"] >= 0.95
    assert result.metrics["watchdog_event_count"] == 0
