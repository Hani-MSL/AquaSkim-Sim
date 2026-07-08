@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Reference Design and Hopper-Governed Mission
echo ========================================================================
call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Conda environment aquaskim-sim could not be activated.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

call scripts\check_project_contract.bat
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_6
if errorlevel 1 exit /b 1

python -m pytest -q tests\test_hopper_model.py tests\test_reference_design_contract.py tests\test_paths_contract.py
if errorlevel 1 exit /b 1

echo [OK] Reference mission generated with fixed configuration; no interactive prompt was used.
endlocal
