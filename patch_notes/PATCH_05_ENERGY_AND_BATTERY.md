# Patch 05 — Energy, Battery SOC and Return-Home Policy

## Added
- Transparent battery usable-energy and pack-side electrical demand model.
- SOC integration with DC-bus conversion efficiency, capacity derating and mild Peukert-style current penalty.
- 60-minute duty-cycle mission profiles.
- Battery current / endurance operating envelope.
- Return-home energy envelope versus distance and head current.
- High-resolution PNG + SVG figures, CSVs, JSON, report summary and visual manifest.
- Official runner with immutable evidence package and handoff.

## Single command

```bat
scripts\run_patch_05.bat
```

## Limitation
This is a preliminary mission-energy model. It does not attempt electrochemical cell, thermal, ageing or BMS transient modelling.
