from __future__ import annotations
from functools import lru_cache

from aquaskim.payload_maneuver_validation import assess_suite, load_payload_maneuver_protocol, run_payload_maneuver_suite


@lru_cache(maxsize=1)
def _suite():
    return run_payload_maneuver_suite()


def test_payload_protocol_is_limited_to_documented_low_current() -> None:
    protocol = load_payload_maneuver_protocol()
    assert float(protocol["validated_current_magnitude_mps"]) == 0.020
    assert float(protocol["manoeuvres"]["low_current_turn"]["current_earth_mps"][1]) == 0.020


def test_full_payload_and_raised_payload_preserve_static_acceptance_thresholds() -> None:
    static, _, protocol = _suite()
    required_gm = float(protocol["static_analysis"]["required_minimum_gm_m"])
    required_freeboard = float(protocol["static_analysis"]["required_minimum_freeboard_m"])
    selected = [item for item in static if item.payload_case.identifier in {"full_low_central", "full_raised_central"}]
    assert len(selected) == 2
    assert all(item.hydro_case.gm_m >= required_gm for item in selected)
    assert all(item.hydro_case.freeboard_m >= required_freeboard for item in selected)


def test_port_offset_case_has_bounded_quasistatic_equilibrium_heel() -> None:
    static, _, protocol = _suite()
    offset = next(item for item in static if item.payload_case.identifier == "full_port_offset")
    assert offset.payload_heeling_moment_n_m > 0.0
    assert 0.0 < offset.offset_equilibrium_heel_deg <= float(protocol["static_analysis"]["offset_equilibrium_limit_deg"])
    assert offset.offset_righting_margin_ratio >= float(protocol["static_analysis"]["required_righting_margin_ratio"])


def test_payload_manoeuvre_suite_records_mass_and_low_current_effects() -> None:
    _, maneuvers, protocol = _suite()
    assert float(maneuvers["step_full"].metrics["steady_speed_mps"]) >= float(protocol["acceptance"]["minimum_full_payload_steady_speed_mps"])
    assert float(maneuvers["turn_full_current"].metrics["final_y_m"]) > float(maneuvers["turn_full_calm"].metrics["final_y_m"])
    assert float(maneuvers["zigzag_full"].metrics["reversal_count"]) >= float(protocol["acceptance"]["minimum_zigzag_heading_crossings"])


def test_payload_manoeuvre_acceptance_ledger_passes() -> None:
    static, maneuvers, protocol = _suite()
    checks = assess_suite(static, maneuvers, protocol)
    assert len(checks) >= 20
    assert all(bool(row["passed"]) for row in checks)
