from pathlib import Path

from aquaskim.autonomy import AutonomousMission, AutonomySettings
from aquaskim.config import load_base_configuration
from aquaskim.phase08_2 import _overview_config
from aquaskim.project_profile import deep_merge


def test_phase08_2_source_compiles() -> None:
    source_path = Path(__file__).resolve().parents[1] / "src" / "aquaskim" / "phase08_2.py"
    compile(source_path.read_text(encoding="utf-8"), str(source_path), "exec")


def test_profile_deep_merge_preserves_unrelated_design_data() -> None:
    base = {"autonomy": {"max_collections": 3, "initial_soc": 0.72}, "mechanical": {"geometry": {"hull_length_m": 0.70}}}
    merged = deep_merge(base, {"autonomy": {"max_collections": 5}})
    assert merged["autonomy"]["max_collections"] == 5
    assert merged["autonomy"]["initial_soc"] == 0.72
    assert merged["mechanical"]["geometry"]["hull_length_m"] == 0.70


def test_default_phase08_2_mission_contract_is_more_than_two_objects() -> None:
    config = _overview_config()
    settings = AutonomySettings.from_config(config.data)
    assert settings.max_collections >= 3
    assert settings.safety_guard_distance_m > 0.0
    assert settings.return_energy_reserve_wh > 0.0
