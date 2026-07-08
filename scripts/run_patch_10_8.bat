@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Dynamic Manoeuvre Verification
echo ========================================================================
call conda activate aquaskim-sim
if errorlevel 1 (
  echo [ERROR] The aquaskim-sim Conda environment could not be activated.
  exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

call scripts\check_project_contract.bat
if errorlevel 1 exit /b 1

python -m aquaskim.phase10_8
if errorlevel 1 exit /b 1

python -m pytest -q tests\test_maneuver_validation.py tests\test_dynamics_3dof.py tests\test_paths_contract.py tests\test_reference_mission_calibration.py tests\test_mission_fidelity_quality_gate.py tests\test_animation_audit.py
if errorlevel 1 exit /b 1

echo [OK] Dynamic manoeuvre suite completed with fixed configuration and no interactive input.
endlocal
