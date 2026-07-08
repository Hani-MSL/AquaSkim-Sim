from __future__ import annotations

from functools import lru_cache

from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration

from aquaskim.control_robustness import (
    assess_control_suite,
    control_cases,
    load_control_robustness,
    run_control_suite,
    sensitivity_cases,
)


def test_control_robustness_protocol_declares_bounded_current_and_gain_grid() -> None:
    protocol = load_control_robustness()
    cases = control_cases(protocol)
    sensitivity = sensitivity_cases(protocol)
    assert float(protocol["validated_current_magnitude_mps"]) == 0.02
    assert any(item.control_mode == "open_loop" for item in cases)
    assert any(item.classification == "validated" for item in cases)
    assert len(sensitivity) == 9


@lru_cache(maxsize=1)
def _suite():
    return run_control_suite()


def test_current_aware_nominal_case_reduces_cross_track_error_against_open_loop() -> None:
    cases, sensitivity, protocol = _suite()
    by_id = {item.case.identifier: item for item in cases}
    open_loop = by_id["open_loop_cross_current"].metrics
    nominal = by_id["compensated_nominal"].metrics
    assert nominal["final_abs_cross_track_error_m"] < open_loop["final_abs_cross_track_error_m"]
    assert nominal["p95_abs_cross_track_error_m"] < 0.18
    assert nominal["mean_ground_speed_mps"] > 0.12
    assert len(sensitivity) == 9
    assert all(row["status"] == "PASS" for row in assess_control_suite(cases, sensitivity, protocol))


def test_reference_control_robustness_uses_only_documented_low_current_case() -> None:
    cases, sensitivity, protocol = _suite()
    limit = float(protocol["validated_current_magnitude_mps"])
    assert all(item.metrics["current_magnitude_mps"] <= limit + 1e-12 for item in cases + sensitivity)


def test_reference_design_policy_is_merged_into_effective_noninteractive_configuration() -> None:
    config = load_reference_configuration()
    policy = config.data.get("reference_mission", {}).get("validated_control_policy", {})
    settings = _settings(config.data)
    assert policy["current_compensation_activation_speed_mps"] == 0.0
    assert settings.current_compensation_activation_speed_mps == 0.0
    assert settings.lookahead_m == float(policy["guidance_lookahead_m"])
