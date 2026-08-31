# -*- coding: utf-8 -*-
"""
Elívea — RAG (Retrieval-Augmented Generation) com Pesquisa Web
=====================================================================
Pesquisa na internet em tempo real via DuckDuckGo (gratis).
Indexa resultados localmente para reuso rapido.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


class RAGEngine:
    """Motor RAG com pesquisa web e cache local."""

    _CACHE_DIR = Path(__file__).resolve().parent.parent / "config" / "rag_cache"
    _MAX_CACHE_AGE = 3600 * 6  # 6 horas
    _MAX_RESULTS = 8

    @classmethod
    def _ensure_cache(cls):
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _cache_key(cls, query: str) -> str:
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    @classmethod
    def _get_cached(cls, query: str) -> Optional[dict]:
        cls._ensure_cache()
        key = cls._cache_key(query)
        cache_file = cls._CACHE_DIR / f"{key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) > cls._MAX_CACHE_AGE:
                cache_file.unlink(missing_ok=True)
                return None
            return data
        except Exception:
            return None

    @classmethod
    def _set_cache(cls, query: str, results: list):
        cls._ensure_cache()
        key = cls._cache_key(query)
        cache_file = cls._CACHE_DIR / f"{key}.json"
        data = {"query": query, "timestamp": time.time(), "results": results}
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def search(cls, query: str, max_results: int = 5) -> dict:
        """
        Pesquisa na internet. Retorna:
        {"results": [{"title": ..., "snippet": ..., "url": ...}], "source": "duckduckgo"}
        """
        cached = cls._get_cached(query)
        if cached:
            return {"results": cached["results"][:max_results], "source": "cache"}

        results = cls._search_ddg(query)
        if results:
            cls._set_cache(query, results)
        return {"results": results[:max_results], "source": "duckduckgo"}

    @classmethod
    def _search_ddg(cls, query: str) -> list:
        """Pesquisa via DuckDuckGo instant answer API."""
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, headers={
                "User-Agent": "Elivea/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                })
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })
            return results
        except Exception:
            return cls._search_fallback(query)

    @classmethod
    def _search_fallback(cls, query: str) -> list:
        """Fallback: busca via HTML do DuckDuckGo lite."""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Elivea/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            results = []
            snippets = re.findall(r'class="result-snippet">(.*?)</td>', html, re.DOTALL)
            titles = re.findall(r'class="result-title"[^>]*>(.*?)</a>', html, re.DOTALL)
            urls = re.findall(r'class="result-link"[^>]*>(.*?)</a>', html, re.DOTALL)

            for i in range(min(len(titles), 5)):
                title = re.sub(r"<.*?>", "", titles[i]).strip() if i < len(titles) else ""
                snippet = re.sub(r"<.*?>", "", snippets[i]).strip() if i < len(snippets) else ""
                url = urls[i].strip() if i < len(urls) else ""
                if title or snippet:
                    results.append({"title": title, "snippet": snippet, "url": url})
            return results
        except Exception:
            return []

    @classmethod
    def search_and_summarize(cls, query: str, llm_query_fn=None) -> str:
        """
        Pesquisa e retorna contexto formatado para injecao no prompt.
        Se llm_query_fn for fornecido, usa o LLM para resumir.
        """
        data = cls.search(query)
        results = data["results"]
        if not results:
            return f"Nenhum resultado encontrado para: {query}"

        context_parts = []
        for r in results:
            part = f"{r['title']}: {r['snippet']}"
            if r.get("url"):
                part += f" (fonte: {r['url']})"
            context_parts.append(part)

        context = "\n".join(context_parts)

        if llm_query_fn:
            try:
                prompt = (
                    f"Resuma os seguintes resultados de pesquisa sobre '{query}' "
                    f"em portugues, de forma concisa e informativa:\n\n{context}"
                )
                return llm_query_fn(prompt)
            except Exception:
                pass

        return context

    @classmethod
    def clear_cache(cls):
        """Limpa cache de pesquisas."""
        cls._ensure_cache()
        for f in cls._CACHE_DIR.glob("*.json"):
            f.unlink(missing_ok=True)
