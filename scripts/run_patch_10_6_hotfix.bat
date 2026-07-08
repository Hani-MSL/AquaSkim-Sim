@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
echo ========================================================================
echo AquaSkim-Sim - Patch 10.6.1 Path Compatibility Hotfix
echo ========================================================================
call scripts\run_patch_10_6.bat
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
