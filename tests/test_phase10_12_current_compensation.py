from __future__ import annotations

import math

from aquaskim.mission_quality import current_aware_course_command
from aquaskim.operating_envelope import envelope_scenarios, load_operating_envelope


def test_current_compensation_is_neutral_in_calm_water() -> None:
    course, water_speed, crab = current_aware_course_command(0.42, 0.18, (0.0, 0.0))
    assert math.isclose(course, 0.42, abs_tol=1e-12)
    assert math.isclose(water_speed, 0.18, abs_tol=1e-12)
    assert math.isclose(crab, 0.0, abs_tol=1e-12)


def test_cross_current_produces_a_physical_crab_command() -> None:
    course, water_speed, crab = current_aware_course_command(0.0, 0.18, (0.0, 0.02))
    assert course < 0.0
    assert crab < 0.0
    assert water_speed > 0.18


def test_disabling_compensation_preserves_the_raw_los_command() -> None:
    course, water_speed, crab = current_aware_course_command(0.71, 0.13, (0.0, 0.02), enabled=False)
    assert math.isclose(course, 0.71, abs_tol=1e-12)
    assert math.isclose(water_speed, 0.13, abs_tol=1e-12)
    assert math.isclose(crab, 0.0, abs_tol=1e-12)


def test_operating_envelope_declares_validated_and_boundary_cases() -> None:
    protocol = load_operating_envelope()
    scenarios = envelope_scenarios(protocol)
    validated = [item for item in scenarios if item.classification == "validated"]
    boundary = [item for item in scenarios if item.classification == "boundary"]
    assert len(validated) >= 6
    assert len(boundary) == 1
    limit = float(protocol["validated_current_limit_mps"])
    assert all(item.current_magnitude_mps <= limit + 1e-12 for item in validated)
    assert boundary[0].current_magnitude_mps > limit
