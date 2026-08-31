#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel — Safety Layer
==============================
Sandbox isolation, sensitive data detection, and human approval flow.
Implements the absolute safety rules:
  1. NEVER write to main branch directly
  2. ALL work in isolated sandbox (branch/container)
  3. Detect and ALERT on sensitive data (never auto-fix)
  4. Human sovereignty — user approves every merge
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ApprovalRequest,
    DiffResult,
    FileChange,
    SandboxResult,
    SandboxStatus,
    SensitiveDataAlert,
    SensitivityLevel,
)

logger = logging.getLogger("elvea.deep_dev.safety")

# ═══════════════════════════════════════════════════════════════════════════════
# Sensitive Data Patterns
# ═══════════════════════════════════════════════════════════════════════════════

SENSITIVE_PATTERNS: List[Tuple[str, str, SensitivityLevel]] = [
    # API Keys
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9_\-]{16,}["\']', "api_key", SensitivityLevel.CRITICAL),
    (r'(?i)(secret[_-]?key|client[_-]?secret)\s*[=:]\s*["\'][A-Za-z0-9_\-]{16,}["\']', "secret_key", SensitivityLevel.CRITICAL),
    # Tokens
    (r'(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[=:]\s*["\'][A-Za-z0-9_\-\.]{20,}["\']', "token", SensitivityLevel.CRITICAL),
    (r'(?i)ghp_[A-Za-z0-9]{36}', "github_token", SensitivityLevel.CRITICAL),
    (r'(?i)sk-[A-Za-z0-9]{32,}', "openai_key", SensitivityLevel.CRITICAL),
    (r'(?i)xoxb-[A-Za-z0-9\-]+', "slack_token", SensitivityLevel.CRITICAL),
    # Passwords
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{6,}["\']', "password", SensitivityLevel.DANGER),
    (r'(?i)(db[_-]?password|database[_-]?pass)\s*[=:]\s*["\'][^"\']+["\']', "database_password", SensitivityLevel.CRITICAL),
    # AWS
    (r'(?i)(AKIA[A-Z0-9]{16})', "aws_access_key", SensitivityLevel.CRITICAL),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\'][A-Za-z0-9/+=]{40}["\']', "aws_secret", SensitivityLevel.CRITICAL),
    # Connection strings
    (r'(?i)(mongodb|postgres|mysql|redis|amqp)://[^\s"\']+:[^\s"\']+@[^\s"\']+', "connection_string", SensitivityLevel.DANGER),
    # Private keys
    (r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----', "private_key", SensitivityLevel.CRITICAL),
    # JWT tokens
    (r'eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', "jwt_token", SensitivityLevel.DANGER),
]

# Patterns that are SAFE (should not trigger alerts)
SAFE_PATTERNS = [
    r'(?i)(example|sample|placeholder|xxx|your[_-]?.*here|<.*>)',
    r'(?i)(os\.environ|getenv|env\()',
    r'(?i)(\.env\.example|\.env\.sample)',
]


class SafetyLayer:
    """
    Enforces absolute safety rules for Deep Dev operations.

    Rules:
    1. All work happens in sandbox branches — never touches main
    2. Sensitive data detection with visual alerts (no auto-fix)
    3. Human approval required for every change
    4. Automatic sandbox cleanup on failure
    """

    PROTECTED_BRANCHES = {"main", "master", "production", "prod", "release"}

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._sandbox_branch: Optional[str] = None
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._applied_diffs: List[DiffResult] = []

    # ═══════════════════════════════════════════════════════════════════════
    # Sandbox Management
    # ═══════════════════════════════════════════════════════════════════════

    def create_sandbox(self, prefix: str = "deepdev") -> str:
        """Create an isolated sandbox branch from current HEAD. Returns branch name."""
        timestamp = int(time.time())
        branch_name = f"sandbox/{prefix}-{timestamp}"
        self._sandbox_branch = branch_name

        try:
            # Get current branch
            current = self._git("branch", "--show-current")
            if not current:
                current = "main"

            # Create sandbox branch
            self._git("checkout", "-b", branch_name, current)
            logger.info(f"[Sandbox] Created: {branch_name} from {current}")
            return branch_name

        except Exception as e:
            logger.error(f"[Sandbox] Failed to create: {e}")
            raise

    def cleanup_sandbox(self, merge: bool = False) -> bool:
        """Clean up sandbox branch. If merge=True, merge changes to original branch first."""
        if not self._sandbox_branch:
            return False

        try:
            original_branch = self._git("branch", "--show-current")

            # If merge requested and we're on a sandbox branch
            if merge and self._is_on_sandbox():
                # Stash any uncommitted changes
                self._git("stash")
                # Switch back to original branch
                self._git("checkout", original_branch)
                # Merge sandbox
                self._git("merge", "--no-ff", self._sandbox_branch, "-m",
                         f"Deep Dev: merge {self._sandbox_branch}")
                logger.info(f"[Sandbox] Merged {self._sandbox_branch} into {original_branch}")
            else:
                # Just switch back
                if self._is_on_sandbox():
                    self._git("checkout", original_branch or "main")

            # Delete sandbox branch
            self._git("branch", "-D", self._sandbox_branch)
            logger.info(f"[Sandbox] Cleaned up: {self._sandbox_branch}")
            self._sandbox_branch = None
            return True

        except Exception as e:
            logger.error(f"[Sandbox] Cleanup failed: {e}")
            return False

    def discard_sandbox(self) -> bool:
        """Discard all sandbox changes and delete the branch."""
        if not self._sandbox_branch:
            return False

        try:
            current = self._git("branch", "--show-current")
            # Reset any changes
            if self._is_on_sandbox():
                self._git("checkout", "--", ".")
            # Switch back to main
            self._git("checkout", self.PROTECTED_BRANCHES.intersection(
                self._get_all_branches()
            ).pop() or "main")
            # Delete sandbox
            self._git("branch", "-D", self._sandbox_branch)
            logger.info(f"[Sandbox] Discarded and deleted: {self._sandbox_branch}")
            self._sandbox_branch = None
            return True
        except Exception as e:
            logger.error(f"[Sandbox] Discard failed: {e}")
            return False

    def apply_changes_in_sandbox(self, changes: List[FileChange]) -> bool:
        """Apply file changes within the current sandbox."""
        if not self._is_on_sandbox():
            logger.error("[Sandbox] Cannot apply changes outside sandbox!")
            return False

        try:
            for change in changes:
                file_path = self.project_root / change.path
                file_path.parent.mkdir(parents=True, exist_ok=True)

                if change.change_type == "deleted":
                    if file_path.exists():
                        file_path.unlink()
                elif change.change_type in ("modified", "added"):
                    file_path.write_text(change.new_content, encoding="utf-8")
                elif change.change_type == "renamed" and change.old_path:
                    old = self.project_root / change.old_path
                    if old.exists():
                        old.rename(file_path)

            # Stage changes
            self._git("add", "-A")
            return True
        except Exception as e:
            logger.error(f"[Sandbox] Failed to apply changes: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # Sensitive Data Detection
    # ═══════════════════════════════════════════════════════════════════════

    def scan_for_sensitive_data(self, file_path: str, content: str) -> List[SensitiveDataAlert]:
        """
        Scan file content for sensitive data patterns.
        NEVER auto-fixes — only generates alerts for the UI.
        """
        alerts = []
        lines = content.split("\n")

        # Skip if file is .env.example or similar
        filename = os.path.basename(file_path)
        if filename in (".env.example", ".env.sample", ".env.template"):
            return alerts

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern, data_type, severity in SENSITIVE_PATTERNS:
                if re.search(pattern, line):
                    # Check if it's a false positive
                    is_safe = any(re.search(sp, line) for sp in SAFE_PATTERNS)
                    if not is_safe:
                        context_start = max(0, line_num - 3)
                        context_end = min(len(lines), line_num + 2)
                        context = "\n".join(lines[context_start:context_end])

                        alerts.append(SensitiveDataAlert(
                            file_path=file_path,
                            line=line_num,
                            data_type=data_type,
                            context=context,
                            severity=severity,
                            recommendation=self._get_recommendation(data_type),
                        ))
                        break  # One alert per line

        return alerts

    def scan_directory(self, directory: str, extensions: Optional[List[str]] = None) -> List[SensitiveDataAlert]:
        """Recursively scan a directory for sensitive data."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".env", ".cfg", ".ini"]

        alerts = []
        dir_path = self.project_root / directory if not os.path.isabs(directory) else Path(directory)

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                # Skip git and node_modules
                parts = file_path.parts
                if ".git" in parts or "node_modules" in parts or "__pycache__" in parts:
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    rel = str(file_path.relative_to(self.project_root))
                    alerts.extend(self.scan_for_sensitive_data(rel, content))
                except Exception:
                    continue

        return alerts

    # ═══════════════════════════════════════════════════════════════════════
    # Human Approval Flow
    # ═══════════════════════════════════════════════════════════════════════

    def request_approval(self, source: str, title: str, description: str,
                        diff: Optional[DiffResult] = None,
                        sandbox_result: Optional[SandboxResult] = None) -> ApprovalRequest:
        """Create an approval request for the user."""
        req = ApprovalRequest(
            source=source,
            title=title,
            description=description,
            diff=diff,
            sandbox_result=sandbox_result,
        )
        self._pending_approvals[req.id] = req
        logger.info(f"[Approval] Request created: {req.id} — {title}")
        return req

    def approve(self, request_id: str) -> bool:
        """User approves the request."""
        req = self._pending_approvals.get(request_id)
        if req and req.is_pending:
            req.approved = True
            logger.info(f"[Approval] Approved: {request_id}")
            return True
        return False

    def reject(self, request_id: str) -> bool:
        """User rejects the request."""
        req = self._pending_approvals.get(request_id)
        if req and req.is_pending:
            req.approved = False
            logger.info(f"[Approval] Rejected: {request_id}")
            return True
        return False

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return [r for r in self._pending_approvals.values() if r.is_pending]

    def apply_approved(self) -> List[DiffResult]:
        """Apply all approved changes. Returns list of applied diffs."""
        applied = []
        for req_id, req in list(self._pending_approvals.items()):
            if req.approved is True and req.diff:
                success = self.apply_changes_in_sandbox(
                    req.diff.changes
                )
                if success:
                    applied.append(req.diff)
                    self._applied_diffs.append(req.diff)
                del self._pending_approvals[req_id]
        return applied

    # ═══════════════════════════════════════════════════════════════════════
    # Protected Branch Check
    # ═══════════════════════════════════════════════════════════════════════

    def is_protected_branch(self, branch: Optional[str] = None) -> bool:
        """Check if a branch is protected (cannot be modified directly)."""
        if branch is None:
            branch = self._git("branch", "--show-current") or ""
        return branch in self.PROTECTED_BRANCHES

    def ensure_sandbox(self) -> str:
        """Ensure we're in a sandbox. Creates one if needed."""
        if not self._is_on_sandbox():
            return self.create_sandbox()
        return self._sandbox_branch or ""

    # ═══════════════════════════════════════════════════════════════════════
    # Git Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _git(self, *args: str) -> str:
        """Run a git command and return stdout."""
        try:
            env = {"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(
                ["git"] + list(args),
                cwd=str(self.project_root),
                capture_output=True,
                timeout=30,
                env={**os.environ, **env},
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
                raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
            stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else result.stdout
            return stdout.strip()
        except FileNotFoundError:
            raise RuntimeError("Git not found in PATH")

    def _is_on_sandbox(self) -> bool:
        """Check if current branch is a sandbox branch."""
        current = self._git("branch", "--show-current")
        return current.startswith("sandbox/")

    def _get_all_branches(self) -> set:
        """Get all local branch names."""
        output = self._git("branch", "--format=%(refname:short)")
        return set(output.split("\n")) if output else set()

    def _get_recommendation(self, data_type: str) -> str:
        """Get a recommendation for a detected sensitive data type."""
        recommendations = {
            "api_key": "Move to .env and reference via os.environ. Never commit API keys.",
            "secret_key": "Move to .env immediately. Use environment variables in code.",
            "token": "Token may be compromised. Rotate immediately and move to .env.",
            "github_token": "GitHub token detected! Rotate at github.com/settings/tokens and move to .env.",
            "openai_key": "OpenAI key detected! Rotate at platform.openai.com and move to .env.",
            "slack_token": "Slack token detected! Revoke at api.slack.com/apps and move to .env.",
            "password": "Move password to .env. Use os.environ.get() in code.",
            "database_password": "Critical: database password exposed! Rotate immediately.",
            "aws_access_key": "AWS access key detected! Rotate via IAM console.",
            "aws_secret": "Critical: AWS secret key detected! Rotate immediately via IAM.",
            "connection_string": "Connection string with credentials detected. Use env vars.",
            "private_key": "CRITICAL: Private key exposed! Rotate immediately.",
            "jwt_token": "JWT token detected. Ensure tokens are short-lived.",
        }
        return recommendations.get(data_type, "Move sensitive data to .env file.")
