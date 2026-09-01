#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Response Quality Score v2
===========================
Major upgrade: learning from feedback patterns, provider comparison,
trend analysis, anomaly detection, and adaptive scoring.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class QualityEntry:
    """A single quality score entry."""
    timestamp: float = 0.0
    query: str = ""
    response_preview: str = ""
    auto_score: float = 0.5
    user_rating: Optional[float] = None
    latency_ms: float = 0.0
    provider: str = ""
    category: str = ""
    tokens_used: int = 0
    hallucination_score: float = 1.0
    correction_count: int = 0


@dataclass
class ProviderStats:
    """Statistics for a specific provider."""
    name: str
    total_requests: int = 0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    user_agreement: float = 0.0
    cost_per_token: float = 0.0


class QualityScorer:
    """
    Scores response quality using heuristics + user feedback.
    v2: Learning from patterns, provider comparison, anomaly detection.
    """

    def __init__(self, data_dir: str = "memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._history_file = self.data_dir / "quality_history.jsonl"
        self._history: List[QualityEntry] = []
        self._load_history()

        # Learned weights from feedback
        self._learned_weights: Dict[str, float] = {
            "length": 0.15,
            "structure": 0.1,
            "completeness": 0.1,
            "relevance": 0.2,
            "latency": 0.1,
            "no_errors": 0.15,
            "source_quality": 0.1,
            "code_quality": 0.1,
        }

        # Provider cost models
        self._provider_costs: Dict[str, float] = {
            "gemini": 0.000001,
            "openai": 0.00001,
            "claude": 0.000015,
            "local": 0.0,
        }

    def auto_score(self, query: str, response: str, latency_ms: float = 0,
                   provider: str = "", tokens: int = 0,
                   hallucination_score: float = 1.0,
                   correction_count: int = 0) -> float:
        """
        Calculate automatic quality score with learned weights.
        v2: More granular scoring with adaptive weights.
        """
        scores = {}

        # Length appropriateness
        if len(response) < 10:
            scores["length"] = 0.1
        elif len(response) < 50:
            scores["length"] = 0.4
        elif len(response) < 500:
            scores["length"] = 0.7
        elif len(response) < 2000:
            scores["length"] = 0.9
        else:
            scores["length"] = 0.8  # Detailed but not excessive

        # Structure quality
        structure_score = 0.5
        if "```" in response:
            structure_score += 0.15
        if any(response.startswith(h) for h in ["#", "**", "-", "•"]):
            structure_score += 0.1
        if "\n\n" in response:
            structure_score += 0.1  # Has paragraph breaks
        if re.search(r"\d+\.\s", response):
            structure_score += 0.05  # Has numbered list
        scores["structure"] = min(1.0, structure_score)

        # Completeness
        completeness = 0.5
        if response.endswith((".", "```", '"', "'", "]", ")", "}")):
            completeness += 0.2
        if "..." in response or "…" in response:
            completeness -= 0.2
        if len(response) > 100 and "\n" in response:
            completeness += 0.1
        scores["completeness"] = max(0.0, min(1.0, completeness))

        # Relevance (keyword overlap)
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        overlap = len(query_words & response_words) / max(len(query_words), 1)
        scores["relevance"] = min(1.0, 0.3 + overlap * 0.7)

        # Latency
        if latency_ms < 1000:
            scores["latency"] = 1.0
        elif latency_ms < 3000:
            scores["latency"] = 0.8
        elif latency_ms < 5000:
            scores["latency"] = 0.6
        elif latency_ms < 10000:
            scores["latency"] = 0.4
        else:
            scores["latency"] = 0.2

        # No errors
        error_signals = ["error", "exception", "traceback", "erro:", "failed"]
        error_count = sum(1 for s in error_signals if s in response.lower()[:200])
        scores["no_errors"] = max(0.0, 1.0 - error_count * 0.3)

        # Source quality (based on hallucination guard)
        scores["source_quality"] = hallucination_score

        # Code quality (if code is present)
        if "```" in response:
            code_blocks = re.findall(r"```(?:python|py|js|ts)\n(.*?)```", response, re.DOTALL)
            code_score = 0.5
            for block in code_blocks:
                if "def " in block or "class " in block:
                    code_score += 0.1
                if '"""' in block or "'''" in block:
                    code_score += 0.1
                if "try:" in block and "except" in block:
                    code_score += 0.1
                if ":" in block and "=" in block:
                    code_score += 0.05  # Has assignments
            scores["code_quality"] = min(1.0, code_score)
        else:
            scores["code_quality"] = 0.7  # Neutral for non-code

        # Calculate weighted score
        total = sum(scores[k] * self._learned_weights[k] for k in scores)
        return max(0.0, min(1.0, total))

    def record(self, query: str, response: str, latency_ms: float = 0,
               provider: str = "", tokens: int = 0, category: str = "",
               hallucination_score: float = 1.0,
               correction_count: int = 0) -> QualityEntry:
        """Record a response with auto-score."""
        auto = self.auto_score(query, response, latency_ms, provider, tokens,
                              hallucination_score, correction_count)
        entry = QualityEntry(
            timestamp=time.time(),
            query=query[:200],
            response_preview=response[:100],
            auto_score=auto,
            latency_ms=latency_ms,
            provider=provider,
            category=category,
            tokens_used=tokens,
            hallucination_score=hallucination_score,
            correction_count=correction_count,
        )
        self._history.append(entry)
        self._save_entry(entry)
        return entry

    def rate(self, index: int, rating: float) -> bool:
        """Rate a response (1.0=good, 0.0=bad). Triggers weight learning."""
        if 0 <= index < len(self._history):
            self._history[index].user_rating = rating
            # Learn from this feedback
            self._learn_from_feedback(self._history[index])
            self._save_history()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive quality statistics."""
        if not self._history:
            return {"total": 0, "avg_score": 0, "avg_latency": 0}

        rated = [e for e in self._history if e.user_rating is not None]
        avg_score = sum(e.auto_score for e in self._history) / len(self._history)
        avg_latency = sum(e.latency_ms for e in self._history) / len(self._history)

        user_agreement = 0
        if rated:
            agreements = sum(1 for e in rated
                           if (e.user_rating > 0.5) == (e.auto_score > 0.5))
            user_agreement = agreements / len(rated)

        # Trend (last 10 vs previous 10)
        trend = self._calculate_trend()

        # Provider comparison
        provider_stats = self._get_provider_stats()

        return {
            "total": len(self._history),
            "rated": len(rated),
            "avg_score": round(avg_score, 3),
            "avg_latency_ms": round(avg_latency, 0),
            "user_agreement": round(user_agreement, 3),
            "trend": trend,
            "category_scores": self._category_scores(),
            "provider_stats": provider_stats,
            "learned_weights": dict(self._learned_weights),
        }

    def get_trend(self, last_n: int = 20) -> List[float]:
        """Get the trend of auto-scores for the last N entries."""
        return [e.auto_score for e in self._history[-last_n:]]

    def get_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in quality scores."""
        if len(self._history) < 10:
            return []

        anomalies = []
        scores = [e.auto_score for e in self._history[-20:]]
        mean = sum(scores) / len(scores) if scores else 0
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5 if scores else 0

        for i, entry in enumerate(self._history[-20:]):
            if abs(entry.auto_score - mean) > 2 * std:
                anomalies.append({
                    "timestamp": entry.timestamp,
                    "score": entry.auto_score,
                    "query": entry.query[:50],
                    "deviation": round((entry.auto_score - mean) / max(std, 0.01), 2),
                })

        return anomalies

    # ═══ Learning from Feedback ═══════════════════════════════════════════════

    def _learn_from_feedback(self, entry: QualityEntry):
        """Adjust scoring weights based on user feedback."""
        if entry.user_rating is None:
            return

        # Simple gradient descent: if user disagrees with auto-score, adjust weights
        predicted = entry.auto_score
        actual = entry.user_rating
        error = actual - predicted

        # Only adjust if significant disagreement
        if abs(error) < 0.2:
            return

        # Increase weights for features that correlate with user satisfaction
        for key in self._learned_weights:
            # Simplified: boost weights when user likes what auto-score liked
            if error > 0 and predicted < 0.5:
                # User liked it more than we thought — boost positive features
                self._learned_weights[key] *= 1.01
            elif error < 0 and predicted > 0.5:
                # User liked it less — reduce weights
                self._learned_weights[key] *= 0.99

        # Normalize weights
        total = sum(self._learned_weights.values())
        if total > 0:
            for key in self._learned_weights:
                self._learned_weights[key] /= total / len(self._learned_weights)

    def _calculate_trend(self) -> Dict[str, Any]:
        """Calculate quality trend."""
        if len(self._history) < 10:
            return {"direction": "stable", "change": 0}

        recent = [e.auto_score for e in self._history[-10:]]
        previous = [e.auto_score for e in self._history[-20:-10]]

        recent_avg = sum(recent) / len(recent) if recent else 0
        previous_avg = sum(previous) / len(previous) if previous else recent_avg

        change = recent_avg - previous_avg
        direction = "improving" if change > 0.05 else "declining" if change < -0.05 else "stable"

        return {"direction": direction, "change": round(change, 3)}

    def _get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats per provider."""
        provider_data: Dict[str, List[QualityEntry]] = defaultdict(list)
        for entry in self._history:
            if entry.provider:
                provider_data[entry.provider].append(entry)

        stats = {}
        for provider, entries in provider_data.items():
            avg_score = sum(e.auto_score for e in entries) / len(entries)
            avg_latency = sum(e.latency_ms for e in entries) / len(entries)
            rated = [e for e in entries if e.user_rating is not None]
            agreement = 0
            if rated:
                agreements = sum(1 for e in rated
                               if (e.user_rating > 0.5) == (e.auto_score > 0.5))
                agreement = agreements / len(rated)

            stats[provider] = {
                "total": len(entries),
                "avg_score": round(avg_score, 3),
                "avg_latency_ms": round(avg_latency, 0),
                "user_agreement": round(agreement, 3),
            }

        return stats

    def _category_scores(self) -> Dict[str, float]:
        """Get average score per category."""
        categories: Dict[str, List[float]] = defaultdict(list)
        for e in self._history:
            cat = e.category or "general"
            categories[cat].append(e.auto_score)
        return {cat: round(sum(scores) / len(scores), 3)
                for cat, scores in categories.items()}

    # ═══ Persistence ═══════════════════════════════════════════════════════════

    def _load_history(self):
        if self._history_file.exists():
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            self._history.append(QualityEntry(**data))
            except Exception:
                self._history = []

    def _save_entry(self, entry: QualityEntry):
        try:
            with open(self._history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": entry.timestamp,
                    "query": entry.query,
                    "response_preview": entry.response_preview,
                    "auto_score": entry.auto_score,
                    "user_rating": entry.user_rating,
                    "latency_ms": entry.latency_ms,
                    "provider": entry.provider,
                    "category": entry.category,
                    "tokens_used": entry.tokens_used,
                    "hallucination_score": entry.hallucination_score,
                    "correction_count": entry.correction_count,
                }) + "\n")
        except Exception:
            pass

    def _save_history(self):
        try:
            with open(self._history_file, "w", encoding="utf-8") as f:
                for entry in self._history:
                    f.write(json.dumps({
                        "timestamp": entry.timestamp,
                        "query": entry.query,
                        "response_preview": entry.response_preview,
                        "auto_score": entry.auto_score,
                        "user_rating": entry.user_rating,
                        "latency_ms": entry.latency_ms,
                        "provider": entry.provider,
                        "category": entry.category,
                        "tokens_used": entry.tokens_used,
                        "hallucination_score": entry.hallucination_score,
                        "correction_count": entry.correction_count,
                    }) + "\n")
        except Exception:
            pass
