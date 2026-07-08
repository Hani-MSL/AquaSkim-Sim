# Phase 07 — Environment and Sensor Model Derivation

## Occupancy condition
For a world point `p=(x,y)`, let `d_boundary(p)` be its signed distance to the basin boundary and `d_i(p)` be the signed distance to obstacle `i`. With vessel safety radius `r_safe`, the point is navigable when:

```text
 d_boundary(p) >= r_safe  and  d_i(p) >= r_safe for all i
```

Every cell center that violates this condition is marked occupied. This is a configuration-space transformation: it converts a finite-width vessel to a point vehicle that must remain outside inflated hazards.

## Circle signed distance

```text
 d_circle(p) = ||p - c|| - R
```

where `c` is obstacle center and `R` is physical radius.

## Rectangle signed distance
The implementation uses the standard analytic signed Euclidean distance to an axis-aligned rectangle. Positive values are outside, zero is on the boundary, and negative values are inside.

## Ray-cast range model
For each beam angle `alpha_j`, the sensor samples points along:

```text
 p(s) = p_vehicle + s [cos(psi + alpha_j), sin(psi + alpha_j)]
```

until a basin/obstacle intersection is detected or the maximum range is reached. The sampling increment is stored in `config/base_parameters.yaml`.

## Debris detector model
For a debris target in field of view and range `d`, the probability is a bounded linear decay:

```text
 p_detect(d) = p_min + (p_zero - p_min) (1 - d / d_max)
```

for `0 <= d <= d_max`; it is zero outside field of view or beyond maximum range. A seeded Bernoulli draw creates each logged detection outcome.

## Sensor error models
- Position: independent Gaussian perturbations in x and y.
- Heading: Gaussian perturbation, wrapped to `[-180°, 180°)`.
- Range: deterministic geometric ray result in this phase.

All random streams use explicit seeds, so identical input files reproduce identical outputs.
