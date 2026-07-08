import math

from aquaskim.config import load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrostatics import CatamaranHydrostatics, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases


def _model():
    config = load_base_configuration()
    hydro = CatamaranHydrostatics(
        CatamaranGeometry.from_config(config.data),
        HydrostaticSettings.from_config(config.data),
    )
    load_cases = build_load_cases(config.data)
    cases = {name: hydro.case_from_mass_properties(name, props) for name, (_, props) in load_cases.items()}
    return hydro, cases


def test_hydrostatic_cases_have_positive_draft_freeboard_and_gm() -> None:
    hydro, cases = _model()
    for case in cases.values():
        assert 0.0 < case.draft_m < hydro.geometry.hull_height_m
        assert case.freeboard_m > hydro.settings.minimum_freeboard_m
        assert case.gm_m > hydro.settings.minimum_gm_m


def test_full_payload_is_governing_for_freeboard_and_initial_gm() -> None:
    _, cases = _model()
    dry = cases["dry_empty_basket"]
    full = cases["full_design_payload"]
    assert full.freeboard_m < dry.freeboard_m
    assert full.gm_m < dry.gm_m


def test_finite_heel_conserves_displaced_volume() -> None:
    hydro, cases = _model()
    case = cases["full_design_payload"]
    state = hydro.heel_state(case, 5.0)
    integrated = hydro._integrate_at_level(math.radians(5.0), state.equilibrium_draft_m)
    assert math.isclose(float(integrated["total_volume"]), case.displacement_volume_m3, rel_tol=0.0, abs_tol=1e-9)


def test_nonlinear_gz_matches_small_angle_reference_near_one_degree() -> None:
    hydro, cases = _model()
    case = cases["full_design_payload"]
    state = hydro.heel_state(case, 1.0)
    assert math.isclose(state.gz_nonlinear_m, state.gz_linear_m, rel_tol=0.035, abs_tol=1e-4)


def test_operating_heel_has_positive_righting_moment() -> None:
    hydro, cases = _model()
    for case in cases.values():
        state = hydro.operating_state(case)
        assert state.righting_moment_n_m > 0.0
        assert state.min_freeboard_m >= hydro.settings.minimum_freeboard_m
