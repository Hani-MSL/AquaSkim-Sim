# Incident: visual audit exposed mission-guidance and contact-sheet weaknesses

## Observed evidence

The submitted mission map and dashboard showed that a run could satisfy the
old docking/clearance checks while still having large heading excursions,
repeated reverse-thrust changes and visually implausible loops around waypoint
corners. The original contact sheets also copied GIF frame zero only, so they
could not demonstrate the motion progression.

## Root causes

1. The follower extended look-ahead from the vessel position, rather than from
   a projection on the retained A* polyline. This allowed corner-cutting targets
   to appear behind or across a moving vessel.
2. Reorientation began while surge momentum remained, so a pivot command created
   a broad moving turn rather than a controlled in-place turn.
3. A planner path was inflated only by the vehicle safety radius, while the
   numerical guard used a larger clearance threshold.
4. A target whose nearest free cell sat outside capture radius could be reissued
   indefinitely instead of being deferred once and recorded.
5. Contact sheets did not sample the temporal evolution of GIFs.

## Corrections

- Segment-conservative stop-turn-go tracking replaces corner-cutting guidance.
- The controller brakes first, pivots under hysteresis, then resumes forward
  tracking with non-negative allocation except for deliberate braking/pivot.
- Planning uses a documented clearance buffer beyond the safety guard.
- Unreachable local targets are deferred once, added to a persistent set and
  preserved in the event ledger.
- A low-speed resistance extension prevents an invalid ITTC correlation call
  during deliberate stop/turn manoeuvres.
- Contact sheets now show evenly sampled 0/25/50/75/100 percent frames.

## Acceptance criteria

The reference suite must demonstrate full nominal coverage and home docking,
no watchdog loop, forward-tracking heading-error p95 no greater than 15 deg,
and no more than one numerical safety intervention in either fixed scenario.
