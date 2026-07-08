"""Fresh-process renderer for Patch 10.13 media jobs."""
from __future__ import annotations

import argparse
from pathlib import Path

from aquaskim.control_robustness import load_control_robustness, run_control_suite
from aquaskim.phase10_13 import _read_visual_protocol, _render_comparison, _render_force, _render_response, _render_sensitivity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render one Patch 10.13 replay in a fresh Python process.")
    parser.add_argument("--kind", choices=("comparison", "response", "sensitivity", "force"), required=True)
    parser.add_argument("--gif", required=True)
    parser.add_argument("--mp4", required=True)
    args = parser.parse_args(argv)
    protocol = load_control_robustness()
    cases, sensitivity, _ = run_control_suite(protocol)
    by_id = {item.case.identifier: item for item in cases}
    visual = _read_visual_protocol()
    gif, mp4 = Path(args.gif), Path(args.mp4)
    print(f"[RENDER] Patch 10.13 {args.kind} replay")
    if args.kind == "comparison":
        _render_comparison(by_id["open_loop_cross_current"], by_id["compensated_nominal"], gif, mp4, visual)
    elif args.kind == "response":
        _render_response(by_id["compensated_nominal"], gif, mp4, visual)
    elif args.kind == "sensitivity":
        _render_sensitivity(sensitivity, gif, mp4, visual)
    else:
        _render_force(by_id["compensated_nominal"], gif, mp4, visual)
    print(f"[RENDER] Complete: {gif.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
