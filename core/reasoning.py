#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — Raciocínio Avançado (Chain of Thought)
=======================================================
Multi-camada: Análise → Contra-argumento → Verificação → Síntese
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("greatsage.reasoning")


class Complexity(Enum):
    SIMPLE = 1      # Pergunta direta
    MODERATE = 2    # Raciocínio médio
    COMPLEX = 3     # Análise profunda
    EXPERT = 4      # Problema de nível expert


@dataclass
class ReasoningResult:
    """Resultado do raciocínio."""
    complexity: Complexity
    steps: List[str]
    answer: str
    confidence: float  # 0.0 a 1.0
    alternatives: List[str]
    biases_detected: List[str]


class ChainOfThought:
    """Motor de raciocínio multi-camada."""

    # Padrões que indicam complexidade
    COMPLEX_INDICATORS = [
        r"(?i)(explique|explica|por que|porque|como funciona|qual a razão)",
        r"(?i)(comparar|diferença|vantagem|desvantagem|trade-?off)",
        r"(?i)(projete|desenhe|implemente|crie|desenvolva|architect)",
        r"(?i)(otimize|melhore|refatore|performance|escala)",
        r"(?i)(segurança|vulnerabilidade|ataque|defesa|proteção)",
        r"(?i)(algoritmo|estrutura de dados|design pattern|clean code)",
    ]

    EXPERT_INDICATORS = [
        r"(?i)(complexidade computacional|NP-?hard|o\(n\))",
        r"(?i)(concorrência|deadlock|race condition|thread.?safe)",
        r"(?i)(arquitetura de microserviços|event.?driven|CQRS|DDD)",
        r"(?i)(machine.?learning|neural|transformer|attention mechanism)",
        r"(?i)(criptografia|hash|RSA|AES|blockchain)",
    ]

    def analyze(self, query: str, context: str = "") -> ReasoningResult:
        """Analisa a complexidade e gera raciocínio."""
        complexity = self._assess_complexity(query)
        steps = self._generate_steps(query, complexity)
        biases = self._detect_biases(query)

        # Calculate real confidence based on analysis quality
        confidence = self._calculate_confidence(query, complexity, steps, biases)

        return ReasoningResult(
            complexity=complexity,
            steps=steps,
            answer="",  # Preenchido pelo LLM
            confidence=confidence,
            alternatives=[],
            biases_detected=biases,
        )

    def _assess_complexity(self, query: str) -> Complexity:
        """Avalia a complexidade da pergunta."""
        score = 0

        for pattern in self.EXPERT_INDICATORS:
            if re.search(pattern, query):
                score += 3

        for pattern in self.COMPLEX_INDICATORS:
            if re.search(pattern, query):
                score += 1

        # Perguntas longas tendem a ser mais complexas
        if len(query) > 200:
            score += 1
        if len(query) > 500:
            score += 1

        # Múltiplas perguntas = mais complexo
        question_marks = query.count("?") + query.count("?")
        if question_marks > 1:
            score += 1

        if score >= 5:
            return Complexity.EXPERT
        elif score >= 3:
            return Complexity.COMPLEX
        elif score >= 1:
            return Complexity.MODERATE
        return Complexity.SIMPLE

    def _generate_steps(self, query: str, complexity: Complexity) -> List[str]:
        """Gera passos de raciocínio baseado na complexidade."""
        steps = []

        # Camada 1: Análise
        steps.append("📐 **Análise**: Identificando componentes e relacionamentos")

        if complexity.value >= Complexity.MODERATE.value:
            # Camada 2: Perspectivas
            steps.append("🔍 **Perspectivas**: Analisando de múltiplos ângulos")

        if complexity.value >= Complexity.COMPLEX.value:
            # Camada 3: Contra-argumento
            steps.append("⚔️ **Contra-argumento**: Testando a solução contra objeções")
            # Camada 4: Verificação cruzada
            steps.append("✅ **Verificação**: Validando com analogias de domínios diferentes")
            # Camada 5: Detecção de vieses
            steps.append("🧠 **Viéses**: Verificando se há raciocínio enviesado")

        if complexity.value >= Complexity.EXPERT.value:
            # Camada 6: Análise de trade-offs
            steps.append("📊 **Trade-offs**: Comparando opções com métricas")
            # Camada 7: Recomendação final
            steps.append("🎯 **Síntese**: Consolidando em recomendação acionável")

        return steps

    def _calculate_confidence(self, query: str, complexity: Complexity, steps: List[str], biases: List[str]) -> float:
        """Calcula confiança real do raciocínio (0.0 a 1.0)."""
        base = 0.5  # Base confidence

        # More steps = higher confidence (we analyzed more)
        base += len(steps) * 0.05

        # Complex questions get higher confidence when well-analyzed
        if complexity == Complexity.EXPERT and len(steps) >= 5:
            base += 0.15
        elif complexity == Complexity.COMPLEX and len(steps) >= 3:
            base += 0.10

        # Biases detected = we're being thorough
        if biases:
            base += len(biases) * 0.03

        # Longer queries = more context = higher confidence
        if len(query) > 100:
            base += 0.05
        if len(query) > 300:
            base += 0.05

        # Has question words = clearer intent = higher confidence
        question_words = r"(?i)(como|por que|o que|qual|explique|comparar|diferença)"
        if re.search(question_words, query):
            base += 0.05

        return min(1.0, max(0.1, base))

    def _detect_biases(self, query: str) -> List[str]:
        """Detecta vieses cognitivos na pergunta."""
        biases = []

        # Viés de confirmação
        if re.search(r"(?i)(confirmar|provar que|não é verdade que)", query):
            biases.append("Viés de confirmação detectado: parece estar buscando confirmação em vez de verdade")

        # Viés de autoridade
        if re.search(r"(?i)(todo mundo|sempre foi|todos sabem|é óbvio)", query):
            biases.append("Viés de autoridade/maioria detectado: 'todo mundo' não significa 'correto'")

        # Viés de sobrevivência
        if re.search(r"(?i)(funciona para mim|nunca deu problema)", query):
            biases.append("Viés de sobrevivência detectado: ausência de evidência não é evidência de ausência")

        # Dunning-Kruger
        if re.search(r"(?i)(fácil|simples|qualquer um|básico)", query) and len(query) < 50:
            biases.append("Possível efeito Dunning-Kruger: tarefas 'fácies' frequentemente não são")

        return biases

    def build_reasoning_prompt(self, query: str) -> str:
        """
        Constrói prompt que instrui o LLM a usar raciocínio em cadeia.
        """
        result = self.analyze(query)

        prompt_parts = [
            "ANTES de responder, siga estas etapas de raciocínio:\n"
        ]

        for i, step in enumerate(result.steps, 1):
            prompt_parts.append(f"  {i}. {step}")

        if result.biases_detected:
            prompt_parts.append("\n⚠️ Vieses detectados na pergunta:")
            for bias in result.biases_detected:
                prompt_parts.append(f"  - {bias}")

        if result.complexity == Complexity.EXPERT:
            prompt_parts.append("\n📋 Esta é uma questão de nível EXPERT. Use sua melhor análise.")
        elif result.complexity == Complexity.COMPLEX:
            prompt_parts.append("\n📋 Questão COMPLEXA. Analise profundamente antes de responder.")

        prompt_parts.append("\nFormate sua resposta com raciocínio visível (use ### para cada etapa).")

        return "\n".join(prompt_parts)


class CodeReasoner:
    """Raciocínio específico para código e programação."""

    @staticmethod
    def analyze_code(code: str, language: str = "") -> Dict:
        """Analisa código e retorna insights."""
        issues = []
        suggestions = []

        # Detecta padrões problemáticos
        patterns = {
            r"except\s*:": "Exceção genérica capturada — especifique o tipo",
            r"eval\(": "Uso de eval() é perigoso — risco de injection",
            r"exec\(": "Uso de exec() é perigoso — risco de segurança",
            r"(?i)password\s*=\s*[\"']": "Hardcoded password detectado",
            r"SELECT.*FROM.*WHERE.*\+": "SQL injection possível — use parâmetros",
            r"print\(": "Print em código de produção — use logging",
            r"# ?TODO": "TODO pendente encontrado",
            r"# ?FIXME": "FIXME detectado — requer atenção",
            r"except.*pass": "Exceção silenciada — pode esconder erros",
            r"import \*": "Wildcard import — polui namespace",
        }

        for pattern, msg in patterns.items():
            if re.search(pattern, code):
                issues.append(msg)

        # Sugestões de melhoria
        lines = code.split("\n")
        if len(lines) > 50:
            suggestions.append("Função muito longa — considere dividir em funções menores")

        # Detecta funções sem docstring
        func_pattern = r"def \w+\("
        for i, line in enumerate(lines):
            if re.search(func_pattern, line.strip()):
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith(("\"\"\"", "'''", "#")):
                    suggestions.append(f"Linha {i+1}: Função sem docstring")

        # Detecta complexidade ciclomática alta
        complexity_keywords = ["if ", "elif ", "else:", "for ", "while ", "try:", "except"]
        max_depth = 0
        current_depth = 0
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in complexity_keywords):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif stripped and not stripped.startswith((" ", "\t", "#")):
                current_depth = 0

        if max_depth > 4:
            suggestions.append(f"Profundidade de aninhamento alta ({max_depth}) — considere refatorar")

        return {
            "language": language,
            "issues": issues,
            "suggestions": suggestions,
            "lines": len(lines),
            "complexity_depth": max_depth,
            "score": max(0, 100 - len(issues) * 10 - len(suggestions) * 5),
        }

    @staticmethod
    def build_code_analysis_prompt(code: str, language: str, task: str) -> str:
        """Constrói prompt para análise de código."""
        return f"""Analise o seguinte código {language} e realize tarefa: {task}

```{language}
{code}
```

Forneça:
1. **Análise**: O que o código faz e como funciona
2. **Problemas**: Bugs, vulnerabilidades, más práticas
3. **Sugestões**: Melhorias específicas com código
4. **Refatoração**: Versão melhorada do código (se aplicável)
5. **Complexidade**: Análise de performance e escalabilidade

Seja específico, dê exemplos de código, e justifique cada sugestão."""
