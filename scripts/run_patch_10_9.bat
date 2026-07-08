@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - Mission Fidelity Correction and Visual Evidence Audit
echo ========================================================================
echo This run is non-interactive. It regenerates the fixed reference mission
echo and manoeuvre evidence with the corrected stop-turn-go controller.

call scripts\run_patch_10_7.bat
if errorlevel 1 exit /b 1

call scripts\run_patch_10_8.bat
if errorlevel 1 exit /b 1

echo [OK] Mission and manoeuvre visual audit completed.
endlocal
