# -*- coding: utf-8 -*-
"""
Great Sage AI — Build Script (PyInstaller)
Gera executavel standalone.

Execute: py -3 build.py
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent  # GreatSageAI_Clone/
PARENT = PROJECT.parent
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
ICON = PROJECT / "great_sage.ico"

# Subpasta do app dentro do pacote
APP_FILES = [
    "modules", "ui", "core", "memory", "plugins",
    "config", "providers", "security", "audio", "features",
    "tests",
]

APP_PY_FILES = [
    "main.py", "great_sage_app.py", "great_sage_console.py",
    "assistant.py", "app_tray.py", "gui_launcher.py",
]

APP_DATA = [
    "great_sage.ico", "great_sage_icon.png",
    ".env.example",
]

def clean():
    print("[1/3] Limpando builds anteriores...")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
    for f in PROJECT.glob("*.spec"):
        f.unlink()

def build():
    print("[2/3] Buildando executavel...")
    print("  Isso pode demorar alguns minutos...")

    # Collect hidden imports from all modules
    hidden = []
    for pkg in ["PySide6", "groq", "requests", "numpy",
                "sounddevice", "pydub", "scipy", "edge_tts",
                "google.genai", "dotenv", "imageio_ffmpeg",
                "ddgs", "pydantic", "speech_recognition",
                "psutil", "pyautogui", "keyboard", "json",
                "threading", "subprocess", "pathlib"]:
        hidden.extend(["--hidden-import", pkg])

    # Collect sub-packages
    collect = []
    for pkg in ["PySide6", "groq", "sounddevice",
                "pydub", "edge_tts", "google", "ddgs"]:
        collect.extend(["--collect-all", pkg])

    # Data files (add modules, ui, core etc as data)
    data = []
    for name in APP_FILES + APP_DATA:
        src = PROJECT / name
        if src.is_dir():
            data.extend(["--add-data", f"{src};GreatSageAI_Clone\\{name}"])
        elif src.is_file():
            data.extend(["--add-data", f"{src};GreatSageAI_Clone"])

    # Also add root-level .py files as data (they're imported as GreatSageAI_Clone.xxx)
    for name in APP_PY_FILES:
        src = PROJECT / name
        if src.is_file():
            data.extend(["--add-data", f"{src};GreatSageAI_Clone"])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "GreatSageAI",
        "--clean",
        f"--distpath={DIST}",
        f"--workpath={BUILD}",
        f"--specpath={PROJECT}",
        *hidden,
        *collect,
        *data,
        str(PROJECT / "main.py"),
    ]

    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])

    print(f"  Comando: PyInstaller --onedir --windowed --name GreatSageAI ...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PARENT))

    if result.returncode != 0:
        # Show last 2000 chars of stderr
        print(f"\n[ERRO] Build falhou. Ultimas 2000 linhas:")
        print(result.stderr[-2000:] if result.stderr else "(sem stderr)")
        return False

    print("  [OK] Executavel gerado!")
    return True

def package():
    print("[3/3] Empacotando distribuicao...")

    dist_app = DIST / "GreatSageAI"
    portable = DIST / "GreatSageAI_Portatil"
    if portable.exists():
        shutil.rmtree(portable)

    # Copy build output
    if dist_app.exists():
        shutil.copytree(dist_app, portable)

    # Create launcher
    (portable / "Iniciar.bat").write_text(
        '@echo off\n'
        'chcp 65001 >nul 2>&1\n'
        'title Great Sage AI\n'
        'cd /d "%~dp0GreatSageAI"\n'
        'start "" GreatSageAI.exe\n',
        encoding="utf-8"
    )

    # README
    (portable / "LEIA-ME.txt").write_text(
        "========================================\n"
        "  GREAT SAGE AI — v1.0\n"
        "  Assistente Pessoal com IA\n"
        "========================================\n\n"
        "COMO USAR:\n"
        "1. Clique duas vezes em 'Iniciar.bat'\n"
        "2. Pronto! O Great Sage AI vai abrir.\n\n"
        "CONFIGURACAO (opcional):\n"
        "- Edite o arquivo '.env' na pasta GreatSageAI\n"
        "- Adicione suas chaves de API:\n"
        "    GROQ_API_KEY=sua_chave\n"
        "    OPENROUTER_API_KEY=sua_chave\n"
        "- Sem chaves, o app funciona com funcs offline\n\n"
        "REQUISITOS:\n"
        "- Windows 10/11 (64-bit)\n"
        "- 4GB RAM minimo\n"
        "- 1GB de espaco em disco\n\n"
        "SUPORTE:\n"
        "- GitHub: https://github.com/anomalyco/opencode/issues\n",
        encoding="utf-8"
    )

    # .env template
    (portable / "GreatSageAI" / ".env").write_text(
        "# Great Sage AI — Configuracao\n"
        "# Adicione suas chaves de API abaixo\n"
        "# Deixe vazio para usar funcs offline\n\n"
        "# GROQ_API_KEY=\n"
        "# OPENROUTER_API_KEY=\n"
        "# GEMINI_API_KEY=\n"
        "# DEEPSEEK_API_KEY=\n",
        encoding="utf-8"
    )

    # Create ZIP
    import zipfile
    zip_path = DIST / "GreatSageAI_Portatil.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(portable):
            for file in files:
                fp = Path(root) / file
                arcname = fp.relative_to(portable.parent)
                zf.write(fp, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] ZIP: {zip_path} ({size_mb:.1f} MB)")
    return True

def main():
    print("=" * 60)
    print("  GREAT SAGE AI — BUILD SYSTEM")
    print("=" * 60)
    print()

    clean()
    if not build():
        print("\n[ERRO] Build falhou!")
        sys.exit(1)
    package()

    print()
    print("=" * 60)
    print("  BUILD CONCLUIDO COM SUCESSO!")
    print("=" * 60)
    print()
    print(f"  Executavel:  {DIST / 'GreatSageAI' / 'GreatSageAI.exe'}")
    print(f"  Portatil:    {DIST / 'GreatSageAI_Portatil'}")
    print(f"  ZIP:         {DIST / 'GreatSageAI_Portatil.zip'}")
    print()
    print("  PARA DISTRIBUIR:")
    print("  Opcao 1: Cole a pasta GreatSageAI_Portatil.zip")
    print("  Opcao 2: Clique duas vezes em GreatSageAI.exe")
    print()

if __name__ == "__main__":
    main()
