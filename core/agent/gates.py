#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Quality Gates
=================================
Automated quality validation after each execution step.
Runs linting, type checking, and tests to ensure code quality.
"""

from __future__ import annotations

import re
import subprocess
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("elvea.agent.gates")


@dataclass
class GateResult:
    """Result of a quality gate check."""
    gate_name: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    details: str = ""
    duration_ms: float = 0.0

    @property
    def issue_count(self) -> int:
        return len(self.issues)


@dataclass
class QualityReport:
    """Combined report from all quality gates."""
    all_passed: bool = True
    gates: List[GateResult] = field(default_factory=list)
    total_issues: int = 0
    blocking_issues: List[str] = field(default_factory=list)

    def add_gate(self, gate: GateResult):
        self.gates.append(gate)
        self.total_issues += gate.issue_count
        if not gate.passed:
            self.all_passed = False
            self.blocking_issues.extend(
                f"[{gate.gate_name}] {issue}" for issue in gate.issues[:3]
            )


class QualityGates:
    """Runs quality checks on code after execution steps."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()

    def validate_all(self, files_changed: List[str] = None) -> QualityReport:
        """Run all quality gates and return combined report."""
        report = QualityReport()

        # Gate 1: Syntax check
        report.add_gate(self.gate_syntax(files_changed))

        # Gate 2: Linting
        report.add_gate(self.gate_lint(files_changed))

        # Gate 3: Type checking (if mypy/pyright available)
        gate_type = self.gate_typecheck(files_changed)
        if gate_type:
            report.add_gate(gate_type)

        # Gate 4: Unit tests
        report.add_gate(self.gate_tests())

        return report

    def gate_syntax(self, files_changed: List[str] = None) -> GateResult:
        """Check Python syntax of changed files."""
        gate = GateResult(gate_name="syntax", passed=True)
        import time
        t0 = time.time()

        py_files = self._get_changed_py_files(files_changed)
        if not py_files:
            gate.details = "No Python files to check"
            gate.duration_ms = (time.time() - t0) * 1000
            return gate

        for fp in py_files:
            try:
                result = subprocess.run(
                    ["python", "-m", "py_compile", str(fp)],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    gate.passed = False
                    error = result.stderr.strip().split("\n")[0]
                    gate.issues.append(f"{fp.name}: {error}")
            except Exception as e:
                gate.issues.append(f"{fp.name}: {e}")

        gate.details = f"Checked {len(py_files)} files"
        gate.duration_ms = (time.time() - t0) * 1000
        return gate

    def gate_lint(self, files_changed: List[str] = None) -> GateResult:
        """Run flake8/ruff linting on changed files."""
        gate = GateResult(gate_name="lint", passed=True)
        import time
        t0 = time.time()

        py_files = self._get_changed_py_files(files_changed)
        if not py_files:
            gate.details = "No Python files to lint"
            gate.duration_ms = (time.time() - t0) * 1000
            return gate

        # Try ruff first (faster), then flake8
        for linter in ["ruff", "flake8"]:
            try:
                cmd = [linter]
                if linter == "ruff":
                    cmd.extend(["check", "--output-format=text"])
                elif linter == "flake8":
                    cmd.extend(["--max-line-length=120", "--ignore=E501,W503"])

                cmd.extend([str(f) for f in py_files])

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30,
                )

                if result.returncode != 0 and result.stdout.strip():
                    issues = result.stdout.strip().split("\n")
                    # Filter to only errors (not warnings for non-blocking)
                    errors = [i for i in issues if " E " in i or "error" in i.lower()]
                    warnings = [i for i in issues if i not in errors]

                    if errors:
                        gate.passed = False
                        gate.issues.extend(errors[:5])
                    gate.details = f"{linter}: {len(errors)} errors, {len(warnings)} warnings"
                else:
                    gate.details = f"{linter}: clean"
                break  # If one linter works, don't try the other
            except FileNotFoundError:
                continue  # Try next linter
            except Exception as e:
                gate.details = f"Lint error: {e}"
                break

        gate.duration_ms = (time.time() - t0) * 1000
        return gate

    def gate_typecheck(self, files_changed: List[str] = None) -> Optional[GateResult]:
        """Run type checking (mypy/pyright) if available."""
        gate = GateResult(gate_name="typecheck", passed=True)
        import time
        t0 = time.time()

        py_files = self._get_changed_py_files(files_changed)
        if not py_files:
            return None

        for checker in ["mypy", "pyright"]:
            try:
                cmd = [checker]
                if checker == "mypy":
                    cmd.extend(["--ignore-missing-imports", "--no-error-summary"])
                cmd.extend([str(f) for f in py_files[:10]])  # limit files

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                )

                if result.returncode != 0 and result.stdout.strip():
                    errors = [l for l in result.stdout.strip().split("\n")
                              if "error" in l.lower()]
                    gate.issues = errors[:5]
                    gate.passed = len(errors) == 0

                gate.details = f"{checker}: checked {len(py_files)} files"
                break
            except FileNotFoundError:
                continue
            except Exception:
                break

        gate.duration_ms = (time.time() - t0) * 1000
        return gate if gate.details else None

    def gate_tests(self, test_path: str = ".") -> GateResult:
        """Run unit tests."""
        gate = GateResult(gate_name="tests", passed=True)
        import time
        t0 = time.time()

        cmd = self._detect_test_command(test_path)
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=str(self.project_root),
                capture_output=True, text=True, timeout=180,
            )

            output = result.stdout + "\n" + result.stderr

            # Parse pytest output
            passed = len(re.findall(r'(\d+) passed', output))
            failed = len(re.findall(r'(\d+) failed', output))
            errors = len(re.findall(r'(\d+) error', output))

            if failed > 0 or errors > 0:
                gate.passed = False
                # Extract failure details
                fail_lines = [l for l in output.split("\n") if "FAILED" in l]
                gate.issues = fail_lines[:5]

            gate.details = f"{passed} passed, {failed} failed, {errors} errors"
        except subprocess.TimeoutExpired:
            gate.passed = False
            gate.issues.append("Tests timed out after 180s")
        except Exception as e:
            gate.passed = False
            gate.issues.append(f"Test execution error: {e}")

        gate.duration_ms = (time.time() - t0) * 1000
        return gate

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_changed_py_files(self, files_changed: List[str] = None) -> List[Path]:
        """Get Python files that were changed."""
        if not files_changed:
            return []
        return [
            self.project_root / f for f in files_changed
            if f.endswith(".py") and (self.project_root / f).exists()
        ]

    def _detect_test_command(self, path: str) -> str:
        """Auto-detect test command."""
        root = self.project_root
        if (root / "pyproject.toml").exists():
            return f"python -m pytest {path} -v --tb=short -x"
        if (root / "package.json").exists():
            return "npm test"
        return f"python -m pytest {path} -v --tb=short -x"
