@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda was not found in this CMD session.
    exit /b 1
)

call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Could not activate conda environment "aquaskim-sim".
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 (
    echo [ERROR] Editable installation failed.
    exit /b 1
)

REM Syntax gate: fail early before importing the project or launching a recorded run.
python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Python syntax gate failed. Review the compiler output above.
    exit /b 1
)

python -m aquaskim.cli run-phase08
set "EXIT_CODE=!ERRORLEVEL!"
endlocal & exit /b %EXIT_CODE%
