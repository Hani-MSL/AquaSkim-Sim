@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.18 Final Word Report Generation and QA
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then Word-only report build.
echo Explicitly disabled: new mission simulation, GIF/MP4 rendering, delivery ZIP and release build.

call conda activate aquaskim-sim
if errorlevel 1 (
  echo [ERROR] The aquaskim-sim Conda environment could not be activated.
  exit /b 1
)

set PIP_DISABLE_PIP_VERSION_CHECK=1
set PIP_NO_INPUT=1

echo [INFO] Offline-safe editable install: using build tools already present in aquaskim-sim.
python -m pip install --editable . --no-build-isolation --no-deps
if errorlevel 1 (
  echo [ERROR] Offline-safe editable install failed. Verify the existing Conda environment includes setuptools and wheel.
  exit /b 1
)

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
echo AquaSkim-Sim - Cleaning stale partial Word artifacts before pre-build tests
echo ========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$paths = @('outputs\reports\AquaSkim-Sim_Final_Report.docx','outputs\reports\phase10_report_build_manifest.json','outputs\reports\final_word_report_qa.md','outputs\logs\final_word_report_qa.json'); foreach ($p in $paths) { if (Test-Path $p) { try { Remove-Item $p -Force -ErrorAction Stop; Write-Host ('[CLEAN] ' + $p) } catch { Write-Error ('[ERROR] Close Word or any viewer that is using: ' + $p); exit 1 } } }"
if errorlevel 1 (
  echo [ERROR] Stale report cleanup failed. Close Microsoft Word or any viewer using the report, then rerun this script.
  exit /b 1
)

echo ========================================================================
echo AquaSkim-Sim - Full pytest suite before Word report generation
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Word-only final report generation
echo ========================================================================
python -m aquaskim.phase10_18
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Post-generation report regression tests
echo ========================================================================
python -m pytest -q tests\test_phase10_report.py tests\test_phase10_18_final_word.py
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.18 Recorded Word Report Build
echo ========================================================================
echo Status       : PASS
echo Report       : outputs\reports\AquaSkim-Sim_Final_Report.docx
echo QA           : outputs\logs\final_word_report_qa.json
echo Manifest     : outputs\reports\phase10_report_build_manifest.json
echo Note         : Delivery ZIP and final release scripts remain disabled.
echo ========================================================================
endlocal
