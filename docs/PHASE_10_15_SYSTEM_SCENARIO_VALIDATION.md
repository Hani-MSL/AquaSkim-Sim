# System-level Scenario Validation and Controlled-Failure Evidence

## Purpose

This stage validates the fixed, non-interactive reference craft across declared
validated conditions, one out-of-envelope boundary observation, and two
controlled-failure conditions. A controlled failure is an expected supervisory
outcome with positive clearance; it is not counted as mission success.

## Classification policy

| Classification | Meaning | Contribution to validated success |
|---|---|---:|
| `validated` | Inside the documented low-current sheltered-basin envelope | Yes |
| `boundary` | Beyond the declared operating envelope; retained as a limitation | No |
| `controlled_failure` | Versioned supervisory termination or deliberately disabled prerequisite | No |

## Scenario set

1. Nominal coverage and docking.
2. Cross-current compensated mission at 0.02 m/s.
3. Energy-reserve return.
4. Hopper-capacity return.
5. Diagonal-current boundary observation around 0.05 m/s.
6. Scheduled time-limit termination.
7. Uncompensated diagonal crossflow outside the validated envelope.

## Exclusions

The stage does not create a Word report, delivery ZIP or release declaration.
It also does not claim sea-trial behavior, current sensing, wave response, roll
transients, sloshing, structural strength or certification.
