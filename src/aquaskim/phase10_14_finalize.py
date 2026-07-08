"""Finalize payload-manoeuvre media QA, evidence snapshot and handoff."""
from aquaskim.phase10_14 import print_phase10_14_summary, run_phase10_14
if __name__ == "__main__":
    result=run_phase10_14(record=True,render=False,require_media=True)
    print_phase10_14_summary(result)
    print("[OK] Payload-manoeuvre media QA, evidence snapshot and handoff are finalized.")
