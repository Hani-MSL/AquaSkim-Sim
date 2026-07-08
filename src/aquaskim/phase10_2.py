"""Phase 10.2 facade for the parametric mechanical design-synthesis package."""
from aquaskim.design_synthesis import (
    DesignSynthesisArtifacts,
    print_design_synthesis_summary,
    run_design_synthesis,
)

run_phase10_2 = run_design_synthesis
print_phase10_2_summary = print_design_synthesis_summary

__all__ = ["DesignSynthesisArtifacts", "run_phase10_2", "print_phase10_2_summary"]
