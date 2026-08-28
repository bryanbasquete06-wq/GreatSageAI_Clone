@echo off
REM ============================================
REM Grande Sabio AI — Instalador Rapido
REM ============================================
REM Execute este arquivo para instalar a IA.
REM Funciona em qualquer PC com Windows 10/11.
REM ============================================

title Grande Sabio AI — Instalador

REM Verifica Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   Python nao encontrado!
    echo.
    echo   O Grande Sabio precisa de Python 3.10+
    echo   para funcionar.
    echo.
    echo   Baixe em: https://www.python.org/downloads/
    echo   IMPORTANTE: Marque "Add Python to PATH"
    echo ========================================
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Verifica se o projeto ja existe
if not exist "main.py" (
    echo.
    echo ========================================
    echo   Arquivos do Grande Sabio nao encontrados.
    echo   Execute o Instalador_Great_Sage.exe
    echo   para baixar a IA primeiro.
    echo ========================================
    pause
    exit /b 1
)

REM Instala dependencias
echo.
echo ========================================
echo   Grande Sabio AI — Instalando...
echo ========================================
echo.

echo [1/3] Instalando dependencias...
pip install -r requirements.txt --quiet --disable-pip-version-check 2>nul
if %errorlevel% neq 0 (
    pip install -r requirements.txt --quiet --break-system-packages 2>nul
)
echo      Dependencias OK.

echo [2/3] Configurando...
if not exist "config" mkdir config
if not exist "memory" mkdir memory
if not exist "logs" mkdir logs

echo [3/3] Iniciando assistente de configuracao...
echo.

REM Abre o wizard de configuracao
python installer.py

echo.
echo ========================================
echo   Instalacao concluida!
echo.
echo   Para iniciar: python main.py
echo   Ou clique duas vezes em "Grande Sabio AI"
echo   na Area de Trabalho.
echo ========================================
pause
