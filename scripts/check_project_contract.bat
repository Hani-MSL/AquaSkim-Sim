@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

python -c "from pathlib import Path; from aquaskim.paths import DIRECTORIES, PROJECT_ROOT; print('[OK] Project root:', PROJECT_ROOT); print('[OK] Config directory:', DIRECTORIES['config']); print('[OK] Evidence root:', DIRECTORIES['phase_records']); required=Path('config')/'base_parameters.yaml'; print('[OK] Base configuration:', required) if required.exists() else (_ for _ in ()).throw(SystemExit('[ERROR] Missing required file: config\\base_parameters.yaml'))"
if errorlevel 1 exit /b 1

python -m compileall -q src
if errorlevel 1 (
    echo [ERROR] Python syntax gate failed.
    exit /b 1
)

echo [OK] Project path contract and syntax gate passed.
endlocal
