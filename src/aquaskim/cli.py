"""Command-line entry points for AquaSkim-Sim.

The CLI is intentionally thin: it dispatches explicit user commands and never
starts a Word report, delivery ZIP or release build implicitly.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable


def _run_preflight() -> int:
    from aquaskim.preflight import run_preflight
    return run_preflight()


def _run_phase02() -> int:
    from aquaskim.phase02 import print_phase02_summary, run_phase02
    print_phase02_summary(run_phase02())
    return 0


def _run_phase(module_name: str, run_name: str, print_name: str, **kwargs: object) -> int:
    module = __import__(module_name, fromlist=[run_name, print_name])
    artifacts = getattr(module, run_name)(**kwargs)
    printer = getattr(module, print_name, None)
    if printer is not None:
        printer(artifacts)
    return 0


def _configure_experiment() -> int:
    from aquaskim.config import load_base_configuration
    from aquaskim.project_profile import create_interactive_profile
    output = create_interactive_profile(load_base_configuration(apply_local_profile=False).data)
    print(f"[OK] Scientific experiment profile saved: {output}")
    print("[INFO] No reference simulation, report, ZIP or release build was launched.")
    return 0


def _run_configured_build_dry_run() -> int:
    print("[INFO] Configured build is intentionally disabled while Release Gate is open.")
    print("[INFO] The local profile can be created and inspected, but it is ignored by the fixed reference build.")
    return 0


def _release_disabled() -> int:
    print("[BLOCKED] Release build is disabled pending the full Source Integrity and Release Gate.")
    print("[BLOCKED] No Word report, delivery ZIP or final submission package has been generated.")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aquaskim", description="AquaSkim-Sim engineering commands")
    parser.add_argument(
        "command",
        choices=(
            "preflight", "phase02", "phase03", "phase04", "phase05", "phase06", "phase07", "phase08", "phase08-2", "phase09", "phase09-2",
            "phase10-2", "phase10-3", "phase10-4", "phase10-6", "phase10-7", "phase10-8", "phase10-11", "phase10-12", "phase10-13", "phase10-14", "phase10-15", "phase10-16", "phase10-17",
            "run-phase03", "run-phase04", "run-phase05", "run-phase06", "run-phase07", "run-phase08", "run-phase08-2", "run-phase09", "run-phase09-2",
            "run-phase10", "run-phase10-2", "run-phase10-3", "run-phase10-4", "run-phase10-6", "run-phase10-7", "run-phase10-8", "run-phase10-11", "run-phase10-12", "run-phase10-13", "run-phase10-14", "run-phase10-15", "run-phase10-16", "run-phase10-17",
            "configure", "run-configured-build", "source-integrity-audit", "rebuild-from-zero",
        ),
    )
    args = parser.parse_args(argv)
    command = args.command
    if command == "preflight":
        return _run_preflight()
    if command == "phase02":
        return _run_phase02()
    if command == "configure":
        return _configure_experiment()
    if command == "run-configured-build":
        return _run_configured_build_dry_run()
    if command == "source-integrity-audit":
        from aquaskim.integrity_audit import main as audit_main
        return audit_main(["report"])
    if command == "rebuild-from-zero":
        from aquaskim.rebuild_from_zero import main as rebuild_main
        return rebuild_main([])
    if command in {"run-phase10", "run-phase10-2"}:
        return _release_disabled()

    normalized = command.removeprefix("run-")
    dispatch: dict[str, tuple[str, str, str]] = {
        "phase03": ("aquaskim.phase03", "run_phase03", "print_phase03_summary"),
        "phase04": ("aquaskim.phase04", "run_phase04", "print_phase04_summary"),
        "phase05": ("aquaskim.phase05", "run_phase05", "print_phase05_summary"),
        "phase06": ("aquaskim.phase06", "run_phase06", "print_phase06_summary"),
        "phase07": ("aquaskim.phase07", "run_phase07", "print_phase07_summary"),
        "phase08": ("aquaskim.phase08", "run_phase08", "print_phase08_summary"),
        "phase08-2": ("aquaskim.phase08_2", "run_phase08_2", "print_phase08_2_summary"),
        "phase09": ("aquaskim.phase09", "run_phase09", "print_phase09_summary"),
        "phase09-2": ("aquaskim.phase09_2", "run_phase09_2", "print_phase09_2_summary"),
        "phase10-3": ("aquaskim.phase10_3", "run_phase10_3", "print_phase10_3_summary"),
        "phase10-4": ("aquaskim.phase10_4", "run_phase10_4", "print_phase10_4_summary"),
        "phase10-6": ("aquaskim.phase10_6", "run_phase10_6", "print_phase10_6_summary"),
        "phase10-7": ("aquaskim.phase10_7", "run_phase10_7", "print_phase10_7_summary"),
        "phase10-8": ("aquaskim.phase10_8", "run_phase10_8", "print_phase10_8_summary"),
        "phase10-11": ("aquaskim.phase10_11", "run_phase10_11", "print_phase10_11_summary"),
        "phase10-12": ("aquaskim.phase10_12", "run_phase10_12", "print_phase10_12_summary"),
        "phase10-13": ("aquaskim.phase10_13", "run_phase10_13", "print_phase10_13_summary"),
        "phase10-14": ("aquaskim.phase10_14", "run_phase10_14", "print_phase10_14_summary"),
        "phase10-15": ("aquaskim.phase10_15", "run_phase10_15", "print_phase10_15_summary"),
        "phase10-16": ("aquaskim.phase10_16", "run_phase10_16", "print_phase10_16_summary"),
        "phase10-17": ("aquaskim.phase10_17", "run_phase10_17", "print_phase10_17_summary"),
    }
    module_name, run_name, print_name = dispatch[normalized]
    return _run_phase(module_name, run_name, print_name)


if __name__ == "__main__":
    raise SystemExit(main())
