@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
echo [BLOCKED] Final delivery disabled pending Release Gate.
echo [BLOCKED] Do not open or distribute Word/ZIP deliverables at this stage.
endlocal & exit /b 2
