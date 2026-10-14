@echo off
chcp 65001 >nul 2>&1
setlocal
title agent学习平台

cd /d "%~dp0"

echo.
echo   ==================================================
echo      agent学习平台
echo      AI Agent 全栈课程 . 7 层 37 章
echo   ==================================================
echo.

rem ---- 查找 Python（用 goto 而非括号块，避免行尾差异导致解析失败）----
set PY=
where py >nul 2>&1 && set PY=py
if not "%PY%"=="" goto :gotpy
where python >nul 2>&1 && set PY=python
if not "%PY%"=="" goto :gotpy
where python3 >nul 2>&1 && set PY=python3
if not "%PY%"=="" goto :gotpy

echo   [错误] 没有找到 Python。
echo.
echo   请先安装 Python 3.8 或更高版本：
echo     https://www.python.org/downloads/
echo   安装时请务必勾选 "Add Python to PATH"
echo.
pause
exit /b 1

:gotpy
for /f "tokens=*" %%v in ('%PY% --version 2^>^&1') do set PYVER=%%v
echo   Python : %PYVER%
echo   目录   : %~dp0
echo.
echo   正在启动服务，浏览器会自动打开...
echo   关闭本窗口即可停止服务（或按 Ctrl+C）
echo.

%PY% "%~dp0server.py"
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" goto :ok
echo   [错误] 服务异常退出，代码 %RC%
echo.
echo   常见原因：
echo     1. 端口 8777~8796 全被占用（正常会自动往后找空闲端口）
echo     2. 资料目录 C:\StudyAI 被移动或删除
echo     3. 防火墙拦截了本机回环端口
echo.
:ok
echo   服务已停止。
pause
