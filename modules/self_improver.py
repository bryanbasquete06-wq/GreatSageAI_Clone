# -*- coding: utf-8 -*-
"""Self-Improver v2 — Motor de Auto-Programação CONTÍNUA do Elívea.

Análise, melhoria e auto-modificação da codebase com:
  - Loop contínuo (melhoria iterativa sem limite de rodadas)
  - Memória de aprendizado (o que funcionou, o que quebrou)
  - Priorização inteligente (bugs > segurança > refatoração > testes > features)
  - Prompt infinito via Ollama local (custo zero)
  - CodeIndex semântico para contexto ilimitado
  - Backup automático + rollback em caso de falha
"""
from __future__ import annotations

import ast
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.smart_agent import SmartCodeAgent

BASE_DIR = Path(__file__).resolve().parent.parent
MODULES_DIR = BASE_DIR / "modules"
CORE_DIR = BASE_DIR / "core"
UI_DIR = BASE_DIR / "ui"
MEMORY_DIR = BASE_DIR / "config" / "agent_memory"
IMPROVE_LOG = MEMORY_DIR / "improvements.jsonl"

# Stop event for continuous improvement loop
_stop_continuous = threading.Event()


# --------------------------------------------------------------------------- #
# Memória de melhorias (persistente entre sessões)
# --------------------------------------------------------------------------- #

def _load_improve_history() -> list[dict]:
    """Carrega histórico de melhorias aplicadas."""
    history = []
    try:
        if IMPROVE_LOG.exists():
            for line in IMPROVE_LOG.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    history.append(json.loads(line))
    except Exception:
        pass
    return history


def _record_improvement(task: str, files_changed: list[str], success: bool, elapsed: float):
    """Registra uma melhoria aplicada (append-only log)."""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "task": task[:200],
            "files": files_changed[:20],
            "success": success,
            "elapsed": round(elapsed, 1),
        }
        with IMPROVE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _get_completed_tasks() -> set[str]:
    """Retorna tasks já executadas com sucesso (evita repetir)."""
    completed = set()
    for h in _load_improve_history():
        if h.get("success"):
            completed.add(h.get("task", "")[:100])
    return completed


# --------------------------------------------------------------------------- #
# System prompts otimizados para tokens infinitos (Ollama)
# --------------------------------------------------------------------------- #

SELF_IMPROVE_PROMPT = """\
MODO AUTO-PROGRAMAÇÃO ATIVADO — você é o Elívea se auto-melhorando.

DIRETRIZES PRIORIZADAS (em ordem de importância):
1. SEGURANÇA: corrija falhas de segurança, injecao, hardcoded secrets, etc.
2. BUGS: corrija erros de lógica, exceptions não tratadas, race conditions.
3. PERFORMANCE: otimize hot paths, reduza complexidade O(n²), cacheie I/O.
4. REFATORAÇÃO: divida arquivos grandes (>400 linhas), elimine duplicação.
5. TIPOS: adicione type hints onde faltam, melhore a documentação.
6. TESTES: crie testes para código sem cobertura.

REGRAS:
- Leia ANTES de modificar (read_file com faixa de linhas).
- Uma alteração por vez → verifique sintaxe → teste → próximo.
- Após cada edit_file/write_file: python -c "import ast; ast.parse(open('path').read())"
- Nunca quebre API pública (nomes de classes/métodos exportados).
- Backup automático: .py.bak criado antes de cada write.
- Se detectar regressão, reverta imediatamente.
- Ao final: rode python run_tests.py e corrija falhas.
- Relatório: lista de arquivos modificados + por quê + resultado dos testes.
"""

PROGRAM_VIA_PROMPT_PROMPT = """\
MODO PROGRAMAR VIA PROMPT — implemente tudo que o Mestre descreveu.

DIRETRIZES:
- Comece listando estrutura (list_files) para contexto.
- Implemente COMPLETO — não peça confirmação, execute.
- Se ambíguo, escolha a melhor interpretação.
- Crie estrutura completa quando necessário (pastas + arquivos + __init__).
- Após implementar: verifique sintaxe (run_python) + rode testes se existirem.
- Responda APENAS em português. Código: linguagem adequada.
- Ao final: resumo FALADO do que foi criado/modificado.
"""

CONTINUOUS_IMPROVE_PROMPT = """\
MODO MELHORIA CONTÍNUA — ciclo iterativo de auto-aprendizado.

VOCÊ DEVE:
1. Escolher UM ponto de melhoria da lista de tarefas pendentes.
2. Implementar a melhoria (edit/write com backup).
3. Verificar sintaxe (ast.parse).
4. Rodar testes (python run_tests.py) e corrigir falhas.
5. Se tudo OK → marcar como concluído e seguir para a próxima tarefa.
6. Se falhar → reverta (use .py.bak) e tente abordagem diferente.

REGRAS ESPECIAIS:
- Não repita tarefas já concluídas (verifique o histórico).
- Máximo 3 tentativas por tarefa antes de pular.
- Se todas as tarefas estiverem concluídas, gere novas tarefas
  analisando a codebase (code smells, TODOs, falta de testes, etc).
- Preserve compatibilidade — nunca quebre imports existentes.
- Contexto ilimitado: use read_file com faixa de linhas, não carregue tudo.
"""


# --------------------------------------------------------------------------- #
# Análise estática avançada
# --------------------------------------------------------------------------- #

def _scan_files(root: Path, exts: set[str] | None = None) -> list[Path]:
    """Lista arquivos de código fonte, ignorando ruído."""
    exts = exts or {".py"}
    skip = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode"}
    result = []
    for p in root.rglob("*"):
        if any(s in p.parts for s in skip):
            continue
        if p.suffix in exts and p.is_file():
            result.append(p)
    return sorted(result)


def analyze_codebase(root: Path | None = None) -> dict:
    """Análise estática completa: arquivos, funções, classes, linhas, issues."""
    root = root or BASE_DIR
    files = _scan_files(root)
    stats = {
        "total_files": len(files),
        "total_lines": 0,
        "total_functions": 0,
        "total_classes": 0,
        "files": [],
        "issues": [],
        "summary": {},
    }
    for fp in files:
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            lines = src.splitlines()
            stats["total_lines"] += len(lines)
            info = {"path": str(fp.relative_to(root)), "lines": len(lines), "issues": []}

            try:
                tree = ast.parse(src)
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                info["functions"] = len(funcs)
                info["classes"] = len(classes)
                stats["total_functions"] += len(funcs)
                stats["total_classes"] += len(classes)
            except SyntaxError as e:
                info["issues"].append(f"SyntaxError: line {e.lineno}: {e.msg}")
                stats["issues"].append(f"{info['path']}: SyntaxError L{e.lineno}")

            # code smells
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if len(line) > 120:
                    info["issues"].append(f"L{i}: linha longa ({len(line)} chars)")
                if "TODO" in line or "FIXME" in line or "HACK" in line:
                    info["issues"].append(f"L{i}: {stripped[:80]}")
                if "except:" in stripped and "Exception" not in stripped:
                    info["issues"].append(f"L{i}: except genérico (bare except)")
                if stripped.startswith("import ") and "* " in stripped:
                    info["issues"].append(f"L{i}: import * (evite)")

            # detecta funções muito grandes (>80 linhas)
            try:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        end = getattr(node, "end_lineno", 0) or 0
                        size = end - node.lineno
                        if size > 80:
                            info["issues"].append(
                                f"L{node.lineno}: função '{node.name}' muito longa ({size} linhas)")
            except Exception:
                pass

            stats["files"].append(info)
        except Exception:
            continue

    stats["summary"] = {
        "files": stats["total_files"],
        "lines": stats["total_lines"],
        "functions": stats["total_functions"],
        "classes": stats["total_classes"],
        "issues": len(stats["issues"]),
    }
    return stats


def suggest_improvements(stats: dict, completed: set[str] | None = None) -> list[str]:
    """Gera tarefas PRIORIZADAS de melhoria (nunca repete concluídas)."""
    completed = completed or set()
    tasks = []

    # 1) BUGS CRÍTICOS (prioridade máxima)
    for f in stats["files"]:
        for issue in f["issues"]:
            if "SyntaxError" in issue:
                task = f"Corrija o erro de sintaxe em {f['path']}: {issue}"
                if task not in completed:
                    tasks.append(task)

    # 2) SEGURANÇA
    for f in stats["files"]:
        for issue in f["issues"]:
            if "bare except" in issue:
                task = f"Corrija {issue} em {f['path']} (use except Exception)"
                if task not in completed:
                    tasks.append(task)
            if "import *" in issue:
                task = f"Corrija {issue} em {f['path']} (imports explícitos)"
                if task not in completed:
                    tasks.append(task)

    # 3) PERFORMANCE — funções gigantes
    for f in stats["files"]:
        for issue in f["issues"]:
            if "muito longa" in issue:
                task = f"Refatore {issue} em {f['path']}"
                if task not in completed:
                    tasks.append(task)

    # 4) REFATORAÇÃO — arquivos grandes
    for f in stats["files"]:
        if f["lines"] > 500:
            task = f"Refatore {f['path']} ({f['lines']} linhas) — divida em módulos"
            if task not in completed:
                tasks.append(task)

    # 5) CÓDIGO LIMPO
    long_lines = sum(1 for f in stats["files"] for i in f["issues"] if "linha longa" in i)
    if long_lines > 10:
        task = f"Corrija {long_lines} linhas >120 chars (PEP8)"
        if task not in completed:
            tasks.append(task)

    # 6) TODOS/FIXMEs
    todos = []
    for f in stats["files"]:
        for issue in f["issues"]:
            if "TODO" in issue or "FIXME" in issue:
                todos.append(f"{f['path']}: {issue}")
    if todos:
        task = "Resolva TODOs/FIXMEs: " + "; ".join(todos[:5])
        if task not in completed:
            tasks.append(task)

    # 7) TESTES
    untested = [f["path"] for f in stats["files"]
                if f["path"].endswith(".py") and "test" not in f["path"].lower()
                and not any(t in f["path"] for t in ["__init__", "app_tray", "gui_launcher"])]
    if untested:
        task = f"Crie testes unitários para: {', '.join(untested[:5])}"
        if task not in completed:
            tasks.append(task)

    return tasks


# --------------------------------------------------------------------------- #
# Motor de auto-programação v2
# --------------------------------------------------------------------------- #

class SelfImproverModule:
    """Motor de auto-programação: analisa, melhora e APRENDE continuamente."""
    BASE_DIR = BASE_DIR

    @classmethod
    def list_own_files(cls) -> list[str]:
        return [str(p.relative_to(cls.BASE_DIR)) for p in _scan_files(cls.BASE_DIR)]

    @classmethod
    def read_own_code(cls, rel_path: str) -> str:
        target = cls.BASE_DIR / rel_path
        if not target.exists():
            return f"[Aviso] Arquivo '{rel_path}' não existe no codebase."
        return target.read_text(encoding="utf-8")

    @classmethod
    def modify_own_code(cls, rel_path: str, new_code: str) -> str:
        target = cls.BASE_DIR / rel_path
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return (f"[Auto-Programação Bloqueada] Erro de sintaxe:\n"
                    f"Linha {e.lineno}: {e.msg}")
        try:
            backup = target.with_suffix(".py.bak")
            if target.exists():
                backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_code, encoding="utf-8")
            return (f"[Auto-Programação OK] '{rel_path}' atualizado. "
                    f"Backup: '{backup.name}'")
        except Exception as e:
            return f"[Erro] Falha ao modificar código: {e}"

    @classmethod
    def add_custom_skill(cls, skill_name: str, code_content: str) -> str:
        module_path = MODULES_DIR / f"{skill_name}.py"
        try:
            ast.parse(code_content)
            module_path.write_text(code_content, encoding="utf-8")
            return f"[Auto-Programação] Skill '{skill_name}' criada e compilada!"
        except SyntaxError as e:
            return f"[Erro de Sintaxe] Python inválido: {e}"

    @classmethod
    def get_analysis(cls, root: Path | None = None) -> dict:
        return analyze_codebase(root or cls.BASE_DIR)

    @classmethod
    def get_stats(cls) -> dict:
        """Retorna estatísticas de aprendizado (melhorias aplicadas, etc)."""
        history = _load_improve_history()
        return {
            "total_improvements": len(history),
            "successful": sum(1 for h in history if h.get("success")),
            "failed": sum(1 for h in history if not h.get("success")),
            "total_time": sum(h.get("elapsed", 0) for h in history),
            "recent": history[-5:] if history else [],
        }

    # ------------------------------------------------------------------ run

    @classmethod
    def run_self_improve(cls, llm, on_step=None, task: str | None = None,
                         max_steps: int = 24) -> tuple[str, str]:
        """Executa auto-programação via SmartCodeAgent.

        Se task é None: analisa codebase → gera tarefas → executa em loop.
        Se task é fornecida: executa essa tarefa específica.
        """
        from modules.smart_agent import SmartCodeAgent
        from modules.code_index import CodeIndex

        workspace = cls.BASE_DIR

        index = None
        try:
            index = CodeIndex(workspace, chunk_size=480, overlap=160, max_files=4000)
            index.build()
        except Exception:
            pass

        if not task:
            stats = analyze_codebase(workspace)
            completed = _get_completed_tasks()
            auto_tasks = suggest_improvements(stats, completed)
            if not auto_tasks:
                return ("A codebase está saudável, Mestre. "
                        "Todas as melhorias conhecidas já foram aplicadas.",
                        "Codebase saudável, sem melhorias pendentes.")
            task = ("Auto-melhoria: analise e corrija os seguintes pontos (priorizados).\n"
                    + "\n".join(f"{i+1}. {t}" for i, t in enumerate(auto_tasks[:10])))

        agent = SmartCodeAgent(
            llm=llm,
            workspace=workspace,
            on_step=on_step,
            max_tokens=0, # 0 = ilimitado (usa janela completa do provider)
            self_program=True,
            reasoning=True,
            index=index,
            system_prompt_extra=SELF_IMPROVE_PROMPT,
            max_steps=max_steps,
            adaptive_steps=True,
        )
        t0 = time.perf_counter()
        report, answer = agent.run(task)
        elapsed = time.perf_counter() - t0

        # registra sucesso/fracasso
        files_changed = [l.split("escrevi ")[-1].split("editei ")[-1]
                         for l in report.split("\n")
                         if any(k in l for k in ("escrevi", "editei", "apaguei"))]
        _record_improvement(task[:200], files_changed, bool(answer), elapsed)

        return report, answer

    # ------------------------------------------------ auto-start (proactive)

    @classmethod
    def on_autonomous_diagnostic(cls, health, llm=None, on_step=None):
        """Called by AutonomousEngine when health drops below threshold.

        This enables PROACTIVE self-improvement: the AI fixes issues
        without the Mestre asking.
        """
        if health is None or health.health_score >= 80:
            return  # health is fine, no intervention needed

        critical = [i for i in health.issues if i.severity == "critical"]
        if not critical:
            return  # only warnings/info, not urgent

        # Check if we already tried to fix these recently
        recent = _get_recent_failures(hours=6)
        recent_targets = {f.get("target", "") for f in recent}

        new_issues = [i for i in critical
                      if i.file not in recent_targets]
        if not new_issues:
            return  # already tried and failed

        task = ("Auto-melhoria PROATIVA: a diagnose do sistema detectou "
                f"{len(new_issues)} problemas críticos. Corrija:\n"
                + "\n".join(f"- {i.file}:{i.line} — {i.message}"
                              for i in new_issues[:5]))

        if llm is not None:
            cls.run_self_improve(llm, on_step=on_step, task=task, max_steps=12)

    @classmethod
    def stop_continuous(cls):
        """Para o loop de melhoria contínuo."""
        _stop_continuous.set()

    @classmethod
    def run_continuous(cls, llm, on_step=None, rounds: int = 5,
                       max_steps_per_round: int = 20) -> tuple[str, str]:
        """Loop CONTÍNUO de melhoria: executa N rodadas de auto-aprendizado.

        Cada rodada: analisa → escolhe melhorias → aplica → verifica → próximo.
        Roda indefinidamente se rounds=0.
        Use stop_continuous() para interromper.
        """
        from modules.smart_agent import SmartCodeAgent
        from modules.code_index import CodeIndex

        _stop_continuous.clear()
        workspace = cls.BASE_DIR
        all_reports = []
        total_improved = 0

        for round_num in range(1, rounds + 1) if rounds > 0 else iter(int, 1):
            if _stop_continuous.is_set():
                all_reports.append("Interrompido pelo Mestre.")
                break
            index = None
            try:
                index = CodeIndex(workspace, chunk_size=480, overlap=160, max_files=4000)
                index.build()
            except Exception:
                pass

            stats = analyze_codebase(workspace)
            completed = _get_completed_tasks()
            tasks = suggest_improvements(stats, completed)

            if not tasks:
                all_reports.append(f"Rodada {round_num}: codebase saudável, sem tarefas pendentes.")
                break

            task = tasks[0] # pega a mais prioritária
            if on_step:
                on_step(f" Rodada {round_num}/{rounds or '∞'}: {task}\n")

            agent = SmartCodeAgent(
                llm=llm,
                workspace=workspace,
                on_step=on_step,
                max_tokens=0,
                self_program=True,
                reasoning=True,
                index=index,
                system_prompt_extra=CONTINUOUS_IMPROVE_PROMPT,
                max_steps=max_steps_per_round,
                adaptive_steps=True,
            )

            t0 = time.perf_counter()
            report, answer = agent.run(task)
            elapsed = time.perf_counter() - t0

            success = bool(answer and "ERRO" not in answer.upper()[:50])
            files_changed = [l.split("escrevi ")[-1].split("editei ")[-1]
                             for l in report.split("\n")
                             if any(k in l for k in ("escrevi", "editei", "apaguei"))]
            _record_improvement(task[:200], files_changed, success, elapsed)

            if success:
                total_improved += 1
            all_reports.append(f"Rodada {round_num}: {task[:80]}... → {'' if success else ''}")

        summary = (f" MELHORIA CONTÍNUA: {total_improved} melhorias aplicadas em "
                   f"{round_num} rodadas.\n\n" + "\n".join(all_reports))
        return summary, summary

    @classmethod
    def run_prompt(cls, llm, prompt: str, on_step=None,
                   max_steps: int = 24) -> tuple[str, str]:
        """Modo 'programar via prompt': o Mestre descreve em linguagem natural."""
        from modules.smart_agent import SmartCodeAgent
        from modules.code_index import CodeIndex

        workspace = cls.BASE_DIR

        index = None
        try:
            index = CodeIndex(workspace, chunk_size=480, overlap=160, max_files=4000)
            index.build()
        except Exception:
            pass

        agent = SmartCodeAgent(
            llm=llm,
            workspace=workspace,
            on_step=on_step,
            max_tokens=0,
            self_program=True,
            reasoning=True,
            index=index,
            system_prompt_extra=PROGRAM_VIA_PROMPT_PROMPT,
            max_steps=max_steps,
            adaptive_steps=True,
        )

        t0 = time.perf_counter()
        report, answer = agent.run(prompt)
        elapsed = time.perf_counter() - t0

        files_changed = [l.split("escrevi ")[-1].split("editei ")[-1]
                         for l in report.split("\n")
                         if any(k in l for k in ("escrevi", "editei", "apaguei"))]
        _record_improvement(f"prompt: {prompt[:100]}", files_changed, bool(answer), elapsed)

        return report, answer
