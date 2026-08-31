#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Assistente de Programação
==========================================
Geração, análise, refatoração e debug de código.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger("elvea.programmer")


@dataclass
class CodeTask:
    """Tarefa de programação."""
    language: str
    task_type: str  # generate, analyze, refactor, debug, explain
    description: str
    code: str = ""
    context: str = ""


class Programmer:
    """Assistente de programação avançado."""

    SUPPORTED_LANGS = [
        "python", "javascript", "typescript", "java", "c", "cpp", "csharp",
        "go", "rust", "php", "ruby", "swift", "kotlin", "sql", "html",
        "css", "bash", "powershell", "r", "dart", "lua", "perl",
        "scala", "haskell", "elixir", "assembly",
    ]

    def __init__(self):
        self.project_path = Path(".")

    def detect_language(self, code: str) -> str:
        """Detecta a linguagem de programação do código."""
        indicators = {
            "python": [r"def \w+\(", r"import \w+", r"from \w+ import", r"print\(", r"class \w+:"],
            "javascript": [r"function \w+\(", r"const \w+ =", r"let \w+ =", r"console\.log", r"=>"],
            "typescript": [r": (string|number|boolean|any)", r"interface \w+", r"<[A-Z]\w+>"],
            "java": [r"public class", r"public static void main", r"System\.out\.print"],
            "cpp": [r"#include", r"std::", r"cout", r"cin", r"int main\("],
            "csharp": [r"using System", r"namespace \w+", r"public class", r"Console\."],
            "go": [r"func \w+\(", r"package \w+", r"fmt\.", r":="],
            "rust": [r"fn \w+\(", r"let mut", r"impl \w+", r"pub fn", r"macro_rules!"],
            "php": [r"<\?php", r"\$\w+ =", r"echo ", r"function \w+\("],
            "ruby": [r"def \w+", r"end$", r"puts ", r"require ", r"class \w+"],
            "sql": [r"SELECT", r"FROM", r"WHERE", r"INSERT", r"CREATE TABLE"],
            "html": [r"<html", r"<div", r"<script", r"<!DOCTYPE"],
            "css": [r"\{.*:\s*\w+;", r"@media", r"\.\w+\s*\{", r"#\w+\s*\{"],
            "bash": [r"#!/bin/bash", r"echo ", r"\$\{", r"if \[", r"fi$"],
            "powershell": [r"Get-\w+", r"Set-\w+", r"Write-Host", r"\$\w+\s*="],
        }

        scores = {}
        for lang, patterns in indicators.items():
            score = sum(1 for p in patterns if re.search(p, code, re.MULTILINE))
            if score > 0:
                scores[lang] = score

        if scores:
            return max(scores, key=scores.get)
        return "unknown"

    def build_generation_prompt(self, task: CodeTask) -> str:
        """Constrói prompt para geração de código."""
        lines = []
        lines.append(f"Gere código {task.language} para a seguinte tarefa:")
        lines.append("")
        lines.append(task.description)
        lines.append("")
        if task.code:
            nl = chr(10)
            lines.append(f"Código existente (para referência):```{task.language}{nl}{task.code}{nl}```")
            lines.append("")
        lines.append("Requisitos:")
        lines.append("1. Código completo e funcional")
        lines.append("2. Comentários explicativos")
        lines.append("3. Tratamento de erros")
        lines.append("4. Seguindo boas práticas da linguagem")
        lines.append("5. Use nomes descritivos e significativos")
        lines.append("")
        lines.append("Forneça:")
        lines.append(f"- Código completo em bloco {task.language}")
        lines.append("- Breve explicação de como funciona")
        lines.append("- Possíveis melhorias")
        return chr(10).join(lines)

    def build_analysis_prompt(self, task: CodeTask) -> str:
        """Constrói prompt para análise de código."""
        return f"""Analise o seguinte código {task.language}:

```{task.language}
{task.code}
```

Forneça uma análise completa:
1. **Resumo**: O que o código faz
2. **Problemas**: Bugs, vulnerabilidades, más práticas (liste todos)
3. **Complexidade**: Análise de performance e complexidade
4. **Sugestões**: Melhorias específicas com código
5. **Segurança**: Possíveis falhas de segurança
6. **Testes**: Sugira testes unitários"""

    def build_refactor_prompt(self, task: CodeTask) -> str:
        """Constrói prompt para refatoração."""
        return f"""Refatore o seguinte código {task.language}:

```{task.language}
{task.code}
```

Objetivo: {task.description or 'Melhorar qualidade, legibilidade e performance'}

Forneça:
1. Código refatorado completo
2. Explicação de cada mudança
3. Antes/Depois comparativo
4. Principais melhorias aplicadas"""

    def build_debug_prompt(self, task: CodeTask) -> str:
        """Constrói prompt para debug."""
        return f"""Encontre e corrija o(s) bug(s) no seguinte código {task.language}:

```{task.language}
{task.code}
```

{f'Erro reportado: {task.description}' if task.description else ''}

Forneça:
1. **Análise do bug**: O que está errado e por quê
2. **Código corrigido**: Versão funcional
3. **Explicação**: Por que o bug existia e como foi corrigido
4. **Prevenção**: Como evitar bugs similares no futuro"""

    def analyze_project_structure(self, path: str = ".") -> Dict:
        """Analisa a estrutura de um projeto."""
        root = Path(path)
        structure = {
            "name": root.name,
            "files": 0,
            "dirs": 0,
            "languages": {},
            "total_size": 0,
            "key_files": [],
        }

        for item in root.rglob("*"):
            if item.is_file() and not any(p in str(item) for p in ["node_modules", "__pycache__", ".git", "venv"]):
                structure["files"] += 1
                structure["total_size"] += item.stat().st_size

                ext = item.suffix.lower()
                structure["languages"][ext] = structure["languages"].get(ext, 0) + 1

                # Arquivos importantes
                if item.name in ["package.json", "pyproject.toml", "Cargo.toml", "go.mod",
                                 "requirements.txt", "Makefile", "Dockerfile", "README.md"]:
                    structure["key_files"].append(str(item.relative_to(root)))

            elif item.is_dir() and not item.name.startswith("."):
                structure["dirs"] += 1

        return structure

    def get_quick_commands(self) -> List[Dict[str, str]]:
        """Retorna comandos rápidos de programação."""
        return [
            {"name": "🐍 Rodar Python", "cmd": "python {file}"},
            {"name": "📦 Instalar pacote", "cmd": "pip install {package}"},
            {"name": "🧪 Rodar testes", "cmd": "python -m pytest -v"},
            {"name": "🔍 Lint código", "cmd": "python -m pylint {file}"},
            {"name": "📐 Type check", "cmd": "python -m mypy {file}"},
            {"name": "📊 Analisar projeto", "cmd": "analyze_project"},
            {"name": "🔧 Git status", "cmd": "git status"},
            {"name": "📝 Git diff", "cmd": "git diff"},
            {"name": "🚀 Git commit", "cmd": "git add . && git commit -m '{msg}'"},
            {"name": "🔄 Git pull", "cmd": "git pull"},
        ]
