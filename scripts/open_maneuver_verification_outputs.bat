@echo off
setlocal
cd /d "%~dp0\.."
start "" outputs\figures\maneuver_step_thrust_response.png
start "" outputs\figures\maneuver_turning_circle.png
start "" outputs\figures\maneuver_zigzag_response.png
start "" outputs\figures\maneuver_force_trajectory_3d.png
start "" outputs\figures\maneuver_time_step_convergence.png
start "" outputs\animations\maneuver_animation_contact_sheet.png
endlocal
