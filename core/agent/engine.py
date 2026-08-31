#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Main Engine
===============================
State machine orchestrator that coordinates planning, execution,
quality gates, recovery, and user collaboration into a seamless
autonomous engineering loop.
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from core.agent.models import (
    AgentPhase, Plan, PlanStep, StepStatus, ExecutionResult,
    Checkpoint, DecisionPoint, Lesson, PlanStrategy,
)
from core.agent.planner import PlanGenerator
from core.agent.executor import StepExecutor, classify_error
from core.agent.gates import QualityGates, QualityReport
from core.agent.recovery import RecoverySystem

logger = logging.getLogger("elvea.agent.engine")


class AgentEngine:
    """
    The autonomous engineering agent.
    
    Orchestrates the full lifecycle:
    1. ANALYZING  — understand the goal
    2. PLANNING   — generate multiple plans
    3. PRESENTING — show plans to user (or auto-select)
    4. EXECUTING  — run steps with quality gates
    5. TESTING    — validate after each step
    6. RECOVERING — handle errors, retry, rollback, replan
    7. DONE       — deliver results
    """

    def __init__(
        self,
        project_root: str = ".",
        llm_engine=None,
        on_progress: Optional[Callable] = None,
        on_decision: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
    ):
        self.project_root = project_root
        self._llm = llm_engine

        # Callbacks for UI integration
        self._on_progress = on_progress
        self._on_decision = on_decision
        self._on_log = on_log

        # Sub-systems
        self.planner = PlanGenerator(llm_engine)
        self.executor = StepExecutor(project_root, llm_engine)
        self.gates = QualityGates(project_root)
        self.recovery = RecoverySystem(self.executor, self.planner)

        # State
        self._phase = AgentPhase.IDLE
        self._plans: List[Plan] = []
        self._selected_plan: Optional[Plan] = None
        self._checkpoints: List[Checkpoint] = []
        self._lessons: List[Lesson] = []
        self._start_time: float = 0.0
        self._total_tokens: int = 0
        self._lock = threading.Lock()

        # Config
        self.max_replans = 3
        self.max_retries_per_step = 3
        self.quality_gates_enabled = True
        self.auto_select_plan = True

    @property
    def phase(self) -> AgentPhase:
        return self._phase

    @property
    def plan(self) -> Optional[Plan]:
        return self._selected_plan

    @property
    def progress(self) -> Dict[str, Any]:
        p = self._selected_plan
        return {
            "phase": self._phase.value,
            "goal": self._selected_plan.goal if p else "",
            "progress_pct": p.progress_pct if p else 0,
            "completed": p.completed_steps if p else 0,
            "total": p.total_steps if p else 0,
            "failed": p.failed_steps if p else 0,
            "elapsed": time.time() - self._start_time if self._start_time else 0,
            "confidence": self._calc_confidence(),
        }

    def set_llm(self, llm_engine):
        """Set or update the LLM engine."""
        self._llm = llm_engine
        self.planner.set_llm(llm_engine)
        self.executor.set_llm(llm_engine)

    # ═══════════════════════════════════════════════════════════════════
    # MAIN EXECUTION LOOP
    # ═══════════════════════════════════════════════════════════════════

    def run(
        self,
        goal: str,
        context: str = "",
        strategy: PlanStrategy = PlanStrategy.BALANCED,
    ) -> Dict[str, Any]:
        """
        Main entry point. Takes a goal and runs the full autonomous loop.
        Returns a result dict with success, output, metrics.
        """
        self._start_time = time.time()
        self.recovery.reset()
        self._log(f"🎯 Agent started: {goal[:100]}")

        try:
            # Phase 1: PLANNING
            self._set_phase(AgentPhase.PLANNING)
            plans = self.planner.generate_plans(goal, context, strategy)
            self._plans = plans

            if not plans:
                self._set_phase(AgentPhase.FAILED)
                return self._make_result(success=False, error="Could not generate any valid plans")

            # Phase 2: SELECT PLAN
            self._set_phase(AgentPhase.PRESENTING)
            selected = self.planner.select_best_plan(plans, strategy)

            if not self.auto_select_plan and self._on_decision:
                decision = self.planner.create_decision_point(plans)
                selected_idx = self._on_decision(decision)
                if selected_idx is not None and 0 <= selected_idx < len(plans):
                    selected = plans[selected_idx]

            self._selected_plan = selected
            self._log(f"📋 Plan selected: {selected.strategy.value} ({selected.total_steps} steps)")

            # Phase 3: EXECUTE
            self._set_phase(AgentPhase.EXECUTING)
            result = self._execute_plan(selected)

            # Phase 4: DONE
            success = not selected.has_failures
            self._set_phase(AgentPhase.DONE if success else AgentPhase.FAILED)

            final_result = self._make_result(
                success=success,
                output=f"Completed {selected.completed_steps}/{selected.total_steps} steps",
            )
            self._log(f"{'✅' if success else '❌'} Agent finished: {final_result['elapsed']:.1f}s")
            return final_result

        except Exception as e:
            self._set_phase(AgentPhase.FAILED)
            logger.error(f"Agent crashed: {e}", exc_info=True)
            return self._make_result(success=False, error=str(e))

    def _execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """Execute all steps in a plan with quality gates and recovery."""
        replan_count = 0

        while not plan.is_complete:
            # Get next runnable step
            step = plan.get_next_runnable()
            if step is None:
                if plan.has_failures:
                    # Check if we should replan
                    if replan_count < self.max_replans and self.recovery.should_replan(plan):
                        self._log("🔄 Replanning due to failures...")
                        self._set_phase(AgentPhase.REPLANING)
                        plan = self._try_replan(plan)
                        replan_count += 1
                        self._set_phase(AgentPhase.EXECUTING)
                        continue
                    else:
                        break  # Can't proceed, done with failures
                else:
                    break  # All steps done

            # Execute the step
            self._log(f"⚡ Step {step.id}/{plan.total_steps}: {step.description[:60]}")
            result = self.executor.execute_step(step)

            # Create checkpoint on success
            if result.success and self.executor._git_enabled:
                commit = self.executor.create_git_checkpoint(step)
                if commit:
                    self._checkpoints.append(Checkpoint(
                        commit_hash=commit,
                        step_id=step.id,
                        description=step.description,
                    ))

            # Quality gates on success
            if result.success and self.quality_gates_enabled and result.files_changed:
                self._set_phase(AgentPhase.TESTING)
                self._log(f"🔍 Running quality gates on {len(result.files_changed)} files...")
                report = self.gates.validate_all(result.files_changed)

                if not report.all_passed:
                    self._log(f"⚠️ Quality gates failed: {report.total_issues} issues")
                    # Treat quality gate failure as step failure
                    result = ExecutionResult(
                        success=False,
                        error=f"Quality gates failed: {'; '.join(report.blocking_issues[:3])}",
                        error_category=classify_error(str(report.blocking_issues)),
                    )
                    step.complete(result)

                self._set_phase(AgentPhase.EXECUTING)

            # Handle failure
            if not result.success:
                self._set_phase(AgentPhase.RECOVERING)
                analysis = self.recovery.analyze_failure(step, result, plan)
                self._log(f"🔧 Recovery: {analysis['action']} ({analysis['message']})")

                if analysis["should_retry"]:
                    self.recovery.prepare_retry(step, analysis, self._llm)
                    # If error was in code, try to fix via LLM
                    if analysis["action"] == "retry_with_fix" and self._llm:
                        self._fix_step_code(step, result)
                    self._set_phase(AgentPhase.EXECUTING)
                    continue

                elif analysis["should_replan"]:
                    # Already handled above
                    continue

                else:
                    # Skip the step
                    self._log(f"⏭️ Skipping step {step.id}")
                    step.skip(f"Skipped after failure: {analysis['message']}")

            # Record lesson on success
            if result.success:
                lesson = Lesson(
                    pattern=f"Step {step.id} ({step.action.value}) succeeded",
                    action="executed",
                    outcome="success",
                    category="execution",
                    confidence=step.confidence,
                )
                self._lessons.append(lesson)

            self._emit_progress()

        return {
            "success": not plan.has_failures,
            "completed": plan.completed_steps,
            "total": plan.total_steps,
        }

    def _try_replan(self, failed_plan: Plan) -> Plan:
        """Attempt to generate a new plan accounting for failures."""
        failed_step = failed_plan.get_failed_steps()
        error_text = ""
        error_cat = "unknown"
        if failed_step:
            r = failed_step[0].result
            if r:
                error_text = r.error or ""
                error_cat = r.error_category.value if r.error_category else "unknown"

        new_plan = self.planner.generate_replan(
            goal=failed_plan.goal,
            failed_plan=failed_plan,
            error=error_text,
            error_category=error_cat,
            lessons=[l.pattern for l in self._lessons],
        )

        if new_plan and new_plan.steps:
            new_plan.goal = failed_plan.goal
            return new_plan

        # If replanning fails, return original plan (will mark as failed)
        return failed_plan

    def _fix_step_code(self, step: PlanStep, failed_result: ExecutionResult):
        """Use LLM to fix code that caused an error."""
        if not self._llm:
            return

        category = failed_result.error_category or classify_error(failed_result.error or "")
        prompt = self.recovery.get_fix_prompt(step, failed_result.error or "", category)

        try:
            if hasattr(self._llm, 'chat'):
                resp = self._llm.chat(
                    [{"role": "user", "content": prompt}],
                    system="You are an expert debugger. Output only the fixed code.",
                    max_tokens=4096,
                )
                if resp.success:
                    # Extract code from response
                    import re
                    code = resp.text
                    match = re.search(r'```(?:\w+)?\n(.*?)```', code, re.DOTALL)
                    if match:
                        code = match.group(1)
                    step.params["content"] = code.strip()
                    self._log(f"🔧 Code fixed via LLM for step {step.id}")
        except Exception as e:
            logger.error(f"LLM fix failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # STATE & PROGRESS
    # ═══════════════════════════════════════════════════════════════════

    def _set_phase(self, phase: AgentPhase):
        with self._lock:
            self._phase = phase
        self._emit_progress()

    def _calc_confidence(self) -> float:
        """Calculate current confidence based on success rate."""
        plan = self._selected_plan
        if not plan or not plan.steps:
            return 0.0
        completed = [s for s in plan.steps if s.status == StepStatus.COMPLETED]
        total = [s for s in plan.steps if s.status != StepStatus.PENDING]
        if not total:
            return 0.8  # initial confidence
        success_rate = len(completed) / len(total)
        return round(success_rate, 2)

    def _emit_progress(self):
        """Emit progress update to UI callback."""
        if self._on_progress:
            try:
                self._on_progress(self.progress)
            except Exception:
                pass

    def _log(self, message: str):
        """Log a message and emit to UI callback."""
        logger.info(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _make_result(
        self, success: bool = True, output: str = "", error: str = ""
    ) -> Dict[str, Any]:
        """Build the final result dict."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        plan = self._selected_plan
        return {
            "success": success,
            "output": output,
            "error": error,
            "elapsed_seconds": round(elapsed, 2),
            "steps_completed": plan.completed_steps if plan else 0,
            "steps_total": plan.total_steps if plan else 0,
            "steps_failed": plan.failed_steps if plan else 0,
            "replans": self.max_replans,
            "lessons_count": len(self._lessons),
            "checkpoints": len(self._checkpoints),
            "confidence": self._calc_confidence(),
            "phase": self._phase.value,
        }

    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "phase": self._phase.value,
            "progress": self.progress,
            "plans_generated": len(self._plans),
            "checkpoints": len(self._checkpoints),
            "lessons": len(self._lessons),
            "error_summary": self.recovery.get_error_summary(),
        }

    def get_plan_summary(self) -> str:
        """Get a formatted summary of the current plan."""
        plan = self._selected_plan
        if not plan:
            return "No plan selected"

        lines = [
            f"Plan: {plan.goal[:80]}",
            f"Strategy: {plan.strategy.value}",
            f"Steps: {plan.total_steps} ({plan.completed_steps} completed)",
            f"Confidence: {self._calc_confidence():.0%}",
            "",
        ]
        for step in plan.steps:
            icon = {"completed": "✅", "failed": "❌", "running": "🔄",
                    "pending": "⏳", "skipped": "⏭️"}.get(step.status.value, "?")
            lines.append(f"  {icon} Step {step.id}: {step.description[:60]}")

        return "\n".join(lines)

    def get_lessons_learned(self) -> List[str]:
        """Get formatted lessons from this session."""
        return [f"[{l.category}] {l.pattern} → {l.outcome}" for l in self._lessons]

    def cancel(self):
        """Cancel the current execution."""
        self._set_phase(AgentPhase.IDLE)
        self._log("⛔ Agent cancelled by user")
