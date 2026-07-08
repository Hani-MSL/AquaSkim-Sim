@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
start "" outputs\figures\reference_nominal_coverage_map.png
start "" outputs\figures\reference_high_loading_map.png
start "" outputs\figures\reference_closed_loop_dynamics.png
start "" outputs\figures\reference_hopper_capacity_return.png
start "" outputs\figures\reference_mission_verification_scorecard.png
start "" outputs\animations\reference_mission_validation_contact_sheet.png
endlocal
