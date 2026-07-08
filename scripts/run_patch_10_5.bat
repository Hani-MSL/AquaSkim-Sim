@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.5 Scientific Configuration Refactor
echo ========================================================================
call conda activate aquaskim-sim
if errorlevel 1 exit /b 1
python -m pip install --editable .
if errorlevel 1 exit /b 1
python -m compileall -q src
if errorlevel 1 exit /b 1
python -m pytest -q tests\test_project_profile_scientific.py tests\test_reproducible_entrypoint.py
if errorlevel 1 exit /b 1
echo [OK] Patch 10.5 installed. No full simulation build was launched.
endlocal
