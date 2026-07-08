@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Mission Fidelity and Advanced Visualisation
echo ========================================================================

call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Could not activate the aquaskim-sim Conda environment.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Python syntax gate failed. No simulation was started.
    exit /b 1
)

python -m aquaskim.cli run-phase10-4
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
