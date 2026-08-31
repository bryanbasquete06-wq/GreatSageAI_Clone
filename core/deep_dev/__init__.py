#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel
================
Autonomous engineering system with three modes:
  - Deep Dev Panel: structured engineering prompts
  - Shadow Dev: autonomous background engineering
  - Time Machine Debugger: git history regression analysis

Safety rules enforced:
  1. All work in sandbox branches — never touches main
  2. Sensitive data detection with alerts (no auto-fix)
  3. Human approval required for every change
"""

from .models import (
    ApprovalRequest,
    CommitInfo,
    DeepDevMode,
    DiffResult,
    ErrorSeverity,
    FileChange,
    RegressionCandidate,
    SandboxResult,
    SandboxStatus,
    SensitiveDataAlert,
    SensitivityLevel,
    ShadowChange,
    ShadowDiagnostic,
    ShadowPhase,
    ShadowReport,
    ShadowTrigger,
    TimeMachinePhase,
    TimeMachineReport,
    TimelineEntry,
)
from .safety import SafetyLayer
from .shadow_dev import ShadowDevEngine, FailureDetector, InactivityMonitor, ShadowAnalyzer
from .time_machine import TimeMachineEngine, GitHistory, RegressionDetector
from .engine import DeepDevEngine

__all__ = [
    # Main engine
    "DeepDevEngine",
    # Sub-engines
    "ShadowDevEngine",
    "TimeMachineEngine",
    "SafetyLayer",
    # Supporting classes
    "FailureDetector",
    "InactivityMonitor",
    "ShadowAnalyzer",
    "GitHistory",
    "RegressionDetector",
    # Models
    "DeepDevMode",
    "ShadowPhase",
    "ShadowTrigger",
    "ShadowReport",
    "ShadowDiagnostic",
    "ShadowChange",
    "TimeMachinePhase",
    "TimeMachineReport",
    "TimelineEntry",
    "CommitInfo",
    "RegressionCandidate",
    "DiffResult",
    "FileChange",
    "ErrorSeverity",
    "SensitivityLevel",
    "SensitiveDataAlert",
    "SandboxStatus",
    "SandboxResult",
    "ApprovalRequest",
]
