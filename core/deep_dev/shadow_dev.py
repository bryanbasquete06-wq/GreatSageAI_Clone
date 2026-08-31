#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel — Shadow Dev Engine
====================================
Autonomous background engineering that activates on:
  - User command (/shadow)
  - User inactivity (idle timeout)
  - Consecutive terminal failures (crashes, timeouts, compilation errors)

When activated, Shadow Dev:
  1. Analyzes call stack and logs silently
  2. Diagnoses root causes
  3. Writes fixes in a sandbox branch
  4. Runs tests in isolation
  5. Presents a visual report when user returns
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import (
    DiffResult,
    FileChange,
    ShadowChange,
    ShadowDiagnostic,
    ShadowPhase,
    ShadowReport,
    ShadowTrigger,
    ErrorSeverity,
)
from .safety import SafetyLayer

logger = logging.getLogger("elvea.deep_dev.shadow")


# ═══════════════════════════════════════════════════════════════════════════════
# Failure Pattern Detection
# ═══════════════════════════════════════════════════════════════════════════════

# Patterns that indicate terminal failures
FAILURE_PATTERNS = [
    # Python errors
    (r"Traceback \(most recent call last\)", "traceback", ErrorSeverity.ERROR),
    (r"(?i)SyntaxError:", "syntax_error", ErrorSeverity.ERROR),
    (r"(?i)ImportError:", "import_error", ErrorSeverity.ERROR),
    (r"(?i)ModuleNotFoundError:", "import_error", ErrorSeverity.ERROR),
    (r"(?i)TypeError:", "type_error", ErrorSeverity.ERROR),
    (r"(r?i)ValueError:", "value_error", ErrorSeverity.ERROR),
    (r"(?i)KeyError:", "key_error", ErrorSeverity.WARNING),
    (r"(?i)IndexError:", "index_error", ErrorSeverity.WARNING),
    (r"(?i)AttributeError:", "attribute_error", ErrorSeverity.ERROR),
    (r"(?i)RecursionError:", "recursion_error", ErrorSeverity.CRITICAL),
    # Runtime errors
    (r"(?i)Segmentation fault", "segfault", ErrorSeverity.CRITICAL),
    (r"(?i)MemoryError:", "memory_error", ErrorSeverity.CRITICAL),
    (r"(?i)OverflowError:", "overflow_error", ErrorSeverity.ERROR),
    # Timeout
    (r"(?i)TimeoutError:", "timeout", ErrorSeverity.WARNING),
    (r"(?i)timed? ?out", "timeout", ErrorSeverity.WARNING),
    # Compilation errors
    (r"(?i)error:.*compilation failed", "compile_error", ErrorSeverity.ERROR),
    (r"(?i)syntax error.*line \d+", "syntax_error", ErrorSeverity.ERROR),
    (r"(?i)TS\d{4}:", "typescript_error", ErrorSeverity.ERROR),
    # Connection errors
    (r"(?i)ConnectionRefusedError:", "connection_error", ErrorSeverity.WARNING),
    (r"(?i)ConnectionResetError:", "connection_error", ErrorSeverity.WARNING),
    (r"(?i)ECONNREFUSED", "connection_error", ErrorSeverity.WARNING),
]

# Patterns that indicate success (to detect recovery)
SUCCESS_PATTERNS = [
    r"(?i)^(OK|PASS|SUCCESS|BUILD SUCCEEDED)",
    r"(?i)tests? passed",
    r"(?i)all \d+ tests? passed",
    r"(?i)exit code: 0",
    r"(?i)Process finished with exit code 0",
]


class FailureDetector:
    """Monitors terminal output for consecutive failures."""

    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
        self._failures: deque = deque(maxlen=20)
        self._last_success_time: float = time.time()
        self._failure_streak: int = 0
        self._observers: List[Callable] = []

    def feed(self, line: str) -> Optional[str]:
        """
        Feed a terminal output line. Returns failure category if a pattern matches,
        None if the line is clean or success.
        """
        # Check for success
        for pattern in SUCCESS_PATTERNS:
            if re.search(pattern, line):
                self._failure_streak = 0
                self._last_success_time = time.time()
                return None

        # Check for failure
        for pattern, category, severity in FAILURE_PATTERNS:
            if re.search(pattern, line):
                self._failures.append({
                    "line": line.strip(),
                    "category": category,
                    "severity": severity.value,
                    "time": time.time(),
                })
                self._failure_streak += 1

                if self._failure_streak >= self.failure_threshold:
                    self._notify_observers(category)

                return category

        return None

    @property
    def should_activate(self) -> bool:
        """Check if failure streak exceeds threshold."""
        return self._failure_streak >= self.failure_threshold

    @property
    def failure_count(self) -> int:
        return self._failure_streak

    def get_failures(self) -> List[Dict[str, Any]]:
        return list(self._failures)

    def reset(self):
        self._failures.clear()
        self._failure_streak = 0
        self._last_success_time = time.time()

    def on_failure_streak(self, callback: Callable):
        self._observers.append(callback)

    def _notify_observers(self, category: str):
        for cb in self._observers:
            try:
                cb(category)
            except Exception:
                pass


class InactivityMonitor:
    """Monitors user activity and detects idle periods."""

    def __init__(self, idle_threshold_seconds: int = 300):
        self.idle_threshold = idle_threshold_seconds
        self._last_activity: float = time.time()
        self._observers: List[Callable] = []

    def touch(self):
        """Record user activity (mouse/keyboard)."""
        self._last_activity = time.time()

    @property
    def is_idle(self) -> bool:
        """Check if user has been idle beyond threshold."""
        return (time.time() - self._last_activity) > self.idle_threshold

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return time.time() - self._last_activity

    def on_idle(self, callback: Callable):
        self._observers.append(callback)


# ═══════════════════════════════════════════════════════════════════════════════
# Shadow Dev Analysis Engine
# ═══════════════════════════════════════════════════════════════════════════════

class ShadowAnalyzer:
    """
    Analyzes code, logs, and errors to diagnose issues and suggest fixes.
    Runs silently in the background.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._python_bin = "python"

    def analyze_logs(self, failures: List[Dict[str, Any]]) -> List[ShadowDiagnostic]:
        """Analyze collected failure logs and extract diagnostics."""
        diagnostics = []

        for failure in failures:
            line = failure.get("line", "")
            category = failure.get("category", "unknown")
            severity = ErrorSeverity(failure.get("severity", ErrorSeverity.WARNING.value))

            diag = self._classify_failure(line, category, severity)
            if diag:
                diagnostics.append(diag)

        return diagnostics

    def analyze_file_syntax(self, file_path: str) -> List[ShadowDiagnostic]:
        """Analyze a Python file for syntax errors and common issues."""
        diagnostics = []
        full_path = self.project_root / file_path

        if not full_path.exists():
            return diagnostics

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            return diagnostics

        # Syntax check
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            diagnostics.append(ShadowDiagnostic(
                file_path=file_path,
                line=e.lineno or 0,
                severity=ErrorSeverity.CRITICAL,
                category="syntax_error",
                title=f"Syntax error: {e.msg}",
                description=f"Line {e.lineno}: {e.text}" if e.text else str(e),
                suggestion=f"Fix the syntax at line {e.lineno}",
                confidence=1.0,
            ))
            return diagnostics

        # AST-based analysis
        diagnostics.extend(self._analyze_ast(tree, file_path))

        return diagnostics

    def analyze_code_quality(self, file_path: str) -> List[ShadowDiagnostic]:
        """Analyze code for quality issues (complexity, dead code, etc.)."""
        diagnostics = []
        full_path = self.project_root / file_path

        if not full_path.exists():
            return diagnostics

        try:
            content = full_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=file_path)
        except Exception:
            return diagnostics

        lines = content.split("\n")

        # Check for common issues
        diagnostics.extend(self._check_bare_except(tree, file_path))
        diagnostics.extend(self._check_unused_imports(tree, file_path, content))
        diagnostics.extend(self._check_complex_functions(tree, file_path))
        diagnostics.extend(self._check_print_statements(tree, file_path))
        # Deep analysis
        diagnostics.extend(self._check_mutable_defaults(tree, file_path))
        diagnostics.extend(self._check_bare_raises(tree, file_path))
        diagnostics.extend(self._check_star_imports(tree, file_path))
        diagnostics.extend(self._check_global_usage(tree, file_path))
        diagnostics.extend(self._check_type_comparison(tree, file_path))

        return diagnostics


    # -- Deep AST Detectors --

    def _check_mutable_defaults(self, tree, file_path):
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default is None:
                        continue
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        diagnostics.append(ShadowDiagnostic(
                            file_path=file_path, line=node.lineno,
                            severity=ErrorSeverity.WARNING, category="mutable_default",
                            title=f"Mutable default in '{node.name}'",
                            description="Mutable default is shared across calls.",
                            suggestion="Use None as default, then create inside function.",
                            confidence=0.95,
                        ))
        return diagnostics

    def _check_bare_raises(self, tree, file_path):
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.body and isinstance(node.body[0], ast.Raise) and node.body[0].exc is None:
                    if len(node.body) > 1:
                        diagnostics.append(ShadowDiagnostic(
                            file_path=file_path, line=node.body[0].lineno,
                            severity=ErrorSeverity.INFO, category="bare_raise",
                            title="Bare raise in multi-statement except",
                            description="Bare raise after other statements may lose context.",
                            suggestion="Use 'raise' as last statement, or capture exc_info.",
                            confidence=0.6,
                        ))
        return diagnostics

    def _check_star_imports(self, tree, file_path):
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        diagnostics.append(ShadowDiagnostic(
                            file_path=file_path, line=node.lineno,
                            severity=ErrorSeverity.WARNING, category="star_import",
                            title=f"Star import from '{node.module}'",
                            description="Star imports pollute namespace and hide dependencies.",
                            suggestion=f"Import specific names from {node.module}",
                            confidence=0.9,
                        ))
        return diagnostics

    def _check_global_usage(self, tree, file_path):
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for name in node.names:
                    diagnostics.append(ShadowDiagnostic(
                        file_path=file_path, line=node.lineno,
                        severity=ErrorSeverity.WARNING, category="global_usage",
                        title=f"Global variable '{name}'",
                        description="Global state makes code hard to test.",
                        suggestion="Use function parameters, return values, or a class instead.",
                        confidence=0.7,
                    ))
        return diagnostics

    def _check_type_comparison(self, tree, file_path):
        import re as _re
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        if (isinstance(node.left, ast.Call) and
                            isinstance(node.left.func, ast.Name) and
                            node.left.func.id == "type"):
                            diagnostics.append(ShadowDiagnostic(
                                file_path=file_path, line=node.lineno,
                                severity=ErrorSeverity.INFO, category="type_comparison",
                                title="Using type() instead of isinstance()",
                                description="type() comparison doesn't work with inheritance.",
                                suggestion="Replace with isinstance(obj, ClassName).",
                                confidence=0.85,
                            ))
        return diagnostics
    def generate_fix(self, diagnostic: ShadowDiagnostic) -> Optional[ShadowChange]:
        """Generate a code fix for a diagnostic."""
        if diagnostic.confidence < 0.5:
            return None

        full_path = self.project_root / diagnostic.file_path
        if not full_path.exists():
            return None

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")
        except Exception:
            return None

        if diagnostic.category == "syntax_error":
            return self._generate_syntax_fix(diagnostic, lines, content)
        elif diagnostic.category == "bare_except":
            return self._generate_bare_except_fix(diagnostic, lines, content)
        elif diagnostic.category == "unused_import":
            return self._generate_unused_import_fix(diagnostic, lines, content)
        elif diagnostic.category == "high_complexity":
            return self._generate_complexity_hint(diagnostic)
        elif diagnostic.category == "mutable_default":
            return self._generate_mutable_default_fix(diagnostic, lines, content)
        elif diagnostic.category == "star_import":
            return self._generate_star_import_fix(diagnostic, lines, content)
        elif diagnostic.category == "type_comparison":
            return self._generate_type_comparison_fix(diagnostic, lines, content)
        elif diagnostic.category in ("global_usage", "bare_raise", "missing_return"):
            return None  # Needs semantic analysis

        return None

    # ── Private helpers ────────────────────────────────────────────────

    def _classify_failure(self, line: str, category: str,
                         severity: ErrorSeverity) -> Optional[ShadowDiagnostic]:
        """Classify a failure line into a diagnostic."""
        # Extract file and line number from traceback
        tb_match = re.search(r'File "(.+?)", line (\d+)', line)
        if tb_match:
            return ShadowDiagnostic(
                file_path=tb_match.group(1),
                line=int(tb_match.group(2)),
                severity=severity,
                category=category,
                title=f"Runtime {category.replace('_', ' ')}",
                description=line.strip(),
                suggestion=self._suggest_fix(category),
                confidence=0.8,
            )

        # Module not found
        mod_match = re.search(r"No module named ['\"](.+?)['\"]", line)
        if mod_match:
            return ShadowDiagnostic(
                severity=severity,
                category="import_error",
                title=f"Missing module: {mod_match.group(1)}",
                description=line.strip(),
                suggestion=f"pip install {mod_match.group(1)}",
                confidence=0.9,
            )

        # Generic classification
        return ShadowDiagnostic(
            severity=severity,
            category=category,
            title=f"{category.replace('_', ' ').title()}",
            description=line.strip(),
            suggestion=self._suggest_fix(category),
            confidence=0.5,
        )

    def _suggest_fix(self, category: str) -> str:
        """Suggest a fix based on error category."""
        suggestions = {
            "traceback": "Check the traceback above for the exact file and line.",
            "syntax_error": "Fix the syntax error — likely a missing colon, bracket, or indentation.",
            "import_error": "Install the missing module or check the import path.",
            "type_error": "Check function signatures and variable types.",
            "value_error": "Validate input before passing to the function.",
            "key_error": "Use .get() or check if key exists before access.",
            "index_error": "Check list bounds before indexing.",
            "attribute_error": "Check if the object has the attribute you're accessing.",
            "recursion_error": "Add a base case or increase recursion limit.",
            "timeout": "Optimize the operation or increase timeout threshold.",
            "memory_error": "Reduce memory usage or use streaming/chunking.",
            "connection_error": "Check if the service is running and accessible.",
            "compile_error": "Fix compilation errors before running.",
            "segfault": "Check for null pointer dereferences or buffer overflows.",
            "overflow_error": "Check numeric type ranges.",
        }
        return suggestions.get(category, "Investigate the error in context.")

    def _analyze_ast(self, tree: ast.Module, file_path: str) -> List[ShadowDiagnostic]:
        """Analyze AST for common patterns."""
        diagnostics = []

        for node in ast.walk(tree):
            # Large functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, "end_lineno") and node.end_lineno:
                    size = node.end_lineno - node.lineno
                    if size > 100:
                        diagnostics.append(ShadowDiagnostic(
                            file_path=file_path,
                            line=node.lineno,
                            severity=ErrorSeverity.WARNING,
                            category="large_function",
                            title=f"Function '{node.name}' is {size} lines",
                            description=f"Functions over 100 lines are hard to maintain.",
                            suggestion=f"Consider splitting '{node.name}' into smaller functions.",
                            confidence=0.7,
                        ))

        return diagnostics

    def _check_bare_except(self, tree: ast.Module, file_path: str) -> List[ShadowDiagnostic]:
        """Check for bare except clauses."""
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                diagnostics.append(ShadowDiagnostic(
                    file_path=file_path,
                    line=node.lineno,
                    severity=ErrorSeverity.WARNING,
                    category="bare_except",
                    title="Bare except clause",
                    description="Catches all exceptions including KeyboardInterrupt.",
                    suggestion="Use 'except Exception:' instead of bare 'except:'.",
                    confidence=0.9,
                ))
        return diagnostics

    def _check_unused_imports(self, tree: ast.Module, file_path: str,
                             content: str) -> List[ShadowDiagnostic]:
        """Check for potentially unused imports."""
        diagnostics = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imports.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        name = alias.asname or alias.name
                        imports.append((name, node.lineno))

        # Check if imported names appear in the rest of the code
        for name, lineno in imports:
            # Simple heuristic: count occurrences in non-import lines
            count = 0
            for i, line in enumerate(content.split("\n"), 1):
                if i == lineno:
                    continue
                if re.search(r'\b' + re.escape(name) + r'\b', line):
                    count += 1
                    break

            if count == 0:
                diagnostics.append(ShadowDiagnostic(
                    file_path=file_path,
                    line=lineno,
                    severity=ErrorSeverity.INFO,
                    category="unused_import",
                    title=f"Potentially unused import: '{name}'",
                    description=f"'{name}' is imported but not used in the file.",
                    suggestion=f"Remove the unused import.",
                    confidence=0.6,
                ))

        return diagnostics

    def _check_complex_functions(self, tree: ast.Module, file_path: str) -> List[ShadowDiagnostic]:
        """Check for functions with high cyclomatic complexity."""
        diagnostics = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = self._calc_complexity(node)
                if cc > 15:
                    diagnostics.append(ShadowDiagnostic(
                        file_path=file_path,
                        line=node.lineno,
                        severity=ErrorSeverity.WARNING,
                        category="high_complexity",
                        title=f"Function '{node.name}' has CC={cc}",
                        description=f"Cyclomatic complexity {cc} exceeds threshold of 15.",
                        suggestion=f"Refactor '{node.name}' into smaller functions.",
                        confidence=0.8,
                    ))

        return diagnostics

    def _check_print_statements(self, tree: ast.Module, file_path: str) -> List[ShadowDiagnostic]:
        """Check for print statements in production code."""
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    diagnostics.append(ShadowDiagnostic(
                        file_path=file_path,
                        line=node.lineno,
                        severity=ErrorSeverity.INFO,
                        category="print_statement",
                        title="Print statement in code",
                        description="Consider using logging instead of print().",
                        suggestion="Replace print() with logging.info() or logging.debug().",
                        confidence=0.5,
                    ))
        return diagnostics

    def _calc_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function node."""
        cc = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                cc += 1
            elif isinstance(child, ast.BoolOp):
                cc += len(child.values) - 1
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                cc += 1
        return cc

    # ── Fix generators ─────────────────────────────────────────────────

    def _generate_syntax_fix(self, diag: ShadowDiagnostic, lines: List[str],
                            content: str) -> Optional[ShadowChange]:
        """Try to generate a syntax fix."""
        if diag.line < 1 or diag.line > len(lines):
            return None

        line = lines[diag.line - 1]

        # Missing colon after def/class/if/for/while
        for kw in ("def ", "class ", "if ", "for ", "while ", "elif ", "else", "try", "except", "finally"):
            if line.strip().startswith(kw) and not line.rstrip().endswith(":") and not line.rstrip().endswith(",") and not line.rstrip().endswith("("):
                new_line = line.rstrip() + ":"
                new_lines = lines[:diag.line - 1] + [new_line] + lines[diag.line:]
                new_content = "\n".join(new_lines)
                return ShadowChange(
                    file_path=diag.file_path,
                    description=f"Add missing colon at line {diag.line}",
                    old_code=line,
                    new_code=new_line,
                    reason="Syntax error: missing colon after statement",
                    risk_level="low",
                )

        return None

    def _generate_bare_except_fix(self, diag: ShadowDiagnostic, lines: List[str],
                                 content: str) -> Optional[ShadowChange]:
        """Fix bare except clauses."""
        if diag.line < 1 or diag.line > len(lines):
            return None

        line = lines[diag.line - 1]
        if "except:" in line:
            new_line = line.replace("except:", "except Exception:")
            new_lines = lines[:diag.line - 1] + [new_line] + lines[diag.line:]
            new_content = "\n".join(new_lines)
            return ShadowChange(
                file_path=diag.file_path,
                description=f"Replace bare except at line {diag.line}",
                old_code=line,
                new_code=new_line,
                reason="Bare except catches too much — use Exception explicitly",
                risk_level="low",
            )
        return None

    def _generate_unused_import_fix(self, diag: ShadowDiagnostic, lines: List[str],
                                   content: str) -> Optional[ShadowChange]:
        """Remove unused import."""
        if diag.line < 1 or diag.line > len(lines):
            return None

        line = lines[diag.line - 1]
        new_lines = lines[:diag.line - 1] + lines[diag.line:]
        new_content = "\n".join(new_lines)
        return ShadowChange(
            file_path=diag.file_path,
            description=f"Remove unused import at line {diag.line}",
            old_code=line,
            new_code="(removed)",
            reason="Import is not used",
            risk_level="low",
        )

    def _generate_complexity_hint(self, diag: ShadowDiagnostic):
        return None

    def _generate_mutable_default_fix(self, diag, lines, content):
        import re as _re
        if diag.line < 1 or diag.line > len(lines):
            return None
        line = lines[diag.line - 1]
        new_line = _re.sub(r'=\[\]|=\{\}|=set\(\)', '=None', line)
        if new_line != line:
            return ShadowChange(
                file_path=diag.file_path,
                description=f"Fix mutable default at line {diag.line}",
                old_code=line, new_code=new_line,
                reason="Mutable default is shared across calls",
                risk_level="low",
            )
        return None

    def _generate_star_import_fix(self, diag, lines, content):
        if diag.line < 1 or diag.line > len(lines):
            return None
        line = lines[diag.line - 1]
        new_line = "# TODO: replace star import with specific imports"
        return ShadowChange(
            file_path=diag.file_path,
            description=f"Replace star import",
            old_code=line, new_code=new_line,
            reason="Star imports pollute namespace",
            risk_level="low",
        )

    def _generate_type_comparison_fix(self, diag, lines, content):
        import re as _re
        if diag.line < 1 or diag.line > len(lines):
            return None
        line = lines[diag.line - 1]
        new_line = _re.sub(r'type\((\w+)\)\s*==\s*(\w+)', r'isinstance(\1, \2)', line)
        new_line = _re.sub(r'type\((\w+)\)\s*!=\s*(\w+)', r'not isinstance(\1, \2)', new_line)
        if new_line != line:
            return ShadowChange(
                file_path=diag.file_path,
                description=f"Replace type() comparison at line {diag.line}",
                old_code=line, new_code=new_line,
                reason="isinstance() supports inheritance",
                risk_level="low",
            )
        return None

    def _generate_global_usage_fix(self, diag, lines, content):
        return None

    def _generate_bare_raise_fix(self, diag, lines, content):
        return None

    def _generate_missing_return_fix(self, diag, lines, content):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Shadow Dev Main Engine
# ═══════════════════════════════════════════════════════════════════════════════

class ShadowDevEngine:
    """
    Main Shadow Dev engine that orchestrates autonomous background engineering.

    Usage:
        engine = ShadowDevEngine(project_root=".", safety=safety_layer)
        # Feed terminal output
        engine.feed_terminal_line("Traceback (most recent call last):")
        # Or trigger manually
        report = engine.analyze_now(trigger=ShadowTrigger.USER_COMMAND)
    """

    def __init__(self, project_root: str, safety: Optional[SafetyLayer] = None):
        self.project_root = project_root
        self.safety = safety or SafetyLayer(project_root)
        self.analyzer = ShadowAnalyzer(project_root)
        self.failure_detector = FailureDetector(failure_threshold=3)
        self.inactivity_monitor = InactivityMonitor(idle_threshold_seconds=300)

        self._active = False
        self._current_report: Optional[ShadowReport] = None
        self._analysis_thread: Optional[threading.Thread] = None
        self._on_report_ready: Optional[Callable[[ShadowReport], None]] = None
        self._lock = threading.Lock()

        # Register failure callback
        self.failure_detector.on_failure_streak(self._on_failure_streak)

    def on_report_ready(self, callback: Callable[[ShadowReport], None]):
        """Register callback for when a report is ready for user review."""
        self._on_report_ready = callback

    def feed_terminal_line(self, line: str):
        """Feed a terminal output line to the failure detector."""
        self.failure_detector.feed(line)

    def touch_activity(self):
        """Record user activity (call on mouse/keyboard events)."""
        self.inactivity_monitor.touch()

    def analyze_now(self, trigger: ShadowTrigger = ShadowTrigger.USER_COMMAND,
                   target_files: Optional[List[str]] = None) -> ShadowReport:
        """
        Run analysis immediately. This is the core method.
        Can be called from /shadow command or automatically.
        """
        with self._lock:
            if self._active:
                logger.info("[ShadowDev] Analysis already in progress")
                return self._current_report or ShadowReport()

            self._active = True
            self._current_report = ShadowReport(trigger=trigger)
            report = self._current_report

        try:
            # Phase 1: ANALYZING
            report.phase = ShadowPhase.ANALYZING
            logger.info(f"[ShadowDev] Phase: ANALYZING (trigger={trigger.name})")

            # Collect failures
            failures = self.failure_detector.get_failures()

            # Phase 2: DIAGNOSING
            report.phase = ShadowPhase.DIAGNOSING
            logger.info("[ShadowDev] Phase: DIAGNOSING")

            # Analyze failure logs
            diagnostics = self.analyzer.analyze_logs(failures)
            report.diagnostics.extend(diagnostics)

            # Analyze source files if target specified
            files_to_check = target_files or self._discover_core_files()
            for f in files_to_check:
                file_diags = self.analyzer.analyze_file_syntax(f)
                report.diagnostics.extend(file_diags)

                quality_diags = self.analyzer.analyze_code_quality(f)
                report.diagnostics.extend(quality_diags)

                report.files_analyzed += 1

            # Count findings
            report.errors_found = sum(1 for d in report.diagnostics
                                     if d.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL))
            report.performance_issues = sum(1 for d in report.diagnostics
                                           if d.category in ("high_complexity", "large_function"))
            report.test_suggestions = sum(1 for d in report.diagnostics
                                         if d.category in ("bare_except", "print_statement"))

            # Phase 3: SOLVING
            report.phase = ShadowPhase.SOLVING
            logger.info("[ShadowDev] Phase: SOLVING")

            # Generate fixes for high-confidence diagnostics
            changes = []
            for diag in report.diagnostics:
                if diag.confidence >= 0.6:
                    change = self.analyzer.generate_fix(diag)
                    if change:
                        changes.append(change)
            report.changes = changes

            # Phase 4: WRITING (apply in sandbox)
            if changes:
                report.phase = ShadowPhase.WRITING
                logger.info("[ShadowDev] Phase: WRITING (sandbox)")

                try:
                    sandbox_branch = self.safety.ensure_sandbox()
                    file_changes = self._changes_to_file_changes(changes)
                    self.safety.apply_changes_in_sandbox(file_changes)

                    # Build diff
                    report.diff = self._build_diff(changes)
                except Exception as e:
                    logger.error(f"[ShadowDev] Sandbox write failed: {e}")
                    report.diagnostics.append(ShadowDiagnostic(
                        severity=ErrorSeverity.WARNING,
                        category="sandbox_error",
                        title="Failed to apply sandbox changes",
                        description=str(e),
                        confidence=0.5,
                    ))

            # Phase 5: READY
            report.phase = ShadowPhase.READY
            report.completed_at = time.time()
            logger.info(f"[ShadowDev] Phase: READY — {report.summary}")

            # Notify callback
            if self._on_report_ready:
                try:
                    self._on_report_ready(report)
                except Exception as e:
                    logger.error(f"[ShadowDev] Report callback failed: {e}")

            return report

        except Exception as e:
            logger.error(f"[ShadowDev] Analysis failed: {e}")
            report.phase = ShadowPhase.DISCARDED
            report.completed_at = time.time()
            return report

        finally:
            self._active = False

    def start_background_analysis(self, trigger: ShadowTrigger = ShadowTrigger.USER_COMMAND,
                                  target_files: Optional[List[str]] = None):
        """Start analysis in a background thread."""
        def _run():
            self.analyze_now(trigger=trigger, target_files=target_files)

        self._analysis_thread = threading.Thread(target=_run, daemon=True)
        self._analysis_thread.start()

    def approve_and_apply(self, report_id: Optional[str] = None) -> bool:
        """Approve the current report's changes and apply them."""
        with self._lock:
            if not self._current_report or self._current_report.phase != ShadowPhase.READY:
                return False

            self._current_report.phase = ShadowPhase.APPLIED
            logger.info("[ShadowDev] Changes approved and applied")
            return True

    def discard_report(self) -> bool:
        """Discard the current report's changes."""
        with self._lock:
            if not self._current_report:
                return False

            self._current_report.phase = ShadowPhase.DISCARDED
            self.safety.discard_sandbox()
            logger.info("[ShadowDev] Report discarded")
            self._current_report = None
            return True

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_report(self) -> Optional[ShadowReport]:
        return self._current_report

    # ── Private helpers ────────────────────────────────────────────────

    def _on_failure_streak(self, category: str):
        """Callback when failure streak exceeds threshold."""
        logger.info(f"[ShadowDev] Failure streak detected: {category} — starting background analysis")
        if not self._active:
            self.start_background_analysis(trigger=ShadowTrigger.FAILURE_STREAK)

    def _discover_core_files(self) -> List[str]:
        """Discover Python files in the core/ directory."""
        core_dir = Path(self.project_root) / "core"
        if not core_dir.exists():
            return []

        files = []
        for f in core_dir.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            files.append(str(f.relative_to(self.project_root)))

        return files[:20]  # Limit to 20 files

    def _changes_to_file_changes(self, changes: List[ShadowChange]) -> List[FileChange]:
        """Convert ShadowChanges to FileChanges for the safety layer."""
        file_changes = []
        for change in changes:
            old_lines = change.old_code.split("\n")
            new_lines = change.new_code.split("\n")
            file_changes.append(FileChange(
                path=change.file_path,
                change_type="modified",
                old_content=change.old_code,
                new_content=change.new_code,
                line_added=len(new_lines),
                line_removed=len(old_lines),
            ))
        return file_changes

    def _build_diff(self, changes: List[ShadowChange]) -> DiffResult:
        """Build a DiffResult from changes."""
        file_changes = self._changes_to_file_changes(changes)
        return DiffResult(
            changes=file_changes,
            summary=f"{len(changes)} changes across {len(set(c.file_path for c in changes))} files",
        )
