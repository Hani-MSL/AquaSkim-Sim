# Current-compensation Model and Boundary Interpretation

The guidance path lives in the earth-fixed basin frame while propulsors create
velocity relative to water. For a known deterministic simulation current, the
course command is formed from the required water-relative velocity:

`V_water = V_ground - gain × V_current`

The reference gain is one. In calm water the relation reduces exactly to the
original line-of-sight command. Under cross-current it produces a measurable
crab angle before the heading feedback loop allocates differential thrust.

The boundary scenario has a diagonal current magnitude above the documented
validated current limit. Its observed time-limited outcome is retained as
negative evidence: it prevents the project from claiming capability beyond
what the numerical controller has demonstrated.
