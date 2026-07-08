from __future__ import annotations

from aquaskim.phase10_7 import _run
from aquaskim.reference_design import load_reference_configuration, load_reference_scenario


def test_nominal_mission_passes_closed_loop_quality_gate() -> None:
    result, _ = _run(load_reference_configuration())
    metrics = result.metrics
    assert metrics["mission_success"] == 1
    assert metrics["coverage_fraction"] >= 0.999
    assert metrics["watchdog_event_count"] == 0
    assert metrics["safety_event_count"] <= 1
    assert metrics["tracking_heading_error_p95_deg"] <= 15.0
    assert metrics["final_distance_home_m"] <= 0.35


def test_high_loading_returns_on_hopper_capacity_with_healthy_tracking() -> None:
    result, _ = _run(load_reference_scenario("reference_high_loading.yaml"))
    metrics = result.metrics
    assert metrics["mission_success"] == 1
    assert "hopper occupied-volume trigger" in metrics["termination_reason"]
    assert metrics["hopper_volume_fraction"] >= 0.95
    assert metrics["watchdog_event_count"] == 0
    assert metrics["safety_event_count"] <= 1
    assert metrics["tracking_heading_error_p95_deg"] <= 15.0


def test_deferred_targets_do_not_retrigger_forever() -> None:
    result, _ = _run(load_reference_configuration())
    confirmed = [event["target_id"] for event in result.events if event.get("event") == "TARGET_CONFIRMED"]
    deferred = [event["target_id"] for event in result.events if event.get("event") == "TARGET_DEFERRED"]
    assert len(confirmed) == len(set(confirmed))
    assert len(deferred) == len(set(deferred))
