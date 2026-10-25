@echo off
chcp 65001 >nul
setlocal
set "BUMBUM_TASK_ROOT=%~dp0"
set "BUMBUM_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
pushd "%~dp0"
if errorlevel 1 goto directory_failed
if not exist "%BUMBUM_POWERSHELL%" goto powershell_missing
echo 正在从此项目根目录打开 PowerShell；不会切换分支或拉取代码。
"%BUMBUM_POWERSHELL%" -NoLogo -NoProfile -NoExit -Command "$ErrorActionPreference = 'Stop'; Set-Location -LiteralPath $env:BUMBUM_TASK_ROOT; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [Console]::OutputEncoding; Write-Host ('当前位置：' + (Get-Location).Path); Write-Host '可在这里执行手册命令；关闭窗口不会停止项目。'"
set "BUMBUM_TOOL_EXIT=%errorlevel%"
echo PowerShell进程已结束，退出码：%BUMBUM_TOOL_EXIT%。
echo 如果没有进入命令窗口，请保留上方错误提示，不必反复双击。
popd
pause
exit /b %BUMBUM_TOOL_EXIT%
:directory_failed
echo 无法进入此bat所在文件夹，请保留文件位置和错误提示。
pause
exit /b 1
:powershell_missing
echo 未找到Windows自带的PowerShell，请保留此提示，不修改系统设置。
popd
pause
exit /b 1
