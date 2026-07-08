# Payload Stability Sensitivity and Low-current Manoeuvre Validation

## Purpose

This phase adds a fixed engineering evidence suite for the reference catamaran. It combines:

- calm-water hydrostatic payload sensitivity;
- nonlinear strip-integrated righting curves;
- a quasi-static port-offset payload moment comparison;
- symmetric thrust-step response for dry and full payload states;
- differential-thrust turning trajectories with and without the documented low cross-current;
- state-triggered zig-zag response for dry and full payload states.

The phase is not a wave model, roll-transient model, structural certification, sea-trial result, physical current-sensing demonstration, or full-scale design claim.

## Payload model

Collected debris is represented as a point mass added at a documented basket location. The `full_port_offset` case moves that same mass by 0.10 m to port. Its applied static heeling moment is:

`M_payload = m_payload × g × |y_payload|`

The reported equilibrium heel is obtained by locating the point where this moment intersects the nonlinear hydrostatic righting curve. The margin uses the recorded righting moment at the documented 5 degree operating heel limit.

## Dynamic model

The manoeuvres run on the existing planar surge-sway-yaw model with the same twin-thruster allocation, added-mass terms, drag model, integration step and logging structure as the reference mission. The low-current turn applies the declared 0.02 m/s earth-frame current. It is a disturbance demonstration, not a current-aware navigation mission.

## Evidence and release policy

The Windows runner performs YAML parse, import audit, `compileall`, and the full pytest suite before creating any new plots or media. It does not build a Word report, delivery ZIP, or release artifact.
