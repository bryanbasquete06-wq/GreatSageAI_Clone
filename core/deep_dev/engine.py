#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel — Main Engine
==============================
Orchestrates Shadow Dev, Time Machine Debugger, and the Safety Layer.
Provides a unified interface for the Deep Dev Panel UI.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .models import (
    ApprovalRequest,
    DeepDevMode,
    DiffResult,
    ShadowPhase,
    ShadowReport,
    ShadowTrigger,
    TimeMachinePhase,
    TimeMachineReport,
)
from .safety import SafetyLayer
from .shadow_dev import ShadowDevEngine
from .time_machine import TimeMachineEngine

logger = logging.getLogger("elvea.deep_dev.engine")


class DeepDevEngine:
    """
    Main orchestrator for the Deep Dev Panel.

    Manages three modes:
      1. PANEL — Structured engineering prompts (delegates to main LLM)
      2. SHADOW — Autonomous background engineering
      3. TIME_MACHINE — Git history regression analysis

    Enforces safety rules:
      - All work in sandbox branches
      - Sensitive data detection
      - Human approval for all changes
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.mode = DeepDevMode.IDLE

        # Sub-engines
        self.safety = SafetyLayer(project_root)
        self.shadow = ShadowDevEngine(project_root, self.safety)
        self.time_machine = TimeMachineEngine(project_root)

        # Callbacks for UI updates
        self._on_mode_change: Optional[Callable[[DeepDevMode], None]] = None
        self._on_shadow_report: Optional[Callable[[ShadowReport], None]] = None
        self._on_time_machine_report: Optional[Callable[[TimeMachineReport], None]] = None
        self._on_approval_needed: Optional[Callable[[ApprovalRequest], None]] = None
        self._on_log: Optional[Callable[[str], None]] = None

        # State
        self._lock = threading.Lock()
        self._last_shadow_report: Optional[ShadowReport] = None
        self._last_tm_report: Optional[TimeMachineReport] = None

        # Wire up Shadow Dev callback
        self.shadow.on_report_ready(self._handle_shadow_report)

    # ═══════════════════════════════════════════════════════════════════════
    # UI Callback Registration
    # ═══════════════════════════════════════════════════════════════════════

    def on_mode_change(self, callback: Callable[[DeepDevMode], None]):
        self._on_mode_change = callback

    def on_shadow_report(self, callback: Callable[[ShadowReport], None]):
        self._on_shadow_report = callback

    def on_time_machine_report(self, callback: Callable[[TimeMachineReport], None]):
        self._on_time_machine_report = callback

    def on_approval_needed(self, callback: Callable[[ApprovalRequest], None]):
        self._on_approval_needed = callback

    def on_log(self, callback: Callable[[str], None]):
        self._on_log = callback

    # ═══════════════════════════════════════════════════════════════════════
    # Mode Management
    # ═══════════════════════════════════════════════════════════════════════

    def set_mode(self, mode: DeepDevMode):
        """Switch the active mode."""
        with self._lock:
            old = self.mode
            self.mode = mode
            logger.info(f"[DeepDev] Mode: {old.name} → {mode.name}")
            if self._on_mode_change:
                self._on_mode_change(mode)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel Mode
    # ═══════════════════════════════════════════════════════════════════════

    def process_panel_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Process a prompt from the Deep Dev Panel.
        Returns structured engineering guidance.
        """
        self.set_mode(DeepDevMode.PANEL)

        # Analyze the prompt for engineering intent
        intent = self._classify_prompt(prompt)

        # Run safety scan
        sensitive_alerts = self.safety.scan_directory(".")

        result = {
            "intent": intent,
            "prompt": prompt,
            "sensitive_alerts": [
                {
                    "file": a.file_path,
                    "line": a.line,
                    "type": a.data_type,
                    "severity": a.severity.name,
                    "recommendation": a.recommendation,
                }
                for a in sensitive_alerts
            ],
            "suggestions": self._generate_suggestions(prompt, intent),
        }

        self._log(f"[Panel] Processed prompt: {intent['category']}")
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # Shadow Dev Mode
    # ═══════════════════════════════════════════════════════════════════════

    def activate_shadow(self, target_files: Optional[List[str]] = None) -> ShadowReport:
        """Manually activate Shadow Dev analysis."""
        self.set_mode(DeepDevMode.SHADOW)
        self._log("[ShadowDev] Activated by user")

        report = self.shadow.analyze_now(
            trigger=ShadowTrigger.USER_COMMAND,
            target_files=target_files,
        )

        self._last_shadow_report = report
        return report

    def activate_shadow_background(self, trigger: ShadowTrigger = ShadowTrigger.USER_COMMAND,
                                   target_files: Optional[List[str]] = None):
        """Start Shadow Dev in background thread."""
        self.set_mode(DeepDevMode.SHADOW)
        self._log(f"[ShadowDev] Background analysis started (trigger={trigger.name})")
        self.shadow.start_background_analysis(trigger=trigger, target_files=target_files)

    def feed_terminal_output(self, line: str):
        """Feed terminal output to Shadow Dev's failure detector."""
        self.shadow.feed_terminal_line(line)

    def touch_activity(self):
        """Record user activity for inactivity monitoring."""
        self.shadow.touch_activity()

    def approve_shadow_changes(self) -> bool:
        """Approve and apply Shadow Dev changes."""
        success = self.shadow.approve_and_apply()
        if success:
            self._log("[ShadowDev] Changes approved")
            # Create approval request for safety
            if self._last_shadow_report and self._last_shadow_report.diff:
                req = self.safety.request_approval(
                    source="shadow_dev",
                    title="Shadow Dev Changes",
                    description=self._last_shadow_report.summary,
                    diff=self._last_shadow_report.diff,
                )
                if self._on_approval_needed:
                    self._on_approval_needed(req)
        return success

    def discard_shadow_changes(self) -> bool:
        """Discard Shadow Dev changes."""
        success = self.shadow.discard_report()
        if success:
            self._log("[ShadowDev] Changes discarded")
        return success

    # ═══════════════════════════════════════════════════════════════════════
    # Time Machine Mode
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_time_machine(self, query: str,
                            target_file: Optional[str] = None,
                            max_commits: int = 50) -> TimeMachineReport:
        """Run Time Machine analysis."""
        self.set_mode(DeepDevMode.TIME_MACHINE)
        self._log(f"[TimeMachine] Analyzing: {query}")

        report = self.time_machine.analyze(query, target_file, max_commits)

        self._last_tm_report = report
        return report

    def approve_time_machine_patch(self) -> bool:
        """Approve and apply Time Machine patch."""
        if not self._last_tm_report or not self._last_tm_report.suggested_patch:
            return False

        # Create approval request
        req = self.safety.request_approval(
            source="time_machine",
            title="Time Machine Patch",
            description=f"Patch for: {self._last_tm_report.root_cause[:200]}",
            diff=self._last_tm_report.suggested_patch,
        )

        if self._on_approval_needed:
            self._on_approval_needed(req)

        self._log("[TimeMachine] Patch submitted for approval")
        return True

    def discard_time_machine_patch(self) -> bool:
        """Discard the Time Machine patch."""
        self._last_tm_report = None
        self._log("[TimeMachine] Patch discarded")
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # Approval Flow
    # ═══════════════════════════════════════════════════════════════════════

    def approve(self, request_id: str) -> bool:
        """Approve an approval request."""
        success = self.safety.approve(request_id)
        if success:
            applied = self.safety.apply_approved()
            self._log(f"[Approval] Approved and applied {len(applied)} diffs")
        return success

    def reject(self, request_id: str) -> bool:
        """Reject an approval request."""
        success = self.safety.reject(request_id)
        if success:
            self._log(f"[Approval] Rejected: {request_id}")
        return success

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        return self.safety.get_pending_approvals()

    # ═══════════════════════════════════════════════════════════════════════
    # Status & Queries
    # ═══════════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get current Deep Dev status."""
        return {
            "mode": self.mode.name,
            "shadow_active": self.shadow.is_active,
            "shadow_report": self._last_shadow_report.to_visual_report()
                           if self._last_shadow_report else None,
            "time_machine_report": self._last_tm_report.to_visual_report()
                                  if self._last_tm_report else None,
            "pending_approvals": len(self.get_pending_approvals()),
            "sandbox_branch": self.safety._sandbox_branch,
        }

    def get_shadow_status(self) -> Dict[str, Any]:
        """Get Shadow Dev specific status."""
        report = self.shadow.current_report
        return {
            "active": self.shadow.is_active,
            "phase": report.phase.name if report else "IDLE",
            "failure_streak": self.shadow.failure_detector.failure_count,
            "is_idle": self.shadow.inactivity_monitor.is_idle,
            "idle_seconds": self.shadow.inactivity_monitor.idle_seconds,
            "report": report.to_visual_report() if report else None,
        }

    def get_time_machine_status(self) -> Dict[str, Any]:
        """Get Time Machine specific status."""
        report = self._last_tm_report
        return {
            "has_report": report is not None,
            "phase": report.phase.name if report else "IDLE",
            "report": report.to_visual_report() if report else None,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Command Routing
    # ═══════════════════════════════════════════════════════════════════════

    def handle_command(self, text: str) -> Optional[str]:
        """
        Handle Deep Dev specific commands.
        Returns response string if handled, None if not a Deep Dev command.
        """
        t = text.lower().strip()

        if t in ("/shadow", "shadow dev", "deep dev shadow"):
            report = self.activate_shadow()
            return self._format_shadow_report(report)

        if t.startswith("/shadow ") or t.startswith("shadow "):
            # Shadow with target files
            files = t.replace("/shadow ", "").replace("shadow ", "").strip().split()
            report = self.activate_shadow(target_files=files)
            return self._format_shadow_report(report)

        if t.startswith("/timemachine ") or t.startswith("time machine "):
            query = t.replace("/timemachine ", "").replace("time machine ", "").strip()
            report = self.analyze_time_machine(query)
            return self._format_time_machine_report(report)

        if t in ("/timemachine", "time machine", "quando quebrou", "quando quebrou?"):
            report = self.analyze_time_machine("regression analysis")
            return self._format_time_machine_report(report)

        if t == "approve shadow" or t == "aplicar shadow":
            success = self.approve_shadow_changes()
            return "Changes applied." if success else "No changes to apply."

        if t == "discard shadow" or t == "descartar shadow":
            success = self.discard_shadow_changes()
            return "Changes discarded." if success else "No changes to discard."

        if t == "approve patch" or t == "aplicar patch":
            success = self.approve_time_machine_patch()
            return "Patch submitted for approval." if success else "No patch to apply."

        if t == "discard patch" or t == "descartar patch":
            success = self.discard_time_machine_patch()
            return "Patch discarded." if success else "No patch to discard."

        if t == "deep dev status":
            status = self.get_status()
            return self._format_status(status)

        if t == "scan secrets" or t == "scanar segredos":
            alerts = self.safety.scan_directory(".")
            return self._format_security_scan(alerts)

        return None

    # ═══════════════════════════════════════════════════════════════════════
    # Private Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _handle_shadow_report(self, report: ShadowReport):
        """Callback for when Shadow Dev produces a report."""
        self._last_shadow_report = report
        if report.phase == ShadowPhase.READY:
            self._log(f"[ShadowDev] Report ready: {report.summary}")
            if self._on_shadow_report:
                self._on_shadow_report(report)

    def _classify_prompt(self, prompt: str) -> Dict[str, Any]:
        """Classify a panel prompt into engineering intent categories."""
        p = prompt.lower()

        categories = {
            "refactoring": ["refator", "refactor", "clean", "limpar", "organizar", "organize"],
            "architecture": ["arquitetura", "architecture", "design", "padrão", "pattern", "estrutura"],
            "performance": ["performance", "velocidade", "speed", "otimizar", "optimize", "lento", "slow"],
            "security": ["segurança", "security", "vulnerabilidade", "vulnerability", "exploit", "auth"],
            "testing": ["teste", "test", "coverage", "cobertura", "mock", "unit"],
            "debugging": ["debug", "bug", "erro", "error", "crash", "broken"],
            "code_review": ["review", "revisar", "analisar", "analyze", "smell"],
        }

        scores = {}
        for cat, keywords in categories.items():
            score = sum(1 for kw in keywords if kw in p)
            if score > 0:
                scores[cat] = score

        if scores:
            best = max(scores, key=scores.get)
        else:
            best = "general"

        return {
            "category": best,
            "scores": scores,
            "is_structural": best in ("refactoring", "architecture", "code_review"),
            "is_safety": best in ("security", "testing"),
        }

    def _generate_suggestions(self, prompt: str, intent: Dict[str, Any]) -> List[str]:
        """Generate engineering suggestions based on intent."""
        suggestions = []
        cat = intent.get("category", "general")

        if cat == "refactoring":
            suggestions.extend([
                "Run cyclomatic complexity analysis first",
                "Create unit tests before refactoring",
                "Use extract method pattern for large functions",
                "Apply SOLID principles",
            ])
        elif cat == "architecture":
            suggestions.extend([
                "Map current module dependencies",
                "Identify circular imports",
                "Consider dependency injection",
                "Apply single responsibility principle",
            ])
        elif cat == "performance":
            suggestions.extend([
                "Profile before optimizing",
                "Check for O(n²) loops",
                "Consider caching strategies",
                "Measure memory allocation patterns",
            ])
        elif cat == "security":
            suggestions.extend([
                "Run sensitive data scan",
                "Check OWASP Top 10 vulnerabilities",
                "Validate input sanitization",
                "Review authentication flow",
            ])
        elif cat == "testing":
            suggestions.extend([
                "Check current test coverage",
                "Add edge case tests",
                "Mock external dependencies",
                "Test error handling paths",
            ])
        elif cat == "debugging":
            suggestions.extend([
                "Check recent commits for regression",
                "Analyze call stack and logs",
                "Add strategic logging points",
                "Check environment variables",
            ])
        else:
            suggestions.extend([
                "Consider running Shadow Dev for autonomous analysis",
                "Check git history with Time Machine for context",
            ])

        return suggestions

    def _format_shadow_report(self, report: ShadowReport) -> str:
        """Format a Shadow Report for text display."""
        lines = [
            f"## Deep Dev — Shadow Report",
            f"**Status:** {report.phase.name}",
            f"**Elapsed:** {report.elapsed_seconds:.1f}s",
            f"**Files analyzed:** {report.files_analyzed}",
            "",
        ]

        if report.errors_found:
            lines.append(f"**Errors found:** {report.errors_found}")
        if report.performance_issues:
            lines.append(f"**Performance issues:** {report.performance_issues}")
        if report.test_suggestions:
            lines.append(f"**Test suggestions:** {report.test_suggestions}")

        if report.diagnostics:
            lines.append("\n### Diagnostics")
            for d in report.diagnostics[:10]:
                severity_icon = {"CRITICAL": "🔴", "ERROR": "🟠", "WARNING": "🟡", "INFO": "🔵"}.get(
                    d.severity.name, "⚪"
                )
                lines.append(f"{severity_icon} **{d.title}** — {d.file_path}:{d.line}")
                lines.append(f"  → {d.suggestion}")

        if report.changes:
            lines.append("\n### Suggested Changes")
            for c in report.changes:
                risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(c.risk_level, "⚪")
                lines.append(f"{risk_icon} {c.file_path}: {c.description}")

        if report.diff:
            lines.append(f"\n### Diff Summary")
            lines.append(f"Files: {report.diff.files_changed} | +{report.diff.total_added}/-{report.diff.total_removed}")

        if report.phase == ShadowPhase.READY:
            lines.append("\n**Commands:** `approve shadow` / `discard shadow`")

        return "\n".join(lines)

    def _format_time_machine_report(self, report: TimeMachineReport) -> str:
        """Format a Time Machine Report for text display."""
        lines = [
            f"## Time Machine — Regression Analysis",
            f"**Status:** {report.phase.name}",
            f"**Commits scanned:** {report.commits_scanned}",
            f"**Files analyzed:** {report.files_analyzed}",
            f"**Elapsed:** {report.elapsed_seconds:.1f}s",
            "",
        ]

        if report.root_cause:
            lines.append(f"### Root Cause")
            lines.append(report.root_cause)

        if report.domino_effect:
            lines.append(f"\n### Domino Effect")
            lines.append(report.domino_effect)

        if report.timeline:
            lines.append(f"\n### Timeline ({len(report.timeline)} commits)")
            for entry in report.timeline[:15]:
                impact_icon = {
                    "critical": "🔴", "major": "🟠", "minor": "🟡", "none": "⚪"
                }.get(entry.impact_level, "⚪")
                lines.append(
                    f"{impact_icon} `{entry.commit.short_sha}` [{entry.role}] "
                    f"{entry.commit.message[:80]}"
                )

        if report.candidates:
            lines.append(f"\n### Top Candidates")
            for c in report.candidates[:5]:
                lines.append(
                    f"  `{c.commit.short_sha}` — {c.confidence:.0%} confidence "
                    f"({c.commit.author}, {c.commit.date})"
                )

        if report.suggested_patch:
            lines.append(f"\n### Suggested Patch")
            lines.append(f"Files: {report.suggested_patch.files_changed} | +{report.suggested_patch.total_added}/-{report.suggested_patch.total_removed}")
            lines.append("\n**Commands:** `approve patch` / `discard patch`")

        return "\n".join(lines)

    def _format_status(self, status: Dict[str, Any]) -> str:
        """Format status for display."""
        lines = [
            f"## Deep Dev Status",
            f"**Mode:** {status['mode']}",
            f"**Shadow active:** {status['shadow_active']}",
            f"**Pending approvals:** {status['pending_approvals']}",
            f"**Sandbox:** {status.get('sandbox_branch') or 'None'}",
        ]
        return "\n".join(lines)

    def _format_security_scan(self, alerts) -> str:
        """Format security scan results."""
        if not alerts:
            return "## Security Scan\nNo sensitive data found. ✅"

        lines = [
            f"## Security Scan — {len(alerts)} alerts",
            "",
        ]

        for alert in alerts[:20]:
            severity_icon = {
                "CRITICAL": "🔴", "DANGER": "🟠", "CAUTION": "🟡", "SAFE": "🟢"
            }.get(alert.severity.name, "⚪")
            lines.append(f"{severity_icon} **{alert.data_type}** in {alert.file_path}:{alert.line}")
            lines.append(f"  → {alert.recommendation}")

        lines.append(f"\n⚠️ These are alerts only. I will NOT auto-fix sensitive data.")
        return "\n".join(lines)

    def _log(self, message: str):
        """Send log message to observers."""
        logger.info(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass
