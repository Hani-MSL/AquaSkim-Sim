@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.17 Engineering Release Gate
echo ========================================================================
echo Gate order: YAML parse, import audit, syntax, full tests, then audit-only release gate.
echo Explicitly disabled: new mission simulation, GIF/MP4 rendering, Word, delivery ZIP and release build.

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
  echo [ERROR] Offline-safe editable install failed. Verify the existing Conda environment includes setuptools^>=69 and wheel, then retry.
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
echo AquaSkim-Sim - Full pytest suite before Engineering Release Gate
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Audit-only Engineering Release Gate
echo ========================================================================
python -m aquaskim.phase10_17
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.17 Recorded Engineering Release Gate
echo ========================================================================
echo Status       : PASS
echo Candidate    : ENGINEERING_RELEASE_CANDIDATE
echo Report       : outputs\reports\engineering_release_gate.md
echo Manifest     : outputs\logs\engineering_release_gate.json
echo Note         : Word, delivery ZIP and final release scripts remain disabled.
echo ========================================================================
endlocal
