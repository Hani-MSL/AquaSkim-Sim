from __future__ import annotations

"""One-command clean rebuild entry point for public GitHub users.

The command intentionally rebuilds generated evidence from source instead of
using committed output artifacts. It creates a fresh ``outputs/`` tree and then
assembles the final delivery ZIP from the newly generated evidence.
"""

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aquaskim import __version__
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root


@dataclass(frozen=True)
class RebuildStep:
    name: str
    description: str
    action: Callable[[], Any]


def _banner(title: str) -> None:
    print("=" * 72, flush=True)
    print(f"AquaSkim-Sim | {title}", flush=True)
    print("=" * 72, flush=True)


def _run_pytest(label: str, args: list[str] | None = None) -> None:
    cmd = [sys.executable, "-m", "pytest", "-q", *(args or [])]
    _banner(label)
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def _clean_generated_outputs() -> None:
    for key in ("outputs", "records"):
        path = DIRECTORIES[key]
        if path.exists():
            print(f"[CLEAN] {relative_to_root(path)}")
            shutil.rmtree(path)
    ensure_runtime_directories()


def _source_integrity_report() -> None:
    from aquaskim.integrity_audit import main as audit_main

    code = audit_main(["report"])
    if code != 0:
        raise RuntimeError("Source-integrity audit failed")


def _call(module_name: str, run_name: str, print_name: str | None = None, **kwargs: Any) -> None:
    module = __import__(module_name, fromlist=[run_name] + ([print_name] if print_name else []))
    result = getattr(module, run_name)(**kwargs)
    if print_name:
        printer = getattr(module, print_name)
        printer(result)


def _steps() -> list[RebuildStep]:
    return [
        RebuildStep("clean", "Remove generated outputs/ and records/ from previous local runs.", _clean_generated_outputs),
        RebuildStep("source-audit", "Parse YAML, import modules, and verify source/reference isolation.", _source_integrity_report),
        RebuildStep("phase02", "Generate mechanical architecture evidence.", lambda: _call("aquaskim.phase02", "run_phase02", "print_phase02_summary")),
        RebuildStep("phase03", "Generate hydrostatics and stability evidence.", lambda: _call("aquaskim.phase03", "run_phase03", "print_phase03_summary")),
        RebuildStep("phase04", "Generate hydrodynamics and propulsion evidence.", lambda: _call("aquaskim.phase04", "run_phase04", "print_phase04_summary")),
        RebuildStep("phase05", "Generate energy and battery evidence.", lambda: _call("aquaskim.phase05", "run_phase05", "print_phase05_summary")),
        RebuildStep("phase06", "Generate low-speed 3-DOF dynamics evidence.", lambda: _call("aquaskim.phase06", "run_phase06", "print_phase06_summary")),
        RebuildStep("phase07", "Generate environment, sensor, and debris evidence.", lambda: _call("aquaskim.phase07", "run_phase07", "print_phase07_summary")),
        RebuildStep("phase08", "Generate autonomy, planning, and control evidence.", lambda: _call("aquaskim.phase08", "run_phase08", "print_phase08_summary")),
        RebuildStep("phase08-2", "Generate mission-overhaul validation evidence.", lambda: _call("aquaskim.phase08_2", "run_phase08_2", "print_phase08_2_summary")),
        RebuildStep("phase09", "Generate scenario-validation evidence.", lambda: _call("aquaskim.phase09", "run_phase09", "print_phase09_summary")),
        RebuildStep("phase09-2", "Generate comprehensive validation evidence.", lambda: _call("aquaskim.phase09_2", "run_phase09_2", "print_phase09_2_summary")),
        RebuildStep("phase10-2", "Generate reference design-synthesis evidence.", lambda: _call("aquaskim.phase10_2", "run_phase10_2", "print_phase10_2_summary")),
        RebuildStep("phase10-3", "Generate parametric trade-study evidence.", lambda: _call("aquaskim.phase10_3", "run_phase10_3", "print_phase10_3_summary")),
        RebuildStep("phase10-4", "Generate visual audit and legacy-deliverable context evidence.", lambda: _call("aquaskim.phase10_4", "run_phase10_4", "print_phase10_4_summary")),
        RebuildStep("phase10-11", "Generate fixed-reference mission fidelity figures, GIFs, MP4s, reports, and tables.", lambda: _call("aquaskim.phase10_11", "run_phase10_11", "print_phase10_11_summary", record=True, render=True)),
        RebuildStep("phase10-12", "Generate current-aware operating-envelope evidence.", lambda: _call("aquaskim.phase10_12", "run_phase10_12", "print_phase10_12_summary")),
        RebuildStep("phase10-13", "Generate current-aware control robustness evidence.", lambda: _call("aquaskim.phase10_13", "run_phase10_13", "print_phase10_13_summary")),
        RebuildStep("phase10-14", "Generate payload stability and manoeuvre evidence.", lambda: _call("aquaskim.phase10_14", "run_phase10_14", "print_phase10_14_summary")),
        RebuildStep("phase10-15", "Generate system-level scenario validation evidence.", lambda: _call("aquaskim.phase10_15", "run_phase10_15", "print_phase10_15_summary")),
        RebuildStep("phase10-16", "Curate final presentation evidence.", lambda: _call("aquaskim.phase10_16", "run_phase10_16", "print_phase10_16_summary")),
        RebuildStep("phase10-17", "Run engineering release-candidate gate.", lambda: _call("aquaskim.phase10_17", "run_phase10_17", "print_phase10_17_summary")),
        RebuildStep("phase10-18", "Build and QA the final Word report.", lambda: _call("aquaskim.phase10_18", "run_phase10_18", "print_phase10_18_summary")),
        RebuildStep("phase10-19", "Assemble and verify the final delivery ZIP.", lambda: _call("aquaskim.phase10_19", "run_phase10_19", "print_phase10_19_summary")),
    ]


def run_rebuild(*, skip_final_tests: bool = False) -> Path:
    _banner(f"Clean rebuild from source | version {__version__}")
    print("This command regenerates outputs/ and records/ locally; generated artifacts are not committed to Git.", flush=True)
    start = time.perf_counter()
    for index, step in enumerate(_steps(), start=1):
        _banner(f"Step {index:02d}/{len(_steps()):02d}: {step.name}")
        print(step.description, flush=True)
        step.action()
    if not skip_final_tests:
        _run_pytest("Final regression tests after delivery package")
    package = DIRECTORIES["deliverables"] / f"AquaSkim-Sim_Final_Delivery_v{__version__}.zip"
    if not package.exists():
        raise RuntimeError(f"Expected final delivery ZIP was not created: {relative_to_root(package)}")
    elapsed = time.perf_counter() - start
    _banner("Rebuild complete")
    print(f"Status  : DELIVERY_PACKAGE_READY", flush=True)
    print(f"Package : {relative_to_root(package)}", flush=True)
    print(f"Elapsed : {elapsed / 60:.1f} minutes", flush=True)
    return package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild AquaSkim-Sim from source and create a new outputs/ tree.")
    parser.add_argument("--list-steps", action="store_true", help="Print the rebuild pipeline without executing it.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the command and print the planned pipeline only.")
    parser.add_argument("--skip-final-tests", action="store_true", help="Skip the final pytest pass after package creation.")
    args = parser.parse_args(argv)
    if args.list_steps or args.dry_run:
        _banner("Planned clean rebuild pipeline")
        for index, step in enumerate(_steps(), start=1):
            print(f"{index:02d}. {step.name}: {step.description}")
        if args.dry_run:
            print("[DRY-RUN] No files were generated.")
        return 0
    run_rebuild(skip_final_tests=args.skip_final_tests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
