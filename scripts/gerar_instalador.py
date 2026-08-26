# -*- coding: utf-8 -*-
"""
Great Sage AI — Gerador de Instalador
Cria um instalador .exe completo com PyInstaller + Inno Setup.
Execute: py -3 gerar_instalador.py
"""
import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
DIST = PROJECT / "dist"
INSTALLER = PROJECT / "installer"

def step1_build_exe():
    print("[1/4] Buildando executavel...")
    result = subprocess.run(
        [sys.executable, "build.py"],
        cwd=str(PROJECT),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERRO: {result.stderr[-1000:]}")
        return False
    print("  [OK] Executavel pronto")
    return True

def step2_create_portable():
    print("[2/4] Criando versao portatil...")
    portable = DIST / "GreatSageAI_Portatil"
    if portable.exists():
        shutil.rmtree(portable)
    portable.mkdir(parents=True)

    # Copy build output
    src = DIST / "GreatSageAI"
    if src.exists():
        shutil.copytree(src, portable / "GreatSageAI")

    # Create launcher bat
    launcher = portable / "Iniciar.bat"
    launcher.write_text(
        '@echo off\n'
        'chcp 65001 >nul 2>&1\n'
        'title Great Sage AI\n'
        'cd /d "%~dp0GreatSageAI"\n'
        'start "" GreatSageAI.exe\n',
        encoding="utf-8"
    )

    # Create README
    readme = portable / "LEIA-ME.txt"
    readme.write_text(
        "========================================\n"
        "  GREAT SAGE AI — Portable\n"
        "========================================\n\n"
        "COMO USAR:\n"
        "1. Extraia todos os arquivos\n"
        "2. Clique duas vezes em 'Iniciar.bat'\n"
        "3. Pronto!\n\n"
        "CONFIGURACAO:\n"
        "- Edite o arquivo '.env' na pasta GreatSageAI\n"
        "- Adicione suas chaves de API (opcional)\n"
        "- O app funciona offline sem chaves\n\n"
        "REQUISITOS:\n"
        "- Windows 10/11 (64-bit)\n"
        "- 4GB RAM minimo\n"
        "- 500MB de espaco em disco\n\n"
        "SUPORTE:\n"
        "- GitHub: https://github.com/anomalyco/opencode/issues\n",
        encoding="utf-8"
    )

    print(f"  [OK] Portatil criado: {portable}")
    return True

def step3_create_zip():
    print("[3/4] Gerando arquivo ZIP...")
    zip_path = DIST / "GreatSageAI_Portatil.zip"
    portable = DIST / "GreatSageAI_Portatil"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(portable):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(portable.parent)
                zf.write(file_path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] ZIP criado: {zip_path} ({size_mb:.1f} MB)")
    return True

def step4_create_installer_script():
    print("[4/4] Gerando script de instalador...")
    INSTALLER.mkdir(exist_ok=True)

    iss = INSTALLER / "GreatSageAI.iss"
    project_str = str(PROJECT).replace("\\", "\\\\")

    iss.write_text(f'''
; Great Sage AI — Inno Setup Installer
; Compile com Inno Setup 6+

#define MyAppName "Great Sage AI"
#define MyAppVersion "1.0.0"
#define MyAppExeName "GreatSageAI.exe"

[Setup]
AppId={{{{GREAT-SAGE-AI-12345}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{autopf}}\\GreatSageAI
DefaultGroupName={{#MyAppName}}
OutputDir={project_str}\\installer
OutputBaseFilename=GreatSageAI_Instalador
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\\\\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Icones adicionais:"; Flags: unchecked

[Files]
Source: "{project_str}\\\\dist\\\\GreatSageAI\\\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\\\{{#MyAppName}}"; Filename: "{{app}}\\\\{{#MyAppExeName}}"
Name: "{{group}}\\\\Desinstalar {{#MyAppName}}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\\\{{#MyAppName}}"; Filename: "{{app}}\\\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\\\{{#MyAppExeName}}"; Description: "Iniciar {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
'''.strip())

    # Create bat to compile ISS
    compile_bat = INSTALLER / "Compilar.bat"
    compile_bat.write_text(
        '@echo off\n'
        'echo.\n'
        'echo  Great Sage AI — Gerando Instalador...\n'
        'echo.\n'
        'if exist "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" (\n'
        '    "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" GreatSageAI.iss\n'
        ') else if exist "C:\\Program Files\\Inno Setup 6\\ISCC.exe" (\n'
        '    "C:\\Program Files\\Inno Setup 6\\ISCC.exe" GreatSageAI.iss\n'
        ') else (\n'
        '    echo [ERRO] Inno Setup nao encontrado!\n'
        '    echo Baixe de: https://jrsoftware.org/isinfo.php\n'
        '    echo.\n'
        '    pause\n'
        '    exit /b 1\n'
        ')\n'
        'echo.\n'
        'echo [OK] Instalador gerado: GreatSageAI_Instalador.exe\n'
        'pause\n',
        encoding="utf-8"
    )

    print(f"  [OK] Script criado: {iss}")
    return True

def main():
    print("=" * 60)
    print("  GREAT SAGE AI — GERADOR DE INSTALADOR")
    print("=" * 60)
    print()

    if not step1_build_exe():
        sys.exit(1)
    if not step2_create_portable():
        sys.exit(1)
    if not step3_create_zip():
        sys.exit(1)
    step4_create_installer_script()

    print()
    print("=" * 60)
    print("  TUDO PRONTO!")
    print("=" * 60)
    print()
    print("  ARQUIVOS GERADOS:")
    print(f"  - Portable:  dist/GreatSageAI_Portatil/")
    print(f"  - ZIP:       dist/GreatSageAI_Portatil.zip")
    print(f"  - Installer: installer/GreatSageAI.iss")
    print()
    print("  OPCAO 1 — Portable (mais simples):")
    print("  Cole a pasta GreatSageAI_Portatil e distribua!")
    print()
    print("  OPCAO 2 — Instalador (.exe):")
    print("  1. Instale Inno Setup: https://jrsoftware.org/isinfo.php")
    print("  2. Execute: installer/Compilar.bat")
    print("  3. O instalador sera gerado em: installer/GreatSageAI_Instalador.exe")
    print()

if __name__ == "__main__":
    main()
