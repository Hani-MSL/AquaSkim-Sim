"""Facade for the engineering release-candidate gate."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aquaskim.release_gate import print_release_gate_summary, run_release_gate


def run_phase10_17(*, record: bool = True) -> dict[str, Any]:
    report, run_dir = run_release_gate(record=record)
    return {"report": report, "run_dir": run_dir}


def print_phase10_17_summary(artifacts: dict[str, Any]) -> None:
    print_release_gate_summary(artifacts["report"], artifacts["run_dir"])


if __name__ == "__main__":
    print_phase10_17_summary(run_phase10_17(record=True))
