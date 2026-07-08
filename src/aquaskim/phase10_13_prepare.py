"""Prepare static Patch 10.13 artifacts before isolated animation jobs."""
from __future__ import annotations
from aquaskim.phase10_13 import print_phase10_13_summary, run_phase10_13

def main() -> int:
    result = run_phase10_13(record=False, render=False, require_media=False)
    print_phase10_13_summary(result)
    print("[OK] Static control-robustness figures and tables are prepared.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
