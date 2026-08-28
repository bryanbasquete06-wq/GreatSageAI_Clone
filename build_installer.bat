@echo off
REM ============================================
REM Great Sage AI — Build Standalone Installer
REM ============================================
REM Compila o instalador em um .exe único que
REM qualquer pessoa pode executar sem ter Python.
REM ============================================

echo.
echo ========================================
echo   Great Sage AI - Build Installer v2.0
echo ========================================
echo.

REM Verifica Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3.11+ e adicione ao PATH.
    pause
    exit /b 1
)

REM Verifica/instala PyInstaller
echo [1/4] Verificando PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo      Instalando PyInstaller...
    pip install pyinstaller --quiet --disable-pip-version-check
    if %errorlevel% neq 0 (
        echo [ERRO] Nao foi possivel instalar PyInstaller.
        pause
        exit /b 1
    )
)
echo      PyInstaller OK.

REM Limpa builds anteriores
echo [2/4] Limpando builds anteriores...
if exist build\installer rmdir /s /q build\installer
if exist dist rmdir /s /q dist

REM Compila o instalador
echo [3/4] Compilando Instalador_Great_Sage.exe...
python -m PyInstaller ^
    --onefile ^
    --name "Instalador_Great_Sage" ^
    --console ^
    --clean ^
    --noconfirm ^
    --distpath dist ^
    --workpath build\installer ^
    Instalador_Great_Sage.py

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Build falhou. Verifique os erros acima.
    pause
    exit /b 1
)

REM Verifica se o .exe foi criado
if not exist "dist\Instalador_Great_Sage.exe" (
    echo [ERRO] .exe nao foi encontrado em dist\
    pause
    exit /b 1
)

echo [4/4] Build concluido!
echo.
echo ========================================
echo   SUCESSO!
echo.
echo   O instalador esta em:
echo   dist\Instalador_Great_Sage.exe
echo.
echo   Envie este arquivo para quem quiser
echo   instalar o Grande Sabio AI.
echo ========================================
echo.

REM Abre a pasta dist
explorer dist

pause
