from __future__ import annotations

import math

from aquaskim.mission_quality import current_aware_course_command


def test_zero_activation_keeps_feedforward_active_for_any_nonzero_ground_speed() -> None:
    course, water_speed, crab = current_aware_course_command(
        0.0,
        0.01,
        (0.0, 0.02),
        enabled=True,
        gain=1.0,
        activation_speed_mps=0.0,
    )
    assert water_speed > 0.01
    assert course < 0.0
    assert crab < 0.0


def test_positive_activation_is_explicitly_respected_for_nonreference_experiments() -> None:
    course, water_speed, crab = current_aware_course_command(
        math.pi / 4.0,
        0.02,
        (0.0, 0.02),
        enabled=True,
        gain=1.0,
        activation_speed_mps=0.03,
    )
    assert course == math.pi / 4.0
    assert water_speed == 0.02
    assert crab == 0.0
