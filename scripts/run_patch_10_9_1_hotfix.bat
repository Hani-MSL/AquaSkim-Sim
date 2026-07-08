@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Patch 10.9.1 Registry and Test Hotfix
echo ========================================================================
echo This hotfix validates configuration and tests only.
echo Existing mission figures, GIFs, MP4s and evidence are not regenerated.

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

python -c "from pathlib import Path; import yaml; p=Path('config')/'parameter_registry.yaml'; d=yaml.safe_load(p.read_text(encoding='utf-8')); print('[OK] Parameter registry parsed:', len(d['parameters']), 'entries')"
if errorlevel 1 exit /b 1

python -m pytest -q tests\test_reference_design_contract.py tests\test_mission_fidelity_quality_gate.py tests\test_animation_audit.py tests\test_dynamics_3dof.py
if errorlevel 1 exit /b 1

echo [OK] Patch 10.9.1 passed. No expensive simulation or media render was launched.
endlocal
