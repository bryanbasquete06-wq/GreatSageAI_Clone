#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personal Knowledge Graph v2
=============================
Major upgrade: deeper relationship extraction, temporal reasoning,
context-aware queries, pattern detection, and knowledge decay.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Entity:
    """A concept/entity in the knowledge graph."""
    name: str
    type: str  # "technology", "person", "project", "concept", "file", "function", "pattern"
    mentions: int = 1
    last_seen: float = 0.0
    first_seen: float = 0.0
    context: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class Edge:
    """A relationship between two entities."""
    source: str
    target: str
    relation: str
    weight: int = 1
    last_seen: float = 0.0
    evidence: List[str] = field(default_factory=list)


@dataclass
class Pattern:
    """A detected pattern in user behavior."""
    name: str
    description: str
    frequency: int = 0
    last_seen: float = 0.0
    entities: List[str] = field(default_factory=list)


class KnowledgeGraph:
    """
    Maintains a personal knowledge graph from conversations.
    v2: Deeper extraction, temporal reasoning, pattern detection.
    """

    ENTITY_PATTERNS = {
        "technology": [
            (r"\b(Python|JavaScript|TypeScript|Rust|Go|Java|C\+\+|PHP|Ruby|Swift|Kotlin)\b", 2),
            (r"\b(React|Vue|Angular|Svelte|Next\.js|FastAPI|Flask|Django|Express|Spring|PySide6|PyQt6)\b", 2),
            (r"\b(PostgreSQL|MySQL|MongoDB|Redis|SQLite|Docker|Kubernetes|AWS|GCP|Azure|Terraform)\b", 2),
            (r"\b(Git|GitHub|GitLab|VSCode|Neovim|Vim|IntelliJ|PyCharm)\b", 1),
            (r"\b(psutil|requests|httpx|aiohttp|celery|redis|sqlalchemy|alembic)\b", 1),
        ],
        "concept": [
            (r"\b(API|REST|GraphQL|gRPC|WebSocket|HTTP|HTTPS|TCP|UDP|WebSocket)\b", 1),
            (r"\b(SQL|NoSQL|ORM|CRUD|MVC|MVP|MVVM|SOLID|DRY|KISS|YAGNI)\b", 2),
            (r"\b(autenticacao|autorizacao|JWT|OAuth|RBAC|CORS|CSRF|XSS|encryption)\b", 1),
            (r"\b(teste|mock|stub|fixture|coverage|TDD|BDD|CI/CD|DevOps|MLOps)\b", 1),
            (r"\b(async|await|concurrency|parallel|threading|multiprocessing)\b", 1),
        ],
        "file": [
            (r"[\w/\\]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|html|css|json|yaml|yml|toml|md)", 1),
        ],
        "function": [
            (r"\b([a-z_][a-z0-9_]*)\s*\(", 1),
            (r"\b([A-Z][a-zA-Z]+(?:Engine|Manager|Service|Handler|Controller|Factory|Adapter|Provider|Router|Guard|Analyzer|Detector|Monitor))\b", 2),
        ],
        "pattern": [
            (r"(?i)(design pattern|factory pattern|observer pattern|singleton|strategy pattern)\b", 3),
            (r"(?i)(dependency injection|inversion of control|middleware|decorator pattern)\b", 3),
        ],
    }

    RELATION_PATTERNS = [
        (r"(\w+)\s+(?:usa|uses?|importa?|imports?|requer|requires?)\s+(\w+)", "uses"),
        (r"(\w+)\s+(?:depende|depends?)\s+(?:de|of|on)\s+(\w+)", "depends_on"),
        (r"(\w+)\s+(?:e|is|e\s+um|is\s+a)\s+(?:parte|part)\s+(?:de|of)\s+(\w+)", "part_of"),
        (r"(\w+)\s+(?:herda|extends?|implementa?|implements?)\s+(\w+)", "extends"),
        (r"(\w+)\s+(?:chama|calls?|invoca?|invokes?|delega?)\s+(\w+)", "calls"),
        (r"(\w+)\s+(?:conflita|conflicts?|clashes?)\s+(?:com|with)\s+(\w+)", "conflicts_with"),
        (r"(\w+)\s+(?:substitui|replaces?|supersedes?)\s+(\w+)", "replaces"),
    ]

    def __init__(self, data_dir: str = "memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._graph_file = self.data_dir / "knowledge_graph.json"

        self._entities: Dict[str, Entity] = {}
        self._edges: List[Edge] = []
        self._topic_history: List[Tuple[float, str]] = []
        self._patterns: List[Pattern] = []

        self._load_graph()

    def update(self, text: str, context: str = ""):
        """Process text and extract entities/relationships."""
        now = time.time()

        # Extract entities
        new_entities = self._extract_entities(text)
        for name, etype, weight in new_entities:
            if name in self._entities:
                self._entities[name].mentions += weight
                self._entities[name].last_seen = now
                if context and len(self._entities[name].context) < 5:
                    self._entities[name].context.append(context[:100])
            else:
                self._entities[name] = Entity(
                    name=name, type=etype, first_seen=now, last_seen=now,
                    context=[context[:100]] if context else [],
                )

        # Extract relationships
        new_edges = self._extract_relationships(text)
        for edge in new_edges:
            edge.last_seen = now
            existing = None
            for e in self._edges:
                if e.source == edge.source and e.target == edge.target and e.relation == edge.relation:
                    existing = e
                    break
            if existing:
                existing.weight += 1
                existing.last_seen = now
                if text[:100] not in existing.evidence:
                    existing.evidence.append(text[:100])
            else:
                self._edges.append(edge)

        # Detect patterns
        self._detect_patterns(text, now)

        # Track topics
        topic = self._detect_topic(text)
        if topic:
            self._topic_history.append((now, topic))
            if len(self._topic_history) > 500:
                self._topic_history = self._topic_history[-500:]

        # Auto-save periodically
        if len(self._entities) % 10 == 0:
            self._save_graph()

    def query(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Query information about an entity with temporal context."""
        entity = self._entities.get(entity_name)
        if not entity:
            return None

        connections = []
        for edge in self._edges:
            if edge.source == entity_name:
                connections.append({
                    "entity": edge.target, "relation": edge.relation,
                    "weight": edge.weight, "last_seen": edge.last_seen,
                })
            elif edge.target == entity_name:
                connections.append({
                    "entity": edge.source, "relation": edge.relation,
                    "weight": edge.weight, "last_seen": edge.last_seen,
                })

        # Calculate freshness
        now = time.time()
        days_since_last = (now - entity.last_seen) / 86400
        freshness = max(0.0, 1.0 - days_since_last / 30)  # Decays over 30 days

        return {
            "name": entity.name,
            "type": entity.type,
            "mentions": entity.mentions,
            "first_seen": entity.first_seen,
            "last_seen": entity.last_seen,
            "freshness": round(freshness, 3),
            "context": entity.context,
            "connections": sorted(connections, key=lambda c: c["weight"], reverse=True),
        }

    def get_context_for_query(self, query: str) -> str:
        """Get relevant knowledge context for a query."""
        query_entities = self._extract_entities(query)
        context_parts = []

        for name, etype, weight in query_entities:
            info = self.query(name)
            if info and info["mentions"] > 1:
                connections = info["connections"][:3]
                if connections:
                    conn_str = ", ".join(f"{c['entity']} ({c['relation']})" for c in connections)
                    freshness = info["freshness"]
                    fresh_tag = "recente" if freshness > 0.7 else "antigo"
                    context_parts.append(f"{name} ({fresh_tag}): {conn_str}")

        if context_parts:
            return "[CONHECIMENTO] " + "; ".join(context_parts)
        return ""

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics with temporal analysis."""
        type_counts = Counter(e.type for e in self._entities.values())

        # Most active entities (last 7 days)
        now = time.time()
        week_ago = now - 7 * 86400
        active = [e for e in self._entities.values() if e.last_seen > week_ago]

        # Knowledge decay analysis
        decay_stats = {"fresh": 0, "aging": 0, "stale": 0}
        for e in self._entities.values():
            days = (now - e.last_seen) / 86400
            if days < 7:
                decay_stats["fresh"] += 1
            elif days < 30:
                decay_stats["aging"] += 1
            else:
                decay_stats["stale"] += 1

        return {
            "total_entities": len(self._entities),
            "total_edges": len(self._edges),
            "types": dict(type_counts),
            "active_last_7d": len(active),
            "decay": decay_stats,
            "patterns": len(self._patterns),
            "top_entities": sorted(
                self._entities.values(), key=lambda e: e.mentions, reverse=True
            )[:10],
        }

    def get_recent_topics(self, n: int = 10) -> List[str]:
        """Get the N most recent unique topics."""
        seen = []
        for _, topic in reversed(self._topic_history):
            if topic not in seen:
                seen.append(topic)
                if len(seen) >= n:
                    break
        return seen

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get detected behavioral patterns."""
        return [
            {"name": p.name, "description": p.description, "frequency": p.frequency,
             "entities": p.entities[:5]}
            for p in sorted(self._patterns, key=lambda p: p.frequency, reverse=True)[:10]
        ]

    def find_path(self, entity_a: str, entity_b: str, max_depth: int = 3) -> List[str]:
        """Find connection path between two entities (BFS)."""
        if entity_a not in self._entities or entity_b not in self._entities:
            return []

        # Build adjacency
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in self._edges:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)

        # BFS
        visited = {entity_a}
        queue = [(entity_a, [entity_a])]
        while queue:
            current, path = queue.pop(0)
            if current == entity_b:
                return path
            if len(path) > max_depth:
                continue
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    # ═══ Private helpers ═══════════════════════════════════════════════════════

    def _extract_entities(self, text: str) -> List[Tuple[str, str, int]]:
        """Extract entities with types and importance weights."""
        entities = []
        for etype, patterns in self.ENTITY_PATTERNS.items():
            for pattern, weight in patterns:
                for match in re.finditer(pattern, text):
                    name = match.group(1) if match.lastindex else match.group()
                    if len(name) > 1 and name.lower() not in ("the", "a", "an", "is", "are", "was", "de", "do", "da"):
                        entities.append((name, etype, weight))
        return entities

    def _extract_relationships(self, text: str) -> List[Edge]:
        """Extract relationships from text."""
        edges = []
        for pattern, relation in self.RELATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                source, target = match.group(1), match.group(2)
                if source.lower() != target.lower():
                    edges.append(Edge(
                        source=source, target=target, relation=relation,
                        evidence=[text[:100]],
                    ))
        return edges

    def _detect_topic(self, text: str) -> str:
        text_lower = text.lower()
        topics = {
            "python": ["python", "pip", "venv", "pylint", "pytest", "fastapi", "flask"],
            "javascript": ["javascript", "typescript", "node", "npm", "react", "vue", "next"],
            "database": ["sql", "postgres", "mysql", "mongo", "redis", "query", "select"],
            "devops": ["docker", "kubernetes", "ci/cd", "deploy", "aws", "azure"],
            "security": ["auth", "jwt", "oauth", "password", "encryption", "xss", "csrf"],
            "ai_ml": ["machine learning", "deep learning", "neural", "model", "llm"],
            "architecture": ["arquitetura", "design pattern", "solid", "refactor"],
        }
        scores = {}
        for topic, keywords in topics.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[topic] = score
        return max(scores, key=scores.get) if scores else "general"

    def _detect_patterns(self, text: str, now: float):
        """Detect behavioral patterns from text."""
        text_lower = text.lower()

        # Pattern: User frequently asks about the same technology
        if "como" in text_lower and ("usar" in text_lower or "fazer" in text_lower):
            entities = self._extract_entities(text)
            for name, etype, _ in entities:
                existing = next((p for p in self._patterns if p.name == f"uses_{name}"), None)
                if existing:
                    existing.frequency += 1
                    existing.last_seen = now
                else:
                    self._patterns.append(Pattern(
                        name=f"uses_{name}",
                        description=f"User frequently asks about using {name}",
                        frequency=1, last_seen=now, entities=[name],
                    ))

        # Pattern: User debugs specific types of issues
        debug_words = ["bug", "erro", "error", "crash", "nao funciona"]
        if any(w in text_lower for w in debug_words):
            existing = next((p for p in self._patterns if p.name == "debug_pattern"), None)
            if existing:
                existing.frequency += 1
                existing.last_seen = now
            else:
                self._patterns.append(Pattern(
                    name="debug_pattern",
                    description="User frequently encounters debugging issues",
                    frequency=1, last_seen=now,
                ))

    def _load_graph(self):
        if self._graph_file.exists():
            try:
                with open(self._graph_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for e_data in data.get("entities", []):
                    e = Entity(**{k: v for k, v in e_data.items() if k in Entity.__dataclass_fields__})
                    self._entities[e.name] = e
                for edge_data in data.get("edges", []):
                    filtered = {k: v for k, v in edge_data.items() if k in Edge.__dataclass_fields__}
                    self._edges.append(Edge(**filtered))
                for pat_data in data.get("patterns", []):
                    filtered = {k: v for k, v in pat_data.items() if k in Pattern.__dataclass_fields__}
                    self._patterns.append(Pattern(**filtered))
            except Exception:
                pass

    def _save_graph(self):
        try:
            data = {
                "entities": [
                    {"name": e.name, "type": e.type, "mentions": e.mentions,
                     "last_seen": e.last_seen, "first_seen": e.first_seen,
                     "context": e.context, "metadata": e.metadata, "confidence": e.confidence}
                    for e in self._entities.values()
                ],
                "edges": [
                    {"source": edge.source, "target": edge.target,
                     "relation": edge.relation, "weight": edge.weight,
                     "last_seen": edge.last_seen, "evidence": edge.evidence}
                    for edge in self._edges
                ],
                "patterns": [
                    {"name": p.name, "description": p.description,
                     "frequency": p.frequency, "last_seen": p.last_seen,
                     "entities": p.entities}
                    for p in self._patterns
                ],
            }
            with open(self._graph_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
