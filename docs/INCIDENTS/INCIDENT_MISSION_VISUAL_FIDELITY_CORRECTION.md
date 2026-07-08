# Incident record — mission visual fidelity correction

## Observed issue
Historical short GIFs contained early returns and visually looped trajectories. The user correctly flagged that those outputs did not adequately demonstrate a natural multi-target mission.

## Root causes
- collection quota was too small for a representative demonstration;
- controller allocation did not use reverse differential pivot turns for sharp heading reversals;
- non-contiguous state samples were connected in a state-coloured plot;
- short animations were rendered with too few frames for a full mission review.

## Corrective action
The active build replaces those reels with a progress-monitored multi-target 3-DOF mission, reverse differential pivot allocation, event logging, contiguous state-segment plotting, user-configurable replay density, six animation types, 2-D and 3-D force/dynamics visualisations, and evidence snapshots.

## Status
Corrected mission suite is the active build target. Historical artifacts remain preserved in prior evidence folders and are not overwritten as a claim of current behaviour.
