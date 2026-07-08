# Patch 10.12 — Apply Instructions

## Purpose

This patch adds deterministic current-aware guidance and a versioned
operating-envelope validation suite. It does not generate a Word report,
delivery ZIP or release build.

## Apply

```bat
cd /d C:\Projects
powershell -NoProfile -Command "Compress-Archive -Path 'C:\Projects\AquaSkim-Sim\*' -DestinationPath 'C:\Projects\AquaSkim-Sim_backup_before_patch_10_12.zip' -Force"
tar -xf "%USERPROFILE%\Downloads\AquaSkim-Sim_Patch_10_12_Current_Aware_Operating_Envelope.zip" -C C:\Projects
cd /d C:\Projects\AquaSkim-Sim
scripts\run_patch_10_12_operating_envelope.bat
```

## Gate Order

1. YAML audit
2. Import audit
3. `compileall`
4. Full pytest suite
5. Deterministic operating-envelope scenarios
6. GIF/MP4 rendering and visual QA
7. Evidence, SHA-256 manifest and handoff creation

The patch must stop on any failed gate. Release artifacts remain disabled.
