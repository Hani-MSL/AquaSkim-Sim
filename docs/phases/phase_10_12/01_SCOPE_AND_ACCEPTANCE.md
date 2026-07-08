# Current-aware Guidance and Operating-envelope Validation

## Scope

This phase adds a deterministic low-current course feedforward to the fixed
reference mission. The commanded water-relative velocity is defined as:

`V_water = V_ground - V_current`

The policy is valid only inside the versioned sheltered-basin envelope. It is
not a current estimator, adaptive controller, sea-trial result, or open-water
station-keeping claim.

## Acceptance

1. All YAML, imports, syntax and full pytest checks must pass before media.
2. Every scenario classified as `validated` must meet its explicit success,
   termination, clearance, coverage and docking criteria.
3. The `boundary` scenario must be reported separately and not included in a
   validated-success statement.
4. Four GIFs, four MP4s and a multi-frame contact sheet must pass frame,
   duration, resolution and file-existence checks.
5. Word, delivery ZIP and release build remain disabled.
