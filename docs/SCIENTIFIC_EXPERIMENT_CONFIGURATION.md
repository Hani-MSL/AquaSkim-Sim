# Scientific Experiment Configuration Contract

## Scope
`config/user_profile.yaml` is a **local experiment definition**. It is intended for parameter studies and is excluded from Git. It must not contain personal student, course, institution, or submission-cover information.

## What is physically meaningful to vary?

### Environment loading
The debris field is described primarily by **areal density** (items/m²) and an equivalent mass distribution. The simulation derives a discrete count from basin area × density only because the numerical simulator must instantiate individual objects.

A manually typed debris count is therefore **not** a vehicle-design variable and is not used as a mission completion criterion.

### Vehicle payload capacity
The collector/hopper is constrained by both:

- usable internal volume [L], and
- allowable payload mass [kg].

A packing factor maps the equivalent object volume to occupied hopper volume. A physically meaningful mission policy must return when either capacity limit is reached; collected item count remains an output metric.

### Energy and operating conditions
Reasonable scenario variables include battery capacity, initial usable SOC, mission-time limit, current magnitude/direction, cruise speed, safety radius, and the Monte Carlo sample count.

## Configuration modes
The wizard offers:

1. Reference configuration
2. Debris-field loading study
3. Hopper-capacity study
4. Energy/endurance study
5. Current-robustness study
6. Advanced guided study

It asks only values relevant to the selected experiment family.

## Release workflow
During active model development, `scripts\bootstrap_and_build.bat` creates or updates a scientific profile only. It deliberately does **not** start a full build. The final release version will use this same entry point to generate all analyses, figures, videos, evidence, report and delivery package after final quality gates pass.
