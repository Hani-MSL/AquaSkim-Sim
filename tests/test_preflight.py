from aquaskim.preflight import build_preflight_report


def test_preflight_report_contains_expected_phase_01_data() -> None:
    report = build_preflight_report()
    assert report["configuration"]["project_name"] == "AquaSkim-Sim"
    assert report["configuration"]["dry_mass_budget_kg"] > 0.0
    assert set(report["scenarios"]) == {
        "calm_water",
        "lateral_current",
        "obstacles",
        "low_battery",
    }
