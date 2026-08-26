@echo off
chcp 65001 >nul 2>&1
title Great Sage AI — Launcher
color 0A
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║        大賢者 GREAT SAGE AI — LAUNCHER          ║
echo  ╚══════════════════════════════════════════════════╝
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3.10+ em https://www.python.org/downloads/
    echo Marque "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [OK] Python:
python --version
echo.

echo Verificando / baixando dependencias...
python -m pip install -r requirements.txt --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [AVISO] requirements.txt falhou. Tentando pacotes essenciais...
    python -m pip install python-dotenv requests numpy groq sounddevice PySide6 psutil ddgs pydub scipy edge-tts pydantic pyautogui keyboard SpeechRecognition imageio-ffmpeg
)
echo.

if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado. O app sobe em modo offline.
    echo Crie .env com GROQ_API_KEY=... para a IA online.
    echo.
)

echo Iniciando Great Sage AI (terminal ficará invisível)...
:: Usa pythonw para não mostrar console preto feio — cai para python se pythonw não existir
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw main.py
    exit /b 0
) else (
    :: fallback: python normal mas main.py já esconde o console sozinho
    python main.py
    if %errorlevel% neq 0 (
        echo.
        echo [ERRO] O app encerrou com erro. Veja config\crash.log se existir.
        pause
    )
)
