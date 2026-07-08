"""Finalize Patch 10.13 after each media item was rendered in a fresh process."""
from __future__ import annotations
from aquaskim.animation_audit import write_animation_audit_sheet
from aquaskim.phase10_13 import _dirs, _read_visual_protocol, print_phase10_13_summary, run_phase10_13


def main() -> int:
    dirs = _dirs()
    visual = _read_visual_protocol()
    media = [
        dirs["animations"] / "reference_open_loop_vs_current_aware_replay.gif",
        dirs["animations"] / "reference_current_control_response_replay.gif",
        dirs["animations"] / "reference_controller_sensitivity_replay.gif",
        dirs["animations"] / "reference_current_force_yaw_replay.gif",
    ]
    write_animation_audit_sheet(media, dirs["animations"] / "reference_current_control_contact_sheet.png", samples_per_animation=int(visual["render"]["contact_sheet_samples"]))
    result = run_phase10_13(record=True, render=False, require_media=True)
    print_phase10_13_summary(result)
    print("[OK] Media QA, evidence snapshot and handoff have been finalized.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
