"""
Elivea — Autonomous Task Planner
========================================
Planejador autônomo que:
  • Decompõe metas complexas em passos executáveis
  • Rastreia progresso e adapta o plano
  • Aprende com tarefas concluídas
  • Pode ser acionado por voz, chat ou programação
  • Gera relatórios de progresso em tempo real
"""

from __future__ import annotations

import json
import os
import time
import threading
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("elvea.planner")

MEMORY_DIR = Path(__file__).resolve().parent.parent / "config" / "planner_memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    dependencies: list[int] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class TaskPlan:
    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    context: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    success: bool = False
    total_tokens_used: int = 0


class AutonomousPlanner:
    """Planejador autônomo de tarefas multi-etapa."""

    PLAN_PROMPT = """Você é a Elívea, um planejador autônomo de tarefas.
Decomponha a meta em passos concretos, executáveis e ordenados.

META: {goal}
CONTEXTO: {context}

Retorne EXATAMENTE neste formato (um passo por linha):
PASSO_1: [descrição concreta e acionável]
PASSO_2: [descrição concreta e acionável]
...
DEPENDENCIAS: [opcional: formato PASSO_X depende de PASSO_Y,PASSO_Z; ...]

Regras:
- Cada passo deve ser auto-contido e verificável
- Máximo 15 passos
- Se um passo falhar, o plano deve poder continuar
- Inclua verificação de sucesso quando possível
- Não inclua passos vagos como "verificar" sem critério concreto"""

    PROGRESS_PROMPT = """Analise o progresso desta tarefa e sugira adaptações:
META ORIGINAL: {goal}
PASSOS FEITOS:
{completed}
PASSOS PENDENTES:
{pending}
ERROS:
{errors}

Responda em JSON:
{{"should_continue": true/false, "adaptations": ["mudança sugerida"], "confidence": 0.0-1.0}}"""

    def __init__(self, llm=None):
        self.llm = llm
        self._plans: list[TaskPlan] = []
        self._current_plan: TaskPlan | None = None
        self._lock = threading.Lock()
        self._progress_callback: Callable[[str, str], None] | None = None
        self._load_history()

    # ---- Public API ----

    def plan(self, goal: str, context: str = "") -> TaskPlan:
        """Cria um plano a partir de uma meta."""
        plan = TaskPlan(goal=goal, context=context)

        if self.llm:
            try:
                prompt = self.PLAN_PROMPT.format(goal=goal, context=context or "Nenhum")
                response = self._call_llm(prompt)
                plan.steps = self._parse_steps(response)
                plan.context = context
            except Exception as e:
                logger.error(f"Erro ao planejar: {e}")
                plan.steps = [TaskStep(id=1, description=f"Erro ao gerar plano: {e}")]
        else:
            plan.steps = [TaskStep(id=1, description=f"Meta: {goal}")]

        with self._lock:
            self._plans.append(plan)
            self._current_plan = plan
        self._save_history()
        return plan

    def execute_plan(self, plan: TaskPlan, executor: Callable[[TaskStep], str] | None = None) -> TaskPlan:
        """Executa um plano passo a passo."""
        for step in plan.steps:
            if step.status in (StepStatus.DONE, StepStatus.SKIPPED):
                continue

            # Check dependencies
            if step.dependencies:
                all_deps_met = all(
                    any(s.id == dep and s.status == StepStatus.DONE for s in plan.steps)
                    for dep in step.dependencies
                )
                if not all_deps_met:
                    step.status = StepStatus.SKIPPED
                    step.result = "Dependências não atendidas"
                    continue

            step.status = StepStatus.RUNNING
            step.started_at = time.time()
            self._notify_progress("step_start", step.description)

            try:
                if executor:
                    result = executor(step)
                    step.result = result or ""
                    step.status = StepStatus.DONE
                else:
                    step.result = "Executor não configurado"
                    step.status = StepStatus.SKIPPED
            except Exception as e:
                step.error = str(e)
                step.status = StepStatus.FAILED
                logger.error(f"Step {step.id} failed: {e}")
            finally:
                step.finished_at = time.time()

            self._notify_progress("step_done", f"[{step.status.value}] {step.description}")

        # Evaluate completion
        done = sum(1 for s in plan.steps if s.status == StepStatus.DONE)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        plan.completed_at = time.time()
        plan.success = done > 0 and failed == 0

        self._notify_progress("plan_done",
            f"Plano concluído: {done}/{len(plan.steps)} passos OK, {failed} falhas")
        self._save_history()
        return plan

    def adapt_plan(self, plan: TaskPlan) -> TaskPlan:
        """Adapta um plano baseado no progresso atual (usa LLM)."""
        if not self.llm or not plan.steps:
            return plan

        completed = "\n".join(
            f" PASSO_{s.id}: {s.description} → {s.status.value}: {s.result[:100]}"
            for s in plan.steps if s.status in (StepStatus.DONE, StepStatus.FAILED)
        ) or " Nenhum"

        pending = "\n".join(
            f" PASSO_{s.id}: {s.description}"
            for s in plan.steps if s.status == StepStatus.PENDING
        ) or " Nenhum"

        errors = "\n".join(
            f" PASSO_{s.id}: {s.error}"
            for s in plan.steps if s.status == StepStatus.FAILED
        ) or " Nenhum"

        prompt = self.PROGRESS_PROMPT.format(
            goal=plan.goal, completed=completed, pending=pending, errors=errors
        )

        try:
            response = self._call_llm(prompt)
            adaptations = self._parse_adaptations(response)
            if adaptations:
                self._notify_progress("adapt", "; ".join(adaptations))
        except Exception as e:
            logger.error(f"Erro ao adaptar plano: {e}")

        return plan

    def get_status(self) -> str:
        """Retorna status do plano atual."""
        plan = self._current_plan
        if not plan:
            return "Nenhum plano ativo."

        done = sum(1 for s in plan.steps if s.status == StepStatus.DONE)
        total = len(plan.steps)
        running = sum(1 for s in plan.steps if s.status == StepStatus.RUNNING)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)

        lines = [f"Meta: {plan.goal}", f"Progresso: {done}/{total} passos concluídos"]
        if running:
            lines.append(f"Executando: {running} passo(s)")
        if failed:
            lines.append(f"Falhas: {failed}")

        for s in plan.steps:
            icon = {"done": "", "failed": "", "running": "", "pending": "", "skipped": "—"}
            lines.append(f" {icon.get(s.status.value, '?')} {s.description[:80]}")

        return "\n".join(lines)

    def get_history(self, limit: int = 5) -> list[TaskPlan]:
        return self._plans[-limit:]

    def set_progress_callback(self, callback: Callable[[str, str], None]):
        self._progress_callback = callback

    # ---- Internal ----

    def _call_llm(self, prompt: str) -> str:
        if hasattr(self.llm, 'generate'):
            return self.llm.generate(prompt)
        elif callable(self.llm):
            return self.llm(prompt)
        return ""

    def _parse_steps(self, response: str) -> list[TaskStep]:
        steps = []
        dependencies = {}
        for line in response.strip().splitlines():
            line = line.strip()
            if line.upper().startswith("PASSO_"):
                try:
                    parts = line.split(":", 1)
                    num = int(parts[0].split("_")[1])
                    desc = parts[1].strip() if len(parts) > 1 else ""
                    steps.append(TaskStep(id=num, description=desc))
                except (ValueError, IndexError):
                    pass
            elif line.upper().startswith("DEPENDENCIAS:"):
                dep_text = line.split(":", 1)[1].strip()
                for dep_part in dep_text.split(";"):
                    dep_part = dep_part.strip()
                    if "depende de" in dep_part.lower():
                        try:
                            src = int(dep_part.split("PASSO_")[1].split("_")[0].split()[0])
                            deps = [int(d.strip().replace("PASSO_", ""))
                                    for d in dep_part.split("PASSO_")[2:]]
                            dependencies[src] = deps
                        except (ValueError, IndexError):
                            pass

        for step in steps:
            if step.id in dependencies:
                step.dependencies = dependencies[step.id]

        return steps

    def _parse_adaptations(self, response: str) -> list[str]:
        try:
            data = json.loads(response)
            return data.get("adaptations", [])
        except (json.JSONDecodeError, AttributeError):
            pass
        # Fallback: extract lines
        return [line.strip("- ").strip()
                for line in response.splitlines()
                if line.strip().startswith("-")]

    def _notify_progress(self, event: str, message: str):
        if self._progress_callback:
            try:
                self._progress_callback(event, message)
            except Exception:
                pass
        logger.info(f"[Planner] {event}: {message}")

    def _save_history(self):
        try:
            path = MEMORY_DIR / "plans.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                for plan in self._plans[-1:]:
                    data = {
                        "goal": plan.goal,
                        "steps": len(plan.steps),
                        "success": plan.success,
                        "completed": plan.completed_at > 0,
                        "at": plan.created_at,
                    }
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_history(self):
        path = MEMORY_DIR / "plans.jsonl"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            json.loads(line)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
