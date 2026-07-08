@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
start "" outputs\figures\reference_nominal_coverage_map.png
start "" outputs\figures\reference_closed_loop_dynamics.png
start "" outputs\figures\reference_mission_verification_scorecard.png
start "" outputs\figures\maneuver_turning_circle.png
start "" outputs\figures\maneuver_force_trajectory_3d.png
start "" outputs\animations\reference_mission_validation_contact_sheet.png
start "" outputs\animations\maneuver_animation_contact_sheet.png
endlocal
