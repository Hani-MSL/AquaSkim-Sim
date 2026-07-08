@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim ^| Patch 08.1 Syntax Hotfix
echo ========================================================================
echo This hotfix replaces the Phase 08 summary formatter and runs a syntax gate.
call scripts\run_patch_08.bat
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
