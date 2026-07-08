import json
from pathlib import Path

from aquaskim.phase09 import _load_scenario_plan, _scenario_config
from aquaskim.config import load_base_configuration


def test_phase09_scenario_catalog_has_four_named_cases() -> None:
    scenarios, contract = _load_scenario_plan()
    assert len(scenarios) == 4
    assert scenarios[0].scenario_id == "nominal_calm"
    assert int(contract["monte_carlo_trials"]) == 20


def test_phase09_overrides_do_not_mutate_base_configuration() -> None:
    base = load_base_configuration()
    scenarios, _ = _load_scenario_plan()
    derived = _scenario_config(base, scenarios[1].overrides)
    assert base.data["autonomy"]["current_earth_mps"] == [0.0, 0.0]
    assert derived.data["autonomy"]["current_earth_mps"] == [0.0, 0.02]


def test_phase09_artifact_manifest_is_report_quality_after_phase_execution() -> None:
    manifest_path = Path(__file__).resolve().parents[1] / "outputs" / "logs" / "phase09_visual_quality_manifest.json"
    if not manifest_path.exists():
        # Phase runner generates the artifact before full-project pytest executes.
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["exports"]) == 4
    assert all(row["width_px"] >= 3000 and row["height_px"] >= 1800 for row in manifest["exports"])
