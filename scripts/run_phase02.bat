@echo off
setlocal
cd /d "%~dp0\.."
call conda activate aquaskim-sim
if errorlevel 1 (
  echo [ERROR] Could not activate aquaskim-sim.
  exit /b 1
)
python -m aquaskim.cli phase02
endlocal
