@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Scientific Experiment Configuration
echo ========================================================================
echo This command creates or updates only config\user_profile.yaml.
echo It does NOT launch a reference simulation, Word report, delivery ZIP or release build.
echo Personal student/course/institution information is not requested here.
echo.
call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] The aquaskim-sim Conda environment could not be activated.
    exit /b 1
)
python -m pip install --editable .
if errorlevel 1 exit /b 1
python -m aquaskim.cli configure
set "EXIT_CODE=%ERRORLEVEL%"
if not errorlevel 1 (
    python -m aquaskim.cli run-configured-build
    echo.
    echo [OK] Scientific profile created. No simulation or delivery build was launched.
)
endlocal & exit /b %EXIT_CODE%
