@echo off
chcp 65001 >nul
title Great Sage AI - Raphael Class v3
color 0B
cls

rem Portable Python detection: bundled folder, then per-user install, then PATH
set "PY="
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-3.11-*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined PY set "PY=python"

echo  +------------------------------------------------------+
echo    GREAT SAGE AI - RAPHAEL CLASS v3
echo    Pipeline de voz unificado + TTS neural streaming
echo  +------------------------------------------------------+
echo.

cd /d "%~dp0"
rem tenta pythonw para sem console
echo Iniciando sem console...
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    if exist "%~dp0python\pythonw.exe" (
        start "" "%~dp0python\pythonw.exe" great_sage_app.py
    ) else (
        start "" pythonw great_sage_app.py
    )
    exit /b 0
)
"%PY%" great_sage_app.py
pause
