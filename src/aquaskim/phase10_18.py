from __future__ import annotations

"""Patch 10.18 facade for final Word report generation and QA."""

from typing import Any

from aquaskim.final_word_report import build_final_word_report, print_final_word_summary


def run_phase10_18(*, record: bool = True) -> dict[str, Any]:
    artifacts = build_final_word_report(record=record)
    return {"artifacts": artifacts}


def print_phase10_18_summary(result: dict[str, Any]) -> None:
    print_final_word_summary(result["artifacts"])


if __name__ == "__main__":
    print_phase10_18_summary(run_phase10_18(record=True))
