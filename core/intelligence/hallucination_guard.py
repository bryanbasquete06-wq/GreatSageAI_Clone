#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anti-Hallucination Guard v2
=============================
Major upgrade: deeper pattern detection, source verification,
contradiction detection, confidence calibration, and self-consistency checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class HallucinationFlag:
    """A single flag for potential hallucination."""
    text: str
    category: str
    severity: str  # "low", "medium", "high"
    suggestion: str
    line: int = 0


@dataclass
class GuardResult:
    """Result of hallucination analysis."""
    flags: List[HallucinationFlag] = field(default_factory=list)
    overall_confidence: float = 1.0
    requires_confirmation: bool = False
    summary: str = ""
    source_coverage: float = 0.0  # % of claims that have sources

    @property
    def flag_count(self) -> int:
        return len(self.flags)

    @property
    def high_severity(self) -> int:
        return sum(1 for f in self.flags if f.severity == "high")

    @property
    def medium_severity(self) -> int:
        return sum(1 for f in self.flags if f.severity == "medium")


class HallucinationGuard:
    """
    Detects potential hallucinations in AI responses.
    v2: Deeper detection, source verification, contradiction detection.
    """

    # ═══ Absolute claims (high confidence of being hallucinated) ═══
    ABSOLUTE_PATTERNS = [
        (r"(?i)(sempre|nunca|jamais|definitivamente|com certeza|100%|absolutamente)", "absolute_claim", "medium"),
        (r"(?i)(e o (unico|melhor|pior) (modo|caminho|jeito|solucao))", "absolute_claim", "medium"),
        (r"(?i)(impossivel|nao existe|nao ha|nunca existiu)", "absolute_claim", "medium"),
        (r"(?i)(todos os (?:desenvolvedores|programadores|engenheiros|usuarios))", "absolute_claim", "low"),
        (r"(?i)(nenhum (?:sistema|framework|linguagem|biblioteca))", "absolute_claim", "low"),
        (r"(?i)(e (?:sempre|obrigatorio|necessario) (?:usar|fazer|aplicar))", "absolute_claim", "medium"),
    ]

    # ═══ Fabricated numbers ═══
    NUMERIC_PATTERNS = [
        (r"\b(?:exatamente|precisamente)\s+\d+", "numeric_specific", "medium"),
        (r"\b\d{1,3}(?:\.\d{1,2})?%\s+(?:dos?|das?)\b", "numeric_specific", "low"),
        (r"(?i)(?:em|latencia de|tempo de)\s+\d+\s*(?:ms|segundos|minutos)", "numeric_specific", "medium"),
        (r"(?i)(?:aumenta|diminui|melhora|piora)\s+\d+\s*%", "numeric_specific", "medium"),
        (r"(?i)(?:custa|custo de|preco de)\s+\$?\d+", "numeric_specific", "high"),
    ]

    # ═══ Unverifiable claims ═══
    UNVERIFIABLE_PATTERNS = [
        (r"(?i)(estudos mostram|pesquisas indicam|segundo (?:um|a) estudo)", "unverifiable", "medium"),
        (r"(?i)(e (?:cientificamente|comprovadamente|estatisticamente) provado)", "unverifiable", "high"),
        (r"(?i)(a (?:maioria|99%|80%) dos?)", "unverifiable", "medium"),
        (r"(?i)(todos os (?:estudos|pesquisas|expertos|especialistas))", "unverifiable", "medium"),
        (r"(?i)(e (?:universalmente|geralmente|amplamente) aceito)", "unverifiable", "low"),
    ]

    # ═══ Source citation patterns (positive signals) ═══
    SOURCE_PATTERNS = [
        r"(?i)(arquivo|file|linha|line|commit|doc|documentacao|docs)",
        r"`[^`]+`",  # Inline code references
        r"(?:https?://\S+)",  # URLs
        r"(?i)(pydoc|mdn|wikipedia|stackoverflow|github\.com)",
    ]

    # ═══ Contradiction detection ═══
    CONTRADICTION_PAIRS = [
        (r"(?i)(e (?:rapido|eficiente|otimo|excelente))", r"(?i)(e (?:lento|ineficiente|ruim|pessimo))"),
        (r"(?i)(funciona (?:bem|perfeitamente|sem problemas))", r"(?i)(nao funciona|quebra|falha)"),
        (r"(?i)(e (?:seguro|protegido|hardened))", r"(?i)(e (?:inseguro|vulneravel|perigoso))"),
        (r"(?i)(deve (?:ser|usar|fazer))", r"(?i)(nao deve (?:ser|usar|fazer))"),
    ]

    def analyze(self, response: str, context: Optional[str] = None,
                previous_responses: Optional[List[str]] = None) -> GuardResult:
        """
        Analyze an AI response for potential hallucinations.
        v2: Adds contradiction detection and source coverage.
        """
        flags = []
        lines = response.split("\n")

        # Track claims for contradiction detection
        claims: List[str] = []

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```") or len(stripped) < 10:
                continue

            # Absolute claims
            for pattern, category, severity in self.ABSOLUTE_PATTERNS:
                if re.search(pattern, line):
                    flags.append(HallucinationFlag(
                        text=stripped[:100], category=category, severity=severity,
                        suggestion="Adicione qualificadores (ex: 'geralmente', 'na minha experiencia')",
                        line=line_num,
                    ))
                    claims.append(stripped)

            # Numeric claims without sources
            for pattern, category, severity in self.NUMERIC_PATTERNS:
                if re.search(pattern, line):
                    has_source = any(re.search(sp, line) for sp in self.SOURCE_PATTERNS)
                    if not has_source:
                        flags.append(HallucinationFlag(
                            text=stripped[:100], category=category, severity=severity,
                            suggestion="Numeros especificos sem fonte podem ser imprecisos",
                            line=line_num,
                        ))

            # Unverifiable claims
            for pattern, category, severity in self.UNVERIFIABLE_PATTERNS:
                if re.search(pattern, line):
                    flags.append(HallucinationFlag(
                        text=stripped[:100], category=category, severity=severity,
                        suggestion="Afirmacoes generalizadas precisam de evidencia",
                        line=line_num,
                    ))

        # Contradiction detection within same response
        contradiction_flags = self._detect_contradictions(response)
        flags.extend(contradiction_flags)

        # Cross-response contradiction detection
        if previous_responses:
            cross_flags = self._detect_cross_contradictions(response, previous_responses)
            flags.extend(cross_flags)

        # Source coverage
        source_coverage = self._calculate_source_coverage(response, flags)

        # Calculate confidence
        high_flags = sum(1 for f in flags if f.severity == "high")
        med_flags = sum(1 for f in flags if f.severity == "medium")
        low_flags = sum(1 for f in flags if f.severity == "low")

        confidence = 1.0
        confidence -= high_flags * 0.15
        confidence -= med_flags * 0.05
        confidence -= low_flags * 0.02
        confidence += source_coverage * 0.1  # Bonus for source citation
        confidence = max(0.1, min(1.0, confidence))

        return GuardResult(
            flags=flags,
            overall_confidence=confidence,
            requires_confirmation=high_flags > 0,
            summary=self._build_summary(flags, confidence, source_coverage),
            source_coverage=source_coverage,
        )

    def _detect_contradictions(self, text: str) -> List[HallucinationFlag]:
        """Detect contradictory statements within the same response."""
        flags = []
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for i, line_a in enumerate(lines):
            for line_b in lines[i+1:]:
                for pos_pat, neg_pat in self.CONTRADICTION_PAIRS:
                    if (re.search(pos_pat, line_a) and re.search(neg_pat, line_b)):
                        flags.append(HallucinationFlag(
                            text=f"{line_a[:50]} vs {line_b[:50]}",
                            category="contradiction",
                            severity="high",
                            suggestion="Contradicao detectada na mesma resposta",
                        ))
                        break

        return flags

    def _detect_cross_contradictions(self, current: str,
                                     previous: List[str]) -> List[HallucinationFlag]:
        """Detect contradictions with previous responses."""
        flags = []
        current_lower = current.lower()

        for prev in previous[-3:]:  # Check last 3 responses
            prev_lower = prev.lower()

            # Check for flip-flops on key statements
            for pos_pat, neg_pat in self.CONTRADICTION_PAIRS:
                if (re.search(pos_pat, current_lower) and re.search(neg_pat, prev_lower)):
                    flags.append(HallucinationFlag(
                        text="Contradicts previous response",
                        category="cross_contradiction",
                        severity="medium",
                        suggestion="Verifique se a informacao mudou ou se ha erro",
                    ))
                    break
                if (re.search(neg_pat, current_lower) and re.search(pos_pat, prev_lower)):
                    flags.append(HallucinationFlag(
                        text="Contradicts previous response",
                        category="cross_contradiction",
                        severity="medium",
                        suggestion="Verifique se a informacao mudou ou se ha erro",
                    ))
                    break

        return flags

    def _calculate_source_coverage(self, response: str, flags: List[HallucinationFlag]) -> float:
        """Calculate what percentage of claims have source citations."""
        # Count total claim lines
        claim_lines = []
        for line in response.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
                # Check if it's a substantive claim (not just a greeting)
                if len(stripped) > 20 and any(c.isalpha() for c in stripped):
                    claim_lines.append(stripped)

        if not claim_lines:
            return 1.0

        # Count lines with sources
        sourced = 0
        for line in claim_lines:
            if any(re.search(sp, line) for sp in self.SOURCE_PATTERNS):
                sourced += 1

        return sourced / len(claim_lines)

    def _build_summary(self, flags: List[HallucinationFlag], confidence: float,
                       source_coverage: float) -> str:
        """Build human-readable summary."""
        if not flags:
            return f"Confianca alta ({confidence:.0%}) — nenhuma marcacao detectada."

        high = sum(1 for f in flags if f.severity == "high")
        med = sum(1 for f in flags if f.severity == "medium")
        low = sum(1 for f in flags if f.severity == "low")

        parts = [f"Confianca: {confidence:.0%}"]
        if high:
            parts.append(f"{high} alegacoes incertas (ALTA)")
        if med:
            parts.append(f"{med} alegacoes incertas (MEDIA)")
        if low:
            parts.append(f"{low} observacoes (baixa)")
        parts.append(f"Cobertura de fontes: {source_coverage:.0%}")

        return " | ".join(parts)
