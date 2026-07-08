@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Activate the aquaskim-sim environment first, or use configure_and_build.bat.
    exit /b 1
)
python -m pip install --editable .
if errorlevel 1 exit /b 1
python -m aquaskim.cli configure
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
