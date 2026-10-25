@echo off
chcp 65001 >nul
setlocal
set "BUMBUM_TASK_ROOT=%~dp0"
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo 本工具只检查已运行的后端和本机测试库，不启动服务、不升级或备份。
if exist ".venv\Scripts\python.exe" goto checks
echo 未找到本项目Python环境。请先按手册执行首次准备。
popd
pause
exit /b 1
:checks
set "BUMBUM_TOOL_EXIT=0"
echo [1/3] 后端与数据库就绪检查；未启动项目时失败属于预期。
".venv\Scripts\python.exe" -X utf8 "scripts\verify_local.py"
if errorlevel 1 set "BUMBUM_TOOL_EXIT=1"
echo [2/3] 芯片项目可空结构；缺少升级时仅提示，不执行。
".venv\Scripts\python.exe" -X utf8 "scripts\migrate_local.py"
if errorlevel 1 set "BUMBUM_TOOL_EXIT=1"
echo [3/3] 首次登记来源字段；缺少升级时仅提示，不执行。
".venv\Scripts\python.exe" -X utf8 "scripts\migrate_local.py" --registration-source
if errorlevel 1 set "BUMBUM_TOOL_EXIT=1"
echo 检查结束。结构检查显示需要升级时，仍需按手册单独处理，不能视为全部通过。
popd
pause
exit /b %BUMBUM_TOOL_EXIT%
