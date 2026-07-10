from aquaskim.paths import PROJECT_ROOT


def test_public_rebuild_entrypoints_exist_and_are_clean() -> None:
    entrypoints = (
        PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat",
        PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.sh",
        PROJECT_ROOT / "scripts" / "run_tests.bat",
    )
    for path in entrypoints:
        assert path.exists()
        assert path.stat().st_size > 0
        content = path.read_text(encoding="utf-8").lower()
        assert "run_patch_" not in content
        assert "chatgpt" not in content
        assert "openai" not in content


def test_platform_entrypoints_invoke_the_same_rebuild_module() -> None:
    windows = (PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat").read_text(
        encoding="utf-8"
    )
    shell = (PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.sh").read_text(
        encoding="utf-8"
    )
    assert "python -m aquaskim.rebuild_from_zero" in windows
    assert "python -m aquaskim.rebuild_from_zero" in shell
