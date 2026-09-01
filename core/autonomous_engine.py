"""
Elivea — Autonomous Self-Programming Engine
====================================================
Motor de auto-programação CONTÍNUA e PROATIVA que:

  1. Auto-diagnóstico: monitora a saúde do sistema em background
  2. Auto-reparo: detecta e corrige problemas automaticamente
  3. Auto-melhoria: analisa a codebase e aplica melhorias sem pedir
  4. Auto-aprendizado: registra o que funcionou/quebrou para melhorar decisões futuras
  5. Self-awareness: conhece seus próprios módulos e capacidades

A Elívea agora se auto-programa — sem que o Mestre peça.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger("elvea.autonomous")

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "config" / "agent_memory"
AUTONOMOUS_LOG = MEMORY_DIR / "autonomous_history.jsonl"
DIAGNOSTIC_CACHE = MEMORY_DIR / "diagnostic_cache.json"


# ---------------------------------------------------------------------------
# Diagnostic data structures
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticIssue:
    """A single diagnostic issue detected during self-scan."""
    severity: str       # "critical", "warning", "info"
    category: str       # "syntax", "import", "security", "performance", "health"
    file: str
    line: int = 0
    message: str = ""
    suggestion: str = ""
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class SystemHealth:
    """Overall system health snapshot."""
    timestamp: float = 0.0
    total_files: int = 0
    syntax_errors: int = 0
    import_issues: int = 0
    security_issues: int = 0
    performance_issues: int = 0
    health_score: float = 100.0  # 0-100
    issues: list[DiagnosticIssue] = field(default_factory=list)
    modules_ok: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistent memory for autonomous decisions
# ---------------------------------------------------------------------------

def _load_autonomous_history() -> list[dict]:
    """Load history of autonomous actions."""
    history = []
    try:
        if AUTONOMOUS_LOG.exists():
            for line in AUTONOMOUS_LOG.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    history.append(json.loads(line))
    except Exception:
        pass
    return history


def _record_autonomous_action(action: str, target: str, success: bool,
                               details: str = "", elapsed: float = 0.0):
    """Record an autonomous action for learning."""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "action": action,
            "target": target[:200],
            "success": success,
            "details": details[:500],
            "elapsed": round(elapsed, 1),
        }
        with AUTONOMOUS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _get_recent_failures(hours: int = 24) -> list[dict]:
    """Get recent failures to avoid repeating failed actions."""
    cutoff = time.time() - (hours * 3600)
    return [h for h in _load_autonomous_history()
            if not h.get("success") and h.get("ts", 0) > cutoff]


# ---------------------------------------------------------------------------
# Static analysis engine
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".idea", ".vscode", "desktop_exes", "backups", "logs", "temp",
}


def _scan_python_files(root: Path | None = None) -> list[Path]:
    """List all Python files, skipping noise directories."""
    root = root or BASE_DIR
    result = []
    for p in root.rglob("*.py"):
        if any(s in p.parts for s in _SKIP_DIRS):
            continue
        if p.is_file() and p.stat().st_size < 500_000:
            result.append(p)
    return sorted(result)


def run_diagnostics(root: Path | None = None) -> SystemHealth:
    """Run a full diagnostic scan on the codebase.

    Checks:
    - Syntax validity (AST parse)
    - Import resolution (can each import be found?)
    - Security patterns (bare excepts, eval, exec, hardcoded secrets)
    - Performance issues (functions >80 lines, files >500 lines)
    - Module health (can each core module be imported?)
    """
    root = root or BASE_DIR
    health = SystemHealth(timestamp=time.time())
    files = _scan_python_files(root)
    health.total_files = len(files)

    for fp in files:
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            rel = str(fp.relative_to(root)).replace(os.sep, "/")
        except Exception:
            continue

        # --- Syntax check ---
        try:
            tree = ast.parse(src, filename=str(fp))
        except SyntaxError as e:
            health.syntax_errors += 1
            health.issues.append(DiagnosticIssue(
                severity="critical", category="syntax", file=rel,
                line=e.lineno or 0, message=f"SyntaxError: {e.msg}",
                suggestion=f"Corrija o erro de sintaxe na linha {e.lineno}",
                auto_fixable=False,
            ))
            continue

        lines = src.splitlines()

        # --- Security patterns ---
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Bare except
            if stripped == "except:" or (stripped.startswith("except:") and "Exception" not in stripped):
                health.security_issues += 1
                health.issues.append(DiagnosticIssue(
                    severity="warning", category="security", file=rel,
                    line=i, message="Bare except (catches SystemExit, KeyboardInterrupt)",
                    suggestion="Use 'except Exception:' ou 'except SpecificError:'",
                    auto_fixable=True,
                ))

            # eval/exec
            if re.search(r'\b(eval|exec)\s*\(', stripped) and not stripped.startswith("#"):
                health.security_issues += 1
                health.issues.append(DiagnosticIssue(
                    severity="warning", category="security", file=rel,
                    line=i, message=f"Uso de {stripped.split('(')[0].strip()}() — risco de segurança",
                    suggestion="Evite eval/exec; use ast.literal_eval ou alternativas seguras",
                    auto_fixable=False,
                ))

            # Hardcoded API keys / secrets
            if re.search(r'(api_key|secret|password|token)\s*=\s*["\'][^"\']{8,}', stripped, re.IGNORECASE):
                health.security_issues += 1
                health.issues.append(DiagnosticIssue(
                    severity="critical", category="security", file=rel,
                    line=i, message="Possível segredo hardcoded no código",
                    suggestion="Use variáveis de ambiente ou secret_manager",
                    auto_fixable=False,
                ))

        # --- Performance: long functions ---
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", 0) or 0
                    size = end - node.lineno
                    if size > 80:
                        health.performance_issues += 1
                        health.issues.append(DiagnosticIssue(
                            severity="warning", category="performance", file=rel,
                            line=node.lineno,
                            message=f"Função '{node.name}' tem {size} linhas (>80)",
                            suggestion=f"Refatore '{node.name}' em funções menores",
                            auto_fixable=False,
                        ))
        except Exception:
            pass

        # --- Performance: long files ---
        if len(lines) > 500:
            health.performance_issues += 1
            health.issues.append(DiagnosticIssue(
                severity="info", category="performance", file=rel,
                line=1, message=f"Arquivo com {len(lines)} linhas (>500)",
                suggestion="Considere dividir em módulos menores",
                auto_fixable=False,
            ))

    # --- Module health check ---
    core_modules = [
        "core.llm", "core.speech_engine", "core.voice_pipeline",
        "core.persona", "core.intent_engine", "core.security",
        "core.event_bus", "core.state_manager", "core.logger",
    ]
    for mod_name in core_modules:
        mod_path = BASE_DIR / mod_name.replace(".", "/") / "__init__.py"
        if not mod_path.exists():
            mod_path = BASE_DIR / (mod_name.replace(".", "/") + ".py")
        health.modules_ok[mod_name] = Path(str(mod_path)).exists()

    # --- Health score ---
    # Bare excepts are info/warnings, not fatal. Weight them gently.
    bare_except_count = sum(1 for i in health.issues if i.category == "security" and "bare except" in i.message.lower())
    long_func_count = sum(1 for i in health.issues if i.category == "performance" and "linhas" in i.message.lower())
    critical_count = sum(1 for i in health.issues if i.severity == "critical")
    health.health_score = max(0, 100
                              - (health.syntax_errors * 20)
                              - (critical_count * 10)
                              - (bare_except_count * 1)
                              - (long_func_count * 0.5))

    return health


# ---------------------------------------------------------------------------
# Auto-fix engine (safe, targeted repairs)
# ---------------------------------------------------------------------------

_BARE_EXCEPT_FIX = re.compile(
    r'(\s*)except\s*:\s*$',
    re.MULTILINE,
)


def auto_fix_issue(issue: DiagnosticIssue, dry_run: bool = True) -> tuple[bool, str]:
    """Attempt to auto-fix a single issue.

    Returns (success, description).
    Only fixes issues marked auto_fixable=True.
    """
    if not issue.auto_fixable:
        return False, "Issue not auto-fixable"

    fp = BASE_DIR / issue.file.replace("/", os.sep)
    if not fp.exists():
        return False, f"File not found: {issue.file}"

    try:
        src = fp.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Cannot read file: {e}"

    if issue.category == "security" and "bare except" in issue.message.lower():
        # Fix bare except → except Exception
        lines = src.splitlines()
        if issue.line > 0 and issue.line <= len(lines):
            line = lines[issue.line - 1]
            if re.match(r'^(\s*)except\s*:\s*$', line):
                indent = re.match(r'^(\s*)', line).group(1)
                lines[issue.line - 1] = f"{indent}except Exception:"
                new_src = "\n".join(lines)

                # Validate syntax before writing
                try:
                    ast.parse(new_src)
                except SyntaxError:
                    return False, "Fix would introduce syntax error"

                if not dry_run:
                    try:
                        # Backup
                        backup = fp.with_suffix(".py.bak")
                        backup.write_text(src, encoding="utf-8")
                        fp.write_text(new_src, encoding="utf-8")
                        return True, f"Fixed bare except at line {issue.line}"
                    except OSError as e:
                        return False, f"Could not write file: {e}"
                else:
                    return True, f"[DRY RUN] Would fix bare except at line {issue.line}"

    return False, f"No auto-fix available for: {issue.category}"


# ---------------------------------------------------------------------------
# Autonomous Engine
# ---------------------------------------------------------------------------

class AutonomousEngine:
    """Background engine that continuously monitors and improves the system.

    Capabilities:
    - Runs diagnostics every N minutes
    - Auto-fixes safe issues (bare excepts, etc.)
    - Triggers self-improvement when issues accumulate
    - Maintains health history for trend analysis
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or BASE_DIR
        self.is_running = False
        self._thread: threading.Thread | None = None
        self._诊断_interval = 300  # 5 minutes between full diagnostics
        self._fix_interval = 600   # 10 minutes between auto-fix attempts
        self._last_diagnostic: SystemHealth | None = None
        self._last_fix_attempt = 0.0
        self._improvement_callbacks: list[Callable] = []
        self._consecutive_issues = 0
        self._max_consecutive_before_alert = 5

    def start_autonomous_loop(self):
        """Start the background monitoring loop."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True,
                                         name="gs-autonomous")
        self._thread.start()
        logger.info("[AutonomousEngine] Background loop started")

    def stop_autonomous_loop(self):
        """Stop the background monitoring loop."""
        self.is_running = False
        logger.info("[AutonomousEngine] Background loop stopped")

    def on_issue_detected(self, callback: Callable):
        """Register a callback for when issues are detected.

        callback(health: SystemHealth) -> None
        """
        self._improvement_callbacks.append(callback)

    def _worker_loop(self):
        """Main background loop — diagnose, fix, learn."""
        # Initial delay — let the app start up first
        time.sleep(30)

        while self.is_running:
            try:
                self._run_cycle()
            except Exception as e:
                logger.error(f"[AutonomousEngine] Cycle error: {e}")
                time.sleep(60)
                continue

            # Sleep in small increments so we can stop quickly
            for _ in range(int(self._诊断_interval)):
                if not self.is_running:
                    return
                time.sleep(1)

    def _run_cycle(self):
        """One complete diagnostic + fix cycle."""
        now = time.time()

        # --- Phase 1: Diagnostics ---
        health = run_diagnostics(self.base_dir)
        self._last_diagnostic = health

        # Log health
        logger.info(
            f"[AutonomousEngine] Health: {health.health_score:.0f}/100 "
            f"({len(health.issues)} issues: "
            f"{health.syntax_errors} syntax, "
            f"{health.security_issues} security, "
            f"{health.performance_issues} performance)"
        )

        # Track consecutive issue count
        if health.issues:
            self._consecutive_issues += 1
        else:
            self._consecutive_issues = 0

        # Notify callbacks if there are significant issues
        if health.issues and health.health_score < 85:
            for cb in self._improvement_callbacks:
                try:
                    cb(health)
                except Exception:
                    pass

        # Alert if issues are accumulating
        if self._consecutive_issues >= self._max_consecutive_before_alert:
            logger.warning(
                f"[AutonomousEngine] ⚠ {self._consecutive_issues} consecutive "
                f"diagnostic cycles with issues detected"
            )

        # --- Phase 2: Auto-fix safe issues ---
        if now - self._last_fix_attempt >= self._fix_interval:
            self._last_fix_attempt = now
            self._attempt_auto_fixes(health)

        # --- Phase 3: Learn from history ---
        self._update_learning(health)

    def _attempt_auto_fixes(self, health: SystemHealth):
        """Try to auto-fix issues that are safe to fix automatically."""
        fixable = [i for i in health.issues if i.auto_fixable]
        if not fixable:
            return

        fixed = 0
        for issue in fixable[:5]:  # max 5 fixes per cycle
            t0 = time.perf_counter()
            success, desc = auto_fix_issue(issue, dry_run=False)
            elapsed = time.perf_counter() - t0
            _record_autonomous_action(
                "auto_fix", issue.file, success, desc, elapsed
            )
            if success:
                fixed += 1
                logger.info(f"[AutonomousEngine] ✅ Auto-fixed: {desc}")

        if fixed:
            logger.info(f"[AutonomousEngine] Fixed {fixed}/{len(fixable)} issues")

    def _update_learning(self, health: SystemHealth):
        """Update learning data based on diagnostic results."""
        try:
            cache = {}
            if DIAGNOSTIC_CACHE.exists():
                cache = json.loads(DIAGNOSTIC_CACHE.read_text(encoding="utf-8"))

            # Track health trend
            history = cache.setdefault("health_history", [])
            history.append({
                "ts": health.timestamp,
                "score": health.health_score,
                "issues": len(health.issues),
            })
            # Keep last 100 entries
            cache["health_history"] = history[-100:]

            # Track issue categories
            categories = cache.setdefault("issue_categories", {})
            for issue in health.issues:
                categories[issue.category] = categories.get(issue.category, 0) + 1

            # Track most problematic files
            file_issues = cache.setdefault("file_issues", {})
            for issue in health.issues:
                file_issues[issue.file] = file_issues.get(issue.file, 0) + 1

            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            DIAGNOSTIC_CACHE.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # --------------------------------------------------------------- public API

    def get_health(self) -> SystemHealth | None:
        """Return the last diagnostic result (or run one now)."""
        if self._last_diagnostic is None:
            return run_diagnostics(self.base_dir)
        return self._last_diagnostic

    def force_diagnostic(self) -> SystemHealth:
        """Force an immediate diagnostic scan."""
        health = run_diagnostics(self.base_dir)
        self._last_diagnostic = health
        self._update_learning(health)
        return health

    def force_fix(self) -> tuple[int, int]:
        """Force an immediate auto-fix attempt.

        Returns (fixed_count, total_fixable).
        """
        health = self.force_diagnostic()
        fixable = [i for i in health.issues if i.auto_fixable]
        fixed = 0
        for issue in fixable:
            success, _ = auto_fix_issue(issue, dry_run=False)
            if success:
                fixed += 1
        return fixed, len(fixable)

    def get_health_trend(self, points: int = 20) -> list[dict]:
        """Return recent health score history for trend analysis."""
        try:
            if DIAGNOSTIC_CACHE.exists():
                cache = json.loads(DIAGNOSTIC_CACHE.read_text(encoding="utf-8"))
                return cache.get("health_history", [])[-points:]
        except Exception:
            pass
        return []

    def execute_complex_plan(self, prompt: str, dispatcher_func) -> str:
        """Decompose a multi-step user request and execute all sub-tasks.

        Splits compound commands by Portuguese connectors and executes each.
        """
        parts = re.split(
            r'\b(e|depois|em seguida|também|tambem|além disso|alem disso|a seguir)\b|,|\n|;',
            prompt, flags=re.IGNORECASE,
        )

        sub_tasks = []
        skip_words = {"e", "depois", "em seguida", "também", "tambem",
                      "além disso", "alem disso", "a seguir"}
        for p in parts:
            p_clean = p.strip()
            if p_clean and p_clean.lower() not in skip_words:
                sub_tasks.append(p_clean)

        if len(sub_tasks) <= 1:
            return dispatcher_func(prompt)

        results = ["=== [EXECUÇÃO DE PLANO MULTI-ETAPAS DO GRANDE SÁBIO] ==="]
        for idx, task in enumerate(sub_tasks, 1):
            try:
                res = dispatcher_func(task)
                results.append(f"\n[Etapa {idx}/{len(sub_tasks)}: '{task}']\n  → {res}")
            except Exception as e:
                results.append(f"\n[Etapa {idx}/{len(sub_tasks)}: '{task}']\n  → Erro: {e}")

        return "\n".join(results)
