# Legacy Pipeline Isolation Policy

## Purpose

The repository retains earlier Phase 08/09 quota-based mission modules because
those files document the development history and explain previously generated
artefacts. They are **not** evidence for the fixed reference design.

## Legacy quota-based modules

- `aquaskim.autonomy`
- `aquaskim.phase08`
- `aquaskim.phase08_2`
- `aquaskim.phase09`
- `aquaskim.phase09_2`
- `aquaskim.phase10_4`

The historical branch may use `max_collections` as a mission termination
condition. It must not be used to substantiate reference-mission performance.

## Reference-only path

```text
reference_design
→ mission_plant
→ mission_quality
→ phase10_7
→ phase10_8
```

Reference mission termination uses only:

1. hopper mass/occupied-volume capacity;
2. safe return-energy requirement or SOC floor;
3. time limit;
4. safety/progress protection; or
5. completed coverage with no reachable target.

## Enforced checks

`aquaskim.integrity_audit` parses the reference source imports and checks that
no quota-based legacy module is imported by the reference mission, manoeuvre or
plant-assembly path. The corresponding pytest regression test is intentionally
static and explicit so accidental re-coupling is detected before a heavy build.

## Reference-configuration normalization (Patch 10.17)

`config/base_parameters.yaml` retains `autonomy.max_collections` only so the
historical Phase 08/09 branch can be reproduced. `load_reference_configuration()`
now removes that key before building the effective fixed-reference
configuration. Consequently it cannot enter `QualityMissionSettings` or alter
reference termination. The engineering release gate verifies this invariant by
injecting different legacy values and confirming that the effective reference
settings remain identical.
