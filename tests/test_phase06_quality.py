from aquaskim.phase06 import run_phase06


def test_phase06_generates_report_quality_artifacts() -> None:
    artifacts = run_phase06()
    for path in artifacts.__dict__.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_phase06_summary_contains_three_scenarios() -> None:
    import json
    artifacts = run_phase06()
    summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
    assert len(summary["scenario_metrics"]) == 3
    assert {row["scenario"] for row in summary["scenario_metrics"]} == {
        "calm_straight", "differential_turn", "cross_current"
    }
