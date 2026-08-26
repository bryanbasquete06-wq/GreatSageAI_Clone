"""
Great Sage AI - Advanced Hardware & OS Automation Controller
Enterprise-grade Windows hardware management, power, display, audio, process & desktop automation.
"""

import os
import sys
import time
import socket
import urllib.request
import subprocess
import shutil
import ctypes
import psutil
from pathlib import Path
import pyautogui


class HardwareController:
    @staticmethod
    def set_system_volume(level_pct: int) -> str:
        """Sets Windows Master Volume (0 to 100%)."""
        try:
            level = max(0, min(100, level_pct))
            # Execute PowerShell audio control
            ps_cmd = f"(New-Object -ComObject WScript.Shell).SendKeys([char]174 * 50); "
            ps_cmd += f"1..{int(level/2)} | % {{ (New-Object -ComObject WScript.Shell).SendKeys([char]175) }}"
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=3,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return f"[Ação] Volume ajustado para {level}%."
        except Exception as e:
            return f"[Hardware Error] Não foi possível ajustar o volume: {e}"

    @staticmethod
    def get_ip_info() -> str:
        """Returns local and public IP addresses."""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "127.0.0.1"

        public_ip = "Desconhecido"
        try:
            req = urllib.request.urlopen("https://api.ipify.org", timeout=2)
            public_ip = req.read().decode('utf-8').strip()
        except Exception:
            pass

        return (
            f"[Telemetria de Rede]\n"
            f"  - Hostname: {hostname}\n"
            f"  - IP Local (LAN): {local_ip}\n"
            f"  - IP Público (WAN): {public_ip}"
        )

    @staticmethod
    def get_disk_info() -> str:
        """Lists usage statistics for all active drive partitions."""
        lines = ["[Relatório de Armazenamento]"]
        try:
            partitions = psutil.disk_partitions()
            for part in partitions:
                if 'cdrom' in part.opts or not part.fstype:
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    free_gb = usage.free // (1024**3)
                    total_gb = usage.total // (1024**3)
                    lines.append(f"  - Unidade {part.device} ({part.mountpoint}): {usage.percent}% usado ({free_gb} GB livres de {total_gb} GB)")
                except Exception:
                    pass
            return "\n".join(lines)
        except Exception as e:
            return f"[Erro] Falha ao verificar discos: {e}"

    @staticmethod
    def clean_recycle_bin() -> str:
        """Cleans Windows Recycle Bin."""
        try:
            # SHEmptyRecycleBinW flags: SHERB_NOCONFIRMATION = 0x00000001, SHERB_NOPROGRESSUI = 0x00000002, SHERB_NOSOUND = 0x00000004
            flags = 1 | 2 | 4
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return "[Ação] Lixeira do Windows esvaziada com sucesso!"
        except Exception as e:
            return f"[Erro] Não foi possível esvaziar a lixeira: {e}"

    @staticmethod
    def kill_process(target: str) -> str:
        """Terminates a running process by name or PID."""
        target_clean = target.strip().lower()
        terminated = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                pname = proc.info['name'].lower() if proc.info['name'] else ""
                pid = str(proc.info['pid'])
                if target_clean in pname or target_clean == pid:
                    proc.kill()
                    terminated.append(f"{proc.info['name']} (PID {proc.info['pid']})")

            if terminated:
                return f"[Ação] Processos encerrados: {', '.join(terminated)}"
            else:
                return f"[Aviso] Nenhum processo correspondente a '{target}' foi encontrado."
        except Exception as e:
            return f"[Erro] Falha ao encerrar processo: {e}"

    @staticmethod
    def get_full_telemetry() -> dict:
        """Collects complete hardware & network telemetry."""
        cpu_cores = psutil.cpu_percent(interval=0.1, percpu=True)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()

        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent}% ({'Carregando' if battery.power_plugged else 'Bateria'})" if battery else "Desktop (Sem Bateria)"

        return {
            "CPU Total": f"{psutil.cpu_percent()}% ({len(cpu_cores)} núcleos)",
            "RAM": f"{ram.percent}% ({ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB)",
            "Disco C:": f"{disk.percent}% livre ({disk.free // (1024**3)} GB livre de {disk.total // (1024**3)} GB)",
            "Energia": bat_str,
            "Rede Enviada": f"{net.bytes_sent // (1024**2)} MB",
            "Rede Recebida": f"{net.bytes_recv // (1024**2)} MB",
            "Processos Ativos": len(psutil.pids())
        }

    @staticmethod
    def boost_system_memory() -> str:
        """Frees up RAM by clearing working set and reporting usage."""
        ram_before = psutil.virtual_memory().percent
        try:
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
        ram_after = psutil.virtual_memory().percent
        return f"[Ação] Memória otimizada. RAM antes: {ram_before:.1f}% -> Agora: {ram_after:.1f}%."

    @staticmethod
    def organize_desktop_files() -> str:
        """Organizes files on Desktop into categorized subfolders."""
        desktop_path = Path(os.path.expanduser('~/Desktop'))
        if not desktop_path.exists():
            return "[Erro] Área de Trabalho não encontrada."

        categories = {
            "Imagens": [".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp"],
            "Documentos": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
            "Executaveis": [".exe", ".msi", ".bat", ".vbs"],
            "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz"]
        }

        moved_count = 0
        for item in desktop_path.iterdir():
            if item.is_file() and not item.name.startswith("Great Sage"):
                ext = item.suffix.lower()
                for cat, ext_list in categories.items():
                    if ext in ext_list:
                        target_dir = desktop_path / cat
                        target_dir.mkdir(exist_ok=True)
                        try:
                            shutil.move(str(item), str(target_dir / item.name))
                            moved_count += 1
                        except Exception:
                            pass
                        break

        return f"[Ação] Área de Trabalho organizada. {moved_count} arquivos movidos para pastas categorizadas."

    @staticmethod
    def clean_temp_files() -> str:
        """Cleans temporary cache files from %TEMP% and C:\\Windows\\Temp."""
        cleaned_files = 0
        freed_bytes = 0

        temp_dirs = [
            Path(os.environ.get('TEMP', 'C:\\Users\\Public\\AppData\\Local\\Temp')),
            Path('C:\\Windows\\Temp')
        ]

        for temp_dir in temp_dirs:
            if not temp_dir.exists():
                continue
            for item in temp_dir.iterdir():
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        item.unlink()
                        cleaned_files += 1
                        freed_bytes += size
                    elif item.is_dir():
                        shutil.rmtree(str(item), ignore_errors=True)
                except Exception:
                    pass

        freed_mb = freed_bytes / (1024 ** 2)
        return f"[Ação] Arquivos temporários limpos! {cleaned_files} arquivos removidos ({freed_mb:.1f} MB liberados)."

    @staticmethod
    def take_screenshot() -> str:
        """Captures a screenshot and saves it to Desktop with date timestamp."""
        try:
            desktop = Path(os.path.expanduser('~/Desktop'))
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_path = desktop / f"Screenshot_Sage_{timestamp}.png"
            screenshot = pyautogui.screenshot()
            screenshot.save(str(file_path))
            return f"[Ação] Captura de tela salva com sucesso em: '{file_path.name}'"
        except Exception as e:
            return f"[Erro] Falha ao capturar tela: {e}"

    @staticmethod
    def media_control(action: str) -> str:
        """Controls media playback (play/pause, next, prev, mute)."""
        action_clean = action.lower().strip()
        VK_MEDIA_NEXT_TRACK = 0xB0
        VK_MEDIA_PREV_TRACK = 0xB1
        VK_MEDIA_PLAY_PAUSE = 0xCD
        VK_VOLUME_MUTE = 0xAD

        try:
            if "play" in action_clean or "paus" in action_clean or "tocar" in action_clean:
                ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
                return "[Mídia] Play/Pause de mídia executado."
            elif "proxim" in action_clean or "seguinte" in action_clean or "next" in action_clean:
                ctypes.windll.user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, 0, 0)
                return "[Mídia] Próxima faixa acionada."
            elif "anterior" in action_clean or "prev" in action_clean:
                ctypes.windll.user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, 0, 0)
                return "[Mídia] Faixa anterior acionada."
            elif "mudo" in action_clean or "mutar" in action_clean:
                ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                return "[Mídia] Som mutado/desmutado."
            else:
                return f"[Mídia] Comando de mídia não reconhecido: {action}"
        except Exception as e:
            return f"[Erro] Falha ao controlar mídia: {e}"

    @staticmethod
    def get_active_window_title() -> str:
        """Returns title of currently focused active window on Windows."""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            return f"[Aviso] Janela ativa em foco: '{title}'" if title else "[Aviso] Nenhuma janela ativa focada."
        except Exception as e:
            return f"[Erro] Não foi possível obter janela ativa: {e}"

