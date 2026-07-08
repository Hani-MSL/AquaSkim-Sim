@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.12 Current-aware Operating-envelope Validation
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then deterministic envelope media.
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
echo AquaSkim-Sim - Full pytest suite before operating-envelope media
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Fixed operating-envelope validation and media build
echo ========================================================================
python -m aquaskim.phase10_12
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.12 Recorded Operating-envelope Run
echo ========================================================================
echo Status       : PASS
echo Contact sheet: outputs\animations\reference_operating_envelope_contact_sheet.png
echo Visual QA    : outputs\logs\reference_operating_envelope_visual_quality_manifest.json
echo Note         : No Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
