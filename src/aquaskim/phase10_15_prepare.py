"""Prepare static system-validation evidence before isolated media jobs."""
from aquaskim.phase10_15 import Phase1015Artifacts, prepare_phase10_15, print_phase10_15_summary

if __name__ == "__main__":
    artifacts, _, _, _ = prepare_phase10_15()
    print_phase10_15_summary(artifacts)
    print("[OK] Static system-level scenario figures and tables are prepared.")
