@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.14 Payload Stability and Manoeuvre Validation
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then payload media.
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
echo AquaSkim-Sim - Full pytest suite before payload manoeuvre media
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Fixed payload stability and low-current manoeuvre evidence
echo ========================================================================
python -m aquaskim.phase10_14_prepare
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_14_render --kind stability
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_14_render --kind step
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_14_render --kind turn
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_14_render --kind zigzag
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_14_finalize
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.14 Recorded Payload-manoeuvre Run
echo ========================================================================
echo Status       : PASS
echo Contact sheet: outputs\animations\reference_payload_maneuver_contact_sheet.png
echo Visual QA    : outputs\logs\reference_payload_maneuver_visual_quality_manifest.json
echo Note         : No Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
