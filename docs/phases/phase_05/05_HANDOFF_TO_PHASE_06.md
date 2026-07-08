# Handoff to Phase 06

Phase 06 will construct the 3-DOF planar dynamics model. It will use the Phase 04 thrust and resistance relationships plus the Phase 05 pack-side electrical demand model to update SOC during dynamic manoeuvres.

Inputs transferred:
- Full-payload mass and inertia approximation.
- Hydrostatic draft and stability constraints.
- Phase 04 resistance / thrust / RPM / power relations.
- Phase 05 battery SOC integration, current limit and RTH threshold.

New work in Phase 06:
- Surge, sway and yaw states.
- Added mass and damping.
- Differential thrust allocation.
- Current disturbance vector.
- Dynamic energy consumption coupled to the commanded thrust.
