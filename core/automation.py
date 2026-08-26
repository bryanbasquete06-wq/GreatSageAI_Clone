#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — Automação de Desktop
======================================
Controla o computador: teclado, mouse, apps, arquivos, screenshot.
"""

import os
import sys
import subprocess
import logging
import platform
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger("greatsage.automation")


class DesktopAutomation:
    """Automação completa do desktop."""

    def __init__(self):
        self.system = platform.system()
        self._pyautogui = None
        try:
            import pyautogui
            self._pyautogui = pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.3
        except ImportError:
            logger.warning("pyautogui não instalado")

    @property
    def available(self) -> bool:
        return self._pyautogui is not None

    # ─── Mouse ────────────────────────────────────────────────────

    def click(self, x: int = None, y: int = None):
        """Clica em uma posição (ou posição atual)."""
        if x is not None and y is not None:
            self._pyautogui.click(x, y)
        else:
            self._pyautogui.click()

    def move_mouse(self, x: int, y: int, duration: float = 0.3):
        """Move o mouse suavemente."""
        self._pyautogui.moveTo(x, y, duration=duration)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """Arrasta de um ponto para outro."""
        self._pyautogui.moveTo(x1, y1)
        self._pyautogui.drag(x2 - x1, y2 - y1, duration=duration)

    # ─── Teclado ──────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.02):
        """Digita texto."""
        self._pyautogui.typewrite(text, interval=interval)

    def press_key(self, *keys):
        """Pressiona tecla(s). Ex: press_key('ctrl', 'c')"""
        self._pyautogui.hotkey(*keys)

    def press_once(self, key: str):
        """Pressiona uma tecla uma vez."""
        self._pyautogui.press(key)

    # ─── Apps ─────────────────────────────────────────────────────

    def open_app(self, app_name: str) -> bool:
        """Abre um aplicativo."""
        try:
            if self.system == "Windows":
                os.startfile(app_name)
            elif self.system == "Darwin":
                subprocess.Popen(["open", app_name])
            else:
                subprocess.Popen([app_name])
            return True
        except Exception as e:
            logger.error(f"Erro ao abrir {app_name}: {e}")
            return False

    def open_url(self, url: str):
        """Abre URL no navegador padrão."""
        import webbrowser
        webbrowser.open(url)

    def open_folder(self, path: str):
        """Abre uma pasta no explorador."""
        path = os.path.expanduser(path)
        if self.system == "Windows":
            os.startfile(path)
        elif self.system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def list_running_processes(self) -> List[str]:
        """Lista processos em execução."""
        try:
            result = subprocess.run(
                ["tasklist" if self.system == "Windows" else "ps", "aux"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.splitlines()[:30]
        except:
            return []

    def kill_process(self, name: str) -> bool:
        """Mata um processo pelo nome."""
        try:
            if self.system == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
            else:
                subprocess.run(["pkill", name], capture_output=True)
            return True
        except:
            return False

    # ─── Sistema ──────────────────────────────────────────────────

    def get_system_info(self) -> Dict:
        """Retorna informações do sistema."""
        import psutil
        info = {
            "sistema": self.system,
            "versao": platform.version(),
            "processador": platform.processor(),
            "maquina": platform.machine(),
        }
        try:
            info["cpu_percent"] = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            info["ram_total"] = f"{mem.total / (1024**3):.1f} GB"
            info["ram_uso"] = f"{mem.percent}%"
            info["disco"] = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    info["disco"].append({
                        "device": part.device,
                        "total": f"{usage.total / (1024**3):.1f} GB",
                        "free": f"{usage.free / (1024**3):.1f} GB",
                        "percent": f"{usage.percent}%",
                    })
                except:
                    pass
        except:
            pass
        return info

    def get_clipboard(self) -> str:
        """Lê o conteúdo da área de transferência."""
        try:
            if self.system == "Windows":
                result = subprocess.run(
                    ["powershell", "-command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=5,
                )
                return result.stdout.strip()
        except:
            pass
        return ""

    def set_clipboard(self, text: str):
        """Define o conteúdo da área de transferência."""
        try:
            if self.system == "Windows":
                subprocess.run(
                    ["powershell", "-command", f"Set-Clipboard -Value '{text}'"],
                    capture_output=True, timeout=5,
                )
        except:
            pass

    def screenshot(self, save_path: str = None) -> Optional[str]:
        """Tira screenshot."""
        if not self._pyautogui:
            return None
        if save_path is None:
            save_path = f"logs/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        img = self._pyautogui.screenshot()
        img.save(save_path)
        return save_path

    # ─── Ações Avançadas ──────────────────────────────────────────

    def search_and_open(self, query: str) -> str:
        """Pesquisa e abre algo no Windows."""
        if self.system == "Windows":
            # Abre o menu Iniciar e digita
            self.press_once("win")
            import time
            time.sleep(0.5)
            self._pyautogui.typewrite(query, interval=0.05)
            import time
            time.sleep(1)
            self.press_once("enter")
            return f"Pesquisando por: {query}"
        return "Pesquisa não disponível neste sistema"

    def lock_screen(self):
        """Bloqueia a tela."""
        if self.system == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])

    def empty_trash(self):
        """Esvazia a lixeira."""
        try:
            if self.system == "Windows":
                from comtypes.client import CreateObject
                shell = CreateObject("Shell.Application")
                trash = shell.NameSpace(0x0a)  # lixeira
                trash.InvokeVerb("empty")
                return True
        except:
            pass
        return False

    def get_ip(self) -> str:
        """Obtém o IP público."""
        try:
            import requests
            resp = requests.get("https://api.ipify.org", timeout=5)
            return resp.text
        except:
            return "Não foi possível obter o IP"
