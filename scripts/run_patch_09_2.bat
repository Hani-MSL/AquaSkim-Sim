@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Phase 09.2 Comprehensive Validation and Visual Evidence
echo ========================================================================

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda was not found in this CMD session.
    exit /b 1
)

call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Could not activate conda environment aquaskim-sim.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 exit /b 1

python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Python syntax gate failed.
    exit /b 1
)

python -m aquaskim.cli run-phase09-2
set "EXIT_CODE=!ERRORLEVEL!"
endlocal & exit /b %EXIT_CODE%
