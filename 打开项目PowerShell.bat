@echo off
setlocal
set "BUMBUM_PROJECT_ROOT=%~dp0"
set "BUMBUM_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%BUMBUM_POWERSHELL%" goto missing
start "BUMBUM Windows PowerShell" /D "%BUMBUM_PROJECT_ROOT%" "%BUMBUM_POWERSHELL%" -NoLogo -NoProfile -NoExit -Command "Set-Location -LiteralPath $env:BUMBUM_PROJECT_ROOT"
if errorlevel 1 goto failed
exit /b 0
:missing
echo Windows PowerShell was not found.
pause
exit /b 1
:failed
echo Could not open Windows PowerShell in the project directory.
pause
exit /b 1
