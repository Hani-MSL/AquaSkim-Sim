@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ========================================================================
echo AquaSkim-Sim - One-command rebuild from zero to final delivery
echo ========================================================================
echo This command regenerates outputs\ and records\ locally from source.
echo Generated artifacts are intentionally ignored by Git.
echo.

where conda >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Conda was not found on PATH.
  echo [INFO] Install Miniconda/Mambaforge, then run: conda env create -f environment.yml
  exit /b 1
)

call conda activate aquaskim-sim
if errorlevel 1 (
  echo [INFO] Conda environment aquaskim-sim was not found. Creating it from environment.yml...
  call conda env create -f environment.yml
  if errorlevel 1 exit /b 1
  call conda activate aquaskim-sim
  if errorlevel 1 exit /b 1
)

set PIP_DISABLE_PIP_VERSION_CHECK=1
set PIP_NO_INPUT=1

echo [INFO] Installing package in editable mode using local build tools.
python -m pip install --editable . --no-build-isolation --no-deps
if errorlevel 1 (
  echo [ERROR] Editable install failed. Verify the environment includes setuptools and wheel.
  exit /b 1
)

python -m aquaskim.rebuild_from_zero
if errorlevel 1 exit /b 1

echo ========================================================================
echo DONE - New output folder and final delivery package are ready.
echo Package: outputs\deliverables\AquaSkim-Sim_Final_Delivery_v1.6.21.zip
echo ========================================================================
endlocal
