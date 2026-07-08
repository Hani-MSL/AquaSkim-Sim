from aquaskim.phase10_3 import run_phase10_3


def test_phase10_3_generates_trade_study_outputs() -> None:
    artifacts = run_phase10_3()
    for path in artifacts.all_paths():
        assert path.exists()
        assert path.stat().st_size > 0
