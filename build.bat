@echo off
REM ============================================
REM Elívea — Build Script
REM ============================================
REM Executa: build.bat
REM Output: dist/EliveaAI/
REM ============================================

echo.
echo ========================================
echo   Elívea - Build Script v1.0
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

REM Verifica PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Instalando PyInstaller...
    pip install pyinstaller --quiet
)

REM Limpa builds anteriores
echo [1/4] Limpando builds anteriores...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Build
echo [2/4] Compilando com PyInstaller...
python -m PyInstaller elvea.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo [ERRO] Build falhou.
    pause
    exit /b 1
)

REM Cria instalador (se Inno Setup estiver disponível)
echo [3/4] Verificando Inno Setup...
where iscc >nul 2>&1
if %errorlevel% equ 0 (
    echo [4/4] Criando instalador...
    iscc installer.iss
    if %errorlevel% equ 0 (
        echo.
        echo ========================================
        echo   Build CONCLUIDO com sucesso!
        echo   EXE: dist\EliveaAI\EliveaAI.exe
        echo   Instalador: dist\EliveaAI-Setup.exe
        echo ========================================
    ) else (
        echo [AVISO] Instalador falhou, mas EXE foi criado.
        echo.
        echo ========================================
        echo   Build CONCLUIDO com sucesso!
        echo   EXE: dist\EliveaAI\EliveaAI.exe
        echo ========================================
    )
) else (
    echo [INFO] Inno Setup nao encontrado. Pulando instalador.
    echo.
    echo ========================================
    echo   Build CONCLUIDO com sucesso!
    echo   EXE: dist\EliveaAI\EliveaAI.exe
    echo ========================================
)

echo.
pause
