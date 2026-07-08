@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
echo This removes generated outputs and evidence records only.
set /p CONFIRM=Type DELETE to continue: 
if /I not "%CONFIRM%"=="DELETE" (
    echo Cancelled.
    exit /b 0
)
for %%D in (outputs records\phases records\handoffs records\manifests records\bootstrap) do (
    if exist "%%D" rmdir /s /q "%%D"
)
mkdir outputs\figures outputs\animations outputs\videos outputs\logs outputs\tables outputs\reports outputs\cad_renders 2>nul
mkdir records\phases records\handoffs records\manifests records\bootstrap 2>nul
echo [OK] Generated artifacts removed. Source and configuration files were preserved.
endlocal
