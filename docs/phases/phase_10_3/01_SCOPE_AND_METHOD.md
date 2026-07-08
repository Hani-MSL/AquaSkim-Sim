# Phase 10.3 — Parametric Trade Study and Release-Quality Inventory

## Purpose
This phase expands the nominal AquaSkim-Sim design into a reproducible preliminary design-space study. It is deliberately a transparent screening study, not a claim of global optimisation, CFD certification, FEA certification or manufacturing readiness.

## Trade spaces

### A. Hull spacing × collected payload
For each point, the model recomputes the full-load mass case, draft, freeboard, `KB`, `BM`, `KG` and `GM` using the Phase 03 catamaran hydrostatic model. The port/starboard hull and thruster positions move symmetrically when hull spacing changes.

Acceptance constraints are:

- `GM >= minimum_gm_m`
- calm-water and operational-heel freeboard `>= minimum_freeboard_m`
- conceptual displacement capacity greater than requested displacement

### B. Battery capacity × cruise speed
For each point, the model recomputes hull resistance, symmetric thruster RPM, bus power, pack current and endurance to the configured return-home SOC floor. Acceptance constraints are:

- required operating point is feasible for both thrusters;
- thrust reserve meets the Phase 04 configured minimum;
- endurance meets the Phase 05 configured minimum.

### C. Candidate comparison
Six explicit candidates expose the trade-off between nominal design, stability margin, payload margin, endurance, throughput and a deliberately constrained boundary case. The ranking score is the minimum normalized margin across GM, freeboard, endurance and thrust reserve.

## Important limitation
Changing battery capacity changes energy availability but **does not automatically add physical battery mass** to the Phase 02 mass budget. This is retained as an explicit future model refinement. No result is interpreted as a certified optimal design.
