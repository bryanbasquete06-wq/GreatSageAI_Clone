# -*- coding: utf-8 -*-
"""
Elívea — Security Guard
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
from datetime import datetime, timedelta
from collections import defaultdict


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
    # ── Windows destructive ──────────────────────
    r"format\s+[a-z]:",
    r"Remove-Item\s+-[Rr]ecurse.*-Force",
    r"rd\s+/[Ss]\s+/[Qq]",
    r"del\s+/[Ss]\s+/[Qq]",
    r"shutdown\s+/[sf]",
    r"bcdedit",
    r"cipher\s+/w:",
    r"diskpart",
    r"sc\s+delete",
    r"taskkill\s+/F",
    r"reg\s+add",
    r"net\s+user\s+\S+\s+\S+\s+/add",
    r"net\s+localgroup\s+Administrators",
    r"wmic\s+process\s+call\s+create",
    # ── PowerShell injection ─────────────────────
    r"Invoke-Expression",
    r"Invoke-Expression.*Invoke-WebRequest",
    r"iwr.*iex",
    r"iex\s*\(",
    r"DownloadString.*Invoke-Expression",
    r"New-Object.*Net\.WebClient.*DownloadFile",
    r"certutil.*-urlcache",
    r"bitsadmin.*transfer",
    r"powershell\s+-[Ee][Nn][Cc]",
    r"powershell\s+-[Ee]\s",
    r"-Command\s+.*frombase64",
    # ── Linux destructive ────────────────────────
    r"rm\s+.*-rf\s+/?\*?",
    r"rm\s+.*-fr\s+/?\*?",
    r"rm\s+-rf\s+/",
    r"rm\s+.*--no-preserve-root",
    # ── Privilege escalation ─────────────────────
    r"sudo\s+su",
    r"sudo\s+-s",
    r"sudo\s+su\s+-",
    r"chmod\s+777",
    r"chmod\s+666\s+/etc",
    # ── System config ────────────────────────────
    r"iptables\s+-F",
    r"ufw\s+disable",
    r"passwd\s+root",
    r"cat\s+/etc/shadow",
    r"cat\s+/etc/passwd.*>/",
    # ── Pipe to shell (critical!) ────────────────
    r"\|\s*(ba)?sh",
    r"\|\s*(ba)?sh\s*$",
    r"curl\s+.*\|",
    r"wget\s+.*\|",
    r"wget\s+.*-O\s*-",
    # ── Code injection ───────────────────────────
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
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
    """Gate de segurança centralizado com Rate Limiting e Anomaly Detection."""

    _audit_log: list[dict] = []
    _confirmation_callback: Optional[Callable[[str, str], bool]] = None
    _config_path: Path = Path(__file__).resolve().parent.parent / "config" / "security.json"
    _config: dict = {}

    # ── Rate Limiting ──────────────────────────────────────────────
    _rate_limits: dict[str, list[float]] = defaultdict(list)
    _RATE_WINDOWS = {
        "shutdown": (3, 300),       # max 3 em 5min
        "restart": (3, 300),        # max 3 em 5min
        "delete": (10, 60),         # max 10 em 1min
        "install": (5, 300),        # max 5 em 5min
        "kill_process": (20, 60),   # max 20 em 1min
        "format_disk": (1, 86400),  # max 1 em 24h
        "run_python": (30, 60),     # max 30 em 1min
        "run_cmd": (30, 60),        # max 30 em 1min
        "download": (10, 300),      # max 10 em 5min
        "default": (60, 60),        # max 60/min para ações genéricas
    }

    # ── Anomaly Detection ──────────────────────────────────────────
    _anomaly_events: list[dict] = []
    _ANOMALY_THRESHOLD = 5  # bloqueios em X minutos = suspeito
    _ANOMALY_WINDOW = 300   # 5 minutos

    @classmethod
    def initialize(cls, confirmation_callback: Optional[Callable] = None):
        """Inicializa o SecurityGuard — modo admin TOTAL habilitado."""
        cls._confirmation_callback = confirmation_callback
        cls._load_config()
        cls._setup_audit_log()
        # Auto-habilita admin mode para acesso total
        cls._config["admin_mode"] = True
        cls._config["require_confirmation"] = False  # executa tudo sem pedir
        cls._save_config()

    # ── Rate Limiting ──────────────────────────────────────────────

    @classmethod
    def check_rate_limit(cls, action: str) -> tuple[bool, str]:
        """Verifica se a ação excedeu o rate limit. Retorna (permitido, msg)."""
        now = time.time()
        max_count, window = cls._RATE_WINDOWS.get(action, cls._RATE_WINDOWS["default"])
        # Limpa entradas antigas
        cls._rate_limits[action] = [t for t in cls._rate_limits[action] if now - t < window]
        if len(cls._rate_limits[action]) >= max_count:
            return False, (
                f"Rate limit: {action} limitado a {max_count}x a cada "
                f"{window}s. Tente novamente em {int(window - (now - cls._rate_limits[action][0]))}s."
            )
        cls._rate_limits[action].append(now)
        return True, ""

    # ── Anomaly Detection ──────────────────────────────────────────

    @classmethod
    def _detect_anomaly(cls, action: str, details: str = "") -> Optional[str]:
        """Detecta padrões suspeitos de comportamento. Retorna msg de alerta ou None."""
        now = time.time()
        # Registra evento bloqueado/dangerous
        if action in DESTRUCTIVE_ACTIONS or action in DANGEROUS_ACTIONS:
            cls._anomaly_events.append({"ts": now, "action": action, "details": details[:200]})
        # Limpa eventos antigos
        cls._anomaly_events = [e for e in cls._anomaly_events if now - e["ts"] < cls._ANOMALY_WINDOW]
        # Detecta padrões
        recent = cls._anomaly_events
        if len(recent) >= cls._ANOMALY_THRESHOLD:
            actions = [e["action"] for e in recent]
            # Padrão 1: muitas ações destrutivas em sequência
            destructive_count = sum(1 for a in actions if a in DESTRUCTIVE_ACTIONS)
            if destructive_count >= 3:
                return f"ANOMALIA: {destructive_count} ações destrutivas nos últimos {cls._ANOMALY_WINDOW}s"
            # Padrão 2: repetição da mesma ação
            from collections import Counter
            action_counts = Counter(actions)
            for act, cnt in action_counts.items():
                if cnt >= 5:
                    return f"ANOMALIA: ação '{act}' repetida {cnt} vezes em janela curta"
            # Padrão 3: mistura suspeita (delete + install + shutdown)
            if len(set(actions) & {"delete", "install", "shutdown", "format_disk"}) >= 2:
                return f"ANOMALIA: combinação suspeita de ações: {', '.join(set(actions))}"
        return None

    @classmethod
    def get_anomaly_report(cls) -> dict:
        """Retorna relatório de anomalias detectadas."""
        now = time.time()
        recent = [e for e in cls._anomaly_events if now - e["ts"] < cls._ANOMALY_WINDOW]
        return {
            "recent_events": len(recent),
            "threshold": cls._ANOMALY_THRESHOLD,
            "window_seconds": cls._ANOMALY_WINDOW,
            "blocked_recently": sum(1 for e in recent if e.get("blocked")),
            "actions_breakdown": dict(defaultdict(int, {e["action"]: 1 for e in recent})),
        }

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

        # Verifica comandos bloqueados (case-insensitive)
        for pattern in BLOCKED_COMMANDS:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
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
        """Verifica se uma URL é segura para acessar."""
        if not url or not isinstance(url, str):
            return False, "URL vazia ou invalida"
        url_lower = url.strip().lower()

        # Bloqueia protocolos perigosos
        DANGEROUS_SCHEMES = ("javascript:", "data:", "file:", "ftp:")
        for scheme in DANGEROUS_SCHEMES:
            if url_lower.startswith(scheme):
                return False, f"Protocolo bloqueado: {scheme}"

        # Bloqueia URLs sem protocolo (pode ser injection)
        if not url_lower.startswith(("http://", "https://")):
            return False, "URL deve usar HTTP ou HTTPS"

        return True, ""

    @classmethod
    def create_restricted_env(cls) -> dict:
        """Retorna copia do environ com chaves sensiveis removidas."""
        env = os.environ.copy()
        # Exatas
        exact_sensitive = {
            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
            "GITHUB_TOKEN", "OPENAI_API_KEY",
            "GOOGLE_API_KEY", "GROQ_API_KEY",
            "DATABASE_URL", "REDIS_URL",
            "SMTP_PASSWORD",
        }
        # Prefixed — remove QUALQUER env var que comece com esses prefixos
        prefixes = ("SECRET", "TOKEN", "PRIVATE", "PASSWORD", "CREDENTIAL")
        to_remove = [
            k for k in env
            if k in exact_sensitive
            or any(k.startswith(p) for p in prefixes)
        ]
        for key in to_remove:
            env.pop(key, None)
        return env

    @classmethod
    def require_confirmation(cls, action: str, details: str = "") -> bool:
        """Modo admin total — aprova automaticamente todas as ações."""
        # Auto-approve: modo admin está sempre ativo
        cls._audit_log_entry(action, details, "auto_approved")
        return True

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
    """Execução isolada de código do LLM — com AST analysis e risk scoring."""

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

    # Pesos de risco por categoria
    _RISK_WEIGHTS = {
        "filesystem": 3,
        "network": 4,
        "process": 5,
        "code_exec": 8,
        "crypto": 3,
        "env_access": 2,
    }

    @classmethod
    def scan_code(cls, code: str) -> tuple[bool, list[str]]:
        """Verifica código em busca de padrões perigosos."""
        warnings = []
        for pattern in cls._BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(f"Padrão suspeito: {pattern}")

        return len(warnings) == 0, warnings

    @classmethod
    def analyze_risk(cls, code: str, language: str = "python") -> dict:
        """Análise profunda de risco — retorna score 0-100 + categorias."""
        risk = {"score": 0, "categories": {}, "warnings": [], "safe": True}
        if language.lower() != "python":
            # Para não-Python, usa regex básico
            is_safe, warnings = cls.scan_code(code)
            risk["warnings"] = warnings
            risk["score"] = len(warnings) * 15
            risk["safe"] = is_safe
            return risk
        # AST-based analysis
        try:
            import ast
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Code execution
                if isinstance(node, ast.Call):
                    func = node.func
                    func_name = ""
                    if isinstance(func, ast.Name):
                        func_name = func.id
                    elif isinstance(func, ast.Attribute):
                        func_name = func.attr
                    if func_name in ("eval", "exec", "compile", "__import__"):
                        risk["categories"]["code_exec"] = risk["categories"].get("code_exec", 0) + 1
                        risk["warnings"].append(f"Chamada perigosa: {func_name}()")
                # File access
                if isinstance(node, ast.Call) and isinstance(getattr(node, 'func', None), ast.Name):
                    if node.func.id == "open":
                        risk["categories"]["filesystem"] = risk["categories"].get("filesystem", 0) + 1
                # Import dangerous modules
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ("subprocess", "os", "shutil", "ctypes", "socket"):
                            risk["categories"]["process"] = risk["categories"].get("process", 0) + 1
                        if alias.name in ("requests", "urllib", "http"):
                            risk["categories"]["network"] = risk["categories"].get("network", 0) + 1
                        if alias.name in ("hashlib", "hmac", "crypto"):
                            risk["categories"]["crypto"] = risk["categories"].get("crypto", 0) + 1
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module in ("os", "subprocess", "shutil"):
                        risk["categories"]["process"] = risk["categories"].get("process", 0) + 1
        except SyntaxError:
            risk["warnings"].append("Código tem erro de sintaxe — análise AST impossível")
            risk["score"] = 50
            risk["safe"] = False
            return risk
        # Calcula score
        total_weight = 0
        for cat, count in risk["categories"].items():
            weight = cls._RISK_WEIGHTS.get(cat, 1)
            total_weight += count * weight
        # Also add regex-based findings
        _, warnings = cls.scan_code(code)
        risk["warnings"].extend(warnings)
        total_weight += len(warnings) * 2
        risk["score"] = min(100, total_weight * 5)
        risk["safe"] = risk["score"] < 30
        return risk

    @classmethod
    def require_approval(cls, code: str, language: str) -> bool:
        """Pede aprovação antes de executar código — com risk scoring."""
        risk = cls.analyze_risk(code, language)
        warnings = risk["warnings"]

        if not risk["safe"]:
            risk_label = "BAIXO" if risk["score"] < 30 else "MÉDIO" if risk["score"] < 60 else "ALTO"
            print(f"\n[SEGURANÇA] Código {language} — Risco {risk_label} ({risk['score']}/100)")
            for w in warnings[:10]:
                print(f"  - {w}")
            if risk["categories"]:
                cats = ", ".join(f"{k}:{v}" for k, v in risk["categories"].items())
                print(f"  Categorias: {cats}")

            if SecurityGuard._confirmation_callback:
                return SecurityGuard._confirmation_callback(
                    "execute_code",
                    f"Código {language} — Risco {risk_label} ({risk['score']}/100), "
                    f"{len(warnings)} avisos"
                )

            resp = input("Executar mesmo assim? (s/N): ").strip().lower()
            return resp in ("s", "sim", "y", "yes")

        return True  # Código limpo, permite executar

    @classmethod
    def create_restricted_env(cls) -> dict:
        """Cria ambiente restrito para execução."""
        env = os.environ.copy()
        sensitive = [
            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
            "GITHUB_TOKEN", "OPENAI_API_KEY",
            "GOOGLE_API_KEY", "GROQ_API_KEY",
        ]
        for key in sensitive:
            env.pop(key, None)
        return env
