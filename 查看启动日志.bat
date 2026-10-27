@echo off
chcp 65001 >nul
setlocal
set "BUMBUM_TASK_ROOT=%~dp0"
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo 只显示后端、管理页和用户页日志末尾各30行，不读取.env。分享前请检查并隐藏个人信息。
powershell.exe -NoLogo -NoProfile -Command "Set-Location -LiteralPath $env:BUMBUM_TASK_ROOT; $failed = $false; foreach ($name in @('backend.log', 'frontend.log', 'user.log')) { Write-Host ('--- ' + $name + ' ---'); $file = Join-Path '.local-run' $name; if (Test-Path -LiteralPath $file -PathType Leaf) { try { Get-Content -LiteralPath $file -Encoding UTF8 -Tail 30 -ErrorAction Stop } catch { Write-Host '日志无法读取，请保留提示后排查权限。'; $failed = $true } } else { Write-Host '尚未找到日志，请确认曾从此目录启动项目。'; $failed = $true } }; if ($failed) { exit 1 }"
set "BUMBUM_TOOL_EXIT=%errorlevel%"
popd
pause
exit /b %BUMBUM_TOOL_EXIT%
