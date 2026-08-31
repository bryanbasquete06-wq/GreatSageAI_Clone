#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Self-Correction Engine v2
===========================
Major upgrade: deeper code smell detection, architectural analysis,
anti-pattern detection, and more auto-fixes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CorrectionIssue:
    """A single issue found during self-review."""
    category: str
    description: str
    original_text: str
    corrected_text: str
    confidence: float = 0.8
    severity: str = "low"  # "low", "medium", "high"


@dataclass
class CorrectionResult:
    """Result of self-correction analysis."""
    issues: List[CorrectionIssue] = field(default_factory=list)
    corrected_response: str = ""
    was_modified: bool = False
    corrections_applied: int = 0
    severity_summary: dict = field(default_factory=dict)


class SelfCorrectionEngine:
    """
    Reviews AI responses and suggests/applies corrections.
    v2: Deeper code smell detection, anti-patterns, architectural analysis.
    """

    # ═══ Code Quality Patterns ═══
    CODE_SMELL_PATTERNS = [
        # Bare except
        (r"except\s*:\s*\n\s*pass", "Bare except with pass — silences all errors",
         "except Exception as e:\n    logging.error(f'Error: {e}')", "high"),
        # Print in production
        (r"(?m)^(?!\s*#)\s*print\(", "print() in production — use logging",
         None, "medium"),
        # Hardcoded credentials
        (r"(?i)(password|secret|key|token)\s*=\s*[\"'][^\"']{6,}[\"']",
         "Hardcoded credential detected", None, "high"),
        # TODO without owner
        (r"(?m)^\s*#\s*TODO(?!\s*\()", "TODO without owner/plan",
         None, "low"),
        # Long line (>120 chars)
        (r".{121,}", "Line exceeds 120 characters", None, "low"),
        # Nested imports
        (r"(?m)^\s{8,}import\s+", "Deeply nested import (should be at top)",
         None, "medium"),
        # Star import
        (r"from\s+\S+\s+import\s+\*", "Star import — pollutes namespace",
         None, "medium"),
        # Mutable default
        (r"def\s+\w+\([^)]*=\s*\[\]", "Mutable default argument (list)", None, "high"),
        (r"def\s+\w+\([^)]*=\s*\{\}", "Mutable default argument (dict)", None, "high"),
        # type() comparison
        (r"type\(\w+\)\s*==", "type() comparison — use isinstance()",
         None, "medium"),
        # Global keyword
        (r"(?m)^\s*global\s+", "Global variable — reduces testability", None, "medium"),
        # Empty except
        (r"except\s+\w+.*:\s*\n\s*pass", "Empty except — swallows errors silently",
         None, "medium"),
        # assert in production
        (r"(?m)^\s*assert\s+", "assert in production — removed with -O flag",
         None, "medium"),
        # exec/eval usage
        (r"\b(exec|eval)\s*\(", "exec/eval usage — potential security risk",
         None, "high"),
        # Unsorted imports
        (r"(?m)^import\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*\nimport\s+.*",
         "Consider sorting imports (isort)", None, "low"),
    ]

    # ═══ Tone Patterns ═══
    TONE_ISSUES = [
        (r"(?i)(obviamente|claro que|e logico que|nao precisa nem perguntar)",
         "Condescending tone", "medium"),
        (r"(?i)(nao sei|nao tenho certeza|posso estar errado|talvez)",
         "Excessive uncertainty — be more confident when you know", "low"),
        (r"(?i)(nao e minha area|nao posso ajudar com isso)",
         "Deflecting — try to help or explain limitations", "medium"),
    ]

    # ═══ Structural Issues ═══
    STRUCTURAL_PATTERNS = [
        # Response starts with code but no explanation
        (r"^```(?:python|js|ts|java|go|rust)\n", "Code without prior explanation",
         None, "medium"),
        # Response ends with code block (no conclusion)
        (r"```\s*$", "Response ends with code — add a conclusion", None, "low"),
        # No line breaks in long response
        (r"(?s)^.{500,}$", "Very long response — consider breaking into sections",
         None, "low"),
    ]

    def review(self, response: str, is_code: bool = False,
               context: Optional[str] = None) -> CorrectionResult:
        """
        Review a response and apply corrections.
        v2: Deeper analysis, severity tracking, structural checks.
        """
        issues = []
        corrected = response

        # Code-specific checks
        if is_code or "```" in response:
            issues.extend(self._check_code_quality(response))

        # Tone checks
        issues.extend(self._check_tone(response))

        # Structural checks
        issues.extend(self._check_structure(response))

        # Completeness checks
        issues.extend(self._check_completeness(response))

        # Apply high-confidence corrections
        for issue in issues:
            if issue.confidence >= 0.8 and issue.corrected_text:
                corrected = corrected.replace(issue.original_text, issue.corrected_text, 1)

        # Severity summary
        severity_counts = {}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        return CorrectionResult(
            issues=issues,
            corrected_response=corrected,
            was_modified=(corrected != response),
            corrections_applied=sum(1 for i in issues if i.corrected_text and i.confidence >= 0.8),
            severity_summary=severity_counts,
        )

    def _check_code_quality(self, code: str) -> List[CorrectionIssue]:
        issues = []
        for pattern, desc, fix, severity in self.CODE_SMELL_PATTERNS:
            for match in re.finditer(pattern, code):
                issues.append(CorrectionIssue(
                    category="code_quality",
                    description=desc,
                    original_text=match.group(),
                    corrected_text=fix or "",
                    confidence=0.7 if fix else 0.4,
                    severity=severity,
                ))
        return issues

    def _check_tone(self, text: str) -> List[CorrectionIssue]:
        issues = []
        for pattern, desc, severity in self.TONE_ISSUES:
            for match in re.finditer(pattern, text):
                issues.append(CorrectionIssue(
                    category="tone",
                    description=desc,
                    original_text=match.group(),
                    corrected_text="",
                    confidence=0.6 if severity == "low" else 0.8,
                    severity=severity,
                ))
        return issues

    def _check_structure(self, text: str) -> List[CorrectionIssue]:
        issues = []
        for pattern, desc, fix, severity in self.STRUCTURAL_PATTERNS:
            if re.search(pattern, text):
                issues.append(CorrectionIssue(
                    category="structure",
                    description=desc,
                    original_text="",
                    corrected_text=fix or "",
                    confidence=0.5,
                    severity=severity,
                ))
        return issues

    def _check_completeness(self, text: str) -> List[CorrectionIssue]:
        issues = []

        # Check for code blocks without docstrings
        code_blocks = re.findall(r"```(?:python|py)\n(.*?)```", text, re.DOTALL)
        for block in code_blocks:
            if "def " in block and '"""' not in block and "'''" not in block:
                issues.append(CorrectionIssue(
                    category="incomplete",
                    description="Code lacks docstrings",
                    original_text="",
                    corrected_text="",
                    confidence=0.5,
                    severity="low",
                ))

        # Check for truncated responses
        if text.rstrip().endswith(("...", "...", "[truncated]")):
            issues.append(CorrectionIssue(
                category="incomplete",
                description="Response appears truncated",
                original_text="",
                corrected_text="",
                confidence=0.6,
                severity="medium",
            ))

        # Check for missing error handling in code
        if "try:" in text and "except" not in text:
            issues.append(CorrectionIssue(
                category="incomplete",
                description="try block without except clause",
                original_text="",
                corrected_text="",
                confidence=0.4,
                severity="medium",
            ))

        return issues
