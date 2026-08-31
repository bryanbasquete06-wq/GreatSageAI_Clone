#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Step Executor
================================
Executes individual plan steps: code generation, file operations,
command execution, with automatic checkpointing and rollback support.
"""

from __future__ import annotations

import json
import os
import re
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.agent.models import (
    PlanStep, StepAction, StepStatus, ExecutionResult,
    Checkpoint, ErrorCategory,
)

logger = logging.getLogger("elvea.agent.executor")


# ═══════════════════════════════════════════════════════════════════════════════
# Error Classification
# ═══════════════════════════════════════════════════════════════════════════════

def classify_error(error_text: str) -> ErrorCategory:
    """Classify an error into a category for smart recovery."""
    e = error_text.lower()
    if any(k in e for k in ("syntaxerror", "indentation", "unexpected token", "invalid syntax")):
        return ErrorCategory.SYNTAX
    if any(k in e for k in ("traceback", "runtimeerror", "typeerror", "valueerror",
                              "nameerror", "attributeerror", "indexerror", "keyerror")):
        return ErrorCategory.RUNTIME
    if any(k in e for k in ("assert", "assertionerror", "failed", "expected", "test_")):
        return ErrorCategory.TEST_FAILURE
    if any(k in e for k in ("modulenotfound", "importerror", "no module named",
                              "pip install", "npm install", "not found")):
        return ErrorCategory.DEPENDENCY
    if any(k in e for k in ("config", "configuration", "yaml", "json", "env")):
        return ErrorCategory.CONFIG
    if any(k in e for k in ("timeout", "timed out", "deadline")):
        return ErrorCategory.TIMEOUT
    if any(k in e for k in ("permission", "access denied", "forbidden")):
        return ErrorCategory.PERMISSION
    return ErrorCategory.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# Step Executor
# ═══════════════════════════════════════════════════════════════════════════════

class StepExecutor:
    """Executes individual plan steps with safety and rollback support."""

    def __init__(self, project_root: str = ".", llm_engine=None):
        self.project_root = Path(project_root).resolve()
        self._llm = llm_engine
        self._backups: Dict[int, List[Tuple[str, bytes]]] = {}  # step_id → [(path, original_content)]
        self._git_enabled = self._check_git()

    def set_llm(self, llm_engine):
        self._llm = llm_engine

    def execute_step(self, step: PlanStep, context: Dict[str, Any] = None) -> ExecutionResult:
        """Execute a single plan step and return the result."""
        logger.info(f"Executing step {step.id}: {step.description[:80]}")
        t0 = time.time()
        step.start()

        try:
            # Create checkpoint before risky operations
            if step.action in (StepAction.CREATE_FILE, StepAction.MODIFY_FILE,
                               StepAction.DELETE_FILE, StepAction.RUN_COMMAND):
                self._backup_files(step)

            # Dispatch to appropriate handler
            result = self._dispatch(step, context or {})
            result.duration_ms = (time.time() - t0) * 1000

            step.complete(result)

            if result.success:
                logger.info(f"Step {step.id} completed in {result.duration_ms:.0f}ms")
            else:
                logger.warning(f"Step {step.id} failed: {result.error[:200] if result.error else '?'}")

            return result

        except Exception as e:
            duration = (time.time() - t0) * 1000
            result = ExecutionResult(
                success=False, error=str(e),
                error_category=classify_error(str(e)),
                duration_ms=duration,
            )
            step.complete(result)
            return result

    def rollback_step(self, step: PlanStep) -> bool:
        """Rollback changes made by a step using backups."""
        if step.id not in self._backups:
            logger.warning(f"No backup for step {step.id}")
            return False

        logger.info(f"Rolling back step {step.id}")
        for file_path, original_content in self._backups[step.id]:
            try:
                p = self.project_root / file_path
                if original_content is None:
                    # File was created by this step — delete it
                    if p.exists():
                        p.unlink()
                        logger.info(f"Deleted {file_path}")
                else:
                    # File was modified — restore original
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(original_content)
                    logger.info(f"Restored {file_path}")
            except Exception as e:
                logger.error(f"Rollback failed for {file_path}: {e}")
                return False

        step.status = StepStatus.ROLLING_BACK
        return True

    def create_git_checkpoint(self, step: PlanStep, message: str = "") -> Optional[str]:
        """Create a git commit checkpoint."""
        if not self._git_enabled:
            return None
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(self.project_root),
                capture_output=True, timeout=10,
            )
            msg = message or f"Agent checkpoint: step {step.id} — {step.description[:50]}"
            result = subprocess.run(
                ["git", "commit", "-m", msg, "--allow-empty"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=5,
                )
                commit_hash = hash_result.stdout.strip()
                logger.info(f"Git checkpoint: {commit_hash[:8]}")
                return commit_hash
        except Exception as e:
            logger.debug(f"Git checkpoint failed: {e}")
        return None

    def rollback_to_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Rollback the entire project to a git checkpoint."""
        if not self._git_enabled or not checkpoint.commit_hash:
            return False
        try:
            subprocess.run(
                ["git", "reset", "--hard", checkpoint.commit_hash],
                cwd=str(self.project_root),
                capture_output=True, timeout=10,
            )
            logger.info(f"Rolled back to checkpoint {checkpoint.commit_hash[:8]}")
            return True
        except Exception as e:
            logger.error(f"Git rollback failed: {e}")
            return False

    # ── Action Dispatchers ────────────────────────────────────────────

    def _dispatch(self, step: PlanStep, context: Dict[str, Any]) -> ExecutionResult:
        """Dispatch step to the appropriate handler."""
        handlers = {
            StepAction.CREATE_FILE: self._exec_create_file,
            StepAction.MODIFY_FILE: self._exec_modify_file,
            StepAction.DELETE_FILE: self._exec_delete_file,
            StepAction.RUN_COMMAND: self._exec_run_command,
            StepAction.RUN_TESTS: self._exec_run_tests,
            StepAction.CREATE_DIR: self._exec_create_dir,
            StepAction.WRITE_CONFIG: self._exec_write_config,
            StepAction.INSTALL_DEPS: self._exec_install_deps,
            StepAction.CUSTOM: self._exec_custom,
        }
        handler = handlers.get(step.action, self._exec_custom)
        return handler(step, context)

    def _exec_create_file(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Create a new file with content from step params."""
        path = self._resolve_path(step.params.get("path", ""))
        content = step.params.get("content", "")

        if not path:
            return ExecutionResult(success=False, error="No file path specified")

        # If no content, generate via LLM
        if not content:
            content = self._generate_code(step)

        if not content:
            return ExecutionResult(success=False, error="No content to write")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            rel = str(path.relative_to(self.project_root))
            return ExecutionResult(
                success=True,
                output=f"Created {rel} ({len(content)} bytes)",
                files_changed=[rel],
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _exec_modify_file(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Modify an existing file."""
        path = self._resolve_path(step.params.get("path", ""))
        content = step.params.get("content", "")
        modification = step.params.get("modification", "")

        if not path or not path.exists():
            return ExecutionResult(success=False, error=f"File not found: {step.params.get('path')}")

        try:
            original = path.read_text(encoding="utf-8")
            if content:
                path.write_text(content, encoding="utf-8")
            elif modification:
                # Apply modification (could be append, replace, etc.)
                path.write_text(original + "\n" + modification, encoding="utf-8")

            rel = str(path.relative_to(self.project_root))
            return ExecutionResult(
                success=True,
                output=f"Modified {rel}",
                files_changed=[rel],
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _exec_delete_file(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Delete a file."""
        path = self._resolve_path(step.params.get("path", ""))
        if not path or not path.exists():
            return ExecutionResult(success=True, output="File already absent")
        try:
            rel = str(path.relative_to(self.project_root))
            path.unlink()
            return ExecutionResult(success=True, output=f"Deleted {rel}", files_changed=[rel])
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _exec_run_command(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Run a shell command with timeout and output capture."""
        command = step.params.get("command", step.params.get("content", ""))
        if not command:
            return ExecutionResult(success=False, error="No command specified")

        timeout = step.params.get("timeout", 120)
        logger.info(f"Running: {command[:100]}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            output = result.stdout
            error = result.stderr
            success = result.returncode == 0

            if not success and error:
                return ExecutionResult(
                    success=False, output=output, error=error[:2000],
                    error_category=classify_error(error),
                )

            return ExecutionResult(
                success=True,
                output=output[:2000],
                error=error[:500] if error else None,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Command timed out after {timeout}s",
                error_category=ErrorCategory.TIMEOUT,
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _exec_run_tests(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Run tests and parse results."""
        test_cmd = step.params.get("command", "")
        test_path = step.params.get("path", ".")

        if not test_cmd:
            # Auto-detect test framework
            test_cmd = self._detect_test_command(test_path)

        result = self._exec_run_command(
            PlanStep(id=step.id, description="run tests", action=StepAction.RUN_COMMAND,
                     params={"command": test_cmd, "timeout": 180}),
            ctx,
        )

        # Parse test results
        if result.success:
            passed, total = self._parse_test_output(result.output)
            result.tests_passed = passed
            result.tests_total = total

        return result

    def _exec_create_dir(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Create a directory."""
        path = self._resolve_path(step.params.get("path", ""))
        try:
            path.mkdir(parents=True, exist_ok=True)
            return ExecutionResult(success=True, output=f"Created directory {path.name}")
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _exec_write_config(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Write a configuration file (JSON, YAML, TOML, .env, etc.)."""
        return self._exec_create_file(step, ctx)

    def _exec_install_deps(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Install dependencies."""
        deps = step.params.get("packages", [])
        manager = step.params.get("manager", "pip")
        command = step.params.get("command", "")

        if not command:
            if manager == "pip":
                command = f"pip install {' '.join(deps)}"
            elif manager == "npm":
                command = f"npm install {' '.join(deps)}"
            elif manager == "uv":
                command = f"uv pip install {' '.join(deps)}"

        step.params["command"] = command
        return self._exec_run_command(step, ctx)

    def _exec_custom(self, step: PlanStep, ctx: Dict) -> ExecutionResult:
        """Handle custom/unknown step types — try command or LLM generation."""
        command = step.params.get("command", "")
        if command:
            return self._exec_run_command(step, ctx)

        # Try to generate and execute code
        content = step.params.get("content", "")
        if content:
            return self._exec_create_file(step, ctx)

        return ExecutionResult(
            success=False,
            error=f"Custom step has no command or content: {step.description}"
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path relative to project root."""
        if not path_str:
            return self.project_root / "untitled"
        p = Path(path_str)
        if p.is_absolute():
            return p
        return self.project_root / p

    def _backup_files(self, step: PlanStep):
        """Backup files that will be modified by this step."""
        backups = []
        path_str = step.params.get("path", "")
        if path_str:
            p = self._resolve_path(path_str)
            if p.exists():
                try:
                    backups.append((str(p.relative_to(self.project_root)), p.read_bytes()))
                except Exception:
                    backups.append((str(p.relative_to(self.project_root)), None))
            else:
                # New file being created
                try:
                    backups.append((str(p.relative_to(self.project_root)), None))
                except Exception:
                    pass
        self._backups[step.id] = backups

    def _generate_code(self, step: PlanStep) -> Optional[str]:
        """Generate code for a step using the LLM."""
        if not self._llm:
            return None

        language = step.params.get("language", "python")
        purpose = step.params.get("purpose", step.description)

        prompt = (
            f"Generate complete, production-ready {language} code for:\n"
            f"{purpose}\n\n"
            f"Requirements:\n"
            f"- Complete, runnable code (no placeholders)\n"
            f"- Include error handling\n"
            f"- Follow best practices\n"
            f"- Include type hints where applicable\n"
            f"Return ONLY the code, no explanations."
        )

        try:
            if hasattr(self._llm, 'chat'):
                resp = self._llm.chat(
                    [{"role": "user", "content": prompt}],
                    system="You are an expert programmer. Output only code.",
                    max_tokens=4096,
                )
                if resp.success:
                    # Extract code from markdown code blocks
                    code = resp.text
                    code_match = re.search(r'```(?:\w+)?\n(.*?)```', code, re.DOTALL)
                    if code_match:
                        code = code_match.group(1)
                    return code.strip()
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
        return None

    def _detect_test_command(self, path: str) -> str:
        """Auto-detect the test command for a project."""
        root = self.project_root
        if (root / "pytest.ini").exists() or (root / "setup.cfg").exists():
            return f"python -m pytest {path} -v --tb=short"
        if (root / "pyproject.toml").exists():
            return f"python -m pytest {path} -v --tb=short"
        if (root / "package.json").exists():
            return "npm test"
        if (root / "Makefile").exists():
            return "make test"
        return f"python -m pytest {path} -v --tb=short"

    def _parse_test_output(self, output: str) -> Tuple[int, int]:
        """Parse test output to extract pass/fail counts."""
        # pytest format: "5 passed in 0.23s"
        m = re.search(r'(\d+) passed', output)
        passed = int(m.group(1)) if m else 0
        m = re.search(r'(\d+) failed', output)
        failed = int(m.group(1)) if m else 0
        return passed, passed + failed

    def _check_git(self) -> bool:
        """Check if git is available and project is a git repo."""
        try:
            result = subprocess.run(
                ["git", "status"],
                cwd=str(self.project_root),
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
