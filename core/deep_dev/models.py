#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel — Data Models
=============================
Models for Shadow Dev, Time Machine Debugger, and Deep Dev Panel.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class DeepDevMode(Enum):
    """Operating modes for the Deep Dev Panel."""
    PANEL = auto()       # Deep Dev Panel — structured engineering prompts
    SHADOW = auto()      # Shadow Dev — background autonomous engineering
    TIME_MACHINE = auto() # Time Machine — git history regression analysis
    IDLE = auto()        # Panel open but no active mode


class ShadowTrigger(Enum):
    """What triggered Shadow Dev activation."""
    USER_COMMAND = auto()     # User typed /shadow
    INACTIVITY = auto()       # User idle timeout detected
    FAILURE_STREAK = auto()   # Consecutive terminal failures detected


class ShadowPhase(Enum):
    """Phases of Shadow Dev execution."""
    IDLE = auto()
    ANALYZING = auto()        # Reading call stack, logs, errors
    DIAGNOSING = auto()       # Identifying root cause
    SOLVING = auto()          # Formulating solution
    WRITING = auto()          # Writing code/tests in sandbox
    TESTING = auto()          # Running tests in sandbox
    READY = auto()            # Diff ready for user review
    APPLIED = auto()          # User approved, changes applied
    DISCARDED = auto()        # User rejected or tests failed


class TimeMachinePhase(Enum):
    """Phases of Time Machine analysis."""
    IDLE = auto()
    SCANNING = auto()         # Walking git history
    IDENTIFYING = auto()      # Finding the regression commit
    ANALYZING = auto()        # Tracing the domino effect
    GENERATING = auto()       # Creating the patch
    READY = auto()            # Timeline + patch ready for review


class ErrorSeverity(Enum):
    """Severity of errors detected."""
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class SensitivityLevel(Enum):
    """Sensitivity level for data detection."""
    SAFE = auto()
    CAUTION = auto()
    DANGER = auto()
    CRITICAL = auto()


class SandboxStatus(Enum):
    """Status of sandboxed work."""
    ACTIVE = auto()
    PASSED = auto()
    FAILED = auto()
    DISCARDED = auto()


# ═══════════════════════════════════════════════════════════════════════════════
# Diff & Patch Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FileChange:
    """A single file change in a diff."""
    path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    old_content: str = ""
    new_content: str = ""
    old_path: str = ""  # For renames
    line_added: int = 0
    line_removed: int = 0
    hunks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def diff_stat(self) -> str:
        """Compact diff stat like: +12/-5."""
        return f"+{self.line_added}/-{self.line_removed}"


@dataclass
class DiffResult:
    """Complete diff of shadow dev or time machine changes."""
    changes: List[FileChange] = field(default_factory=list)
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_added(self) -> int:
        return sum(c.line_added for c in self.changes)

    @property
    def total_removed(self) -> int:
        return sum(c.line_removed for c in self.changes)

    @property
    def files_changed(self) -> int:
        return len(self.changes)


# ═══════════════════════════════════════════════════════════════════════════════
# Shadow Dev Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ShadowDiagnostic:
    """A single diagnostic finding from Shadow Dev."""
    file_path: str = ""
    line: int = 0
    severity: ErrorSeverity = ErrorSeverity.INFO
    category: str = ""       # "bug", "performance", "security", "test_coverage"
    title: str = ""
    description: str = ""
    suggestion: str = ""
    confidence: float = 0.0  # 0.0 - 1.0


@dataclass
class ShadowChange:
    """A single suggested change from Shadow Dev."""
    file_path: str
    description: str
    old_code: str
    new_code: str
    reason: str = ""
    risk_level: str = "low"  # "low", "medium", "high"


@dataclass
class ShadowReport:
    """Complete report from Shadow Dev execution."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trigger: ShadowTrigger = ShadowTrigger.USER_COMMAND
    phase: ShadowPhase = ShadowPhase.IDLE
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    # Diagnostics
    diagnostics: List[ShadowDiagnostic] = field(default_factory=list)
    changes: List[ShadowChange] = field(default_factory=list)
    diff: Optional[DiffResult] = None

    # Metrics
    files_analyzed: int = 0
    errors_found: int = 0
    performance_issues: int = 0
    test_suggestions: int = 0
    estimated_latency_improvement: str = ""
    estimated_test_coverage_gain: str = ""

    # Sandbox
    sandbox_passed: bool = False
    tests_ran: int = 0
    tests_passed: int = 0

    @property
    def elapsed_seconds(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at

    @property
    def summary(self) -> str:
        parts = []
        if self.errors_found:
            parts.append(f"{self.errors_found} bugs found")
        if self.performance_issues:
            parts.append(f"{self.performance_issues} perf issues")
        if self.test_suggestions:
            parts.append(f"{self.test_suggestions} test suggestions")
        return ", ".join(parts) if parts else "No issues found"

    def to_visual_report(self) -> Dict[str, Any]:
        """Generate data for the visual report panel."""
        return {
            "title": "Deep Dev Report",
            "trigger": self.trigger.name,
            "elapsed": f"{self.elapsed_seconds:.1f}s",
            "diagnostics": [
                {
                    "severity": d.severity.name,
                    "file": d.file_path,
                    "line": d.line,
                    "category": d.category,
                    "title": d.title,
                    "description": d.description,
                    "suggestion": d.suggestion,
                    "confidence": f"{d.confidence:.0%}",
                }
                for d in self.diagnostics
            ],
            "changes": [
                {
                    "file": c.file_path,
                    "description": c.description,
                    "risk": c.risk_level,
                }
                for c in self.changes
            ],
            "metrics": {
                "files_analyzed": self.files_analyzed,
                "errors_found": self.errors_found,
                "performance_issues": self.performance_issues,
                "test_suggestions": self.test_suggestions,
                "sandbox_passed": self.sandbox_passed,
                "tests_ran": self.tests_ran,
                "tests_passed": self.tests_passed,
                "latency_improvement": self.estimated_latency_improvement,
                "coverage_gain": self.estimated_test_coverage_gain,
            },
            "diff_summary": self.diff.summary if self.diff else "",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Time Machine Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CommitInfo:
    """Information about a single git commit."""
    sha: str = ""
    short_sha: str = ""
    author: str = ""
    date: str = ""
    timestamp: float = 0.0
    message: str = ""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    is_merge: bool = False

    @classmethod
    def from_git_log(cls, line: str) -> "CommitInfo":
        """Parse a git log --format line: SHA|author|date|message."""
        parts = line.split("|", 3)
        if len(parts) < 4:
            return cls()
        return cls(
            sha=parts[0].strip(),
            short_sha=parts[0].strip()[:8],
            author=parts[1].strip(),
            date=parts[2].strip(),
            message=parts[3].strip(),
        )


@dataclass
class RegressionCandidate:
    """A commit identified as a potential regression source."""
    commit: CommitInfo
    confidence: float = 0.0    # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    impact_description: str = ""


@dataclass
class TimelineEntry:
    """A single entry in the regression timeline."""
    commit: CommitInfo
    role: str = ""           # "introduced", "amplified", "triggered", "unrelated"
    description: str = ""
    impact_level: str = ""   # "none", "minor", "major", "critical"


@dataclass
class TimeMachineReport:
    """Complete report from Time Machine analysis."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    phase: TimeMachinePhase = TimeMachinePhase.IDLE
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    # Query context
    query: str = ""          # What the user asked about
    target_file: str = ""    # If they specified a file

    # Results
    candidates: List[RegressionCandidate] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)
    root_cause: str = ""
    domino_effect: str = ""
    suggested_patch: Optional[DiffResult] = None

    # Stats
    commits_scanned: int = 0
    files_analyzed: int = 0

    @property
    def elapsed_seconds(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at

    @property
    def best_candidate(self) -> Optional[RegressionCandidate]:
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.confidence)

    def to_visual_report(self) -> Dict[str, Any]:
        """Generate data for the timeline visualization."""
        return {
            "title": "Time Machine Report",
            "query": self.query,
            "elapsed": f"{self.elapsed_seconds:.1f}s",
            "commits_scanned": self.commits_scanned,
            "files_analyzed": self.files_analyzed,
            "root_cause": self.root_cause,
            "domino_effect": self.domino_effect,
            "timeline": [
                {
                    "sha": e.commit.short_sha,
                    "author": e.commit.author,
                    "date": e.commit.date,
                    "message": e.commit.message,
                    "role": e.role,
                    "description": e.description,
                    "impact": e.impact_level,
                }
                for e in self.timeline
            ],
            "patch": {
                "summary": self.suggested_patch.summary,
                "files": self.suggested_patch.files_changed,
                "added": self.suggested_patch.total_added,
                "removed": self.suggested_patch.total_removed,
            } if self.suggested_patch else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Safety Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SensitiveDataAlert:
    """Alert about sensitive data found in code."""
    file_path: str
    line: int
    data_type: str        # "api_key", "password", "token", "env_var", "credential"
    context: str          # Surrounding code snippet
    severity: SensitivityLevel = SensitivityLevel.DANGER
    recommendation: str = ""


@dataclass
class SandboxResult:
    """Result of running code in sandbox."""
    status: SandboxStatus = SandboxStatus.ACTIVE
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    errors: List[str] = field(default_factory=list)
    output: str = ""
    execution_time_ms: float = 0.0
    branch_name: str = ""

    @property
    def all_passed(self) -> bool:
        return self.status == SandboxStatus.PASSED or (
            self.tests_run > 0 and self.tests_passed == self.tests_run
        )


@dataclass
class ApprovalRequest:
    """Request for user approval before applying changes."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    source: str = ""       # "shadow_dev", "time_machine"
    title: str = ""
    description: str = ""
    diff: Optional[DiffResult] = None
    sandbox_result: Optional[SandboxResult] = None
    approved: Optional[bool] = None  # None = pending

    @property
    def is_pending(self) -> bool:
        return self.approved is None
