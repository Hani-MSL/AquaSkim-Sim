from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root


def test_all_core_directories_are_available() -> None:
    required = {
        "config", "outputs", "figures", "animations", "videos", "logs",
        "tables", "reports", "records", "handoffs", "phase10_records",
        "phase10_6_records",
    }
    assert required.issubset(DIRECTORIES)
    assert DIRECTORIES["root"] == PROJECT_ROOT


def test_runtime_directories_are_created_and_relative_paths_are_stable() -> None:
    ensure_runtime_directories()
    assert DIRECTORIES["figures"].exists()
    assert DIRECTORIES["phase10_6_records"].exists()
    assert relative_to_root(DIRECTORIES["figures"]) == "outputs/figures"
