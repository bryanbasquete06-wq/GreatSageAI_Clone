"""
Great Sage AI — Deep Code Analyzer (AST-based)
===============================================
Análise profunda de código-fonte usando AST do Python:
  • Extração de funções, classes, métodos com métricas
  • Complexidade ciclomática e cognitiva
  • Detecção de code smells
  • Análise de dependências
  • Sugestões de melhoria priorizadas
  • Suporte a análise de múltiplos arquivos
"""

from __future__ import annotations

import ast
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FunctionInfo:
    name: str
    file: str
    line: int
    end_line: int
    args: list[str]
    decorators: list[str]
    docstring: str | None
    complexity: int = 1
    cognitive: int = 0
    lines: int = 0
    nesting_depth: int = 0
    has_return: bool = False
    has_type_hints: bool = False
    calls: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    file: str
    line: int
    end_line: int
    bases: list[str]
    decorators: list[str]
    docstring: str | None
    methods: list[FunctionInfo] = field(default_factory=list)
    class_vars: list[str] = field(default_factory=list)
    lines: int = 0


@dataclass
class ImportInfo:
    module: str
    names: list[str]
    file: str
    line: int
    is_from: bool = False


@dataclass
class CodeSmell:
    severity: str  # critical, warning, info
    category: str
    message: str
    file: str
    line: int
    suggestion: str


@dataclass
class FileAnalysis:
    path: str
    lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    smells: list[CodeSmell] = field(default_factory=list)
    global_vars: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ProjectAnalysis:
    root: str
    files: list[FileAnalysis] = field(default_factory=list)
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_smells: int = 0
    dependency_graph: dict[str, set[str]] = field(default_factory=dict)
    top_issues: list[CodeSmell] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# AST Visitors
# ---------------------------------------------------------------------------

class _CodeVisitor(ast.NodeVisitor):
    """Extracts structured information from a Python AST."""

    def __init__(self, source: str, filepath: str):
        self.source = source
        self.filepath = filepath
        self.source_lines = source.splitlines()
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[ImportInfo] = []
        self.global_vars: list[str] = []
        self._nesting = 0

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        info = FunctionInfo(
            name=node.name,
            file=self.filepath,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            args=[a.arg for a in node.args.args],
            decorators=[_unparse(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            lines=(getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1,
            has_type_hints=any(
                a.annotation is not None for a in node.args.args
            ) or node.returns is not None,
        )
        # Complexity
        info.complexity = self._cyclomatic(node)
        info.cognitive = self._cognitive(node)
        info.nesting_depth = self._max_nesting(node)
        info.has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))

        # Calls / reads / writes
        tracker = _NameTracker()
        tracker.visit(node)
        info.calls = list(tracker.calls)
        info.reads = list(tracker.reads)
        info.writes = list(tracker.writes)

        self.functions.append(info)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        info = ClassInfo(
            name=node.name,
            file=self.filepath,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            bases=[_unparse(b) for b in node.bases],
            decorators=[_unparse(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            lines=(getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1,
        )
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)
                info.methods.append(self.functions[-1])
            elif isinstance(child, ast.Assign):
                for t in child.targets:
                    if isinstance(t, ast.Name):
                        info.class_vars.append(t.id)
        self.classes.append(info)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name, names=[alias.asname or alias.name],
                file=self.filepath, line=node.lineno,
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = [alias.name for alias in node.names]
        self.imports.append(ImportInfo(
            module=node.module or "", names=names,
            file=self.filepath, line=node.lineno, is_from=True,
        ))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and self._is_global_scope(node):
                self.global_vars.append(target.id)
        self.generic_visit(node)

    def _is_global_scope(self, node: ast.AST) -> bool:
        return not any(
            isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for p in ast.walk(self._tree) if any(
                c is node or any(c2 is node for c2 in ast.walk(c))
                for c in ast.iter_child_nodes(p)
            )
        ) if hasattr(self, "_tree") else True

    def set_tree(self, tree: ast.Module):
        self._tree = tree

    # -- Complexity metrics --

    @staticmethod
    def _cyclomatic(node: ast.AST) -> int:
        """McCabe cyclomatic complexity."""
        base = 1
        for n in ast.walk(node):
            if isinstance(n, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                base += 1
            elif isinstance(n, ast.BoolOp):
                base += len(n.values) - 1
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                base += 1
            elif isinstance(n, ast.ExceptHandler):
                base += 1
            elif isinstance(n, ast.Assert):
                base += 1
            elif isinstance(n, ast.comprehension):
                base += 1 + len(n.ifs)
        return base

    @staticmethod
    def _cognitive(node: ast.AST) -> int:
        """Cognitive complexity (simplified)."""
        score = 0
        nesting = [0]

        def _walk(n, depth):
            score = 0
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                    nesting[0] += 1
                    score += 1 + nesting[0]
                    _walk(child, depth + 1)
                    nesting[0] -= 1
                elif isinstance(child, ast.BoolOp):
                    score += len(child.values) - 1
                elif isinstance(child, (ast.Try,)):
                    score += 1
                    nesting[0] += 1
                    _walk(child, depth + 1)
                    nesting[0] -= 1
                elif isinstance(child, ast.ExceptHandler):
                    score += 1
                else:
                    _walk(child, depth)

        _walk(node, 0)
        return score

    @staticmethod
    def _max_nesting(node: ast.AST) -> int:
        depth = 0
        max_d = 0

        def _walk(n):
            nonlocal depth, max_d
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.Try)):
                    depth += 1
                    max_d = max(max_d, depth)
                    _walk(child)
                    depth -= 1
                else:
                    _walk(child)

        _walk(node)
        return max_d


class _NameTracker(ast.NodeVisitor):
    """Tracks function calls, variable reads, and writes."""
    def __init__(self):
        self.calls: set[str] = set()
        self.reads: set[str] = set()
        self.writes: set[str] = set()
        self._assign_targets: set[str] = set()

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            parts = []
            n = node.func
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if isinstance(n, ast.Name):
                parts.append(n.id)
            self.calls.add(".".join(reversed(parts)))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.reads.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            self.writes.add(node.id)
        self.generic_visit(node)


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Code Smell Detection
# ---------------------------------------------------------------------------

_SMELL_CONFIGS = {
    "long_function": {"threshold": 60, "severity": "warning"},
    "deep_nesting": {"threshold": 4, "severity": "warning"},
    "high_complexity": {"threshold": 10, "severity": "warning"},
    "high_cognitive": {"threshold": 15, "severity": "warning"},
    "too_many_args": {"threshold": 6, "severity": "info"},
    "missing_docstring": {"severity": "info"},
    "missing_type_hints": {"severity": "info"},
    "bare_except": {"severity": "critical"},
    "star_import": {"severity": "warning"},
    "long_file": {"threshold": 500, "severity": "info"},
    "too_many_methods": {"threshold": 20, "severity": "warning"},
    "no_return": {"severity": "info"},
    "god_class": {"threshold": 300, "severity": "warning"},
}


def _detect_smells(analysis: FileAnalysis) -> list[CodeSmell]:
    smells = []
    cfg = _SMELL_CONFIGS

    for fn in analysis.functions:
        if fn.lines > cfg["long_function"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="long_function",
                message=f"Funcao '{fn.name}' tem {fn.lines} linhas (limite: {cfg['long_function']['threshold']})",
                file=analysis.path, line=fn.line,
                suggestion=f"Refatore '{fn.name}' em funcoes menores responsaveis.",
            ))
        if fn.nesting_depth > cfg["deep_nesting"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="deep_nesting",
                message=f"Funcao '{fn.name}' tem aninhamento de nivel {fn.nesting_depth}",
                file=analysis.path, line=fn.line,
                suggestion=f"Extraia blocos internos de '{fn.name}' em funcoes auxiliares.",
            ))
        if fn.complexity > cfg["high_complexity"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="high_complexity",
                message=f"Funcao '{fn.name}' tem complexidade ciclomatica {fn.complexity}",
                file=analysis.path, line=fn.line,
                suggestion=f"Simplifique a logica condicional de '{fn.name}' com early returns ou tabela de dispatch.",
            ))
        if fn.cognitive > cfg["high_cognitive"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="high_cognitive",
                message=f"Funcao '{fn.name}' tem complexidade cognitiva {fn.cognitive}",
                file=analysis.path, line=fn.line,
                suggestion=f"Reduza o aninhamento e simplifique condicoes em '{fn.name}'.",
            ))
        if len(fn.args) > cfg["too_many_args"]["threshold"]:
            smells.append(CodeSmell(
                severity="info", category="too_many_args",
                message=f"Funcao '{fn.name}' tem {len(fn.args)} argumentos",
                file=analysis.path, line=fn.line,
                suggestion=f"Considere agrupar argumentos relacionados em um dataclass ou dicionario.",
            ))
        if not fn.docstring and cfg["missing_docstring"]["severity"]:
            smells.append(CodeSmell(
                severity="info", category="missing_docstring",
                message=f"Funcao '{fn.name}' nao tem docstring",
                file=analysis.path, line=fn.line,
                suggestion=f"Adicione docstring descritiva a '{fn.name}'.",
            ))

    for cls in analysis.classes:
        if len(cls.methods) > cfg["too_many_methods"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="too_many_methods",
                message=f"Classe '{cls.name}' tem {len(cls.methods)} metodos",
                file=analysis.path, line=cls.line,
                suggestion=f"Considere dividir '{cls.name}' em classes menores (SRP).",
            ))
        cls_lines = cls.end_line - cls.line + 1
        if cls_lines > cfg["god_class"]["threshold"]:
            smells.append(CodeSmell(
                severity="warning", category="god_class",
                message=f"Classe '{cls.name}' tem {cls_lines} linhas (possivel God Class)",
                file=analysis.path, line=cls.line,
                suggestion=f"Extraia responsabilidades de '{cls.name}' em classes auxiliares.",
            ))

    if analysis.lines > cfg["long_file"]["threshold"]:
        smells.append(CodeSmell(
            severity="info", category="long_file",
            message=f"Arquivo tem {analysis.lines} linhas",
            file=analysis.path, line=1,
            suggestion="Considere dividir em modulos menores.",
        ))

    return smells


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_file(filepath: str) -> FileAnalysis:
    """Analisa um unico arquivo Python via AST."""
    analysis = FileAnalysis(path=filepath)
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        analysis.error = str(e)
        return analysis

    lines = source.splitlines()
    analysis.lines = len(lines)
    analysis.blank_lines = sum(1 for l in lines if not l.strip())
    analysis.comment_lines = sum(1 for l in lines if l.strip().startswith("#"))
    analysis.code_lines = analysis.lines - analysis.blank_lines - analysis.comment_lines

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        analysis.error = f"SyntaxError: {e}"
        return analysis

    visitor = _CodeVisitor(source, filepath)
    visitor.set_tree(tree)
    visitor.visit(tree)
    analysis.functions = visitor.functions
    analysis.classes = visitor.classes
    analysis.imports = visitor.imports
    analysis.global_vars = visitor.global_vars
    analysis.smells = _detect_smells(analysis)
    return analysis


def analyze_project(root: str, max_files: int = 200) -> ProjectAnalysis:
    """Analisa recursivamente um projeto Python."""
    result = ProjectAnalysis(root=root)
    root_path = Path(root)
    skip = {".git", "__pycache__", "venv", ".venv", "node_modules", "dist", "build", ".mypy_cache"}

    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            fa = analyze_file(fp)
            result.files.append(fa)
            result.total_lines += fa.lines
            result.total_functions += len(fa.functions)
            result.total_classes += len(fa.classes)
            result.total_smells += len(fa.smells)
            count += 1
            if count >= max_files:
                break
        if count >= max_files:
            break

    # Dependency graph (module imports)
    all_modules = set()
    for fa in result.files:
        mod = os.path.relpath(fa.path, root).replace(os.sep, ".").replace(".py", "")
        all_modules.add(mod)

    for fa in result.files:
        src_mod = os.path.relpath(fa.path, root).replace(os.sep, ".").replace(".py", "")
        deps = set()
        for imp in fa.imports:
            if imp.is_from and imp.module:
                for am in all_modules:
                    if am == imp.module or am.endswith("." + imp.module):
                        deps.add(am)
        result.dependency_graph[src_mod] = deps

    # Sort smells by severity
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    all_smells = []
    for fa in result.files:
        all_smells.extend(fa.smells)
    all_smells.sort(key=lambda s: sev_order.get(s.severity, 3))
    result.top_issues = all_smells[:30]

    # Summary
    result.summary = (
        f"Analise de {len(result.files)} arquivos: "
        f"{result.total_lines} linhas, "
        f"{result.total_functions} funcoes, "
        f"{result.total_classes} classes, "
        f"{result.total_smells} problemas detectados."
    )
    return result


def quick_analyze(filepath: str) -> str:
    """Analise rapida de um arquivo — retorna texto formatado."""
    a = analyze_file(filepath)
    if a.error:
        return f"Erro ao analisar {filepath}: {a.error}"

    parts = [
        f"Arquivo: {a.path}",
        f"Linhas: {a.code_lines} codigo / {a.lines} total",
        f"Funcoes: {len(a.functions)} | Classes: {len(a.classes)} | Imports: {len(a.imports)}",
    ]

    if a.functions:
        top = sorted(a.functions, key=lambda f: f.complexity, reverse=True)[:5]
        parts.append("Top funcoes por complexidade:")
        for fn in top:
            parts.append(f"  - {fn.name} (L{fn.line}): complexidade={fn.complexity}, "
                         f"cognitiva={fn.cognitive}, linhas={fn.lines}")

    if a.smells:
        parts.append(f"Problemas: {len(a.smells)}")
        for s in a.smells[:5]:
            parts.append(f"  [{s.severity}] {s.message}")
            parts.append(f"    Suggestion: {s.suggestion}")

    return "\n".join(parts)


def generate_improvement_plan(analysis: ProjectAnalysis) -> list[dict]:
    """Gera plano priorizado de melhorias para o projeto — com scoring e estimativa."""
    plan = []
    sev_weight = {"critical": 3, "warning": 2, "info": 1}

    # Group smells by category
    by_cat: dict[str, list[CodeSmell]] = defaultdict(list)
    for smell in analysis.top_issues:
        by_cat[smell.category].append(smell)

    for category, smells in sorted(by_cat.items(), key=lambda x: -sum(sev_weight.get(s.severity, 0) for s in x[1])):
        priority = max(sev_weight.get(s.severity, 0) for s in smells)
        affected = list(set(s.file for s in smells))
        plan.append({
            "category": category,
            "count": len(smells),
            "priority": priority,
            "score": len(smells) * priority,  # impact score
            "affected_files": affected,
            "affected_count": len(affected),
            "worst_example": smells[0].message if smells else "",
            "suggestion": smells[0].suggestion if smells else "",
            "estimated_effort": _estimate_effort(category, len(smells)),
        })

    # Add structural improvements
    if analysis.total_functions > 50:
        plan.append({
            "category": "modularization",
            "count": analysis.total_functions,
            "priority": 1,
            "score": 10,
            "affected_files": [],
            "affected_count": 0,
            "worst_example": f"{analysis.total_functions} funcoes no projeto",
            "suggestion": "Considere agrupar funcoes relacionadas em classes ou modulos.",
            "estimated_effort": "alto",
        })

    # Dependency cycle detection
    graph = analysis.dependency_graph
    for mod, deps in graph.items():
        for dep in deps:
            if dep in graph and mod in graph.get(dep, set()):
                plan.append({
                    "category": "circular_dependency",
                    "count": 2,
                    "priority": 3,
                    "score": 6,
                    "affected_files": [mod, dep],
                    "affected_count": 2,
                    "worst_example": f"Ciclo: {mod} <-> {dep}",
                    "suggestion": "Quebre a dependencia circular com injecao de dependencia ou interface.",
                    "estimated_effort": "medio",
                })
                break

    # Sort by total impact score descending
    plan.sort(key=lambda p: p.get("score", 0), reverse=True)
    return plan


def _estimate_effort(category: str, count: int) -> str:
    """Estima esforço de correção baseado na categoria."""
    effort_map = {
        "bare_except": "baixo",
        "missing_docstring": "baixo",
        "missing_type_hints": "baixo",
        "too_many_args": "medio",
        "long_function": "alto",
        "deep_nesting": "alto",
        "high_complexity": "alto",
        "high_cognitive": "alto",
        "god_class": "muito alto",
        "long_file": "medio",
        "too_many_methods": "medio",
        "star_import": "baixo",
        "circular_dependency": "alto",
    }
    base = effort_map.get(category, "medio")
    if count > 10:
        if base == "baixo":
            return "medio"
        if base == "medio":
            return "alto"
    return base


def project_health_score(analysis: ProjectAnalysis) -> dict:
    """Calcula score de saúde do projeto (0-100)."""
    score = 100.0
    # Deduct for smells
    for smell in analysis.top_issues:
        if smell.severity == "critical":
            score -= 5
        elif smell.severity == "warning":
            score -= 1
        else:
            score -= 0.3
    # Deduct for large files
    for fa in analysis.files:
        if fa.lines > 800:
            score -= 3
        elif fa.lines > 500:
            score -= 1
    # Deduct for high complexity functions
    for fa in analysis.files:
        for fn in fa.functions:
            if fn.complexity > 15:
                score -= 2
            elif fn.complexity > 10:
                score -= 1
    score = max(0, min(100, score))
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"
    return {
        "score": round(score, 1),
        "grade": grade,
        "total_smells": analysis.total_smells,
        "critical_count": sum(1 for s in analysis.top_issues if s.severity == "critical"),
        "warning_count": sum(1 for s in analysis.top_issues if s.severity == "warning"),
        "files_count": len(analysis.files),
        "avg_complexity": round(sum(
            fn.complexity for fa in analysis.files for fn in fa.functions
        ) / max(analysis.total_functions, 1), 1),
    }
