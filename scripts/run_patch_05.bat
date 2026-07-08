@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
call scripts\run_phase05_recorded.bat
set EXIT_CODE=%ERRORLEVEL%
endlocal & exit /b %EXIT_CODE%
