@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.10 Source Integrity Recovery
echo ========================================================================
echo Scope: YAML, imports, syntax and full tests only.
echo Explicitly disabled: reference simulation, GIF/MP4, Word, delivery ZIP, release build.

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
echo AquaSkim-Sim - Full pytest suite
echo ========================================================================
python -m pytest -q
if errorlevel 1 exit /b 1

python -m aquaskim.integrity_audit report
if errorlevel 1 exit /b 1

echo ========================================================================
echo AquaSkim-Sim - Patch 10.10 Recorded Integrity Run
echo ========================================================================
echo Status       : PASS
echo Audit report : outputs\logs\patch10_10_source_integrity_audit.json
echo Note         : No mission/media/report/release build was executed.
echo ========================================================================
endlocal
