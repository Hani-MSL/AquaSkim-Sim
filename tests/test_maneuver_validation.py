from aquaskim.maneuver_validation import result_metrics, run_reference_maneuvers


def test_symmetric_step_is_yaw_neutral_and_reaches_a_finite_steady_speed() -> None:
    results, _, protocol = run_reference_maneuvers()
    metric = result_metrics(results["step"], protocol)
    assert metric["peak_abs_yaw_rate_rps"] < 1e-9
    assert 0.45 < metric["steady_speed_mps"] < 0.65
    assert metric["rise_time_to_90pct_s"] > 0.0


def test_differential_turning_has_real_heading_accumulation() -> None:
    results, _, protocol = run_reference_maneuvers()
    metric = result_metrics(results["turn"], protocol)
    assert metric["heading_change_deg"] > 360.0
    assert metric["kinematic_turn_radius_m"] > 0.5
    assert metric["peak_yaw_rate_rps"] < 1.20


def test_state_triggered_zigzag_reverses_without_extreme_overshoot() -> None:
    results, _, protocol = run_reference_maneuvers()
    metric = result_metrics(results["zigzag"], protocol)
    assert metric["reversal_count"] >= protocol["zig_zag"]["minimum_reversals"]
    assert metric["overshoot_deg"] < 3.0


def test_cross_current_creates_visible_open_loop_drift() -> None:
    results, _, protocol = run_reference_maneuvers()
    metric = result_metrics(results["current"], protocol)
    assert abs(metric["cross_track_drift_m"]) > 0.10


def test_turning_time_step_converges_at_reference_production_step() -> None:
    _, convergence, _ = run_reference_maneuvers()
    dt05 = next(row for row in convergence if abs(row["time_step_s"] - 0.05) < 1e-12)
    assert dt05["position_error_to_reference_m"] < 0.05
    assert dt05["heading_error_to_reference_deg"] < 1.0
