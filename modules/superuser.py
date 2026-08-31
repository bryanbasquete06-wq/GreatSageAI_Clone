# -*- coding: utf-8 -*-
"""SuperUser — Controle TOTAL do PC via prompt ou voz.

Módulo de administração completa que permite ao Elívea executar
QUALQUER ação no Windows como se fosse um humano com acesso admin:

  - Baixar arquivos/programas (URL direta, winget, choco, pip, npm)
  - Instalar/desinstalar software
  - Executar QUALQUER comando (cmd, powershell, com admin)
  - Gerenciar arquivos em QUALQUER lugar do PC
  - Gerenciar processos e serviços
  - Editar registro do Windows
  - Configurar rede (WiFi, IP, DNS, firewall)
  - Controle total de mídia e hardware
  - Abrir/fechar qualquer aplicativo
  - Agendar tarefas
  - Tudo que um humano admin consegue fazer

Uso:
    from modules.superuser import SuperUser
    SuperUser.download_file("https://example.com/file.exe", "C:/Downloads/")
    SuperUser.run_cmd("winget install Notepad++", admin=True)
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable

# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #

DOWNLOADS_DIR = Path(os.path.expanduser("~/Downloads"))
SHELL = "powershell"
TIMEOUT_DEFAULT = 120
TIMEOUT_LONG = 600


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _is_admin() -> bool:
    """Verifica se está rodando como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _elevate_cmd(cmd: str) -> str:
    """Envolve comando para elevação UAC (abre prompt de admin)."""
    # PowerShell com Start-Process -Verb RunAs eleva via UAC
    return (f'Start-Process powershell -ArgumentList "-NoProfile -Command '
            f'& \\"{cmd}\\"" -Verb RunAs -Wait')


def _run(cmd: str, admin: bool = False, timeout: int = TIMEOUT_DEFAULT,
         cwd: str | None = None, shell: bool = True) -> tuple[int, str, str]:
    """Executa comando. Retorna (returncode, stdout, stderr)."""
    if admin and not _is_admin():
        # eleva via UAC
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'Start-Process cmd -ArgumentList "/c {cmd}" -Verb RunAs -Wait -PassThru | Select-Object -ExpandProperty ExitCode'],
                capture_output=True, text=True, timeout=timeout + 30,
                encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW)
            return (result.returncode, result.stdout.strip(), result.stderr.strip())
        except Exception as e:
            return (1, "", f"Erro ao elevar: {e}")
    try:
        proc = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
            encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW)
        return (proc.returncode, proc.stdout or "", proc.stderr or "")
    except subprocess.TimeoutExpired:
        return (1, "", f"Timeout ({timeout}s)")
    except Exception as e:
        return (1, "", str(e))


def _run_ps(cmd: str, admin: bool = False, timeout: int = TIMEOUT_DEFAULT) -> tuple[int, str, str]:
    """Executa PowerShell."""
    full = f"powershell -NoProfile -ExecutionPolicy Bypass -Command \"{cmd}\""
    return _run(full, admin=admin, timeout=timeout)


# --------------------------------------------------------------------------- #
# SuperUser — Controle Total do PC
# --------------------------------------------------------------------------- #

class SuperUser:
    """Módulo de controle TOTAL do PC. Tudo via prompt ou voz."""

    # ================================================================ DOWNLOAD

    @staticmethod
    def download_file(url: str, dest: str | None = None,
                      filename: str | None = None) -> str:
        """Baixa arquivo de qualquer URL. Suporta redirects."""
        dest_dir = Path(dest) if dest else DOWNLOADS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        if filename:
            out_path = dest_dir / filename
        else:
            out_path = dest_dir / url.split("/")[-1].split("?")[0]
            if not out_path.suffix:
                out_path = out_path.with_suffix(".download")
        try:
            def _progress(block, block_size, total):
                pass  # poderia ter progresso, mas simplificado
            urllib.request.urlretrieve(url, str(out_path), _progress)
            size_mb = out_path.stat().st_size / (1024 * 1024)
            return (f"Download concluído: {out_path.name} "
                    f"({size_mb:.1f} MB) em {out_path.parent}")
        except Exception as e:
            return f"Erro no download: {e}"

    @staticmethod
    def download_and_install(url: str, installer_args: str | None = None,
                             name: str | None = None) -> str:
        """Baixa um instalador e roda automaticamente."""
        name = name or url.split("/")[-1].split("?")[0]
        if not any(name.endswith(ext) for ext in (".exe", ".msi", ".bat", ".ps1")):
            name += ".exe"
        result = SuperUser.download_file(url, filename=name)
        if "Erro" in result:
            return result
        installer = DOWNLOADS_DIR / name
        if not installer.exists():
            return f"Arquivo não encontrado após download: {installer}"
        # roda o instalador
        if name.endswith(".msi"):
            cmd = f'msiexec /i "{installer}" {installer_args or "/quiet /norestart"}'
        else:
            cmd = f'"{installer}" {installer_args or "/S"}'
        rc, out, err = _run(cmd, admin=True, timeout=TIMEOUT_LONG)
        if rc == 0:
            return f"Instalação concluída: {name}"
        return f"Instalação pode ter exigido interação: {name} (exit {rc})\n{err[:500]}"

    # ================================================================ WINGET

    @staticmethod
    def winget_install(package: str) -> str:
        """Instala software via winget (repositório Microsoft)."""
        rc, out, err = _run(f"winget install --id {package} --accept-package-agreements --accept-source-agreements",
                            admin=True, timeout=TIMEOUT_LONG)
        if rc == 0:
            return f"{package} instalado com sucesso via winget."
        return f"Winget: {package}\n{out[-500:]}\n{err[-500:]}"

    @staticmethod
    def winget_uninstall(package: str) -> str:
        """Desinstala software via winget."""
        rc, out, err = _run(f"winget uninstall --id {package}", admin=True, timeout=TIMEOUT_LONG)
        if rc == 0:
            return f"{package} desinstalado via winget."
        return f"Winget uninstall: {err[-500:]}"

    @staticmethod
    def winget_search(query: str) -> str:
        """Busca pacotes no winget."""
        rc, out, err = _run(f"winget search {query}", timeout=30)
        return out[:3000] or err[:1000] or "Nenhum resultado."

    @staticmethod
    def winget_upgrade(package: str | None = None) -> str:
        """Atualiza um pacote ou todos via winget."""
        target = f"--id {package}" if package else "--all"
        rc, out, err = _run(f"winget upgrade {target} --accept-package-agreements",
                            admin=True, timeout=TIMEOUT_LONG)
        return f"Atualização winget concluída.\n{out[-1000:]}"

    # ================================================================ PIP/NPM

    @staticmethod
    def pip_install(package: str) -> str:
        """Instala pacote Python via pip."""
        rc, out, err = _run(f"{sys.executable} -m pip install {package}", timeout=TIMEOUT_LONG)
        if rc == 0:
            return f"pip: {package} instalado."
        return f"pip install falhou:\n{err[-800:]}"

    @staticmethod
    def pip_uninstall(package: str) -> str:
        rc, out, err = _run(f"{sys.executable} -m pip uninstall -y {package}", timeout=60)
        return f"pip uninstall {package}: exit {rc}"

    @staticmethod
    def npm_install(package: str, global_: bool = False) -> str:
        flag = "-g" if global_ else ""
        rc, out, err = _run(f"npm install {flag} {package}", timeout=TIMEOUT_LONG)
        if rc == 0:
            return f"npm: {package} instalado."
        return f"npm install falhou:\n{err[-800:]}"

    # ================================================================ CMD

    @staticmethod
    def run_cmd(command: str, admin: bool = False,
                timeout: int = TIMEOUT_DEFAULT) -> str:
        """Executa QUALQUER comando do sistema."""
        rc, out, err = _run(command, admin=admin, timeout=timeout)
        parts = [f"exit code: {rc}"]
        if out.strip():
            parts.append(out[-3000:])
        if err.strip():
            parts.append(f"[stderr]\n{err[-1000:]}")
        return "\n".join(parts)

    @staticmethod
    def run_powershell(command: str, admin: bool = False) -> str:
        """Executa comando PowerShell."""
        rc, out, err = _run_ps(command, admin=admin)
        parts = [f"exit code: {rc}"]
        if out.strip():
            parts.append(out[-3000:])
        if err.strip():
            parts.append(f"[stderr]\n{err[-1000:]}")
        return "\n".join(parts)

    @staticmethod
    def run_python(code: str) -> str:
        """Executa código Python isolado."""
        rc, out, err = _run(f'"{sys.executable}" -c "{code.replace(chr(34), chr(39))}"')
        return f"exit {rc}\n{out[-2000:]}\n{err[-500:]}" if (out or err) else f"exit {rc}"

    # ================================================================ FILES

    @staticmethod
    def copy(src: str, dst: str) -> str:
        """Copia arquivo/pasta."""
        try:
            s, d = Path(src), Path(dst)
            if s.is_dir():
                shutil.copytree(str(s), str(d))
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(s), str(d))
            return f"Copiado: {s.name} → {d}"
        except Exception as e:
            return f"Erro ao copiar: {e}"

    @staticmethod
    def move(src: str, dst: str) -> str:
        """Move arquivo/pasta."""
        try:
            shutil.move(src, dst)
            return f"Movido: {src} → {dst}"
        except Exception as e:
            return f"Erro ao mover: {e}"

    @staticmethod
    def delete(path: str, force: bool = True) -> str:
        """Deleta arquivo ou pasta."""
        try:
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()
            return f"Deletado: {path}"
        except Exception as e:
            return f"Erro ao deletar: {e}"

    @staticmethod
    def rename(src: str, new_name: str) -> str:
        """Renomeia arquivo/pasta."""
        try:
            p = Path(src)
            new = p.parent / new_name
            p.rename(new)
            return f"Renomeado: {p.name} → {new_name}"
        except Exception as e:
            return f"Erro ao renomear: {e}"

    @staticmethod
    def read_file(path: str, max_chars: int = 10000) -> str:
        """Lê conteúdo de qualquer arquivo."""
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                return content[:max_chars] + f"\n... ({len(content)} chars total)"
            return content
        except Exception as e:
            return f"Erro ao ler: {e}"

    @staticmethod
    def write_file(path: str, content: str) -> str:
        """Escreve em qualquer arquivo."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Escrito: {path} ({len(content)} chars)"
        except Exception as e:
            return f"Erro ao escrever: {e}"

    @staticmethod
    def list_dir(path: str = ".", recursive: bool = False) -> str:
        """Lista conteúdo de pasta."""
        try:
            p = Path(path)
            if recursive:
                items = sorted(p.rglob("*"))
            else:
                items = sorted(p.iterdir())
            lines = []
            for item in items[:200]:
                if item.is_dir():
                    lines.append(f"  [DIR]  {item.name}/")
                else:
                    size = item.stat().st_size
                    if size > 1_000_000:
                        size_str = f"{size/1_000_000:.1f}MB"
                    elif size > 1_000:
                        size_str = f"{size/1_000:.1f}KB"
                    else:
                        size_str = f"{size}B"
                    lines.append(f"  [FILE] {item.name} ({size_str})")
            return f"{p}:\n" + "\n".join(lines) if lines else f"{p}: (vazio)"
        except Exception as e:
            return f"Erro ao listar: {e}"

    @staticmethod
    def search_files(query: str, root: str = "C:\\", max_results: int = 30) -> str:
        """Busca arquivos no PC inteiro."""
        results = []
        try:
            for item in Path(root).rglob(f"*{query}*"):
                if len(results) >= max_results:
                    break
                if item.is_file():
                    results.append(str(item))
        except PermissionError:
            pass
        except Exception:
            pass
        if not results:
            return f"Nenhum arquivo encontrado com '{query}'"
        return f"Encontrados {len(results)} resultados:\n" + "\n".join(f"  {r}" for r in results)

    # ================================================================ PROCESS

    @staticmethod
    def list_processes(filter_name: str | None = None) -> str:
        """Lista processos rodando."""
        rc, out, err = _run('tasklist /FO CSV /NH')
        if filter_name:
            lines = [l for l in out.splitlines() if filter_name.lower() in l.lower()]
        else:
            lines = out.splitlines()[:50]
        return "\n".join(lines) or "Nenhum processo encontrado."

    @staticmethod
    def kill_process(name_or_pid: str) -> str:
        """Mata processo por nome ou PID."""
        rc, out, err = _run(f'taskkill /F /IM {name_or_pid}', admin=True)
        if rc == 0:
            return f"Processo {name_or_pid} encerrado."
        # tenta por PID
        rc2, out2, err2 = _run(f'taskkill /F /PID {name_or_pid}', admin=True)
        if rc2 == 0:
            return f"Processo PID {name_or_pid} encerrado."
        return f"Não consegui matar {name_or_pid}: {err[:200]}"

    # ================================================================ SERVICES

    @staticmethod
    def service_list(filter_name: str | None = None) -> str:
        """Lista serviços do Windows."""
        cmd = "Get-Service"
        if filter_name:
            cmd += f" | Where-Object {{$_.Name -like '*{filter_name}*' -or $_.DisplayName -like '*{filter_name}*'}}"
        cmd += " | Format-Table Name, Status, DisplayName -AutoSize"
        rc, out, err = _run_ps(cmd)
        return out[:3000] or err[:1000]

    @staticmethod
    def service_start(name: str) -> str:
        rc, out, err = _run_ps(f"Start-Service -Name '{name}'")
        return f"Serviço {name} iniciado." if rc == 0 else f"Erro: {err[:300]}"

    @staticmethod
    def service_stop(name: str) -> str:
        rc, out, err = _run_ps(f"Stop-Service -Name '{name}' -Force")
        return f"Serviço {name} parado." if rc == 0 else f"Erro: {err[:300]}"

    # ================================================================ REGISTRY

    @staticmethod
    def reg_read(key: str, value_name: str = "") -> str:
        """Lê valor do registro."""
        cmd = f"Get-ItemProperty -Path '{key}'"
        if value_name:
            cmd += f" | Select-Object -ExpandProperty '{value_name}'"
        rc, out, err = _run_ps(cmd)
        return out[:2000] or err[:500] or "Vazio"

    @staticmethod
    def reg_write(key: str, value_name: str, value: str, vtype: str = "String") -> str:
        """Escreve valor no registro."""
        type_map = {"String": "String", "DWORD": "Dword", "QWORD": "QWord",
                    "Binary": "Binary", "ExpandString": "ExpandString"}
        ps_type = type_map.get(vtype, "String")
        cmd = (f"New-ItemProperty -Path '{key}' -Name '{value_name}' "
               f"-Value '{value}' -PropertyType {ps_type} -Force")
        rc, out, err = _run_ps(cmd, admin=True)
        return f"Registro atualizado: {key}\\{value_name}" if rc == 0 else f"Erro: {err[:300]}"

    # ================================================================ NETWORK

    @staticmethod
    def wifi_list() -> str:
        """Lista redes WiFi disponíveis."""
        rc, out, err = _run_ps("netsh wlan show networks mode=bssid")
        return out[:3000] or err[:500]

    @staticmethod
    def wifi_connect(ssid: str, password: str = "") -> str:
        """Conecta a uma rede WiFi."""
        if password:
            # salva perfil temporário
            profile = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
    <connectionType>ESS</connectionType>
    <MSM><security><authEncryption><authentication>WPA2PSK</authentication>
    <encryption>AES</encryption></authEncryption>
    <sharedKey><keyType>passPhrase</keyType><protected>false</protected>
    <keyMaterial>{password}</keyMaterial></sharedKey></security></MSM>
</WLANProfile>"""
            tmp = Path(os.environ.get("TEMP", ".")) / "wifi_profile.xml"
            tmp.write_text(profile, encoding="utf-8")
            _run_ps(f'netsh wlan add profile filename="{tmp}"')
            tmp.unlink(missing_ok=True)
        rc, out, err = _run_ps(f'netsh wlan connect name="{ssid}"')
        return f"Conectando a {ssid}..." if rc == 0 else f"Erro: {err[:300]}"

    @staticmethod
    def set_static_ip(interface: str, ip: str, gateway: str, dns: str = "8.8.8.8") -> str:
        """Configura IP estático."""
        cmds = [
            f'netsh interface ip set address name="{interface}" static {ip} 255.255.255.0 {gateway}',
            f'netsh interface ip set dns name="{interface}" static {dns}',
        ]
        results = []
        for cmd in cmds:
            rc, out, err = _run_ps(cmd, admin=True)
            results.append(f"exit {rc}: {err[:100]}" if rc else "OK")
        return f"IP estático configurado: {interface} → {ip}\n" + "\n".join(results)

    @staticmethod
    def set_dns(server: str = "8.8.8.8", adapter: str | None = None) -> str:
        """Configura DNS."""
        target = f'name="{adapter}"' if adapter else "dhcp"
        if adapter:
            cmd = f'netsh interface ip set dns {target} static {server}'
        else:
            cmd = f'netsh interface ip set dns {target}'
        rc, out, err = _run_ps(cmd, admin=True)
        return f"DNS configurado: {server}" if rc == 0 else f"Erro: {err[:300]}"

    @staticmethod
    def flush_dns() -> str:
        rc, out, err = _run("ipconfig /flushdns", admin=True)
        return "DNS cache limpo." if rc == 0 else f"Erro: {err[:200]}"

    @staticmethod
    def ping(host: str, count: int = 4) -> str:
        rc, out, err = _run(f"ping -n {count} {host}", timeout=30)
        return out[:2000] or err[:500]

    @staticmethod
    def netstat() -> str:
        """Mostra conexões de rede ativas."""
        rc, out, err = _run("netstat -ano", timeout=15)
        return out[:3000] or err[:500]

    @staticmethod
    def firewall_add_rule(name: str, port: int, action: str = "allow",
                          protocol: str = "TCP") -> str:
        """Adiciona regra de firewall."""
        act = "Allow" if action.lower() in ("allow", "permitir", "liberar") else "Block"
        cmd = (f'netsh advfirewall firewall add rule name="{name}" '
               f'dir=in action={act} protocol={protocol} localport={port}')
        rc, out, err = _run_ps(cmd, admin=True)
        return f"Regra de firewall '{name}' criada." if rc == 0 else f"Erro: {err[:300]}"

    # ================================================================ APPS

    @staticmethod
    def open_app(name: str) -> str:
        """Abre qualquer aplicativo."""
        rc, out, err = _run(f'start "" "{name}"')
        if rc == 0:
            return f"{name} aberto."
        # tenta sem aspas
        rc2, out2, err2 = _run(f"start {name}")
        return f"{name} aberto." if rc2 == 0 else f"Erro ao abrir {name}: {err[:200]}"

    @staticmethod
    def close_app(name: str) -> str:
        """Fecha aplicativo."""
        return SuperUser.kill_process(f"{name}.exe")

    # ================================================================ SYSTEM

    @staticmethod
    def shutdown(delay: int = 30, reason: str = "") -> str:
        """Desliga o PC. MINIMO 30 segundos para cancelar."""
        delay = max(delay, 30)  # SAFETY: never less than 30s
        r = f'"{reason}"' if reason else ""
        rc, out, err = _run(f"shutdown /s /t {delay} /c {r}", admin=True)
        return f"PC desligando em {delay}s. Para cancelar: 'cancelar desligamento'." if rc == 0 else f"Erro: {err[:200]}"

    @staticmethod
    def restart(delay: int = 30) -> str:
        """Reinicia o PC. MINIMO 30 segundos para cancelar."""
        delay = max(delay, 30)  # SAFETY: never less than 30s
        rc, out, err = _run(f"shutdown /r /t {delay}", admin=True)
        return f"PC reiniciando em {delay}s. Para cancelar: 'cancelar desligamento'." if rc == 0 else f"Erro: {err[:200]}"

    @staticmethod
    def cancel_shutdown() -> str:
        rc, out, err = _run("shutdown /a")
        return "Desligamento cancelado." if rc == 0 else "Nenhum desligamento agendado."

    @staticmethod
    def lock_pc() -> str:
        """Bloqueia o PC."""
        ctypes.windll.user32.LockWorkStation()
        return "PC bloqueado."

    @staticmethod
    def hibernate() -> str:
        rc, out, err = _run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", admin=True)
        return "Hibernando..."

    @staticmethod
    def set_volume(level: int) -> str:
        """Ajusta volume do sistema (0-100)."""
        level = max(0, min(100, level))
        # PowerShell: define volume via AudioCompositor
        ps = f'$obj = New-Object -ComObject WScript.Shell; 1..50 | % {{$obj.SendKeys([char]174)}}; 1..{int(level/2)} | % {{$obj.SendKeys([char]175)}}'
        _run_ps(ps)
        return f"Volume ajustado para {level}%."

    @staticmethod
    def screenshot(path: str | None = None) -> str:
        """Captura tela."""
        try:
            import pyautogui
            dest = Path(path) if path else DOWNLOADS_DIR / f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(str(dest))
            return f"Screenshot salvo: {dest}"
        except Exception as e:
            return f"Erro ao capturar tela: {e}"

    @staticmethod
    def get_system_info() -> str:
        """Informações detalhadas do sistema."""
        rc, out, err = _run_ps(
            "Get-ComputerInfo | Select-Object CsName, WindowsVersion, OsArchitecture, "
            "CsProcessors, CsPhysicalMemory | Format-List")
        return out[:2000] or err[:500]

    @staticmethod
    def get_battery() -> str:
        rc, out, err = _run_ps(
            "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | Format-List")
        return out[:500] or "Desktop (sem bateria)"

    # ================================================================ TASK SCHEDULER

    @staticmethod
    def schedule_task(name: str, command: str, time_str: str = "",
                      trigger: str = "once") -> str:
        """Cria tarefa agendada."""
        action = f'SchTasks /Create /TN "{name}" /TR "{command}"'
        if trigger == "daily":
            action += " /SC DAILY"
            if time_str:
                action += f" /ST {time_str}"
        elif trigger == "startup":
            action += " /SC ONSTART"
        elif trigger == "logon":
            action += " /SC ONLOGON"
        else:
            action += " /SC ONCE"
            if time_str:
                action += f" /ST {time_str}"
        action += " /F"
        rc, out, err = _run(action, admin=True)
        return f"Tarefa '{name}' criada." if rc == 0 else f"Erro: {err[:300]}"

    @staticmethod
    def delete_task(name: str) -> str:
        rc, out, err = _run(f'SchTasks /Delete /TN "{name}" /F', admin=True)
        return f"Tarefa '{name}' removida." if rc == 0 else f"Erro: {err[:200]}"

    @staticmethod
    def list_tasks() -> str:
        rc, out, err = _run('SchTasks /Query /FO TABLE', timeout=15)
        return out[:3000] or err[:500]

    # ================================================================ ENV VARS

    @staticmethod
    def get_env(name: str) -> str:
        """Lê variável de ambiente."""
        return os.environ.get(name, f"Variável '{name}' não definida.")

    @staticmethod
    def set_env(name: str, value: str, permanent: bool = True) -> str:
        """Define variável de ambiente."""
        os.environ[name] = value
        if permanent:
            _run(f'setx {name} "{value}"', admin=True)
        return f"Variável {name}={value} definida{' (permanente)' if permanent else ''}."

    # ================================================================ BULK

    @staticmethod
    def execute_batch(actions: list[dict]) -> list[str]:
        """Executa múltiplas ações em sequência.

        Cada ação: {"action": "nome_do_metodo", "args": {...}}
        """
        results = []
        for act in actions:
            method_name = act.get("action", "")
            args = act.get("args", {})
            method = getattr(SuperUser, method_name, None)
            if method and callable(method):
                try:
                    results.append(method(**args))
                except Exception as e:
                    results.append(f"Erro em {method_name}: {e}")
            else:
                results.append(f"Ação desconhecida: {method_name}")
        return results

    # ================================================================ BROWSER AUTOMATION

    @staticmethod
    def open_url(url: str) -> str:
        """Abre URL no navegador padrão."""
        rc, out, err = _run(f'start "" "{url}"')
        return f"Abrindo {url}" if rc == 0 else f"Erro: {err[:200]}"

    @staticmethod
    def google_search(query: str) -> str:
        """Pesquisa no Google."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        return SuperUser.open_url(url)

    @staticmethod
    def youtube_search(query: str) -> str:
        """Pesquisa no YouTube."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        return SuperUser.open_url(url)

    @staticmethod
    def open_youtube_video(video_id: str) -> str:
        """Abre vídeo específico no YouTube."""
        return SuperUser.open_url(f"https://www.youtube.com/watch?v={video_id}")

    # ================================================================ CLIPBOARD

    @staticmethod
    def clipboard_get() -> str:
        """Lê conteúdo da área de transferência."""
        rc, out, err = _run_ps('Get-Clipboard')
        return out[:5000] or "(vazio)"

    @staticmethod
    def clipboard_set(text: str) -> str:
        """Define conteúdo da área de transferência."""
        # Escape quotes for PowerShell
        escaped = text.replace("'", "''")
        _run_ps(f"Set-Clipboard -Value '{escaped}'")
        return f"Clipboard definido: {text[:100]}..."

    # ================================================================ SCREEN CONTEXT

    @staticmethod
    def get_screen_text() -> str:
        """Captura e lê texto da tela (OCR básico via PowerShell)."""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            # Save temp
            tmp = Path(os.environ.get("TEMP", ".")) / "screen_ocr.png"
            screenshot.save(str(tmp))
            return f"Screenshot salvo em {tmp} — Use image_analyzer para OCR"
        except Exception as e:
            return f"Erro ao capturar tela: {e}"

    @staticmethod
    def mouse_click(x: int, y: int) -> str:
        """Clica em coordenada da tela."""
        try:
            import pyautogui
            pyautogui.click(x, y)
            return f"Clique em ({x}, {y})"
        except Exception as e:
            return f"Erro ao clicar: {e}"

    @staticmethod
    def mouse_move(x: int, y: int) -> str:
        """Move mouse para coordenada."""
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            return f"Mouse movido para ({x}, {y})"
        except Exception as e:
            return f"Erro ao mover mouse: {e}"

    @staticmethod
    def type_text(text: str) -> str:
        """Digita texto no campo ativo."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            return f"Digitado: {text[:100]}..."
        except Exception as e:
            return f"Erro ao digitar: {e}"

    @staticmethod
    def press_key(key: str) -> str:
        """Pressiona tecla (enter, tab, esc, etc)."""
        try:
            import pyautogui
            pyautogui.press(key)
            return f"Tecla '{key}' pressionada"
        except Exception as e:
            return f"Erro ao pressionar tecla: {e}"

    @staticmethod
    def hotkey(*keys) -> str:
        """Combinação de teclas (ex: ctrl+c, alt+tab)."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return f"Hotkey: {'+'.join(keys)}"
        except Exception as e:
            return f"Erro ao pressionar hotkey: {e}"

    # ================================================================ PROCESS ADVANCED

    @staticmethod
    def get_process_info(name: str) -> str:
        """Informações detalhadas de um processo."""
        rc, out, err = _run_ps(
            f"Get-Process -Name '{name}' | Select-Object Id, ProcessName, CPU, WorkingSet64, StartTime | Format-List")
        return out[:2000] or f"Processo '{name}' não encontrado."

    @staticmethod
    def start_process(path: str, args: str = "") -> str:
        """Inicia processo em background."""
        cmd = f'Start-Process -FilePath "{path}" -ArgumentList "{args}" -WindowStyle Hidden'
        rc, out, err = _run_ps(cmd)
        return f"Processo iniciado: {path}" if rc == 0 else f"Erro: {err[:200]}"

    # ================================================================ MISC

    @staticmethod
    def get_clipboard_history() -> str:
        """Histórico do clipboard (Windows 10+)."""
        rc, out, err = _run_ps('Get-Clipboard -Format List | Out-String')
        return out[:3000] or "Histórico não disponível."

    @staticmethod
    def empty_recycle() -> str:
        """Esvazia a lixeira."""
        try:
            import ctypes
            flags = 1 | 2 | 4  # NOCONFIRM | NOPROGRESSUI | NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return "Lixeira esvaziada."
        except Exception as e:
            return f"Erro: {e}"

    @staticmethod
    def create_system_restore_point(description: str = "Restore point") -> str:
        """Cria ponto de restauração do sistema."""
        rc, out, err = _run_ps(
            f'Checkpoint-Computer -Description "{description}" -RestorePointType MODIFY_SETTINGS',
            admin=True, timeout=300)
        return f"Ponto de restauração criado: {description}" if rc == 0 else f"Erro: {err[:300]}"

    @staticmethod
    def check_windows_updates() -> str:
        """Verifica atualizações do Windows."""
        rc, out, err = _run_ps(
            '(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0").Updates | Select-Object Title, Size | Format-Table -AutoSize',
            timeout=120)
        return out[:3000] or "Nenhuma atualização encontrada ou erro: " + err[:500]

    # ================================================================ HELP

    @staticmethod
    def capabilities() -> str:
        """Retorna lista de TUDO que o SuperUser pode fazer."""
        return """
╔══════════════════════════════════════════════════════════════╗
║  SUPERUSER — CONTROLE TOTAL DO PC                          ║
║  Acesso administrador: HABILITADO                          ║
║  Confirmação: DESABILITADA (executa tudo automaticamente)  ║
╚══════════════════════════════════════════════════════════════╝

📥 DOWNLOAD & INSTALAÇÃO:
  download <url>               Baixar qualquer arquivo
  install <url>                Baixar e instalar automaticamente
  winget install <pacote>      Instalar via winget (Microsoft Store)
  winget search <query>        Buscar pacotes
  pip install <pacote>         Instalar pacote Python
  npm install <pacote>         Instalar pacote Node.js

💻 COMANDOS:
  cmd <comando>                Executar QUALQUER comando CMD
  ps <comando>                 Executar QUALQUER comando PowerShell
  python <código>              Executar código Python

📁 ARQUIVOS:
  copy / move / delete         Copiar, mover, deletar
  list / search                Listar, buscar no PC inteiro
  read / write                 Ler, escrever qualquer arquivo

⚙️ PROCESSOS:
  processes                    Listar processos
  kill <nome>                  Matar processo
  open / close                 Abrir/fechar aplicativos

🌐 REDE:
  wifi list / connect          WiFi
  ip / dns / ping / netstat    Rede
  firewall add                 Regras de firewall
  google / youtube             Pesquisar na web

🖥️ CONTROLE DO PC:
  shutdown / restart / lock    Energia
  volume / screenshot          Áudio e tela
  mouse / keyboard             Automação de interface
  clipboard                    Área de transferência
  schedule                     Tarefas agendadas
  system restore               Ponto de restauração
  updates                      Verificar atualizações do Windows
"""
