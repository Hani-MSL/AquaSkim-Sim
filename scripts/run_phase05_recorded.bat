@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda was not found in this CMD session.
    exit /b 1
)

call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Could not activate environment aquaskim-sim.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 (
    echo [ERROR] Editable installation failed.
    exit /b 1
)

python -m aquaskim.cli run-phase05
set EXIT_CODE=%ERRORLEVEL%
endlocal & exit /b %EXIT_CODE%
