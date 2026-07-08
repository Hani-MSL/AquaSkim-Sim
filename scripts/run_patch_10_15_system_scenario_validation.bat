@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.15 System-level Scenario Validation
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then scenario media.
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
echo AquaSkim-Sim - Full pytest suite before system-scenario media
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Fixed system-level scenario evidence
echo ========================================================================
python -m aquaskim.phase10_15_prepare
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_15_render --kind validated
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_15_render --kind time_limit
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_15_render --kind boundary
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_15_render --kind timeline
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_15_finalize
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.15 Recorded System-scenario Run
echo ========================================================================
echo Status       : PASS
echo Contact sheet: outputs\animations\reference_system_scenario_contact_sheet.png
echo Visual QA    : outputs\logs\reference_system_visual_quality_manifest.json
echo Note         : No Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
