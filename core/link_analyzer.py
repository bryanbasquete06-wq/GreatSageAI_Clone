# -*- coding: utf-8 -*-
"""Analise de links/URLs — fetch, parse e resumo com LLM."""
import logging
import re
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

logger = logging.getLogger("greatsage.link")

@dataclass
class LinkAnalysis:
    url: str = ""
    title: str = ""
    description: str = ""
    content: str = ""
    links_found: List[str] = field(default_factory=list)
    images_found: List[str] = field(default_factory=list)
    summary: str = ""
    provider_used: str = ""
    raw_response: str = ""
    error: str = ""

class LinkAnalyzer:
    """Analise de URLs e paginas web."""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            try:
                from GreatSageAI_Clone.core.llm import GreatSageLLM
                self._llm = GreatSageLLM()
            except Exception:
                pass
        return self._llm

    def fetch_url(self, url: str, max_chars: int = 15000) -> Dict:
        """Busca conteudo de uma URL."""
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "application/json" in content_type:
                return {
                    "type": "json",
                    "content": resp.text[:max_chars],
                    "status": resp.status_code,
                }

            if "text/" not in content_type and "html" not in content_type:
                return {
                    "type": "binary",
                    "content_type": content_type,
                    "size": len(resp.content),
                    "status": resp.status_code,
                }

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script/style
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")

            # Extract main content
            main = soup.find("main") or soup.find("article") or soup.find("body")
            if main:
                text = main.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            text = text[:max_chars]

            # Extract links
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("http://", "https://")):
                    links.append(href)
                elif href.startswith("/"):
                    links.append(urljoin(url, href))

            # Extract images
            images = []
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if src.startswith(("http://", "https://")):
                    images.append(src)
                elif src.startswith("/"):
                    images.append(urljoin(url, src))

            return {
                "type": "html",
                "title": title,
                "description": meta_desc,
                "content": text,
                "links": links[:50],
                "images": images[:20],
                "status": resp.status_code,
                "url_final": resp.url,
            }

        except requests.exceptions.Timeout:
            return {"type": "error", "error": "Timeout ao acessar URL"}
        except requests.exceptions.ConnectionError:
            return {"type": "error", "error": "Erro de conexao"}
        except requests.exceptions.HTTPError as e:
            return {"type": "error", "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"type": "error", "error": str(e)}

    def analyze_url(self, url: str, prompt: str = None,
                    use_llm: bool = True) -> LinkAnalysis:
        """Analisa uma URL completa."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        data = self.fetch_url(url)

        if data.get("type") == "error":
            return LinkAnalysis(url=url, error=data.get("error", "Erro desconhecido"))

        result = LinkAnalysis(
            url=url,
            title=data.get("title", ""),
            description=data.get("description", ""),
            content=data.get("content", "")[:5000],
            links_found=data.get("links", []),
            images_found=data.get("images", []),
        )

        if data.get("type") == "binary":
            result.summary = f"Arquivo binario: {data.get('content_type', 'desconhecido')} ({data.get('size', 0)} bytes)"
            return result

        if data.get("type") == "json":
            result.summary = f"Resposta JSON ({len(data.get('content', ''))} chars)"
            result.content = data.get("content", "")
            return result

        if use_llm and data.get("content"):
            prompt = prompt or f"Analise esta pagina web e faca um resumo conciso. Titulo: {data.get('title', 'N/A')}"
            llm = self._get_llm()
            if llm:
                try:
                    context = f"URL: {url}\nTitulo: {data.get('title', '')}\n\nConteudo:\n{data['content'][:8000]}"
                    full_prompt = f"{prompt}\n\n{context}"
                    if hasattr(llm, 'query_stream'):
                        response = "".join(llm.query_stream(full_prompt))
                    elif hasattr(llm, 'generate'):
                        response = llm.generate(full_prompt)
                    else:
                        response = ""
                    result.summary = response
                    result.raw_response = response
                    result.provider_used = "llm"
                except Exception as e:
                    logger.error(f"Erro LLM na analise de URL: {e}")

        if not result.summary:
            # Fallback: truncar conteudo
            result.summary = data.get("content", "")[:2000]

        return result

    def analyze_text_content(self, text: str, source: str = "") -> LinkAnalysis:
        """Analisa texto extraido de uma pagina."""
        result = LinkAnalysis(url=source, content=text[:5000])
        llm = self._get_llm()
        if llm:
            try:
                prompt = f"Analise este conteudo web e faca um resumo conciso:\n\n{text[:8000]}"
                if hasattr(llm, 'query_stream'):
                    response = "".join(llm.query_stream(prompt))
                elif hasattr(llm, 'generate'):
                    response = llm.generate(prompt)
                else:
                    response = text[:2000]
                result.summary = response
                result.raw_response = response
            except Exception as e:
                logger.error(f"Erro LLM: {e}")
                result.summary = text[:2000]
        else:
            result.summary = text[:2000]
        return result

    def extract_links(self, url: str) -> List[Dict[str, str]]:
        """Extrai todos os links de uma pagina."""
        data = self.fetch_url(url, max_chars=5000)
        links = data.get("links", [])
        return [{"url": link, "domain": urlparse(link).netloc} for link in links[:100]]

    def is_url(self, text: str) -> bool:
        """Verifica se o texto contem uma URL."""
        return bool(re.search(r'https?://[^\s]+', text.strip()))

    def extract_urls(self, text: str) -> List[str]:
        """Extrai URLs de um texto."""
        return re.findall(r'https?://[^\s<>"]+', text)

analyzer = LinkAnalyzer()
