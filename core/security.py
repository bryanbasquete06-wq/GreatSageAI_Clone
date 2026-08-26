# -*- coding: utf-8 -*-
"""
Great Sage AI — Security Guard
================================
Centraliza todas as verificações de segurança do sistema.

Classes:
  - SecurityLevel: Níveis de permissão (SAFE, DANGEROUS, DESTRUCTIVE)
  - SecurityGuard: Gate de confirmação + whitelist + audit log
  - SandBox: Execução isolada de código do LLM
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import hashlib
import logging
import subprocess
from pathlib import Path
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


class SecurityLevel(Enum):
    """Níveis de segurança para ações."""
    SAFE = "safe"           # Leitura, info, consulta — executa direto
    DANGEROUS = "dangerous" # Instalar, matar processo, config — pede confirmação
    DESTRUCTIVE = "destructive"  # Deletar, shutdown, registry — pede confirmação + log


# =====================================================================
# Classificação de ações
# =====================================================================

# Ações PERIGOSAS (precisam confirmação)
DANGEROUS_ACTIONS = {
    "install", "uninstall", "upgrade",
    "kill_process", "service_stop", "service_start",
    "firewall", "network_config",
    "env_set", "env_delete",
    "registry_write",
    "run_python", "run_cmd", "run_powershell",
    "pip_install", "npm_install",
    "download",
}

# Ações DESTRUTIVAS (precisam confirmação + audit)
DESTRUCTIVE_ACTIONS = {
    "delete", "move", "write_file",
    "shutdown", "restart", "hibernate", "lock",
    "schedule_task",
    "wifi_connect",
    "format_disk",
}

# Comandos BLOQUEADOS (nunca executam)
BLOCKED_COMMANDS = [
    r"format\s+[a-z]:",
    r"Remove-Item\s+-[Rr]ecurse.*-Force",
    r"rd\s+/[Ss]\s+/[Qq]",
    r"del\s+/[Ss]\s+/[Qq]",
    r"shutdown\s+/[sf]",
    r"bcdedit",
    r"cipher\s+/w:",
    r"diskpart",
    r"Invoke-Expression.*Invoke-WebRequest",
    r"iwr.*iex",
    r"DownloadString.*Invoke-Expression",
    r"New-Object.*Net\.WebClient.*DownloadFile",
    r"certutil.*-urlcache",
    r"bitsadmin.*transfer",
]

# Caminhos PROTEGIDOS padrão (nunca deletam/movem).
# Pode ser sobrescrito em config/security.json via a chave "protected_paths".
DEFAULT_PROTECTED_PATHS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\Users",
    "C:\\",
    "D:\\",
    "E:\\",
    "F:\\",
]

# Whitelist de comandos SEGUROS (executam sem confirmação)
SAFE_COMMANDS = [
    "dir", "ls", "pwd", "whoami", "hostname",
    "date", "time", "echo",
    "ipconfig", "ifconfig", "ping",
    "systeminfo", "tasklist",
    "python --version", "node --version",
    "pip --version", "npm --version",
]


class SecurityGuard:
    """Gate de segurança centralizado."""

    _audit_log: list[dict] = []
    _confirmation_callback: Optional[Callable[[str, str], bool]] = None
    _config_path: Path = Path(__file__).resolve().parent.parent / "config" / "security.json"
    _config: dict = {}

    @classmethod
    def initialize(cls, confirmation_callback: Optional[Callable] = None):
        """Inicializa o SecurityGuard com callback de confirmação."""
        cls._confirmation_callback = confirmation_callback
        cls._load_config()
        cls._setup_audit_log()

    @classmethod
    def _load_config(cls):
        """Carrega configurações de segurança."""
        try:
            if cls._config_path.exists():
                cls._config = json.loads(cls._config_path.read_text(encoding="utf-8"))
            else:
                cls._config = {
                    "admin_mode": False,
                    "require_confirmation": True,
                    "audit_enabled": True,
                    "max_shutdown_delay": 10,
                }
                cls._save_config()
        except Exception:
            cls._config = {
                "admin_mode": False,
                "require_confirmation": True,
                "audit_enabled": True,
                "max_shutdown_delay": 10,
            }

    @classmethod
    def _save_config(cls):
        """Salva configurações de segurança."""
        try:
            cls._config_path.parent.mkdir(parents=True, exist_ok=True)
            cls._config_path.write_text(
                json.dumps(cls._config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception:
            pass

    @classmethod
    def _setup_audit_log(cls):
        """Configura audit log."""
        log_path = Path(__file__).resolve().parent.parent / "logs" / "security_audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            encoding="utf-8",
        )

    @classmethod
    def classify_action(cls, action: str, params: dict = None) -> SecurityLevel:
        """Classifica uma ação por nível de segurança."""
        if action in DESTRUCTIVE_ACTIONS:
            return SecurityLevel.DESTRUCTIVE
        if action in DANGEROUS_ACTIONS:
            return SecurityLevel.DANGEROUS
        return SecurityLevel.SAFE

    @classmethod
    def check_command(cls, command: str) -> tuple[bool, str]:
        """Verifica se um comando é seguro para executar."""
        cmd_lower = command.lower().strip()

        # Verifica comandos bloqueados
        for pattern in BLOCKED_COMMANDS:
            if re.search(pattern, cmd_lower):
                return False, f"Comando bloqueado por segurança: {pattern}"

        # Verifica whitelist
        for safe in SAFE_COMMANDS:
            if cmd_lower.startswith(safe):
                return True, ""

        return True, ""  # Permite outros comandos (com confirmação)

    @classmethod
    def get_protected_paths(cls) -> list[str]:
        """Retorna os caminhos protegidos (configuráveis via security.json)."""
        paths = cls._config.get("protected_paths", DEFAULT_PROTECTED_PATHS)
        if not isinstance(paths, list):
            return list(DEFAULT_PROTECTED_PATHS)
        return paths

    @classmethod
    def check_path(cls, path: str, action: str = "delete") -> tuple[bool, str]:
        """Verifica se um caminho é seguro para a ação."""
        if action in ("delete", "move", "write"):
            abs_path = os.path.abspath(path)
            for protected in cls.get_protected_paths():
                if abs_path.lower().startswith(protected.lower()):
                    return False, f"Caminho protegido: {protected}"
        return True, ""

    @classmethod
    def check_url(cls, url: str) -> tuple[bool, str]:
        """Verifica se uma URL é segura para download."""
        if not url.startswith("https://"):
            return False, "Apenas HTTPS permitido"

        # Bloqueia hosts suspeitos
        blocked_hosts = [
            "pastebin.com", "hastebin.com", "ghostbin.co",
            "rentry.co", "paste.ee",
        ]
        for host in blocked_hosts:
            if host in url.lower():
                return False, f"Host bloqueado: {host}"

        return True, ""

    @classmethod
    def require_confirmation(cls, action: str, details: str = "") -> bool:
        """Pede confirmação do usuário para uma ação."""
        if not cls._config.get("require_confirmation", True):
            return True

        level = cls.classify_action(action)
        if level == SecurityLevel.SAFE:
            return True

        # Registra tentativa
        cls._audit_log_entry(action, details, "confirmation_requested")

        # Chama callback de confirmação
        if cls._confirmation_callback:
            return cls._confirmation_callback(action, details)

        # Fallback: confirma via console (para testes)
        print(f"\n[SEGURANÇA] Ação {level.value.upper()}: {action}")
        if details:
            print(f"Detalhes: {details}")
        resp = input("Confirmar? (s/N): ").strip().lower()
        return resp in ("s", "sim", "y", "yes")

    @classmethod
    def require_admin(cls) -> bool:
        """Verifica se admin mode está habilitado."""
        if cls._config.get("admin_mode", False):
            return True

        if cls._confirmation_callback:
            return cls._confirmation_callback(
                "admin_mode",
                "Modo administrador necessário para esta ação"
            )

        print("\n[SEGURANÇA] Modo administrador necessário.")
        resp = input("Habilitar admin mode? (s/N): ").strip().lower()
        if resp in ("s", "sim", "y", "yes"):
            cls._config["admin_mode"] = True
            cls._save_config()
            return True
        return False

    @classmethod
    def enable_admin_mode(cls):
        """Habilita admin mode."""
        cls._config["admin_mode"] = True
        cls._save_config()
        cls._audit_log_entry("admin_mode_enabled", "", "config_change")

    @classmethod
    def disable_admin_mode(cls):
        """Desabilita admin mode."""
        cls._config["admin_mode"] = False
        cls._save_config()
        cls._audit_log_entry("admin_mode_disabled", "", "config_change")

    @classmethod
    def audit(cls, action: str, details: str = "", result: str = "success"):
        """Registra ação no audit log."""
        cls._audit_log_entry(action, details, result)

    @classmethod
    def _audit_log_entry(cls, action: str, details: str, result: str):
        """Escreve entrada no audit log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details[:500],
            "result": result,
        }
        cls._audit_log.append(entry)

        if cls._config.get("audit_enabled", True):
            logging.info(f"{action} | {result} | {details[:200]}")

    @classmethod
    def get_audit_log(cls, limit: int = 50) -> list[dict]:
        """Retorna últimas entradas do audit log."""
        return cls._audit_log[-limit:]


class SandBox:
    """Execução isolada de código do LLM."""

    _BLOCKED_PATTERNS = [
        r"import\s+os",
        r"import\s+subprocess",
        r"import\s+shutil",
        r"from\s+os\s+import",
        r"from\s+subprocess\s+import",
        r"os\.(system|popen|exec|remove|rmdir)",
        r"subprocess\.(run|call|Popen)",
        r"__import__",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"open\s*\(.*['\"]w['\"]",
        r"open\s*\(.*['\"]wb['\"]",
        r"shutil\.(rmtree|rmdir|move)",
        r"socket\.",
        r"requests\.(get|post|put|delete)",
        r"urllib\.",
        r"http\.",
        r"ctypes\.",
    ]

    @classmethod
    def scan_code(cls, code: str) -> tuple[bool, list[str]]:
        """Verifica código em busca de padrões perigosos."""
        warnings = []
        for pattern in cls._BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(f"Padrão suspeito: {pattern}")

        return len(warnings) == 0, warnings

    @classmethod
    def require_approval(cls, code: str, language: str) -> bool:
        """Pede aprovação antes de executar código."""
        is_safe, warnings = cls.scan_code(code)

        if not is_safe:
            print(f"\n[SEGURANÇA] Código {language} contém padrões suspeitos:")
            for w in warnings:
                print(f"  - {w}")

            if SecurityGuard._confirmation_callback:
                return SecurityGuard._confirmation_callback(
                    "execute_code",
                    f"Código {language} com {len(warnings)} avisos de segurança"
                )

            resp = input("Executar mesmo assim? (s/N): ").strip().lower()
            return resp in ("s", "sim", "y", "yes")

        return True  # Código limpo, permite executar

    @classmethod
    def create_restricted_env(cls) -> dict:
        """Cria ambiente restrito para execução."""
        env = os.environ.copy()
        # Remove variáveis sensíveis
        sensitive = [
            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
            "GITHUB_TOKEN", "OPENAI_API_KEY",
            "GOOGLE_API_KEY", "GROQ_API_KEY",
        ]
        for key in sensitive:
            env.pop(key, None)
        return env
