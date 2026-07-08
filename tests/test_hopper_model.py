import math

from aquaskim.hopper_model import HopperSettings, HopperState


def test_hopper_volume_conversion_and_effective_limit() -> None:
    settings = HopperSettings(
        usable_volume_l=4.0,
        payload_mass_limit_kg=0.80,
        equivalent_bulk_density_kg_m3=75.0,
        packing_factor=0.62,
    )
    assert math.isclose(settings.mass_equivalent_volume_limit_kg, 0.186, abs_tol=1e-12)
    assert math.isclose(settings.effective_payload_limit_kg, 0.186, abs_tol=1e-12)
    assert math.isclose(settings.occupied_volume_l(0.093), 2.0, abs_tol=1e-12)


def test_hopper_returns_on_volume_trigger_not_item_count() -> None:
    settings = HopperSettings(4.0, 0.80, 75.0, 0.62, 0.95)
    state = HopperState()
    for _ in range(9):
        state = state.add(0.020, settings)
    required, reason = state.return_required(settings)
    assert required
    assert "volume" in reason
    assert state.captured_items == 9


def test_mass_limit_is_independent_from_volume_limit() -> None:
    settings = HopperSettings(20.0, 0.10, 75.0, 0.62, 0.95)
    state = HopperState().add(0.096, settings)
    required, reason = state.return_required(settings)
    assert required
    assert "mass" in reason
