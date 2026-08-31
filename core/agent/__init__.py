#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Autonomous Engineering System
================================================
Public API for the autonomous coding agent.

Usage:
    from core.agent import AgentEngine, PlanStrategy

    engine = AgentEngine(
        project_root=".",
        llm_engine=your_llm,
        on_progress=lambda p: print(p),
        on_log=lambda m: print(m),
    )

    result = engine.run(
        goal="Create a FastAPI REST API with JWT auth and PostgreSQL",
        strategy=PlanStrategy.QUALITY,
    )
"""

from core.agent.engine import AgentEngine
from core.agent.models import (
    AgentPhase, Plan, PlanStep, PlanStrategy,
    StepAction, StepStatus, ExecutionResult,
    DecisionPoint, Checkpoint, Lesson, ErrorCategory,
)
from core.agent.planner import PlanGenerator
from core.agent.executor import StepExecutor, classify_error
from core.agent.gates import QualityGates, QualityReport
from core.agent.recovery import RecoverySystem

__all__ = [
    "AgentEngine",
    "AgentPhase",
    "Plan",
    "PlanStep",
    "PlanStrategy",
    "StepAction",
    "StepStatus",
    "ExecutionResult",
    "DecisionPoint",
    "Checkpoint",
    "Lesson",
    "PlanGenerator",
    "StepExecutor",
    "QualityGates",
    "QualityReport",
    "RecoverySystem",
    "classify_error",
    "ErrorCategory",
]
