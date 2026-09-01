#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Weekly Digest System
================================
Collects data from all intelligence subsystems and generates a comprehensive
activity + AI performance report. Runs on-demand or scheduled.

Sections:
  1. Activity Overview — messages, sessions, uptime
  2. AI Performance — quality scores, latency, provider comparison
  3. Knowledge Growth — entities learned, patterns detected, graph health
  4. Intent Analysis — most common commands, usage patterns
  5. Hallucination & Correction — guard stats, auto-fixes applied
  6. Health & Errors — error log summary, anomaly detection
  7. Recommendations — AI-generated suggestions for improvement
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DigestSection:
    """A single section of the weekly digest."""
    title: str
    icon: str
    content: str
    highlights: List[str] = field(default_factory=list)
    score: Optional[float] = None  # 0-1, optional section score


@dataclass
class WeeklyDigest:
    """Complete weekly digest report."""
    generated_at: str
    period_start: str
    period_end: str
    sections: List[DigestSection]
    overall_score: float
    summary: str


class WeeklyDigestEngine:
    """
    Generates weekly digest reports by aggregating data from all subsystems.
    """

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.memory_dir = self.project_dir / "memory"
        self.config_dir = self.project_dir / "config"
        self.smart_data_dir = self.config_dir / "smart_data"

    def generate(self, days: int = 7) -> WeeklyDigest:
        """Generate a weekly digest for the last N days."""
        now = datetime.now()
        period_start = now - timedelta(days=days)
        period_end = now

        sections = []

        # 1. Activity Overview
        sections.append(self._section_activity(period_start, period_end))

        # 2. AI Performance
        sections.append(self._section_performance(period_start, period_end))

        # 3. Knowledge Growth
        sections.append(self._section_knowledge(period_start, period_end))

        # 4. Intent Analysis
        sections.append(self._section_intents(period_start, period_end))

        # 5. Hallucination & Correction
        sections.append(self._section_guard(period_start, period_end))

        # 6. Health & Errors
        sections.append(self._section_health(period_start, period_end))

        # 7. Recommendations
        sections.append(self._section_recommendations(sections))

        # Calculate overall score
        scores = [s.score for s in sections if s.score is not None]
        overall = sum(scores) / len(scores) if scores else 0.5

        # Build summary
        summary = self._build_summary(sections, overall)

        return WeeklyDigest(
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
            sections=sections,
            overall_score=overall,
            summary=summary,
        )

    def format_markdown(self, digest: WeeklyDigest) -> str:
        """Format digest as rich markdown."""
        lines = []
        lines.append(f"# 📊 Elívea — Digest Semanal")
        lines.append(f"**Período:** {digest.period_start} → {digest.period_end}")
        lines.append(f"**Gerado:** {digest.generated_at}")
        lines.append(f"**Score Geral:** {digest.overall_score:.0%}")
        lines.append("")
        lines.append(f"> {digest.summary}")
        lines.append("")
        lines.append("---")

        for section in digest.sections:
            lines.append("")
            lines.append(f"## {section.icon} {section.title}")
            if section.score is not None:
                bar = self._score_bar(section.score)
                lines.append(f"**Score:** {section.score:.0%} {bar}")
            lines.append("")
            lines.append(section.content)
            if section.highlights:
                lines.append("")
                lines.append("**Destaques:**")
                for h in section.highlights:
                    lines.append(f"- {h}")
            lines.append("")
            lines.append("---")

        lines.append("")
        lines.append("*Relatório gerado automaticamente pelo Elívea — Inteligência Autônoma* ⚔️")
        return "\n".join(lines)

    def format_compact(self, digest: WeeklyDigest) -> str:
        """Format as compact text (for chat)."""
        lines = []
        lines.append(f"📊 **Digest Semanal** ({digest.period_start} → {digest.period_end})")
        lines.append(f"Score Geral: {digest.overall_score:.0%}")
        lines.append("")

        for section in digest.sections:
            score_str = f" ({section.score:.0%})" if section.score is not None else ""
            lines.append(f"{section.icon} **{section.title}**{score_str}")
            # First 2-3 lines of content
            content_lines = [l for l in section.content.split("\n") if l.strip()][:3]
            for cl in content_lines:
                lines.append(f"  {cl}")
            if section.highlights:
                for h in section.highlights[:2]:
                    lines.append(f"  💡 {h}")
            lines.append("")

        lines.append(f"💡 {digest.summary}")
        return "\n".join(lines)

    # ═══ Section Builders ═══════════════════════════════════════════════════

    def _section_activity(self, start: datetime, end: datetime) -> DigestSection:
        """Build activity overview section."""
        chat_data = self._load_json("memory/chat_history.json", [])
        messages = [m for m in chat_data if self._in_period(m.get("timestamp", ""), start, end)]

        user_msgs = [m for m in messages if m.get("role") == "user"]
        ai_msgs = [m for m in messages if m.get("role") == "assistant"]

        total_chars_user = sum(len(m.get("content", "")) for m in user_msgs)
        total_chars_ai = sum(len(m.get("content", "")) for m in ai_msgs)

        # Estimate session count (gaps > 30min = new session)
        sessions = 1
        timestamps = sorted([m.get("timestamp", "") for m in messages if m.get("timestamp")])
        for i in range(1, len(timestamps)):
            try:
                t1 = datetime.fromisoformat(timestamps[i - 1])
                t2 = datetime.fromisoformat(timestamps[i])
                if (t2 - t1).total_seconds() > 1800:
                    sessions += 1
            except (ValueError, TypeError):
                pass

        # Most active hours
        hour_counter = Counter()
        for m in user_msgs:
            ts = m.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                hour_counter[dt.hour] += 1
            except (ValueError, TypeError):
                pass
        peak_hour = hour_counter.most_common(1)[0][0] if hour_counter else -1

        avg_msg_len = total_chars_user // max(len(user_msgs), 1)

        content_lines = [
            f"Total de mensagens: **{len(messages)}** ({len(user_msgs)} do usuário, {len(ai_msgs)} da IA)",
            f"Caracteres enviados: **{total_chars_user:,}**",
            f"Caracteres gerados pela IA: **{total_chars_ai:,}**",
            f"Sessões estimadas: **{sessions}**",
            f"Tamanho médio por mensagem: **{avg_msg_len}** caracteres",
        ]
        if peak_hour >= 0:
            content_lines.append(f"Hora mais ativa: **{peak_hour}:00**")

        highlights = []
        if len(user_msgs) > 50:
            highlights.append(f"Usuário muito ativo: {len(user_msgs)} mensagens na semana!")
        if sessions > 5:
            highlights.append(f"{sessions} sessões — uso frequente do sistema")
        if avg_msg_len > 200:
            highlights.append("Mensagens detalhadas — consultas profundas")

        score = min(1.0, len(user_msgs) / 30)  # 30 msgs/week = perfect score
        return DigestSection(
            title="Visão Geral da Atividade",
            icon="📈",
            content="\n".join(content_lines),
            highlights=highlights,
            score=score,
        )

    def _section_performance(self, start: datetime, end: datetime) -> DigestSection:
        """Build AI performance section from quality history."""
        entries = self._load_jsonl("memory/quality_history.jsonl")
        recent = [e for e in entries if self._ts_in_period(e.get("timestamp", 0), start, end)]

        if not recent:
            return DigestSection(
                title="Performance da IA",
                icon="⚡",
                content="Dados insuficientes para esta semana. Continue usando para gerar métricas.",
                highlights=[],
                score=0.5,
            )

        scores = [e.get("auto_score", 0) for e in recent]
        latencies = [e.get("latency_ms", 0) for e in recent]
        halluc_scores = [e.get("hallucination_score", 1.0) for e in recent]
        corrections = [e.get("correction_count", 0) for e in recent]
        providers = Counter(e.get("provider", "unknown") for e in recent)

        avg_score = sum(scores) / len(scores)
        avg_latency = sum(latencies) / len(latencies)
        avg_halluc = sum(halluc_scores) / len(halluc_scores)
        total_corrections = sum(corrections)

        content_lines = [
            f"Respostas avaliadas: **{len(recent)}**",
            f"Score médio de qualidade: **{avg_score:.1%}**",
            f"Latência média: **{avg_latency:.0f}ms**",
            f"Confiança anti-alucinação: **{avg_halluc:.1%}**",
            f"Auto-correções aplicadas: **{total_corrections}**",
        ]

        if providers:
            prov_str = ", ".join(f"{p}: {c}x" for p, c in providers.most_common(5))
            content_lines.append(f"Providers: {prov_str}")

        # Trend
        if len(scores) >= 6:
            first_half = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
            second_half = sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1)
            trend = "📈 melhorando" if second_half > first_half + 0.05 else \
                    "📉 declinando" if second_half < first_half - 0.05 else "➡️ estável"
            content_lines.append(f"Tendência: **{trend}**")

        highlights = []
        if avg_score > 0.8:
            highlights.append(f"Excelente qualidade média: {avg_score:.0%}")
        if avg_latency < 1000:
            highlights.append(f"Respostas rápidas: {avg_latency:.0f}ms médio")
        if avg_halluc > 0.9:
            highlights.append(f"Alta confiança anti-alucinação: {avg_halluc:.0%}")
        if total_corrections > 10:
            highlights.append(f"{total_corrections} auto-correções — sistema ativo")

        return DigestSection(
            title="Performance da IA",
            icon="⚡",
            content="\n".join(content_lines),
            highlights=highlights,
            score=avg_score,
        )

    def _section_knowledge(self, start: datetime, end: datetime) -> DigestSection:
        """Build knowledge graph section."""
        graph_data = self._load_json("memory/knowledge_graph.json", {"entities": [], "edges": [], "patterns": []})

        entities = graph_data.get("entities", [])
        edges = graph_data.get("edges", [])
        patterns = graph_data.get("patterns", [])

        # New entities this week
        new_entities = [e for e in entities if self._ts_in_period(e.get("last_seen", 0), start, end)]
        fresh = [e for e in entities if (time.time() - e.get("last_seen", 0)) < 7 * 86400]
        stale = [e for e in entities if (time.time() - e.get("last_seen", 0)) > 30 * 86400]

        # Type breakdown
        type_counts = Counter(e.get("type", "unknown") for e in entities)
        top_types = type_counts.most_common(5)

        # Top entities
        top_entities = sorted(entities, key=lambda e: e.get("mentions", 0), reverse=True)[:5]

        content_lines = [
            f"Entidades totais: **{len(entities)}**",
            f"Entidades ativas (7d): **{len(fresh)}**",
            f"Entidades obsoletas: **{len(stale)}**",
            f"Relacionamentos: **{len(edges)}**",
            f"Padrões detectados: **{len(patterns)}**",
        ]

        if top_types:
            type_str = ", ".join(f"{t}: {c}" for t, c in top_types)
            content_lines.append(f"Por tipo: {type_str}")

        if top_entities:
            names = ", ".join(e.get("name", "?") for e in top_entities)
            content_lines.append(f"Top entidades: {names}")

        highlights = []
        if len(new_entities) > 5:
            highlights.append(f"{len(new_entities)} novas entidades aprendidas esta semana")
        if len(stale) > len(entities) * 0.3:
            highlights.append(f"{len(stale)} entidades obsoletas — considere limpar o grafo")
        if patterns:
            top_pat = sorted(patterns, key=lambda p: p.get("frequency", 0), reverse=True)[0]
            highlights.append(f"Padrão mais comum: {top_pat.get('name', '?')} ({top_pat.get('frequency', 0)}x)")

        score = min(1.0, len(fresh) / max(len(entities), 1)) if entities else 0.5
        return DigestSection(
            title="Crescimento do Conhecimento",
            icon="🧠",
            content="\n".join(content_lines),
            highlights=highlights,
            score=score,
        )

    def _section_intents(self, start: datetime, end: datetime) -> DigestSection:
        """Build intent analysis section from conversation patterns."""
        chat_data = self._load_json("memory/chat_history.json", [])
        user_msgs = [m for m in chat_data
                     if m.get("role") == "user" and self._in_period(m.get("timestamp", ""), start, end)]

        if not user_msgs:
            return DigestSection(
                title="Análise de Intenções",
                icon="🎯",
                content="Dados insuficientes para esta semana.",
                highlights=[],
                score=0.5,
            )

        # Categorize intents
        intent_categories = Counter()
        word_freq = Counter()
        for m in user_msgs:
            content = m.get("content", "").lower().strip()
            words = content.split()
            if words:
                word_freq[words[0]] += 1

            # Simple intent detection
            if any(w in content for w in ["crie", "gere", "escreva", "implemente", "code"]):
                intent_categories["code_generation"] += 1
            elif any(w in content for w in ["debug", "erro", "bug", "corrija", "fix"]):
                intent_categories["debugging"] += 1
            elif any(w in content for w in ["refatore", "otimize", "melhore", "limpe"]):
                intent_categories["refactoring"] += 1
            elif any(w in content for w in ["o que", "qual", "como", "explique", "por que"]):
                intent_categories["question"] += 1
            elif any(w in content for w in ["status", "hora", "data", "info"]):
                intent_categories["system"] += 1
            elif any(w in content for w in ["pesquise", "search", "noticias"]):
                intent_categories["search"] += 1
            elif any(w in content for w in ["lembre", "memorize", "salve"]):
                intent_categories["memory"] += 1
            else:
                intent_categories["conversation"] += 1

        total = len(user_msgs)
        content_lines = [f"Total de entradas: **{total}**", ""]

        # Intent breakdown
        for intent, count in intent_categories.most_common():
            pct = count / max(total, 1) * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            content_lines.append(f"  **{intent}**: {count} ({pct:.0f}%) {bar}")

        # Top commands
        if word_freq:
            content_lines.append("")
            content_lines.append("Comandos mais usados:")
            for word, count in word_freq.most_common(5):
                content_lines.append(f"  `{word}` — {count}x")

        highlights = []
        top_intent = intent_categories.most_common(1)[0] if intent_categories else None
        if top_intent:
            highlights.append(f"Intenção mais comum: {top_intent[0]} ({top_intent[1]}x)")
        if intent_categories.get("code_generation", 0) > total * 0.3:
            highlights.append("Forte foco em geração de código esta semana")
        if intent_categories.get("debugging", 0) > total * 0.2:
            highlights.append("Muitas sessões de debugging — considere usar /shadow")

        score = min(1.0, total / 20)  # 20 inputs/week = full score
        return DigestSection(
            title="Análise de Intenções",
            icon="🎯",
            content="\n".join(content_lines),
            highlights=highlights,
            score=score,
        )

    def _section_guard(self, start: datetime, end: datetime) -> DigestSection:
        """Build hallucination guard & self-correction section."""
        entries = self._load_jsonl("memory/quality_history.jsonl")
        recent = [e for e in entries if self._ts_in_period(e.get("timestamp", 0), start, end)]

        if not recent:
            return DigestSection(
                title="Anti-Alucinação & Auto-Correção",
                icon="🛡️",
                content="Dados insuficientes.",
                highlights=[],
                score=0.5,
            )

        hall_scores = [e.get("hallucination_score", 1.0) for e in recent]
        corrections = [e.get("correction_count", 0) for e in recent]

        avg_halluc = sum(hall_scores) / len(hall_scores)
        total_corrections = sum(corrections)
        high_risk = sum(1 for s in hall_scores if s < 0.7)
        clean = sum(1 for s in hall_scores if s >= 0.9)

        content_lines = [
            f"Respostas analisadas: **{len(recent)}**",
            f"Confiança média anti-alucinação: **{avg_halluc:.1%}**",
            f"Respostas limpas (≥90%): **{clean}/{len(recent)}** ({clean/max(len(recent),1)*100:.0f}%)",
            f"Respostas de risco (<70%): **{high_risk}/{len(recent)}**",
            f"Auto-correções aplicadas: **{total_corrections}**",
            f"Média de correções por resposta: **{total_corrections/max(len(recent),1):.1f}**",
        ]

        highlights = []
        if avg_halluc > 0.9:
            highlights.append(f"Excelente confiança: {avg_halluc:.0%} média")
        if high_risk > 0:
            highlights.append(f"{high_risk} respostas com risco de alucinação detectadas")
        if total_corrections > 0:
            highlights.append(f"{total_corrections} correções automáticas aplicadas")

        return DigestSection(
            title="Anti-Alucinação & Auto-Correção",
            icon="🛡️",
            content="\n".join(content_lines),
            highlights=highlights,
            score=avg_halluc,
        )

    def _section_health(self, start: datetime, end: datetime) -> DigestSection:
        """Build health & errors section."""
        error_log = self._load_jsonl("config/smart_data/error_log.jsonl")
        recent_errors = [e for e in error_log if self._ts_in_period_str(e.get("ts", ""), start, end)]

        # Mood history
        mood_data = self._load_json("config/smart_data/mood_history.json", [])
        recent_mood = [m for m in mood_data if self._ts_in_period_str(m.get("timestamp", ""), start, end)]

        # Count error types
        error_types = Counter()
        for e in recent_errors:
            error_types[e.get("level", "unknown")] += 1

        content_lines = [
            f"Erros registrados: **{len(recent_errors)}**",
        ]

        if error_types:
            for level, count in error_types.most_common():
                content_lines.append(f"  {level}: {count}")

        if recent_mood:
            moods = [m.get("mood", "neutral") for m in recent_mood]
            mood_counts = Counter(moods)
            content_lines.append(f"Total de interações de humor: **{len(recent_mood)}**")
            for mood, count in mood_counts.most_common(3):
                content_lines.append(f"  {mood}: {count}")

        highlights = []
        if len(recent_errors) == 0:
            highlights.append("✅ Nenhum erro registrado esta semana!")
        elif len(recent_errors) > 10:
            highlights.append(f"⚠️ {len(recent_errors)} erros — revise os logs")
        if error_types.get("error", 0) > 5:
            highlights.append("Muitos erros — considere rodar /shadow")

        score = max(0.0, 1.0 - len(recent_errors) * 0.05)
        return DigestSection(
            title="Saúde & Erros",
            icon="🏥",
            content="\n".join(content_lines),
            highlights=highlights,
            score=min(score, 1.0),
        )

    def _section_recommendations(self, sections: List[DigestSection]) -> DigestSection:
        """Generate AI recommendations based on all sections."""
        recommendations = []

        # Based on activity
        activity = next((s for s in sections if "Atividade" in s.title), None)
        if activity and activity.score is not None and activity.score < 0.3:
            recommendations.append("📈 Use o Elívea mais frequentemente para maximizar o aprendizado")

        # Based on performance
        perf = next((s for s in sections if "Performance" in s.title), None)
        if perf and perf.score is not None and perf.score < 0.6:
            recommendations.append("⚡ Considere trocar o provider LLM para mejorar qualidade")

        # Based on knowledge
        knowledge = next((s for s in sections if "Conhecimento" in s.title), None)
        if knowledge:
            for h in knowledge.highlights:
                if "obsolet" in h.lower():
                    recommendations.append("🧠 Limite o knowledge graph de entidades obsoletas")

        # Based on guard
        guard = next((s for s in sections if "Alucinação" in s.title), None)
        if guard and guard.highlights:
            for h in guard.highlights:
                if "risco" in h.lower():
                    recommendations.append("🛡️ Respostas com risco detectadas — verifique antes de usar em produção")

        # Based on intents
        intents = next((s for s in sections if "Intenções" in s.title), None)
        if intents:
            for h in intents.highlights:
                if "debugging" in h.lower():
                    recommendations.append("🔧 Muitas sessões de debug — tente /shadow para análise autônoma")

        # Default recommendations
        if not recommendations:
            recommendations.append("✅ Sistema saudável — continue assim!")
            recommendations.append("🎯 Experimente o Deep Dev Panel (Ctrl+D) para engenharia autônoma")
            recommendations.append("🧠 Use 'lembre-se [fato]' para enriquecer o knowledge graph")

        content = "\n".join(f"{i+1}. {r}" for i, r in enumerate(recommendations))
        return DigestSection(
            title="Recomendações",
            icon="💡",
            content=content,
            highlights=[],
            score=None,
        )

    # ═══ Helpers ═══════════════════════════════════════════════════════════

    def _build_summary(self, sections: List[DigestSection], overall: float) -> str:
        """Build a one-line summary."""
        if overall > 0.8:
            emoji = "🏆"
            desc = "Excelente semana! Sistema funcionando em alta performance."
        elif overall > 0.6:
            emoji = "✅"
            desc = "Boa semana. Sistema operando bem com margem de melhoria."
        elif overall > 0.4:
            emoji = "⚡"
            desc = "Semana regular. Algumas áreas precisam de atenção."
        else:
            emoji = "⚠️"
            desc = "Semana abaixo do esperado. Recomenda-se revisão dos sistemas."

        return f"{emoji} {desc} (Score: {overall:.0%})"

    def _score_bar(self, score: float) -> str:
        """Visual score bar."""
        filled = int(score * 10)
        return "█" * filled + "░" * (10 - filled)

    def _load_json(self, path: str, default=None):
        full = self.project_dir / path
        if not full.exists():
            return default if default is not None else {}
        try:
            with open(full, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else {}

    def _load_jsonl(self, path: str) -> List[dict]:
        full = self.project_dir / path
        if not full.exists():
            return []
        entries = []
        try:
            with open(full, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception:
            pass
        return entries

    def _in_period(self, timestamp_str: str, start: datetime, end: datetime) -> bool:
        """Check if an ISO timestamp string is within the period."""
        if not timestamp_str:
            return False
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return start <= dt <= end
        except (ValueError, TypeError):
            return False

    def _ts_in_period(self, timestamp_num: float, start: datetime, end: datetime) -> bool:
        """Check if a Unix timestamp number is within the period."""
        if not timestamp_num:
            return False
        try:
            dt = datetime.fromtimestamp(timestamp_num)
            return start <= dt <= end
        except (ValueError, TypeError, OSError):
            return False

    def _ts_in_period_str(self, timestamp_str: str, start: datetime, end: datetime) -> bool:
        """Check if a string timestamp (various formats) is within period."""
        if not timestamp_str:
            return False
        # Try ISO format first
        if self._in_period(timestamp_str, start, end):
            return True
        # Try common format
        try:
            dt = datetime.strptime(timestamp_str[:19], "%Y-%m-%dT%H:%M:%S")
            return start <= dt <= end
        except (ValueError, TypeError):
            pass
        return False
