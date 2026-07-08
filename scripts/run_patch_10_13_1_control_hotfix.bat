@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.13.1 Current-compensation API Hotfix
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then renewed evidence.
echo Explicitly disabled: Word, delivery ZIP and release build.

call conda activate aquaskim-sim
if errorlevel 1 (
  echo [ERROR] The aquaskim-sim Conda environment could not be activated.
  exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

python -m aquaskim.integrity_audit yaml
if errorlevel 1 exit /b 1

python -m aquaskim.integrity_audit imports
if errorlevel 1 exit /b 1

python -m compileall -q src
if errorlevel 1 (
  echo [ERROR] Python syntax gate failed.
  exit /b 1
)

echo ========================================================================
echo AquaSkim-Sim - Full pytest suite before renewed control evidence
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Renewing source-consistent reference evidence
echo ========================================================================
python -m aquaskim.phase10_11
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_12
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_prepare
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_render --kind comparison --gif "outputs\animations\reference_open_loop_vs_current_aware_replay.gif" --mp4 "outputs\videos\reference_open_loop_vs_current_aware_replay.mp4"
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_render --kind response --gif "outputs\animations\reference_current_control_response_replay.gif" --mp4 "outputs\videos\reference_current_control_response_replay.mp4"
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_render --kind sensitivity --gif "outputs\animations\reference_controller_sensitivity_replay.gif" --mp4 "outputs\videos\reference_controller_sensitivity_replay.mp4"
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_render --kind force --gif "outputs\animations\reference_current_force_yaw_replay.gif" --mp4 "outputs\videos\reference_current_force_yaw_replay.mp4"
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_13_finalize
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.13.1 Recorded Control-robustness Run
echo ========================================================================
echo Status       : PASS
echo Contact sheet: outputs\animations\reference_current_control_contact_sheet.png
echo Visual QA    : outputs\logs\reference_current_control_visual_quality_manifest.json
echo Note         : No Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
