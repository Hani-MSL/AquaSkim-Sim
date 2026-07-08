@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.11 Reference Mission Fidelity and Visual Evidence
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then reference media.
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
echo AquaSkim-Sim - Full pytest suite before visual production
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Fixed Reference Mission Fidelity Evidence Build
echo ========================================================================
python -m aquaskim.phase10_11
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.11 Recorded Fidelity Run
echo ========================================================================
echo Status       : PASS
echo Contact sheet: outputs\animations\reference_fidelity_visual_contact_sheet.png
echo Visual QA    : outputs\logs\reference_visual_evidence_quality_manifest.json
echo Note         : No Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
