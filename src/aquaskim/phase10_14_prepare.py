"""Prepare static payload-manoeuvre evidence before isolated media jobs."""
from aquaskim.phase10_14 import print_phase10_14_summary, run_phase10_14
if __name__ == "__main__":
    result=run_phase10_14(record=False,render=False,require_media=False)
    print_phase10_14_summary(result)
    print("[OK] Static payload-stability and manoeuvre figures are prepared.")
