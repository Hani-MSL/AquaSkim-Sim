from __future__ import annotations

from aquaskim.phase10_7 import _run
from aquaskim.phase10_11 import _load_visualisation_config
from aquaskim.reference_design import load_reference_configuration, load_reference_scenario
from aquaskim.reference_fidelity import audit_reference_result


def test_visual_protocol_requires_long_form_evidence() -> None:
    protocol = _load_visualisation_config()
    assert protocol["render"]["frame_count"] >= 96
    assert protocol["acceptance"]["required_animation_count"] == 6
    assert protocol["acceptance"]["required_video_count"] == 6


def test_nominal_reference_launches_before_first_debris_diversion() -> None:
    result, _ = _run(load_reference_configuration())
    audit = audit_reference_result(
        result,
        scenario="nominal_coverage",
        expected_termination_fragment="all coverage lanes completed",
    )
    assert audit.summary["mission_success"] == 1
    assert audit.summary["first_motion_time_s"] < 12.0
    assert audit.summary["first_target_confirmation_time_s"] is not None
    assert float(audit.summary["first_target_confirmation_time_s"]) >= 12.0
    assert not audit.summary["early_return_before_30_s"]
    assert audit.summary["fixed_quota_absent_from_termination"]


def test_high_loading_fidelity_audit_records_capacity_return() -> None:
    result, _ = _run(load_reference_scenario("reference_high_loading.yaml"))
    audit = audit_reference_result(
        result,
        scenario="high_loading_capacity",
        expected_termination_fragment="hopper occupied-volume trigger",
    )
    assert audit.summary["mission_success"] == 1
    assert audit.summary["expected_termination_match"]
    assert audit.summary["coverage_progress_monotonic"]
    assert audit.summary["collection_event_count"] >= 1
    assert all(check["status"] == "PASS" for check in audit.checks)
