#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — Pesquisa na Web
================================
Busca respostas na web usando DuckDuckGo.
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger("greatsage.web")


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results
    except ImportError:
        logger.warning("duckduckgo-search not installed")
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def search_and_summarize(query: str) -> str:
    """Search and return a formatted summary."""
    results = search_web(query, max_results=3)

    if not results:
        return f"Nao encontrei resultados para: {query}"

    parts = [f"**Resultados para:** {query}\n"]

    for i, r in enumerate(results, 1):
        title = r.get("title", "Sem titulo")
        body = r.get("body", "Sem descricao")
        url = r.get("href", "")
        parts.append(f"**{i}. {title}**")
        parts.append(f"   {body[:200]}")
        if url:
            parts.append(f"   Fonte: {url}")
        parts.append("")

    return "\n".join(parts)


def search_news(query: str, max_results: int = 3) -> str:
    """Search for news."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))

        if not results:
            return f"Nao encontrei noticias sobre: {query}"

        parts = [f"**Noticias sobre:** {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("url", "")
            date = r.get("date", "")
            parts.append(f"**{i}. {title}** ({date})")
            parts.append(f"   {body[:150]}")
            if url:
                parts.append(f"   {url}")
            parts.append("")

        return "\n".join(parts)
    except Exception as e:
        return f"Erro ao buscar noticias: {e}"
