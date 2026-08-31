#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Standalone Installer
=====================================
Executável único que:
  1. Verifica se Python está instalado
  2. Baixa a IA do GitHub
  3. Instala todas as dependências
  4. Abre o Setup Wizard para configurar API keys e voz
  5. Inicia a IA

Para distribuir: envie este arquivo .py ou compile com PyInstaller em .exe
"""

from __future__ import annotations

import os
import subprocess
import sys
import shutil
import tempfile
import zipfile
import json
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── Config ───────────────────────────────────────────────────────────────────
GITHUB_REPO = "https://github.com/bryanbasquete06-wq/EliveaAI_Clone"
GITHUB_API = "https://api.github.com/repos/bryanbasquete06-wq/EliveaAI_Clone/releases/latest"
INSTALL_DIR = Path.home() / "Elívea"
PYTHON_MIN = (3, 10)

# Cores ANSI
C = {
    "gold": "\033[93m",
    "green": "\033[92m",
    "red": "\033[91m",
    "blue": "\033[94m",
    "dim": "\033[90m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}

def c(color, text):
    return f"{C[color]}{text}{C['reset']}"

def logo():
    print(c("gold", r"""
  _____ _____  ______       _______     _____         _____  ______ ______
 / ____|  __ \|  ____|   /\|__   __|   / ____|  /\   / ____|  ____|  ____|
| |  __| |__) | |__     /  \  | |     | (___   /  \ | |  __| |__  | |__  
| | |_ |  _  /|  __|   / /\ \ | |      \___ \ / /\ \| | |_ |  __| |  __| 
| |__| | | \ \| |____ / ____ \| |      ____) / ____ \ |__| | |____| |____ 
 \_____|_|  \_\______/_/    \_\_|     |____//_/    \_\_____|______|______|
"""))
    print(c("dim", "  Instalador Autônomo — Baixa e configura a IA automaticamente\n"))


def check_python():
    """Verifica se Python está instalado e na versão correta."""
    ver = sys.version_info[:2]
    if ver >= PYTHON_MIN:
        print(c("green", f"  ✓ Python {'.'.join(map(str, ver))} detectado"))
        return True
    else:
        print(c("red", f"  ✗ Python {'.'.join(map(str, ver))} encontrado (requer {PYTHON_MIN[0]}.{PYTHON_MIN[1]}+)"))
        return False


def install_python():
    """Tenta instalar Python automaticamente no Windows."""
    print(c("gold", "\n[1/5] Instalando Python..."))
    
    # Tenta via winget
    try:
        result = subprocess.run(
            ["winget", "install", "Python.Python.3.11", "--silent", "--accept-package-agreements"],
            capture_output=True, text=True, timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            print(c("green", "  ✓ Python instalado via winget"))
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Tenta via chocolatey
    try:
        result = subprocess.run(
            ["choco", "install", "python311", "-y"],
            capture_output=True, text=True, timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            print(c("green", "  ✓ Python instalado via Chocolatey"))
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback: abre download
    print(c("red", "  ✗ Não foi possível instalar automaticamente"))
    print(c("dim", "  Baixe manualmente: https://www.python.org/downloads/"))
    print(c("dim", "  IMPORTANTE: Marque 'Add Python to PATH' durante a instalação"))
    
    try:
        import webbrowser
        webbrowser.open("https://www.python.org/downloads/")
    except Exception:
        pass
    
    input(c("gold", "\n  Pressione ENTER após instalar o Python..."))
    return check_python()


def download_github():
    """Baixa a IA do GitHub."""
    print(c("gold", "\n[2/5] Baixando a IA do GitHub..."))
    
    # Tenta pegar a release mais recente
    zip_url = None
    try:
        req = Request(GITHUB_API, headers={"User-Agent": "EliveaInstaller"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    zip_url = asset["browser_download_url"]
                    break
    except Exception:
        pass
    
    # Fallback: baixa o zip do repo principal
    if not zip_url:
        zip_url = f"{GITHUB_REPO}/archive/refs/heads/main.zip"
    
    print(c("dim", f"  URL: {zip_url}"))
    
    try:
        # Download
        tmp_dir = Path(tempfile.mkdtemp(prefix="elvea_"))
        zip_path = tmp_dir / "elvea.zip"
        
        print(c("dim", "  Baixando..."))
        req = Request(zip_url, headers={"User-Agent": "EliveaInstaller"})
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        print(f"\r  Progresso: {pct}% ({downloaded // 1024}KB)", end="", flush=True)
            print()
        
        # Extract
        print(c("dim", "  Extraindo..."))
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the root folder in the zip
            names = zf.namelist()
            root_folder = names[0].split("/")[0] if names else ""
            
            # Extract to temp
            extract_dir = tmp_dir / "extracted"
            zf.extractall(extract_dir)
            
            # Move contents to INSTALL_DIR
            source = extract_dir / root_folder if root_folder else extract_dir
            if INSTALL_DIR.exists():
                print(c("dim", "  Atualizando instalação existente..."))
                # Backup .env
                env_backup = None
                if (INSTALL_DIR / ".env").exists():
                    env_backup = INSTALL_DIR / ".env".read_bytes()
                shutil.rmtree(INSTALL_DIR)
            
            shutil.copytree(str(source), str(INSTALL_DIR))
            
            # Restore .env
            if env_backup:
                (INSTALL_DIR / ".env").write_bytes(env_backup)
        
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
        print(c("green", f"  ✓ IA baixada para: {INSTALL_DIR}"))
        return True
        
    except URLError as e:
        print(c("red", f"  ✗ Erro ao baixar: {e}"))
        print(c("dim", "  Verifique sua conexão com a internet"))
        return False
    except Exception as e:
        print(c("red", f"  ✗ Erro: {e}"))
        return False


def install_deps():
    """Instala todas as dependências."""
    print(c("gold", "\n[3/5] Instalando dependências..."))
    
    python_exe = sys.executable
    
    # Create requirements.txt if not exists
    req_path = INSTALL_DIR / "requirements.txt"
    if not req_path.exists():
        req_path.write_text("""PySide6>=6.5.0
requests>=2.31.0
numpy>=1.24.0
sounddevice>=0.4.6
pydub>=0.25.1
scipy>=1.11.0
edge-tts>=6.1.0
groq>=0.4.0
google-genai>=0.3.0
python-dotenv>=1.0.0
imageio-ffmpeg>=0.4.9
duckduckgo-search>=4.0
psutil>=5.9.0
pyautogui>=0.9.54
keyboard>=0.13.5
pydantic>=2.0.0
SpeechRecognition>=3.10.0
""", encoding="utf-8")
    
    # Install
    cmd = [python_exe, "-m", "pip", "install", "-r", str(req_path),
           "--quiet", "--disable-pip-version-check"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0:
            print(c("green", "  ✓ Dependências instaladas com sucesso"))
            return True
        else:
            # Retry with --break-system-packages
            if "externally-managed" in (result.stderr or ""):
                cmd.append("--break-system-packages")
                result2 = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result2.returncode == 0:
                    print(c("green", "  ✓ Dependências instaladas"))
                    return True
            print(c("red", f"  ✗ Erro no pip (código {result.returncode})"))
            print(c("dim", f"  {result.stderr[-300:] if result.stderr else 'sem detalhes'}"))
            return False
    except subprocess.TimeoutExpired:
        print(c("red", "  ✗ Timeout na instalação (10 min)"))
        return False
    except Exception as e:
        print(c("red", f"  ✗ Erro: {e}"))
        return False


def run_wizard():
    """Abre o Setup Wizard para configurar API keys e voz."""
    print(c("gold", "\n[4/5] Abrindo assistente de configuração..."))
    
    wizard = INSTALL_DIR / "ui" / "installer_gui.py"
    if not wizard.exists():
        wizard = INSTALL_DIR / "installer.py"
    
    if wizard.exists():
        subprocess.Popen(
            [sys.executable, str(wizard)],
            cwd=str(INSTALL_DIR),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) |
                          getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
        print(c("green", "  ✓ Assistente de configuração aberto"))
        return True
    else:
        print(c("red", "  ✗ Assistente não encontrado"))
        return False


def create_shortcuts():
    """Cria atalhos na Área de Trabalho."""
    print(c("gold", "\n[5/5] Criando atalhos..."))
    
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "OneDrive" / "Desktop"
    
    if not desktop.exists():
        print(c("dim", "  ⚠ Área de Trabalho não encontrada"))
        return False
    
    python_exe = sys.executable
    uv_python = Path.home() / "AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe"
    if uv_python.exists():
        python_exe = str(uv_python)
    
    # AI shortcut
    ai_bat = desktop / "Elívea AI.bat"
    ai_bat.write_text(
        f'@echo off\r\ntitle Elívea AI\r\ncd /d "{INSTALL_DIR}"\r\n'
        f'"{python_exe}" main.py\r\nif errorlevel 1 pause\r\n',
        encoding="ascii", errors="replace"
    )
    print(c("green", f"  ✓ {ai_bat.name}"))
    
    # Installer shortcut (for re-running setup)
    inst_bat = desktop / "Configurar Elivea.bat"
    inst_bat.write_text(
        f'@echo off\r\ntitle Configurar Elivea\r\ncd /d "{INSTALL_DIR}"\r\n'
        f'"{python_exe}" installer.py\r\nif errorlevel 1 pause\r\n',
        encoding="ascii", errors="replace"
    )
    print(c("green", f"  ✓ {inst_bat.name}"))
    
    return True


def main():
    logo()
    
    # Step 0: Check Python
    print(c("bold", "[VERIFICANDO SISTEMA]"))
    if not check_python():
        if not install_python():
            print(c("red", "\n✗ Python é necessário. Instale manualmente e tente novamente."))
            input("\nPressione ENTER para sair...")
            sys.exit(1)
    
    # Step 1: Download AI
    print(c("bold", "\n[BAIXANDO A IA]"))
    if not download_github():
        print(c("red", "\n✗ Não foi possível baixar a IA."))
        print(c("dim", "Verifique sua internet e tente novamente."))
        input("\nPressione ENTER para sair...")
        sys.exit(1)
    
    # Step 2: Install dependencies
    print(c("bold", "\n[INSTALANDO DEPENDÊNCIAS]"))
    if not install_deps():
        print(c("red", "\n⚠ Algumas dependências podem ter falhado."))
        print(c("dim", "O assistente tentará novamente ao iniciar."))
    
    # Step 3: Create shortcuts
    print(c("bold", "\n[CRIANDO ATALHOS]"))
    create_shortcuts()
    
    # Step 4: Run wizard
    print(c("bold", "\n[CONFIGURAÇÃO]"))
    run_wizard()
    
    # Done
    print(c("gold", "\n" + "=" * 60))
    print(c("gold", "  ✓ INSTALAÇÃO CONCLUÍDA!"))
    print(c("gold", "=" * 60))
    print()
    print(c("bold", "  O Elívea foi instalado em:"))
    print(c("dim", f"  {INSTALL_DIR}"))
    print()
    print(c("bold", "  Próximos passos:"))
    print(c("dim", "  1. Configure suas API keys no assistente que abriu"))
    print(c("dim", "  2. Escolha a voz do Elívea"))
    print(c("dim", "  3. Clique em 'Instalar e Iniciar'"))
    print()
    print(c("bold", "  Para iniciar depois:"))
    print(c("dim", "  • Clique duas vezes em 'Elívea AI' na Área de Trabalho"))
    print(c("dim", "  • Ou execute: python main.py"))
    print()
    
    input(c("gold", "Pressione ENTER para fechar..."))


if __name__ == "__main__":
    main()
