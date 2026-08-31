# -*- coding: utf-8 -*-
"""
Elívea — App Integration
================================
Integracao com aplicativos do sistema.
"""
from __future__ import annotations

import os
import subprocess
import json
from pathlib import Path
from typing import Optional


class AppIntegration:
    """Integracao com aplicativos e ferramentas."""

    _SHORTCUTS_FILE = Path(__file__).resolve().parent.parent / "config" / "app_shortcuts.json"

    _KNOWN_APPS = {
        "vscode": {"name": "Visual Studio Code", "cmd": "code", "args": []},
        "code": {"name": "Visual Studio Code", "cmd": "code", "args": []},
        "chrome": {"name": "Google Chrome", "cmd": "start chrome", "args": []},
        "firefox": {"name": "Mozilla Firefox", "cmd": "start firefox", "args": []},
        "edge": {"name": "Microsoft Edge", "cmd": "start msedge", "args": []},
        "spotify": {"name": "Spotify", "cmd": "start spotify", "args": []},
        "discord": {"name": "Discord", "cmd": "start discord", "args": []},
        "notepad": {"name": "Notepad", "cmd": "notepad", "args": []},
        "explorer": {"name": "Explorador", "cmd": "explorer", "args": []},
        "terminal": {"name": "Terminal", "cmd": "start wt", "args": []},
        "powershell": {"name": "PowerShell", "cmd": "start powershell", "args": []},
        "cmd": {"name": "Prompt de Comando", "cmd": "start cmd", "args": []},
        "calculator": {"name": "Calculadora", "cmd": "start calc", "args": []},
        "paint": {"name": "Paint", "cmd": "start mspaint", "args": []},
        "word": {"name": "Microsoft Word", "cmd": "start winword", "args": []},
        "excel": {"name": "Microsoft Excel", "cmd": "start excel", "args": []},
        "powerpoint": {"name": "PowerPoint", "cmd": "start powerpnt", "args": []},
        "zoom": {"name": "Zoom", "cmd": "start zoom", "args": []},
        "teams": {"name": "Microsoft Teams", "cmd": "start teams", "args": []},
        "slack": {"name": "Slack", "cmd": "start slack", "args": []},
        "obs": {"name": "OBS Studio", "cmd": "start obs64", "args": []},
        "steam": {"name": "Steam", "cmd": "start steam", "args": []},
        "blender": {"name": "Blender", "cmd": "start blender", "args": []},
        "git": {"name": "Git Bash", "cmd": "start git-bash", "args": []},
    }

    @classmethod
    def _ensure_shortcuts(cls):
        cls._SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not cls._SHORTCUTS_FILE.exists():
            cls._SHORTCUTS_FILE.write_text("{}", encoding="utf-8")

    @classmethod
    def open_app(cls, app_name: str, url: str = None) -> str:
        """Abre um aplicativo pelo nome."""
        app_name_lower = app_name.lower().strip()

        app = cls._KNOWN_APPS.get(app_name_lower)
        if app:
            cmd = app["cmd"]
            if url:
                cmd += f" {url}"
            try:
                os.system(cmd)
                return f"Aviso. Abrindo {app['name']}."
            except Exception as e:
                return f"Erro ao abrir {app['name']}: {e}"

        if os.path.exists(app_name):
            try:
                os.startfile(app_name)
                return f"Aviso. Abrindo {app_name}."
            except Exception:
                pass

        try:
            os.system(f"start {app_name}")
            return f"Aviso. Tentando abrir {app_name}."
        except Exception:
            return f"Nao foi possivel encontrar o aplicativo: {app_name}."

    @classmethod
    def open_url(cls, url: str) -> str:
        """Abre uma URL no navegador padrao."""
        try:
            os.startfile(url)
            return f"Aviso. Abrindo {url}."
        except Exception:
            return f"Erro ao abrir URL: {url}."

    @classmethod
    def open_folder(cls, path: str) -> str:
        """Abre uma pasta no explorador."""
        if not os.path.exists(path):
            return f"Pasta nao encontrada: {path}"
        try:
            os.startfile(path)
            return f"Aviso. Abrindo pasta: {path}."
        except Exception:
            return f"Erro ao abrir pasta: {path}."

    @classmethod
    def open_file(cls, path: str) -> str:
        """Abre um arquivo com o programa padrao."""
        if not os.path.exists(path):
            return f"Arquivo nao encontrado: {path}"
        try:
            os.startfile(path)
            return f"Aviso. Abrindo {os.path.basename(path)}."
        except Exception:
            return f"Erro ao abrir arquivo: {path}."

    @classmethod
    def close_app(cls, app_name: str) -> str:
        """Fecha um aplicativo pelo nome."""
        try:
            os.system(f"taskkill /IM {app_name}.exe /F")
            return f"Aviso. {app_name} fechado."
        except Exception:
            return f"Erro ao fechar {app_name}."

    @classmethod
    def add_shortcut(cls, name: str, command: str, description: str = ""):
        """Adiciona um atalho customizado."""
        cls._ensure_shortcuts()
        try:
            shortcuts = json.loads(cls._SHORTCUTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            shortcuts = {}
        shortcuts[name.lower()] = {"command": command, "description": description}
        cls._SHORTCUTS_FILE.write_text(json.dumps(shortcuts, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def get_shortcuts(cls) -> dict:
        """Retorna todos os atalhos."""
        cls._ensure_shortcuts()
        try:
            return json.loads(cls._SHORTCUTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def get_status(cls) -> str:
        apps = list(cls._KNOWN_APPS.keys())
        shortcuts = cls.get_shortcuts()
        lines = [f"Apps integrados ({len(apps)}): {', '.join(apps[:10])}..."]
        if shortcuts:
            lines.append(f"Atalhos customizados ({len(shortcuts)}): {', '.join(shortcuts.keys())}")
        return "\n".join(lines)
