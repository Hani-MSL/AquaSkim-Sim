@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
echo ========================================================================
echo AquaSkim-Sim - Phase 10.2 Parametric Design Synthesis
echo ========================================================================
call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Could not activate the aquaskim-sim environment.
    exit /b 1
)
python -m pip install --editable .
if errorlevel 1 exit /b 1
python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Syntax gate failed.
    exit /b 1
)
python -m aquaskim.cli run-phase10-2
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
