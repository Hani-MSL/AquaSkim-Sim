"""Traceable behavioural analysis for the non-interactive reference mission.

This module deliberately consumes logged reference-mission data only.  It does
not command the craft, import Legacy quota-based autonomy, or alter any
numerical state.  The resulting audit tables make the behaviour shown in
animations inspectable at state-transition and route-assignment level.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from aquaskim.mission_quality import QualityMissionResult


@dataclass(frozen=True)
class FidelityAudit:
    """Structured behavioural evidence from one closed-loop result."""

    summary: dict[str, Any]
    state_segments: list[dict[str, Any]]
    regime_segments: list[dict[str, Any]]
    event_ledger: list[dict[str, Any]]
    checks: list[dict[str, Any]]


def _segments(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    segments: list[dict[str, Any]] = []
    start = 0
    active = str(rows[0].get(key, "UNKNOWN"))
    for index in range(1, len(rows) + 1):
        candidate = str(rows[index].get(key, "UNKNOWN")) if index < len(rows) else None
        if candidate != active:
            first, last = rows[start], rows[index - 1]
            duration = max(0.0, float(last["time_s"]) - float(first["time_s"]))
            segments.append(
                {
                    "segment_index": len(segments) + 1,
                    "category": key,
                    "value": active,
                    "start_time_s": float(first["time_s"]),
                    "end_time_s": float(last["time_s"]),
                    "duration_s": duration,
                    "start_x_m": float(first["x_m"]),
                    "start_y_m": float(first["y_m"]),
                    "end_x_m": float(last["x_m"]),
                    "end_y_m": float(last["y_m"]),
                    "route_id_start": int(first.get("route_id", 0)),
                    "route_id_end": int(last.get("route_id", 0)),
                }
            )
            start = index
            active = candidate if candidate is not None else ""
    return segments


def _first_event(events: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((event for event in events if str(event.get("event")) == name), None)


def audit_reference_result(
    result: QualityMissionResult,
    *,
    scenario: str,
    expected_termination_fragment: str | None = None,
) -> FidelityAudit:
    """Audit reference-mission fidelity without changing its mission outcome."""
    rows = result.rows
    events = [dict(item) for item in result.events]
    state_segments = _segments(rows, "mode")
    regime_segments = _segments(rows, "control_regime")
    mode_counts = Counter(str(row.get("mode", "UNKNOWN")) for row in rows)
    regime_counts = Counter(str(row.get("control_regime", "UNKNOWN")) for row in rows)
    coverage = np.asarray([float(row.get("coverage_progress", 0.0)) for row in rows])
    coverage_monotonic = bool(np.all(np.diff(coverage) >= -1e-12))
    first_target = _first_event(events, "TARGET_CONFIRMED")
    first_return = _first_event(events, "STATE_CHANGE")
    return_events = [event for event in events if str(event.get("to_mode", "")) == "RETURN_HOME"]
    first_return = return_events[0] if return_events else None
    first_motion_index = next(
        (
            index
            for index, row in enumerate(rows)
            if (float(row["x_m"]) - float(rows[0]["x_m"])) ** 2
            + (float(row["y_m"]) - float(rows[0]["y_m"])) ** 2
            >= 0.25**2
        ),
        None,
    )
    first_motion_s = float(rows[first_motion_index]["time_s"]) if first_motion_index is not None else float("nan")
    termination = str(result.metrics.get("termination_reason", ""))
    no_quota = "quota" not in termination.lower() and "collection quota" not in " ".join(str(e.get("reason", "")) for e in events).lower()
    expected_ok = True if expected_termination_fragment is None else expected_termination_fragment.lower() in termination.lower()
    early_return = bool(first_return is not None and float(first_return.get("time_s", 0.0)) < 30.0)
    state_transitions = sum(1 for event in events if str(event.get("event")) == "STATE_CHANGE")
    collection_events = sum(1 for event in events if str(event.get("event")) == "COLLECTION_CONFIRMED")
    summary = {
        "scenario": scenario,
        "mission_success": int(result.metrics.get("mission_success", 0)),
        "termination_reason": termination,
        "duration_s": float(result.metrics.get("duration_s", 0.0)),
        "coverage_fraction": float(result.metrics.get("coverage_fraction", 0.0)),
        "captured_count": int(result.metrics.get("collected_count", 0)),
        "minimum_clearance_m": float(result.metrics.get("minimum_clearance_m", float("nan"))),
        "final_soc": float(result.metrics.get("final_soc", float("nan"))),
        "first_motion_time_s": first_motion_s,
        "first_target_confirmation_time_s": float(first_target["time_s"]) if first_target is not None else None,
        "first_return_time_s": float(first_return["time_s"]) if first_return is not None else None,
        "state_transition_count": state_transitions,
        "collection_event_count": collection_events,
        "state_sample_counts": dict(sorted(mode_counts.items())),
        "control_regime_sample_counts": dict(sorted(regime_counts.items())),
        "coverage_progress_monotonic": coverage_monotonic,
        "fixed_quota_absent_from_termination": no_quota,
        "expected_termination_match": expected_ok,
        "early_return_before_30_s": early_return,
    }
    checks = [
        {
            "check": "reference mission succeeds and docks",
            "status": "PASS" if summary["mission_success"] else "FAIL",
            "observed": summary["mission_success"],
            "criterion": "mission_success == 1",
        },
        {
            "check": "coverage progress does not regress",
            "status": "PASS" if coverage_monotonic else "FAIL",
            "observed": coverage_monotonic,
            "criterion": "non-decreasing coverage progress",
        },
        {
            "check": "quota is not a return condition",
            "status": "PASS" if no_quota else "FAIL",
            "observed": termination,
            "criterion": "no quota-derived termination or transition reason",
        },
        {
            "check": "no unexplained early return",
            "status": "PASS" if not early_return else "CHECK",
            "observed": summary["first_return_time_s"],
            "criterion": "first RETURN_HOME not before 30 s unless an explicit safety/energy trigger is recorded",
        },
        {
            "check": "scenario termination matches its declared purpose",
            "status": "PASS" if expected_ok else "FAIL",
            "observed": termination,
            "criterion": expected_termination_fragment or "documented mission completion",
        },
        {
            "check": "minimum safety clearance remains positive",
            "status": "PASS" if summary["minimum_clearance_m"] >= 0.35 - 1e-6 else "FAIL",
            "observed": summary["minimum_clearance_m"],
            "criterion": ">= 0.350 m",
        },
    ]
    return FidelityAudit(summary, state_segments, regime_segments, events, checks)
