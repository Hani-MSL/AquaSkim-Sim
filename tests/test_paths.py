from aquaskim.paths import DIRECTORIES, ensure_runtime_directories


def test_runtime_directories_exist_after_initialization() -> None:
    ensure_runtime_directories()
    assert DIRECTORIES["figures"].exists()
    assert DIRECTORIES["animations"].exists()
    assert DIRECTORIES["videos"].exists()
    assert DIRECTORIES["logs"].exists()
