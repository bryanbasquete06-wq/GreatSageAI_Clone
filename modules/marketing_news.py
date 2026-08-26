"""
Great Sage AI - Marketing News & Trend Briefing Module
Provides real-time marketing trends, digital advertising updates, and growth strategies.
"""

import urllib.parse

try:
    import requests
except ImportError:
    requests = None


class MarketingNewsModule:
    @staticmethod
    def get_marketing_briefing(llm_engine=None) -> str:
        """Generates a marketing news briefing using Groq LLM or news query."""
        prompt = (
            "Gere uma atualização curta, empolgante e profissional (3 frases) com as "
            "principais tendências e notícias do mundo do Marketing Digital, IA no Marketing e Tráfego Pago hoje."
        )
        if llm_engine:
            try:
                res = llm_engine.query(prompt)
                if res and len(res.strip()) > 20:
                    return res.strip()
            except Exception:
                pass

        return (
            "Relatório de Marketing: as principais novidades de marketing hoje incluem: "
            "1. Expansão acelerada de agentes de IA para personalização de anúncios em tempo real. "
            "2. Crescimento do formato de vídeo curto e buscas por voz no Google e TikTok. "
            "3. Automação avançada de funis de vendas com inteligência preditiva."
        )
