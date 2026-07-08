@echo off
setlocal
cd /d "%~dp0\.."
call conda activate aquaskim-sim
if errorlevel 1 exit /b 1
python -m pytest -q
endlocal
