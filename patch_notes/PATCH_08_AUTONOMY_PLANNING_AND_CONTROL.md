# Patch 08 — Autonomous Planning, Control and Closed-Loop Mission

## Added engineering capability
Phase 08 connects the completed design layers into the first deterministic closed-loop mission:
1. Phase 07 perception and occupancy map create the safe planning domain.
2. A* creates collision-free routes to confirmed debris targets and to home.
3. A transparent finite-state agent manages SEARCH, TRANSIT_TO_DEBRIS, COLLECT, RETURN_HOME, DOCK and MISSION_COMPLETE transitions.
4. A feedback controller converts speed and heading errors into port/starboard thrust commands.
5. The Phase 06 3-DOF plant integrates motion under differential thrust and current.
6. The Phase 05 battery model updates SOC and can force return-home.

## Deliberate scope of the baseline mission
The baseline is a deterministic proof mission with a two-object collection quota. It demonstrates the entire perception → decision → planning → control → collection → return chain with interpretable logs. Phase 09 will broaden scenario coverage, include adverse-current and low-SOC mission cases, and assemble the presentation-quality video package.

## New source modules
- `src/aquaskim/planner.py`
- `src/aquaskim/autonomy.py`
- `src/aquaskim/phase08.py`

## Key artifacts
- five PNG/SVG report figures,
- mission time series, planned routes, agent-event and collection CSVs,
- GIF and MP4 closed-loop animation,
- JSON summary and quality manifest,
- Phase 08 evidence and handoff.

## Quality controls
- all report figures export to PNG and SVG,
- PNG dimensions are checked against the project visual-quality standard,
- route cells are checked to be free in the occupancy grid,
- the deterministic mission must collect targets, retain positive signed obstacle clearance, and terminate in `MISSION_COMPLETE` at home.
