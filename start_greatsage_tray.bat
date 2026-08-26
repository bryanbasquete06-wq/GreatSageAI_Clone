@echo off
rem Portable Python detection: bundled folder, then per-user install, then PATH
set "PYW="
if exist "%~dp0python\pythonw.exe" set "PYW=%~dp0python\pythonw.exe"
if not defined PYW for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-3.11-*") do if exist "%%D\pythonw.exe" set "PYW=%%D\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Python\bin\pythonw.exe" set "PYW=%LOCALAPPDATA%\Python\bin\pythonw.exe"
if not defined PYW set "PYW=pythonw"
cd /d "%~dp0"
start "" "%PYW%" app_tray.py
