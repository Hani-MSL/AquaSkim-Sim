"""Phase 10.3 facade for parametric trade study and release-quality inventory."""
from aquaskim.design_trade_study import (
    Phase103Artifacts,
    print_design_trade_study_summary,
    run_design_trade_study,
)

run_phase10_3 = run_design_trade_study
print_phase10_3_summary = print_design_trade_study_summary

__all__ = ["Phase103Artifacts", "run_phase10_3", "print_phase10_3_summary"]
