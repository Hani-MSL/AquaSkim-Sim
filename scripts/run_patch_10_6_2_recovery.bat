@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.6.2 Configuration Recovery
echo ========================================================================
call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] The aquaskim-sim Conda environment could not be activated.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Python syntax gate failed.
    exit /b 1
)

python -m pytest -q tests\test_configuration_recovery.py tests\test_paths_contract.py
if errorlevel 1 exit /b 1

python -c "from aquaskim.config import load_base_configuration; c=load_base_configuration(); print('[OK] Complete baseline restored:', c.source_path); print('[OK] Reference profile policy: local profile ignored by default'); print('[OK] Hull length [m]:', c.hull_length_m)"
if errorlevel 1 exit /b 1

echo [OK] Configuration and path recovery succeeded.
echo [INFO] This recovery patch intentionally does NOT start the long Phase 10.6 mission.
endlocal
