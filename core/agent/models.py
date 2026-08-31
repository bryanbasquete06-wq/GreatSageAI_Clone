#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Data Models
==============================
All data structures for the autonomous engineering system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class StepAction(Enum):
    """Types of actions a plan step can perform."""
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_COMMAND = "run_command"
    RUN_TESTS = "run_tests"
    CREATE_DIR = "create_dir"
    WRITE_CONFIG = "write_config"
    INSTALL_DEPS = "install_deps"
    CUSTOM = "custom"


class StepStatus(Enum):
    """Execution status of a plan step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLING_BACK = "rolling_back"
    WAITING_INPUT = "waiting_input"


class AgentPhase(Enum):
    """Current phase of the agent engine."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    PRESENTING = "presenting"
    EXECUTING = "executing"
    TESTING = "testing"
    RECOVERING = "recovering"
    REPLANING = "replaning"
    COLLABORATING = "collaborating"
    DONE = "done"
    FAILED = "failed"


class PlanStrategy(Enum):
    """Strategy used to generate a plan."""
    SPEED = "speed"           # Fastest delivery, minimal tests
    QUALITY = "quality"       # Best code, full test coverage
    BALANCED = "balanced"     # Good trade-off
    LEARNING = "learning"     # Maximize learning, document everything


class ErrorCategory(Enum):
    """Classification of execution errors."""
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    TEST_FAILURE = "test_failure"
    DEPENDENCY = "dependency"
    CONFIG = "config"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# Core Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionResult:
    """Result of executing a single step."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    duration_ms: float = 0.0
    files_changed: List[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_total: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tests_ok(self) -> bool:
        return self.tests_total == 0 or self.tests_passed == self.tests_total


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: int
    description: str
    action: StepAction
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[ExecutionResult] = None
    confidence: float = 0.8
    retry_count: int = 0
    max_retries: int = 3
    rollback_info: Optional[Dict[str, Any]] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (StepStatus.COMPLETED, StepStatus.FAILED,
                               StepStatus.SKIPPED)

    @property
    def can_retry(self) -> bool:
        return self.status == StepStatus.FAILED and self.retry_count < self.max_retries

    def start(self):
        self.status = StepStatus.RUNNING
        self.result = None

    def complete(self, result: ExecutionResult):
        self.result = result
        self.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED

    def skip(self, reason: str = ""):
        self.status = StepStatus.SKIPPED
        self.result = ExecutionResult(success=True, output=f"Skipped: {reason}")


@dataclass
class Plan:
    """A complete execution plan with multiple steps."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str = ""
    description: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    strategy: PlanStrategy = PlanStrategy.BALANCED
    estimated_seconds: int = 0
    tradeoffs: Dict[str, str] = field(default_factory=dict)
    score: float = 0.0
    created_at: float = field(default_factory=time.time)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100

    @property
    def is_complete(self) -> bool:
        return all(s.is_terminal for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def get_next_runnable(self) -> Optional[PlanStep]:
        """Get the next step that can be executed (all deps met)."""
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        skipped_ids = {s.id for s in self.steps if s.status == StepStatus.SKIPPED}
        done_ids = completed_ids | skipped_ids
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep in done_ids for dep in step.dependencies):
                return step
        return None

    def get_failed_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]


@dataclass
class DecisionPoint:
    """A point where user input is needed."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    question: str = ""
    options: List[Dict[str, str]] = field(default_factory=list)
    context: str = ""
    recommended: int = 0  # index of recommended option
    timeout_seconds: int = 30
    auto_select: bool = True  # if True, picks recommended after timeout
    selected: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Checkpoint:
    """A git checkpoint for rollback."""
    commit_hash: str = ""
    step_id: int = -1
    description: str = ""
    files_snapshot: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Lesson:
    """A lesson learned from execution."""
    pattern: str = ""           # what was observed
    action: str = ""            # what was done about it
    outcome: str = ""           # what happened
    category: str = ""          # "error", "optimization", "preference"
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentState:
    """Complete state of the autonomous agent."""
    phase: AgentPhase = AgentPhase.IDLE
    goal: str = ""
    plans: List[Plan] = field(default_factory=list)
    selected_plan: Optional[Plan] = None
    current_step_index: int = 0
    checkpoints: List[Checkpoint] = field(default_factory=list)
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)
    decisions_pending: List[DecisionPoint] = field(default_factory=list)
    lessons: List[Lesson] = field(default_factory=list)
    total_tokens_used: int = 0
    total_time_ms: float = 0.0
    start_time: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time == 0:
            return 0.0
        return time.time() - self.start_time

    @property
    def progress_summary(self) -> Dict[str, Any]:
        plan = self.selected_plan
        if not plan:
            return {"phase": self.phase.value, "progress": 0}
        return {
            "phase": self.phase.value,
            "progress": plan.progress_pct,
            "completed": plan.completed_steps,
            "total": plan.total_steps,
            "failed": plan.failed_steps,
            "confidence": self.confidence,
            "elapsed": self.elapsed_seconds,
        }
