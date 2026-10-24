@echo off
chcp 65001 >nul
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if exist ".venv\Scripts\python.exe" goto use_venv
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 goto use_launcher
python -c "import sys; sys.exit(sys.version_info[:2] != (3,12))" >nul 2>&1
if not errorlevel 1 goto use_python
echo 未找到 Python 3.12。请先安装，然后重新打开此窗口。
echo 安装地址：https://www.python.org/downloads/
set "BUMBUM_EXIT=1"
goto finished
:use_venv
".venv\Scripts\python.exe" -X utf8 "scripts\windows_local.py" stop
set "BUMBUM_EXIT=%errorlevel%"
goto finished
:use_launcher
py -3.12 -X utf8 "scripts\windows_local.py" stop
set "BUMBUM_EXIT=%errorlevel%"
goto finished
:use_python
python -X utf8 "scripts\windows_local.py" stop
set "BUMBUM_EXIT=%errorlevel%"
:finished
if not "%BUMBUM_EXIT%"=="0" if not "%BUMBUM_EXIT%"=="130" echo 请保留上方提示，按 docs\LOCAL_DEVELOPMENT.md 排查。
popd
pause
exit /b %BUMBUM_EXIT%
