@echo off
setlocal
cd /d "%~dp0\.."

echo ================================================================
echo AquaSkim-Sim - Creating Conda Environment
echo ================================================================

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda was not found in this CMD session.
    echo Open Miniconda Prompt or run "conda init cmd.exe", then reopen CMD.
    exit /b 1
)

call conda env create -f environment.yml
if errorlevel 1 (
    echo [ERROR] Conda environment creation failed.
    exit /b 1
)

call conda activate aquaskim-sim
if errorlevel 1 (
    echo [ERROR] Environment activation failed.
    exit /b 1
)

python -m pip install --editable .
if errorlevel 1 (
    echo [ERROR] Editable project installation failed.
    exit /b 1
)

python -m aquaskim.cli preflight
if errorlevel 1 exit /b 1

python -m pytest -q
if errorlevel 1 exit /b 1

echo [OK] Environment is ready.
endlocal
