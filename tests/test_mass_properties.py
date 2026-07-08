import math
from aquaskim.config import load_base_configuration
from aquaskim.mass_properties import build_load_cases

def test_dry_mass_and_lateral_symmetry():
    cases=build_load_cases(load_base_configuration().data);_,dry=cases["dry_empty_basket"]
    assert math.isclose(dry.total_mass_kg,3.0,abs_tol=1e-12)
    assert math.isclose(dry.cg_m[1],0.0,abs_tol=1e-12)

def test_full_payload_shift_and_inertia():
    cases=build_load_cases(load_base_configuration().data);_,dry=cases["dry_empty_basket"];_,full=cases["full_design_payload"]
    assert math.isclose(full.total_mass_kg,dry.total_mass_kg+.8,abs_tol=1e-12)
    assert full.cg_m[0] > dry.cg_m[0]
    assert all(x>0 for x in full.inertia_kg_m2)
