"""
Elivea - Web Navigation & Search Module
Handles web searches and browser operations.
"""

import re
import webbrowser
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

try:
    from duckduckgo_search import DDGS
    _ddgs_available = True
except ImportError:
    try:
        from ddgs import DDGS
        _ddgs_available = True
    except ImportError:
        _ddgs_available = False


class WebModule:
    @staticmethod
    def search_web(query: str) -> str:
        """Executa busca real no DuckDuckGo e retorna resultados processados."""
        # Método 1: duckduckgo-search (mais confiável)
        if _ddgs_available:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=5))
                if results:
                    lines = [f"Resultados para '{query}':\n"]
                    for i, r in enumerate(results, 1):
                        title = r.get("title", "")
                        href = r.get("href", r.get("link", ""))
                        body = r.get("body", r.get("snippet", ""))
                        lines.append(f"{i}. {title}\n   {href}\n   {body}")
                    return "\n\n".join(lines)
                return f"Nenhum resultado encontrado para '{query}'."
            except Exception as e:
                pass  # fallback para requests

        # Método 2: requests direto (fallback)
        if not requests:
            return "Módulo requests não instalado. Execute: pip install requests"

        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code not in (200, 202):
                return f"Busca retornou status {resp.status_code}."

            html = resp.text
            results = []

            title_pattern = re.compile(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            snippet_pattern = re.compile(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
                re.DOTALL
            )

            titles = title_pattern.findall(html)
            snippets = snippet_pattern.findall(html)

            for i, (link, title) in enumerate(titles[:5]):
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                clean_snippet = ""
                if i < len(snippets):
                    clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                real_url = link
                if "uddg=" in link:
                    real_url = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                results.append(f"{i+1}. {clean_title}\n   {real_url}\n   {clean_snippet}")

            if results:
                return f"Resultados para '{query}':\n\n" + "\n\n".join(results)

            return f"Nenhum resultado encontrado para '{query}'."

        except Exception as e:
            return f"Erro na busca web: {e}"

    @staticmethod
    def open_url(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return f"Abrindo navegador: {url}"
