# Current-aware control robustness: scope and design basis

This phase evaluates an earth-fixed straight-track manoeuvre under the fixed
reference northward current of 0.02 m/s. The study uses the same 3-DOF plant,
relative-water resistance model and twin-thruster allocation as the reference
mission.

It separates three questions that should not be conflated:

1. What open-loop drift does the plant show under the imposed current?
2. Does the documented current-aware course relation reduce the residual
   earth-track error under nominal gains?
3. Does a bounded ±20% heading-gain grid remain within declared response bounds?

The current vector is known by construction in this digital-twin experiment. No
current estimator, sensor model or physical sea-trial capability is claimed.

Word, delivery ZIP and release build remain out of scope.

## Reference-policy loader recovery

The fixed design policy is now merged into the effective configuration before
mission settings are derived. This ensures that the versioned current
compensation activation rule and guidance values are not replaced silently by
generic defaults. The runner renews upstream 10.11 and 10.12 evidence because
this policy is a reference-path input.
