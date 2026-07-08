# Mission fidelity and advanced visualisation

## Purpose
This release corrects two shortcomings of the historical mission demonstrations:

1. The earlier forward-only differential-thrust allocation could create broad turning arcs or apparent local loops when the required heading changed sharply.
2. A plotting routine grouped non-contiguous samples by state, visually connecting different mission legs and exaggerating loop-like paths.

## Corrected closed-loop model

The revised mission combines:

```text
Inflated occupancy grid
→ A* global path leg
→ line-of-sight guidance point
→ bounded speed / yaw request
→ forward thrust or reverse differential pivot
→ 3-DOF RK4 plant
→ hydrodynamic drag and earth-frame current
→ energy-to-home decision guard
→ safety and progress-watchdog event ledger
```

## Behaviour claims

The nominal acceptance run is designed to demonstrate three confirmed target captures followed by a home-station return.  It is not presented as a complete coverage or SLAM demonstration.  The project stores the controller state, event ledger, actual trajectory, A* legs, force ledger and energy history so every statement can be checked.
