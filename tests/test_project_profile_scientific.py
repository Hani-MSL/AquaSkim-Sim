from __future__ import annotations

from aquaskim.config import load_base_configuration
from aquaskim.project_profile import build_experiment_profile, derive_debris_count


def test_debris_count_is_derived_from_density_and_basin_area() -> None:
    assert derive_debris_count(
        basin_length_m=12.0,
        basin_width_m=8.0,
        areal_density_items_m2=0.25,
    ) == 24


def test_scientific_profile_contains_no_personal_submission_metadata() -> None:
    config = load_base_configuration(apply_local_profile=False)
    profile = build_experiment_profile(
        profile_name="capacity_study",
        experiment_kind="hopper_capacity",
        base_data=config.data,
        basket_usable_volume_l=5.0,
        payload_mass_limit_kg=1.0,
        basket_packing_factor=0.65,
    )
    assert "submission_metadata" not in profile
    hopper = profile["overrides"]["experiment_model"]["hopper"]
    assert hopper["usable_volume_l"] == 5.0
    assert hopper["payload_mass_limit_kg"] == 1.0
    assert "item count is a reported outcome" in hopper["termination_policy"]


def test_current_magnitude_and_direction_are_converted_to_earth_components() -> None:
    config = load_base_configuration(apply_local_profile=False)
    profile = build_experiment_profile(
        profile_name="current_case",
        experiment_kind="current_robustness",
        base_data=config.data,
        current_speed_mps=0.10,
        current_direction_deg=90.0,
    )
    x, y = profile["overrides"]["autonomy"]["current_earth_mps"]
    assert abs(x) < 1e-10
    assert abs(y - 0.10) < 1e-10
