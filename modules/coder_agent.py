"""
Elivea - Coder Agent Engine
Provides live code execution, static analysis, refactoring, and code generation.
"""

import sys
import io
import ast
import traceback
import subprocess
from pathlib import Path


class CoderAgentModule:
    @staticmethod
    def run_python_code(code_str: str) -> str:
        """Executes a Python code snippet and captures stdout / stderr / return values."""
        buffer_out = io.StringIO()
        buffer_err = io.StringIO()
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        try:
            sys.stdout = buffer_out
            sys.stderr = buffer_err
            
            # Execute in an isolated scope
            exec_globals = {}
            exec(code_str, exec_globals)
            
            output = buffer_out.getvalue().strip()
            errors = buffer_err.getvalue().strip()
            
            result_lines = ["[Execution Result]"]
            if output:
                result_lines.append(f"Output:\n{output}")
            if errors:
                result_lines.append(f"Errors:\n{errors}")
            if not output and not errors:
                result_lines.append("Code executed successfully with no print output.")
                
            return "\n".join(result_lines)
            
        except Exception as e:
            err_msg = traceback.format_exc()
            return f"[Execution Error] Exception raised:\n{err_msg}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    @staticmethod
    def analyze_python_syntax(code_str: str) -> str:
        """Parses Python AST to check for syntax errors and structural metrics."""
        try:
            tree = ast.parse(code_str)
            funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            
            return (
                f"[Analysis] Python Syntax Valid.\n"
                f"  - Functions defined ({len(funcs)}): {', '.join(funcs) if funcs else 'None'}\n"
                f"  - Classes defined ({len(classes)}): {', '.join(classes) if classes else 'None'}"
            )
        except SyntaxError as e:
            return f"[Syntax Error] Line {e.lineno}, Col {e.offset}: {e.msg}\n  -> {e.text}"
        except Exception as e:
            return f"[Analysis Error] {e}"

    @staticmethod
    def generate_file(file_path: str, content: str) -> str:
        """Creates or updates a source code file on disk."""
        try:
            p = Path(file_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"[Action] Source file successfully written to: '{p}' ({len(content)} chars)"
        except Exception as e:
            return f"[Error] Failed to write file: {e}"
