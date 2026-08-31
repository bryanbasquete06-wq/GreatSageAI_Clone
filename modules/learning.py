# -*- coding: utf-8 -*-
"""
Elívea — Continuous Learning
====================================
Aprende interacoes e preferencias do usuario ao longo do tempo.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path


class LearningEngine:
    """Motor de aprendizado continuo do usuario."""

    _DATA_FILE = Path(__file__).resolve().parent.parent / "config" / "learning_data.json"

    @classmethod
    def _ensure_file(cls):
        cls._DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not cls._DATA_FILE.exists():
            default = {
                "preferences": {},
                "interaction_stats": {},
                "topic_interests": {},
                "time_patterns": {},
                "code_preferences": {},
            }
            cls._DATA_FILE.write_text(json.dumps(default, indent=2), encoding="utf-8")

    @classmethod
    def _load(cls) -> dict:
        cls._ensure_file()
        try:
            return json.loads(cls._DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"preferences": {}, "interaction_stats": {}, "topic_interests": {}}

    @classmethod
    def _save(cls, data: dict):
        cls._ensure_file()
        cls._DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def record_interaction(cls, command: str, response: str):
        """Registra uma interacao para analise de padroes."""
        data = cls._load()

        hour = datetime.now().hour
        hour_bucket = f"{(hour // 4) * 4:02d}-{(hour // 4) * 4 + 4:02d}"
        time_stats = data.setdefault("time_patterns", {})
        time_stats[hour_bucket] = time_stats.get(hour_bucket, 0) + 1

        topics = data.setdefault("topic_interests", {})
        words = command.lower().split()
        for word in words:
            if len(word) > 3:
                topics[word] = topics.get(word, 0) + 1
        if len(topics) > 200:
            sorted_topics = sorted(topics.items(), key=lambda x: -x[1])[:100]
            data["topic_interests"] = dict(sorted_topics)

        stats = data.setdefault("interaction_stats", {})
        today = datetime.now().strftime("%Y-%m-%d")
        stats[today] = stats.get(today, 0) + 1

        cls._save(data)

    @classmethod
    def record_preference(cls, key: str, value: str):
        """Registra uma preferencia do usuario."""
        data = cls._load()
        data.setdefault("preferences", {})[key] = value
        cls._save(data)

    @classmethod
    def record_code_preference(cls, language: str, style: str = None):
        """Registra preferencia de linguagem/estilo de codigo."""
        data = cls._load()
        prefs = data.setdefault("code_preferences", {})
        lang_data = prefs.get(language, {"count": 0, "styles": {}})
        lang_data["count"] = lang_data.get("count", 0) + 1
        if style:
            lang_data["styles"][style] = lang_data["styles"].get(style, 0) + 1
        prefs[language] = lang_data
        cls._save(data)

    @classmethod
    def get_preferred_language(cls) -> str | None:
        """Retorna a linguagem de codigo mais usada."""
        data = cls._load()
        prefs = data.get("code_preferences", {})
        if not prefs:
            return None
        return max(prefs, key=lambda k: prefs[k].get("count", 0))

    @classmethod
    def get_peak_hours(cls) -> list:
        """Retorna os horarios mais produtivos do usuario."""
        data = cls._load()
        time_patterns = data.get("time_patterns", {})
        if not time_patterns:
            return []
        sorted_hours = sorted(time_patterns.items(), key=lambda x: -x[1])
        return [h[0] for h in sorted_hours[:3]]

    @classmethod
    def get_interesting_topics(cls, limit: int = 10) -> list:
        """Retorna os topics mais interessantes para o usuario."""
        data = cls._load()
        topics = data.get("topic_interests", {})
        sorted_topics = sorted(topics.items(), key=lambda x: -x[1])
        return [t[0] for t in sorted_topics[:limit]]

    @classmethod
    def get_learning_context(cls) -> str:
        """Gera contexto de aprendizado para o system prompt."""
        data = cls._load()
        lines = []

        prefs = data.get("preferences", {})
        if prefs:
            lines.append("Preferencias do Mestre:")
            for k, v in prefs.items():
                lines.append(f"  - {k}: {v}")

        peak = cls.get_peak_hours()
        if peak:
            lines.append(f"Horarios mais produtivos: {', '.join(peak)}")

        topics = cls.get_interesting_topics(5)
        if topics:
            lines.append(f"Topics de interesse: {', '.join(topics)}")

        code_prefs = data.get("code_preferences", {})
        if code_prefs:
            top_lang = max(code_prefs, key=lambda k: code_prefs[k].get("count", 0))
            lines.append(f"Linguagem preferida: {top_lang}")

        stats = data.get("interaction_stats", {})
        total = sum(stats.values())
        if total > 0:
            lines.append(f"Total de interacoes registradas: {total}")

        return "\n".join(lines) if lines else ""
