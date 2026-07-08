from __future__ import annotations

"""Patch 10.19 facade for final delivery packaging."""

from typing import Any

from aquaskim.delivery_package import build_final_delivery_package, print_delivery_summary


def run_phase10_19(*, record: bool = True) -> dict[str, Any]:
    result = build_final_delivery_package(record=record)
    return {"artifacts": result}


def print_phase10_19_summary(result: dict[str, Any]) -> None:
    print_delivery_summary(result["artifacts"])


if __name__ == "__main__":
    print_phase10_19_summary(run_phase10_19(record=True))
