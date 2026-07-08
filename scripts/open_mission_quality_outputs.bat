@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
start "" "outputs\figures\mission_multitarget_map.png"
start "" "outputs\figures\mechanical_force_diagram_3d.png"
start "" "outputs\figures\mission_tracking_dynamics.png"
start "" "outputs\animations\mission_animation_contact_sheet.png"
start "" "outputs\videos\mission_topdown_replay.mp4"
endlocal
