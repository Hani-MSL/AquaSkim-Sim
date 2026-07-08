@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
start "" outputs\figures\phase10_3_stability_trade_space.png
start "" outputs\figures\phase10_3_endurance_trade_space.png
start "" outputs\figures\phase10_3_candidate_comparison.png
start "" outputs\figures\phase10_3_design_synthesis_dashboard.png
start "" outputs\reports\phase10_3_parametric_trade_study_summary.md
endlocal
