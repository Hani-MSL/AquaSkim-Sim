# Phase 08 — Algorithm and Control Derivation

## 1. Finite-state decision layer

```text
INIT → SEARCH → TRANSIT_TO_DEBRIS → COLLECT → RETURN_HOME → DOCK → MISSION_COMPLETE
```

- `INIT`: verifies that the mission has a valid map and configuration.
- `SEARCH`: follows a safe survey route and accumulates detector confirmations.
- `TRANSIT_TO_DEBRIS`: assigns a globally safe A* route to a confirmed target.
- `COLLECT`: applies a distance-plus-hold-time capture surrogate.
- `RETURN_HOME`: is triggered by the collection quota or the SOC floor.
- `DOCK`: declares arrival inside the home-station radius.
- `MISSION_COMPLETE`: terminal state recorded in the audit log.

## 2. Global planning

A* runs on the Phase 07 occupancy grid after obstacle and boundary inflation.
The search uses eight connected neighbours. Horizontal/vertical motion costs
one cell; diagonal motion costs the square root of two cells. The heuristic is
the Euclidean distance to the goal cell, so it is admissible on this grid.
Diagonal corner cutting through two occupied orthogonal cells is disallowed.

## 3. Guidance

For an active waypoint `(x_w, y_w)`, the desired heading is

```text
psi_d = atan2(y_w - y, x_w - x)
e_psi = wrap_to_pi(psi_d - psi)
```

The active waypoint advances only after the vessel enters the configured
waypoint tolerance.

## 4. Feedback control and thrust allocation

The yaw-moment command is

```text
N_d = Kp_psi * e_psi - Kd_psi * r
```

The total surge-thrust request is the speed-dependent resistance at the desired
speed plus a proportional speed-error correction. It is bounded by the two
virtual thruster limits. With half-spacing `b/2`, the requested differential
force is `DeltaT = N_d / (b/2)` and the allocation is

```text
T_port      = clip(0.5*T_total - 0.5*DeltaT, 0, T_max)
T_starboard = clip(0.5*T_total + 0.5*DeltaT, 0, T_max)
```

These forces feed the Phase 06 RK4 3-DOF dynamic plant directly.

## 5. Energy and return policy

At every integration step, the twin-thruster load is converted to bus load;
Phase 05's battery model integrates SOC. The agent returns home when SOC falls
below the configured floor, or when it completes the configured capture quota.
