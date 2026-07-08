from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aquaskim.mission_plant import build_digital_twin_plant
from aquaskim.mission_quality import QualityMissionSettings, run_quality_mission
from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration
from aquaskim.visual_quality import add_figure_header


def _reference_result(*, compatibility_target_quota: int = 0):
    config = load_reference_configuration()
    model, environment, _, battery, battery_settings, energy_settings = build_digital_twin_plant(config)
    base = _settings(config.data)
    settings = QualityMissionSettings(**{**base.__dict__, "target_quota": compatibility_target_quota})
    return run_quality_mission(
        model=model,
        environment=environment,
        battery=battery,
        battery_settings=battery_settings,
        energy_settings=energy_settings,
        settings=settings,
        debris=environment.generate_debris(),
    )


def test_reference_multitarget_mission_completes_without_watchdog_loop() -> None:
    result = _reference_result()
    assert result.metrics["mission_success"] == 1
    assert result.metrics["final_state"] == "MISSION_COMPLETE"
    assert result.metrics["watchdog_event_count"] == 0
    assert float(result.metrics["minimum_clearance_m"]) >= 0.35 - 1e-9
    assert float(result.metrics["final_distance_home_m"]) < 0.35


def test_mission_has_separate_target_legs_and_real_return_leg() -> None:
    result = _reference_result()
    legs = {str(row["mission_leg"]) for row in result.routes}
    assert "return_home" in legs
    assert sum(1 for leg in legs if leg.startswith("target_")) >= 3
    collection_events = [event for event in result.events if event.get("event") == "STATE_CHANGE" and event.get("to_mode") == "COLLECT"]
    assert len(collection_events) >= 3


def test_compatibility_target_count_does_not_change_reference_termination() -> None:
    low = _reference_result(compatibility_target_quota=0)
    high = _reference_result(compatibility_target_quota=999)
    assert low.metrics["termination_reason"] == "all coverage lanes completed"
    assert high.metrics["termination_reason"] == "all coverage lanes completed"
    assert low.metrics["collected_count"] == high.metrics["collected_count"]
    assert low.metrics["final_state"] == high.metrics["final_state"] == "MISSION_COMPLETE"


def test_visible_title_strips_internal_phase_label() -> None:
    figure = plt.figure(figsize=(5, 3))
    add_figure_header(figure, "AquaSkim-Sim | Phase 09.2 — Test plot", "Phase 09.2 subtitle")
    visible = " ".join(text.get_text() for text in figure.texts)
    plt.close(figure)
    assert "Phase 09.2" not in visible
    assert "Test plot" in visible
