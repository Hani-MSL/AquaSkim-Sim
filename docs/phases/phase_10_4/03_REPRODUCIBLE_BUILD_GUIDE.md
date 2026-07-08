# One-command reproducible build

## Entry point

```bat
scripts\bootstrap_and_build.bat
```

The command validates Conda, creates or activates `aquaskim-sim`, installs the project, checks Python syntax, runs an interactive configuration wizard, writes `config/user_profile.yaml`, then rebuilds the active engineering suite.

## Interactive parameter groups

- submission metadata
- basin geometry and earth-frame current
- hull dimensions, spacing, payload and battery capacity
- initial SOC, collection quota, mission duration and speeds
- safety radius and validation envelope
- animation frame count and FPS

The profile is Git-ignored. It is nevertheless copied into the timestamped build evidence folder with hashes, command transcripts and output manifests.

## Scope boundary

The wizard validates the documented ranges for the twin-hull, twin-thruster low-current model. It does not silently support a different hull architecture, arbitrary thruster count, wave dynamics, hardware certification, or a control policy outside the tested range.
