@echo off
setlocal
cd /d "%~dp0\.."
start "" outputs\figures\reference_mission_map.png
start "" outputs\figures\reference_hopper_energy_coverage.png
start "" outputs\figures\reference_force_trajectory_3d.png
start "" outputs\figures\reference_parameter_traceability.png
start "" outputs\animations\reference_mission_animation_contact_sheet.png
endlocal
