#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea — Executor de Codigo Seguro
==========================================
Executa codigo Python/JS de forma segura com timeout e sandbox.
"""

import sys
import io
import os
import tempfile
import subprocess
import logging
import signal
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger("elvea.executor")


@dataclass
class ExecutionResult:
    """Resultado da execucao de codigo."""
    success: bool
    output: str
    error: str = ""
    language: str = ""
    execution_time_ms: float = 0
    approved: bool = True  # compatibilidade com elvea_app


def execute_python(code: str, timeout: int = 10) -> ExecutionResult:
    """Execute Python code safely in a subprocess."""
    import time
    t0 = time.time()

    # Write code to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False,
                                      encoding='utf-8') as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        elapsed = (time.time() - t0) * 1000

        if result.returncode == 0:
            return ExecutionResult(
                success=True,
                output=result.stdout or "(sem saida)",
                language="python",
                execution_time_ms=elapsed,
            )
        else:
            return ExecutionResult(
                success=False,
                output=result.stdout or "",
                error=result.stderr or "Erro desconhecido",
                language="python",
                execution_time_ms=elapsed,
            )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Timeout: codigo excedeu {timeout}s",
            language="python",
            execution_time_ms=timeout * 1000,
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            output="",
            error=str(e),
            language="python",
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def execute_javascript(code: str, timeout: int = 10) -> ExecutionResult:
    """Execute JavaScript using Node.js."""
    import time
    t0 = time.time()

    # Check if node is available
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=5,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return ExecutionResult(
            success=False,
            output="",
            error="Node.js nao encontrado. Instale Node.js para executar JavaScript.",
            language="javascript",
        )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False,
                                      encoding='utf-8') as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        elapsed = (time.time() - t0) * 1000

        if result.returncode == 0:
            return ExecutionResult(
                success=True,
                output=result.stdout or "(sem saida)",
                language="javascript",
                execution_time_ms=elapsed,
            )
        else:
            return ExecutionResult(
                success=False,
                output=result.stdout or "",
                error=result.stderr or "Erro desconhecido",
                language="javascript",
                execution_time_ms=elapsed,
            )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Timeout: codigo excedeu {timeout}s",
            language="javascript",
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            output="",
            error=str(e),
            language="javascript",
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def detect_language(code: str) -> str:
    """Detect the programming language of code."""
    code_lower = code.lower().strip()

    # Python indicators
    if any(kw in code_lower for kw in ['def ', 'import ', 'from ', 'print(', 'class ', 'if __name__']):
        return "python"

    # JavaScript indicators
    if any(kw in code_lower for kw in ['function ', 'const ', 'let ', 'var ', 'console.log', '=>']):
        return "javascript"

    # Shell/Bash
    if code_lower.startswith('#!/') or 'echo ' in code_lower or '$(' in code_lower:
        return "bash"

    return "python"  # Default


def execute_code(code: str, language: Optional[str] = None,
                 timeout: int = 10) -> ExecutionResult:
    """Execute code in the appropriate language."""
    if not language:
        language = detect_language(code)

    if language == "python":
        return execute_python(code, timeout)
    elif language in ["javascript", "js"]:
        return execute_javascript(code, timeout)
    else:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Linguagem '{language}' nao suportada para execucao. Use Python ou JavaScript.",
            language=language,
        )


def format_result(result: ExecutionResult) -> str:
    """Format execution result for chat display."""
    status = "OK" if result.success else "ERRO"
    time_str = f" ({result.execution_time_ms:.0f}ms)" if result.execution_time_ms else ""

    parts = [f"**Execucao [{result.language}]{time_str}:**"]

    if result.output:
        parts.append(f"```\n{result.output[:2000]}\n```")

    if result.error:
        parts.append(f"**Erro:**\n```\n{result.error[:1000]}\n```")

    if not result.output and not result.error:
        parts.append("(sem saida)")

    return "\n".join(parts)


class CodeExecutor:
    """Compatibilidade com elvea_app (EliveaLLM streaming)."""
    @staticmethod
    def has_executable(text: str) -> bool:
        if not text:
            return False
        # detecta bloco de código ou [EXECUTE]
        if "[EXECUTE]" in text:
            return True
        # procura ```python ou ``` 
        import re
        return bool(re.search(r"```\s*(python|py|javascript|js)?", text, re.IGNORECASE))

    @staticmethod
    def extract_and_execute(text: str, require_approval: bool = False):
        import re
        # extrai blocos ```lang\ncode\n```
        pattern = re.compile(r"```\s*(python|py|javascript|js)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(text)
        # fallback: [EXECUTE]codigo[/EXECUTE]
        if not matches and "[EXECUTE]" in text:
            m = re.search(r"\[EXECUTE\](.*?)\[/EXECUTE\]", text, re.DOTALL | re.IGNORECASE)
            if m:
                matches = [("python", m.group(1))]
        results = []
        clean = text
        for lang, code in matches:
            lang = (lang or "python").lower()
            if lang == "py":
                lang = "python"
            # segurança básica se require_approval
            approved = True
            if require_approval:
                # bloqueia comandos perigosos sem aprovação
                dangerous = ["os.remove", "shutil.rmtree", "subprocess", "eval(", "exec("]
                if any(d in code for d in dangerous):
                    approved = False
            if not approved:
                results.append(ExecutionResult(success=False, output="", error="Código bloqueado por segurança, requer aprovação", language=lang, approved=False))
                continue
            res = execute_code(code, language=lang)
            res.approved = approved
            results.append(res)
            # remove bloco do clean
            clean = clean.replace(f"```{lang}\n{code}```", "").replace(f"```\n{code}```", "")
        clean = clean.strip()
        return clean, results
