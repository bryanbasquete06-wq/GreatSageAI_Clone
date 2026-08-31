#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel — Time Machine Debugger
========================================
Investigates git history to find when a bug was introduced.
Simulates a chronological scan through commits, identifies the exact
moment, line of code, and author that introduced a regression.

Features:
  - Walk through commit history chronologically
  - Detect regression commits by analyzing file changes
  - Trace the "domino effect" of an error
  - Generate a corrective patch
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os

from .models import (
    CommitInfo,
    DiffResult,
    FileChange,
    RegressionCandidate,
    TimeMachinePhase,
    TimeMachineReport,
    TimelineEntry,
    ErrorSeverity,
)

logger = logging.getLogger("elvea.deep_dev.time_machine")


# ═══════════════════════════════════════════════════════════════════════════════
# Regression Signal Patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Keywords in commit messages that might indicate a fix (suggesting a previous regression)
FIX_KEYWORDS = [
    r"(?i)fix", r"(?i)bugfix", r"(?i)bug fix", r"(?i)hotfix",
    r"(?i)patch", r"(?i)repair", r"(?i)resolve", r"(?i)solution",
    r"(?i)regression", r"(?i)broken", r"(?i)broke", r"(?i)issue",
]

# Keywords that indicate risky changes
RISK_KEYWORDS = [
    r"(?i)refactor", r"(?i)rewrite", r"(?i)restructure", r"(?i)reorganize",
    r"(?i)remove", r"(?i)delete", r"(?i)drop", r"(?i)deprecate",
    r"(?i)major", r"(?i)breaking", r"(?i)incompatible", r"(?i)migration",
]


class GitHistory:
    """Git history scanner that extracts commit data."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

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

    def get_commits(self, max_count: int = 100, file_filter: Optional[str] = None) -> List[CommitInfo]:
        """Get recent commits with metadata."""
        fmt = "%H|%an|%ai|%s"
        cmd = ["log", f"--format={fmt}", f"-{max_count}", "--no-merges"]
        if file_filter:
            cmd.extend(["--", file_filter])

        try:
            output = self._git(*cmd)
        except Exception as e:
            logger.error(f"[TimeMachine] Failed to get commits: {e}")
            return []

        commits = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            commit = CommitInfo.from_git_log(line)
            if commit.sha:
                # Get file change stats
                stats = self._get_commit_stats(commit.sha)
                commit.files_changed = stats["files"]
                commit.insertions = stats["insertions"]
                commit.deletions = stats["deletions"]
                commits.append(commit)

        return commits

    def get_commit_diff(self, sha: str) -> Dict[str, Any]:
        """Get the diff for a specific commit."""
        try:
            # Get changed files
            files_output = self._git("diff-tree", "--no-commit-id", "-r", "--name-status", sha)
            files = []
            for line in files_output.split("\n"):
                if line.strip():
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        status = parts[0]
                        name = parts[1]
                        files.append({"status": status, "path": name})

            # Get the actual diff
            diff_output = self._git("diff", f"{sha}~1", sha)

            return {"files": files, "diff": diff_output}
        except Exception as e:
            logger.error(f"[TimeMachine] Failed to get diff for {sha}: {e}")
            return {"files": [], "diff": ""}

    def get_file_history(self, file_path: str, max_count: int = 50) -> List[CommitInfo]:
        """Get commit history for a specific file."""
        return self.get_commits(max_count=max_count, file_filter=file_path)

    def get_file_content_at(self, sha: str, file_path: str) -> Optional[str]:
        """Get the content of a file at a specific commit."""
        try:
            return self._git("show", f"{sha}:{file_path}")
        except Exception:
            return None

    def _get_commit_stats(self, sha: str) -> Dict[str, int]:
        """Get insertion/deletion stats for a commit."""
        try:
            output = self._git("diff-tree", "--shortstat", "--no-commit-id", sha)
            files = insertions = deletions = 0
            if output:
                fm = re.search(r"(\d+) files? changed", output)
                if fm:
                    files = int(fm.group(1))
                im = re.search(r"(\d+) insertions?", output)
                if im:
                    insertions = int(im.group(1))
                dm = re.search(r"(\d+) deletions?", output)
                if dm:
                    deletions = int(dm.group(1))
            return {"files": files, "insertions": insertions, "deletions": deletions}
        except Exception:
            return {"files": 0, "insertions": 0, "deletions": 0}

    def is_repo(self) -> bool:
        """Check if current directory is a git repo."""
        try:
            self._git("rev-parse", "--is-inside-work-tree")
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Regression Detection Engine
# ═══════════════════════════════════════════════════════════════════════════════

class RegressionDetector:
    """
    Analyzes commits to detect regression introductions.
    Uses multiple heuristics:
      1. Commit message analysis (fix-after-change pattern)
      2. File change correlation (file X changed, then errors in X)
      3. Deletion analysis (important code removed)
      4. Pattern matching (common bug-introducing patterns)
    """

    def __init__(self, history: GitHistory):
        self.history = history

    def analyze(self, commits: List[CommitInfo], target_file: Optional[str] = None,
                query: str = "") -> List[RegressionCandidate]:
        """
        Analyze commits and rank them as potential regression sources.
        Returns candidates sorted by confidence (highest first).
        """
        candidates = []

        for commit in commits:
            score = self._score_commit(commit, commits, target_file, query)
            if score > 0.3:  # Threshold
                candidate = RegressionCandidate(
                    commit=commit,
                    confidence=score,
                    evidence=self._gather_evidence(commit, target_file),
                    affected_files=self._get_affected_files(commit),
                )
                candidate.impact_description = self._describe_impact(commit, candidate)
                candidates.append(candidate)

        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:10]  # Top 10

    def _score_commit(self, commit: CommitInfo, all_commits: List[CommitInfo],
                     target_file: Optional[str], query: str) -> float:
        """Score a commit's likelihood of being a regression source."""
        score = 0.0
        msg = commit.message.lower()

        # Signal 1: Fix keywords (suggests previous breakage)
        if any(re.search(kw, msg) for kw in FIX_KEYWORDS):
            score += 0.15

        # Signal 2: Risk keywords (suggests risky change)
        if any(re.search(kw, msg) for kw in RISK_KEYWORDS):
            score += 0.25

        # Signal 3: Large deletions (code removal)
        if commit.deletions > 50:
            score += min(0.3, commit.deletions / 200)

        # Signal 4: Large insertions + deletions (major rewrite)
        if commit.insertions > 50 and commit.deletions > 30:
            score += 0.2

        # Signal 5: File relevance
        if target_file:
            diff = self.history.get_commit_diff(commit.sha)
            for f in diff.get("files", []):
                if target_file in f.get("path", ""):
                    score += 0.3
                    break

        # Signal 6: Query relevance
        if query:
            query_words = set(query.lower().split())
            msg_words = set(msg.split())
            overlap = query_words & msg_words
            if overlap:
                score += min(0.2, len(overlap) / len(query_words))

        # Signal 7: Recent commits are more likely to be the cause
        idx = all_commits.index(commit) if commit in all_commits else len(all_commits)
        recency = 1.0 - (idx / max(len(all_commits), 1))
        score += recency * 0.1

        return min(1.0, score)

    def _gather_evidence(self, commit: CommitInfo,
                        target_file: Optional[str]) -> List[str]:
        """Gather evidence for why this commit might be a regression."""
        evidence = []
        msg = commit.message

        if commit.deletions > 50:
            evidence.append(f"Large deletion: {commit.deletions} lines removed")
        if commit.insertions > 100:
            evidence.append(f"Large insertion: {commit.insertions} lines added")

        if any(re.search(kw, msg, re.IGNORECASE) for kw in RISK_KEYWORDS):
            evidence.append("Contains risky change keywords in commit message")

        if any(re.search(kw, msg, re.IGNORECASE) for kw in FIX_KEYWORDS):
            evidence.append("This commit was itself a fix (potential earlier regression)")

        if target_file:
            diff = self.history.get_commit_diff(commit.sha)
            for f in diff.get("files", []):
                if target_file in f.get("path", ""):
                    evidence.append(f"Affects target file: {f['path']}")
                    break

        return evidence

    def _get_affected_files(self, commit: CommitInfo) -> List[str]:
        """Get list of files affected by a commit."""
        try:
            output = self.history._git("diff-tree", "--no-commit-id", "-r", "--name-only", commit.sha)
            return [f.strip() for f in output.split("\n") if f.strip()]
        except Exception:
            return []

    def _describe_impact(self, commit: CommitInfo,
                        candidate: RegressionCandidate) -> str:
        """Generate a human-readable impact description."""
        parts = []

        if commit.deletions > commit.insertions:
            parts.append(f"Removed {commit.deletions} lines (net -{commit.deletions - commit.insertions})")
        elif commit.insertions > commit.deletions:
            parts.append(f"Added {commit.insertions} lines (net +{commit.insertions - commit.deletions})")

        if candidate.affected_files:
            parts.append(f"Touched {len(candidate.affected_files)} files")

        if candidate.confidence > 0.7:
            parts.append("High confidence regression source")
        elif candidate.confidence > 0.5:
            parts.append("Medium confidence regression source")

        return " | ".join(parts) if parts else "Minimal changes"


# ═══════════════════════════════════════════════════════════════════════════════
# Timeline Builder
# ═══════════════════════════════════════════════════════════════════════════════

class TimelineBuilder:
    """Builds a timeline of events showing the domino effect of a regression."""

    def __init__(self, history: GitHistory):
        self.history = history

    def build(self, commits: List[CommitInfo], target_candidate: Optional[RegressionCandidate] = None,
              target_file: Optional[str] = None) -> List[TimelineEntry]:
        """
        Build a timeline showing how the regression was introduced and propagated.
        """
        if not commits:
            return []

        # Find the regression commit
        regression_sha = None
        if target_candidate:
            regression_sha = target_candidate.commit.sha

        entries = []
        seen_roles = set()

        for i, commit in enumerate(commits):
            role = "unrelated"
            description = ""
            impact = "none"

            if regression_sha and commit.sha == regression_sha:
                role = "introduced"
                description = "This commit introduced the regression."
                impact = "critical"
            elif regression_sha:
                # Check if this commit came after the regression and touches same files
                regression_files = set()
                try:
                    regression_candidate = next(
                        c for c in [target_candidate] if c
                    )
                    regression_files = set(regression_candidate.affected_files)
                except (StopIteration, AttributeError):
                    pass

                current_files = set(self._get_files(commit.sha))

                if current_files & regression_files:
                    if "fix" in commit.message.lower() or "bug" in commit.message.lower():
                        role = "fixed"
                        description = f"Attempted to fix the issue: {commit.message}"
                        impact = "minor"
                    else:
                        role = "amplified"
                        description = f"This commit further modified affected files: {commit.message}"
                        impact = "major"
                else:
                    # Check if it came after regression in time
                    idx_reg = next((j for j, c in enumerate(commits) if c.sha == regression_sha), -1)
                    if i > idx_reg:
                        role = "concurrent"
                        description = f"Unrelated change during regression period: {commit.message}"
                        impact = "none"

            elif self._is_fix_commit(commit):
                role = "triggered"
                description = f"Fix commit suggests a prior breakage: {commit.message}"
                impact = "minor"

            entry = TimelineEntry(
                commit=commit,
                role=role,
                description=description,
                impact_level=impact,
            )
            entries.append(entry)

        return entries

    def _get_files(self, sha: str) -> List[str]:
        """Get files changed in a commit."""
        try:
            output = self.history._git("diff-tree", "--no-commit-id", "-r", "--name-only", sha)
            return [f.strip() for f in output.split("\n") if f.strip()]
        except Exception:
            return []

    def _is_fix_commit(self, commit: CommitInfo) -> bool:
        """Check if a commit message suggests a fix."""
        return any(re.search(kw, commit.message, re.IGNORECASE) for kw in FIX_KEYWORDS)


# ═══════════════════════════════════════════════════════════════════════════════
# Patch Generator
# ═══════════════════════════════════════════════════════════════════════════════

class PatchGenerator:
    """Generates corrective patches based on regression analysis."""

    def __init__(self, history: GitHistory):
        self.history = history

    def generate(self, candidate: RegressionCandidate,
                commits: List[CommitInfo]) -> Optional[DiffResult]:
        """
        Generate a corrective patch that resolves the regression
        without breaking subsequent modifications.
        """
        if not candidate or not candidate.affected_files:
            return None

        changes = []

        for file_path in candidate.affected_files:
            # Get the file content before the regression
            prev_sha = self._find_last_good_commit(file_path, candidate.commit, commits)
            if not prev_sha:
                continue

            old_content = self.history.get_file_content_at(prev_sha, file_path)
            new_content = self.history.get_file_content_at(candidate.commit.sha, file_path)

            if old_content is None or new_content is None:
                continue

            # Get the current content
            current_content = self.history.get_file_content_at("HEAD", file_path)
            if current_content is None:
                continue

            # Generate a patch: revert specific changes from the regression commit
            # while keeping current changes
            patched = self._merge_revert(new_content, old_content, current_content)
            if patched and patched != current_content:
                old_lines = current_content.split("\n")
                new_lines = patched.split("\n")
                changes.append(FileChange(
                    path=file_path,
                    change_type="modified",
                    old_content=current_content,
                    new_content=patched,
                    line_added=sum(1 for a, b in zip(old_lines, new_lines) if a != b) + abs(len(new_lines) - len(old_lines)),
                    line_removed=sum(1 for a, b in zip(old_lines, new_lines) if a != b),
                ))

        if not changes:
            return None

        return DiffResult(
            changes=changes,
            summary=f"Revert regression from {candidate.commit.short_sha} across {len(changes)} files",
            metrics={"source_commit": candidate.commit.sha, "confidence": candidate.confidence},
        )

    def _find_last_good_commit(self, file_path: str, bad_commit: CommitInfo,
                               commits: List[CommitInfo]) -> Optional[str]:
        """Find the last commit before the bad one that touched this file."""
        bad_idx = -1
        for i, c in enumerate(commits):
            if c.sha == bad_commit.sha:
                bad_idx = i
                break

        if bad_idx <= 0:
            return None

        # Walk backwards to find a commit that touched this file
        for i in range(bad_idx - 1, -1, -1):
            diff = self.history.get_commit_diff(commits[i].sha)
            for f in diff.get("files", []):
                if file_path in f.get("path", ""):
                    return commits[i].sha

        return None

    def _merge_revert(self, bad_content: str, good_content: str,
                     current_content: str) -> Optional[str]:
        """
        Smart merge: revert changes from bad_content back to good_content,
        but preserve any subsequent changes in current_content.
        """
        good_lines = good_content.split("\n")
        bad_lines = bad_content.split("\n")
        current_lines = current_content.split("\n")

        # Simple approach: if current matches bad, replace with good
        if current_lines == bad_lines:
            return good_content

        # If current has diverged from both, do line-by-line merge
        result = list(current_lines)
        min_len = min(len(good_lines), len(bad_lines))

        for i in range(min_len):
            if i < len(result) and bad_lines[i] != good_lines[i]:
                # This line was changed in the regression
                if i < len(result) and result[i] == bad_lines[i]:
                    # Current still has the bad version — revert
                    if i < len(good_lines):
                        result[i] = good_lines[i]

        return "\n".join(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Time Machine Main Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TimeMachineEngine:
    """
    Main Time Machine Debugger engine.

    Usage:
        engine = TimeMachineEngine(project_root=".")
        report = engine.analyze("When did the login break?", target_file="auth.py")
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.history = GitHistory(project_root)
        self.detector = RegressionDetector(self.history)
        self.timeline_builder = TimelineBuilder(self.history)
        self.patch_generator = PatchGenerator(self.history)

        self._current_report: Optional[TimeMachineReport] = None

    def analyze(self, query: str, target_file: Optional[str] = None,
               max_commits: int = 50) -> TimeMachineReport:
        """
        Analyze git history to find when a regression was introduced.

        Args:
            query: The user's question (e.g., "When did the login break?")
            target_file: Optional specific file to focus on
            max_commits: Maximum commits to scan

        Returns:
            TimeMachineReport with timeline, candidates, and suggested patch
        """
        report = TimeMachineReport(query=query, target_file=target_file or "")
        self._current_report = report

        # Phase 1: SCANNING
        report.phase = TimeMachinePhase.SCANNING
        logger.info(f"[TimeMachine] Phase: SCANNING (query='{query}', file='{target_file}')")

        if not self.history.is_repo():
            report.phase = TimeMachinePhase.IDLE
            report.completed_at = time.time()
            return report

        commits = self.history.get_commits(max_count=max_commits, file_filter=target_file)
        report.commits_scanned = len(commits)
        logger.info(f"[TimeMachine] Scanned {len(commits)} commits")

        if not commits:
            report.phase = TimeMachinePhase.IDLE
            report.completed_at = time.time()
            return report

        # Phase 2: IDENTIFYING
        report.phase = TimeMachinePhase.IDENTIFYING
        logger.info("[TimeMachine] Phase: IDENTIFYING regression candidates")

        candidates = self.detector.analyze(commits, target_file, query)
        report.candidates = candidates
        report.files_analyzed = len(set(
            f for c in commits
            for f in self._get_files(c.sha)
        ))

        best = report.best_candidate

        # Phase 3: ANALYZING
        report.phase = TimeMachinePhase.ANALYZING
        logger.info("[TimeMachine] Phase: ANALYZING domino effect")

        if best:
            timeline = self.timeline_builder.build(commits, best, target_file)
            report.timeline = timeline
            report.root_cause = self._describe_root_cause(best, timeline)
            report.domino_effect = self._describe_domino_effect(timeline)
        else:
            # Build general timeline
            timeline = self.timeline_builder.build(commits, target_file=target_file)
            report.timeline = timeline
            report.root_cause = "No strong regression candidate found. Consider narrowing the search."
            report.domino_effect = ""

        # Phase 4: GENERATING
        report.phase = TimeMachinePhase.GENERATING
        logger.info("[TimeMachine] Phase: GENERATING patch")

        if best:
            patch = self.patch_generator.generate(best, commits)
            report.suggested_patch = patch

        # Phase 5: READY
        report.phase = TimeMachinePhase.READY
        report.completed_at = time.time()
        logger.info(f"[TimeMachine] Phase: READY — {len(candidates)} candidates, {len(timeline)} timeline entries")

        return report

    def get_report(self) -> Optional[TimeMachineReport]:
        return self._current_report

    # ── Private helpers ────────────────────────────────────────────────

    def _get_files(self, sha: str) -> List[str]:
        """Get files changed in a commit."""
        try:
            output = self.history._git("diff-tree", "--no-commit-id", "-r", "--name-only", sha)
            return [f.strip() for f in output.split("\n") if f.strip()]
        except Exception:
            return []

    def _describe_root_cause(self, candidate: RegressionCandidate,
                            timeline: List[TimelineEntry]) -> str:
        """Describe the root cause based on analysis."""
        commit = candidate.commit
        evidence = "; ".join(candidate.evidence) if candidate.evidence else "Multiple signals"

        return (
            f"**Regression introduced by commit {commit.short_sha}** by {commit.author} "
            f"on {commit.date}\n\n"
            f"Message: \"{commit.message}\"\n\n"
            f"Evidence: {evidence}\n\n"
            f"Impact: {candidate.impact_description}"
        )

    def _describe_domino_effect(self, timeline: List[TimelineEntry]) -> str:
        """Describe the domino effect from the timeline."""
        if not timeline:
            return "No timeline data available."

        critical = [e for e in timeline if e.impact_level in ("major", "critical")]
        if not critical:
            return "The regression had minimal downstream impact."

        effects = []
        for entry in critical:
            effects.append(
                f"→ {entry.commit.short_sha} ({entry.commit.author}): "
                f"{entry.description}"
            )

        return "The domino effect:\n" + "\n".join(effects)
