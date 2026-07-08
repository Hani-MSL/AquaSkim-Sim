@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.16 Final Presentation Evidence Curation
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then curation QA.
echo Explicitly disabled: new mission simulation, Word, delivery ZIP and release build.

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
echo AquaSkim-Sim - Full pytest suite before evidence curation
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Curating existing fixed-reference evidence
echo ========================================================================
python -m aquaskim.phase10_16
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.16 Recorded Presentation Curation

echo ========================================================================
echo Status       : PASS
echo Figure sheet : outputs\presentation_evidence\reference_presentation_figure_contact_sheet.png
echo Media sheet  : outputs\presentation_evidence\reference_presentation_media_contact_sheet.png
echo Visual QA    : outputs\logs\reference_presentation_visual_quality_manifest.json
echo Note         : No new mission simulation, Word, delivery ZIP or release build was executed.
echo ========================================================================
endlocal
