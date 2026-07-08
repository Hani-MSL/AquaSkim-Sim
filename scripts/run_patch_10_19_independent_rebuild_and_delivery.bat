@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.19 Independent Rebuild and Delivery Package
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, Word QA precondition, then delivery ZIP.
echo Explicitly disabled: new mission simulation, GIF/MP4 rendering and certification/release-build claims.

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
echo AquaSkim-Sim - Reproduction script preflight before full delivery tests
echo ========================================================================
python -m aquaskim.delivery_package --preflight-scripts
if errorlevel 1 (
  echo [ERROR] Reproduction script preflight failed.
  exit /b 1
)

echo ========================================================================
echo AquaSkim-Sim - Full pytest suite before delivery packaging
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Final delivery package assembly
echo ========================================================================
python -m aquaskim.phase10_19
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Post-package delivery regression tests
echo ========================================================================
python -m pytest -q tests\test_phase10_19_delivery_package.py
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.19 Recorded Final Delivery Package
echo ========================================================================
echo Status       : PASS
echo Package      : outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
echo Manifest     : outputs\deliverables\FINAL_DELIVERY_PACKAGE_MANIFEST.json
echo SHA256SUMS   : outputs\deliverables\FINAL_DELIVERY_SHA256SUMS.txt
echo Note         : Final package is ready for course-project delivery; no certification claim is created.
echo ========================================================================
endlocal
