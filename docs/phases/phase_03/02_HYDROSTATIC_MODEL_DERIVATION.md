# Phase 03 | Hydrostatic Model and Derivation

## 1. Displacement equilibrium

In static equilibrium, buoyancy equals weight:

```text
ρ g ∇ = m g
∇ = m / ρ
```

For the effective twin-waterplane model:

```text
A_WP = 2 L B_eff
B_eff = B × C_WP
T = ∇ / A_WP
Freeboard = H − T
```

where `C_WP` is the configured waterplane shape factor.

## 2. Initial transverse stability

```text
GM = KB + BM − KG
BM = I_T / ∇
```

The transverse second moment of waterplane area is formed using the parallel-axis theorem:

```text
I_T = 2 [ L B_eff³ / 12 + (L B_eff) (s/2)² ]
```

where `s` is hull-centre spacing. The second term is important for a catamaran: the separated buoyancy volumes substantially increase transverse stability.

## 3. Small-angle righting arm

Within the stated small-angle range:

```text
GZ_linear = GM sin(φ)
M_R = m g GZ
```

The project marks the first `5°` as the nominal linear-design region, not as a universal validity claim.

## 4. Finite-heel strip integration

At a finite heel `φ`, local draft at transverse coordinate `y` is:

```text
d(y) = clip(d0 + y tan(φ), 0, H)
```

`d0` is solved numerically so that integrated displaced volume remains exactly equal to `∇`. The center of buoyancy follows from numerical first moments:

```text
y_B = ∫ L d(y) y dy / ∇
z_B = ∫ L d(y)² / 2 dy / ∇
```

The nonlinear righting arm is then calculated from the projected buoyancy and gravity lines after heel. The clipping operation deliberately exposes partial emergence and low freeboard instead of extrapolating the linear model beyond the physical hull.

## 5. Why this model is appropriate here

The model is more informative than a single `GM` number, is computationally light, uses only traceable project parameters, and remains honest about its limitations. It is therefore appropriate for a simulation-first course project prior to later dynamic and hydrodynamic phases.
