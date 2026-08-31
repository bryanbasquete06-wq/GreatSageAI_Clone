#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Recovery System
===================================
Handles error analysis, checkpoint rollback, replanning, and retry logic.
Ensures the agent never leaves the project in a broken state.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from core.agent.models import (
    Plan, PlanStep, StepStatus, ExecutionResult,
    Checkpoint, ErrorCategory, AgentPhase, Lesson,
)

logger = logging.getLogger("elvea.agent.recovery")


# Error recovery strategies per category
_RECOVERY_STRATEGIES: Dict[ErrorCategory, Dict] = {
    ErrorCategory.SYNTAX: {
        "action": "retry_with_fix",
        "max_retries": 2,
        "hint": "Fix the syntax error in the generated code",
    },
    ErrorCategory.RUNTIME: {
        "action": "retry_with_fix",
        "max_retries": 2,
        "hint": "Analyze the traceback and fix the runtime error",
    },
    ErrorCategory.TEST_FAILURE: {
        "action": "retry_with_fix",
        "max_retries": 2,
        "hint": "Fix the failing tests",
    },
    ErrorCategory.DEPENDENCY: {
        "action": "install_deps_then_retry",
        "max_retries": 1,
        "hint": "Install missing dependencies first",
    },
    ErrorCategory.CONFIG: {
        "action": "retry_with_fix",
        "max_retries": 1,
        "hint": "Fix the configuration issue",
    },
    ErrorCategory.TIMEOUT: {
        "action": "retry_with_longer_timeout",
        "max_retries": 1,
        "hint": "Increase timeout or simplify the operation",
    },
    ErrorCategory.PERMISSION: {
        "action": "skip_or_ask_user",
        "max_retries": 0,
        "hint": "Permission denied — may need user intervention",
    },
    ErrorCategory.UNKNOWN: {
        "action": "retry_once",
        "max_retries": 1,
        "hint": "Unknown error, retry once",
    },
}


class RecoverySystem:
    """Manages error recovery, rollback, and replanning."""

    def __init__(self, executor=None, planner=None):
        self._executor = executor
        self._planner = planner
        self._error_history: List[Tuple[int, str, ErrorCategory]] = []
        self._lessons: List[Lesson] = []

    def set_dependencies(self, executor, planner):
        self._executor = executor
        self._planner = planner

    def analyze_failure(
        self, step: PlanStep, result: ExecutionResult, plan: Plan
    ) -> Dict[str, any]:
        """
        Analyze a failure and determine the best recovery action.
        Returns a dict with: action, should_retry, should_replan, should_rollback, message
        """
        error_text = result.error or ""
        category = result.error_category or ErrorCategory.UNKNOWN
        strategy = _RECOVERY_STRATEGIES.get(category, _RECOVERY_STRATEGIES[ErrorCategory.UNKNOWN])

        self._error_history.append((step.id, error_text, category))

        logger.info(f"Analyzing failure: step={step.id}, category={category.value}")

        # Check if we've seen this exact error before
        similar_count = sum(
            1 for _, e, c in self._error_history
            if c == category and e[:50] == error_text[:50]
        )

        # Determine recovery action
        should_retry = (
            step.retry_count < step.max_retries
            and strategy["max_retries"] > 0
            and similar_count <= strategy["max_retries"]
        )

        # If too many similar errors, replan
        should_replan = (
            similar_count > strategy["max_retries"]
            or step.retry_count >= step.max_retries
            or len(self._error_history) >= 5
        )

        # Rollback if we have a checkpoint and replanning
        should_rollback = should_replan

        # Record lesson
        lesson = Lesson(
            pattern=f"Step {step.id} failed with {category.value}: {error_text[:100]}",
            action=strategy["action"],
            outcome="retry" if should_retry else "replan" if should_replan else "skip",
            category=category.value,
            confidence=0.7,
        )
        self._lessons.append(lesson)

        return {
            "action": strategy["action"],
            "should_retry": should_retry,
            "should_replan": should_replan,
            "should_rollback": should_rollback,
            "should_skip": not should_retry and not should_replan,
            "message": strategy["hint"],
            "error_category": category,
            "similar_errors": similar_count,
        }

    def prepare_retry(
        self, step: PlanStep, analysis: Dict, llm_engine=None
    ) -> PlanStep:
        """
        Prepare a step for retry — modify params based on error analysis.
        Returns a new (modified) step for retry.
        """
        step.retry_count += 1
        action = analysis.get("action", "retry_once")
        category = analysis.get("error_category", ErrorCategory.UNKNOWN)

        if action == "install_deps_then_retry":
            # Prepend dependency installation
            step.params["_pre_install"] = True

        elif action == "retry_with_fix":
            # Mark step as needing code fix
            step.params["_fix_error"] = True
            step.params["_error_context"] = analysis.get("message", "")

        elif action == "retry_with_longer_timeout":
            step.params["timeout"] = step.params.get("timeout", 120) * 2

        logger.info(f"Prepared retry for step {step.id} (attempt {step.retry_count})")
        return step

    def should_replan(
        self, plan: Plan, max_failures: int = 3
    ) -> bool:
        """Determine if the plan should be scrapped and regenerated."""
        failed = plan.failed_steps
        if failed >= max_failures:
            return True
        if plan.has_failures and plan.completed_steps > 0:
            # If more than 50% failed, replan
            if failed > plan.completed_steps:
                return True
        return False

    def get_fix_prompt(
        self, step: PlanStep, error: str, category: ErrorCategory
    ) -> str:
        """Generate a prompt to fix the failed step's code."""
        current_code = step.params.get("content", "")
        language = step.params.get("language", "python")

        return (
            f"The following {language} code has a {category.value} error.\n"
            f"Fix the error and return the corrected complete code.\n\n"
            f"DESCRIPTION: {step.description}\n\n"
            f"CURRENT CODE:\n```{language}\n{current_code}\n```\n\n"
            f"ERROR:\n{error[:500]}\n\n"
            f"Return ONLY the fixed code, no explanations."
        )

    def get_error_summary(self) -> str:
        """Get a summary of all errors encountered."""
        if not self._error_history:
            return "No errors encountered"

        by_category = {}
        for _, error, cat in self._error_history:
            by_category.setdefault(cat.value, []).append(error[:80])

        parts = [f"Total errors: {len(self._error_history)}"]
        for cat, errors in by_category.items():
            parts.append(f"  {cat}: {len(errors)} occurrences")
            for e in errors[:2]:
                parts.append(f"    - {e}")
        return "\n".join(parts)

    def get_lessons(self) -> List[Lesson]:
        """Get accumulated lessons from errors."""
        return list(self._lessons)

    def reset(self):
        """Reset recovery state for a new plan."""
        self._error_history.clear()
        self._lessons.clear()
