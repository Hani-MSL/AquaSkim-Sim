@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Local Scientific Profile Bootstrap
echo ========================================================================
echo This entry point is intentionally NOT a release or delivery build.
echo It creates or updates a local scientific experiment profile only.
echo The fixed reference build ignores config\user_profile.yaml.
call scripts\configure_and_build.bat
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
