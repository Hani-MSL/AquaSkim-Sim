import math

from aquaskim.config import load_base_configuration
from aquaskim.energy_model import BatteryModel, BatterySettings, EnergySettings


def test_usable_energy_is_positive_and_less_than_nominal() -> None:
    config = load_base_configuration()
    battery = BatteryModel(BatterySettings.from_config(config.data))
    assert 0.0 < battery.settings.usable_energy_wh < battery.settings.nominal_energy_wh


def test_soc_decreases_under_positive_load() -> None:
    config = load_base_configuration()
    battery = BatteryModel(BatterySettings.from_config(config.data))
    later_soc = battery.soc_after_interval(1.0, 20.0, 3600.0)
    assert 0.0 < later_soc < 1.0


def test_voltage_is_monotonic_with_soc() -> None:
    config = load_base_configuration()
    battery = BatteryModel(BatterySettings.from_config(config.data))
    assert battery.pack_voltage_v(0.8) > battery.pack_voltage_v(0.2)


def test_energy_settings_are_valid() -> None:
    config = load_base_configuration()
    settings = EnergySettings.from_config(config.data)
    assert settings.analysis_duration_s == 3600.0
    assert settings.return_distance_points >= 3
