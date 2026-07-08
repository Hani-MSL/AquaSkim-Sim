@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Non-interactive Reference Evidence Build
echo ========================================================================
echo Fixed versioned design, reference scenarios and manoeuvre cases will be used.
echo No user information and no local profile will be requested.
echo The source-integrity audit and full pytest suite run before any reference media generation.

call scripts\run_patch_10_10_source_integrity.bat
if errorlevel 1 exit /b 1

call scripts\run_patch_10_9.bat
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
