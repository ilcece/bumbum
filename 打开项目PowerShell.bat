@echo off
chcp 65001 >nul
setlocal
set "BUMBUM_TASK_ROOT=%~dp0"
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo 正在从此项目根目录打开 PowerShell；不会切换分支或拉取代码。
powershell.exe -NoLogo -NoProfile -NoExit -Command "Set-Location -LiteralPath $env:BUMBUM_TASK_ROOT; $OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; Write-Host ('当前位置：' + (Get-Location).Path); Write-Host '可在这里执行手册命令；关闭窗口不会停止项目。'"
set "BUMBUM_TOOL_EXIT=%errorlevel%"
popd
exit /b %BUMBUM_TOOL_EXIT%
