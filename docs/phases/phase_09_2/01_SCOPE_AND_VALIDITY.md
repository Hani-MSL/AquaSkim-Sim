# Phase 09.2 — Comprehensive Mission Validation

## Purpose
Phase 09.2 replaces the earlier short scenario reel as the active validation baseline. It evaluates the same closed-loop vessel model under six deterministic scenario classes and a seeded current/SOC Monte Carlo envelope.

## Scenario classes

1. **Validated cases** — operating conditions counted in acceptance statistics.
2. **Protective energy case** — demonstrates a conservative no-go/return decision rather than a collection objective.
3. **Boundary cases** — deliberately challenging cases retained to show current model/controller limitations. They are not counted as validated mission successes.

## Validity boundary
The active validity limit is written to `config/phase09_2_scenarios.yaml` and copied into each official Evidence run. By default, the accepted envelope is bounded by:

- current magnitude less than or equal to `0.15 m/s`;
- initial SOC greater than or equal to `0.42`;
- static analytic obstacles;
- virtual range/debris sensors; and
- no wave, wind, contact-force, moving-obstacle or hardware-in-the-loop model.

## Why boundary cases are kept
Engineering credibility requires reporting where a simplified controller stops being adequate. A high-current or high-quota result may show a time limit or inability to complete the mission. These outcomes are logged, plotted and animated; they are not silently removed.
