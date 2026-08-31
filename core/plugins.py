#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Sistema de Plugins
===================================
Plugins sob demanda: Calculadora, Conversor Moedas, QR Code, Tradutor, Resumidor.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("elvea.plugins")


@dataclass
class PluginResult:
    """Resultado de um plugin."""
    success: bool
    output: str
    plugin_name: str
    icon: str = ""


class Plugin:
    """Base class for plugins."""

    name: str = ""
    description: str = ""
    icon: str = ""
    keywords: List[str] = []

    def execute(self, query: str) -> PluginResult:
        raise NotImplementedError


# ═══ CALCULATOR PLUGIN ═══════════════════════════════════════════════

class CalculatorPlugin(Plugin):
    name = "Calculadora"
    description = "Calcula expressoes matematicas complexas"
    icon = "🔢"
    keywords = ["calcule", "calcular", "quanto e", "quanto da", "math", "calculate"]

    def execute(self, query: str) -> PluginResult:
        try:
            # Extract math expression
            expr = query.lower()
            for kw in self.keywords:
                expr = expr.replace(kw, "")
            expr = expr.strip()

            # Replace common patterns
            expr = expr.replace("x", "*").replace("×", "*")
            expr = expr.replace("dividido por", "/").replace("/", "/")
            expr = expr.replace("elevado a", "**").replace("elevado ao", "**")
            expr = expr.replace("raiz quadrada de", "(__import__('math').sqrt")
            expr = expr.replace("raiz", "(__import__('math').sqrt")
            expr = expr.replace("pi", str(__import__('math').pi))
            expr = expr.replace("euler", str(__import__('math').e))

            # Safe eval
            allowed = set("0123456789+-*/.() e")
            if not all(c in allowed for c in expr.replace(" ", "")):
                return PluginResult(False, "Expressao invalida", self.name, self.icon)

            result = eval(expr, {"__builtins__": {}}, {
                "sqrt": __import__('math').sqrt,
                "pi": __import__('math').pi,
                "e": __import__('math').e,
                "abs": abs,
                "round": round,
            })

            return PluginResult(True, f"{expr} = **{result}**", self.name, self.icon)
        except Exception as e:
            return PluginResult(False, f"Erro ao calcular: {e}", self.name, self.icon)


# ═══ CURRENCY PLUGIN ═══════════════════════════════════════════════

class CurrencyPlugin(Plugin):
    name = "Conversor de Moedas"
    description = "Converte entre moedas com cotacao em tempo real"
    icon = "💱"
    keywords = ["cotacao", "cambio", "converte", "dolar", "euro", "real"]

    # Fallback rates (USD)
    FALLBACK_RATES = {
        "USD": 1.0, "BRL": 5.05, "EUR": 0.92, "GBP": 0.79,
        "JPY": 149.5, "CNY": 7.24, "ARS": 350.0, "BTC": 0.000015,
    }

    def execute(self, query: str) -> PluginResult:
        try:
            # Try to get real rates
            rates = self._get_live_rates()
            if not rates:
                rates = self.FALLBACK_RATES

            # Parse query: "100 dolares em reais"
            query_lower = query.lower()

            # Extract amount
            amount_match = re.search(r'(\d+(?:\.\d+)?)', query_lower)
            amount = float(amount_match.group(1)) if amount_match else 1.0

            # Detect currencies
            from_cur = "USD"
            to_cur = "BRL"

            if "real" in query_lower or "brl" in query_lower:
                if "em real" in query_lower or "para real" in query_lower:
                    to_cur = "BRL"
                else:
                    from_cur = "BRL"
            if "dolar" in query_lower or "usd" in query_lower:
                if "em dolar" in query_lower or "para dolar" in query_lower:
                    to_cur = "USD"
                else:
                    from_cur = "USD"
            if "euro" in query_lower or "eur" in query_lower:
                if "em euro" in query_lower or "para euro" in query_lower:
                    to_cur = "EUR"
                else:
                    from_cur = "EUR"
            if "libra" in query_lower or "gbp" in query_lower:
                to_cur = "GBP" if "em libra" in query_lower else from_cur
            if "iene" in query_lower or "jpy" in query_lower:
                to_cur = "JPY" if "em iene" in query_lower else from_cur
            if "bitcoin" in query_lower or "btc" in query_lower:
                to_cur = "BTC" if "em bitcoin" in query_lower else from_cur

            # Convert
            usd_amount = amount / rates.get(from_cur, 1.0)
            result = usd_amount * rates.get(to_cur, 1.0)

            rate = rates.get(to_cur, 1.0) / rates.get(from_cur, 1.0)

            return PluginResult(
                True,
                f"**{amount:.2f} {from_cur}** = **{result:.2f} {to_cur}**\n\n"
                f"Taxa: 1 {from_cur} = {rate:.4f} {to_cur}\n"
                f"Fonte: {'API em tempo real' if self._get_live_rates() else 'Taxas de fallback'}",
                self.name, self.icon
            )
        except Exception as e:
            return PluginResult(False, f"Erro na conversao: {e}", self.name, self.icon)

    def _get_live_rates(self) -> Optional[Dict]:
        try:
            import requests
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            data = resp.json()
            if data.get("result") == "success":
                return data.get("rates", {})
        except Exception:
            pass
        return None


# ═══ QR CODE PLUGIN ═══════════════════════════════════════════════

class QRCodePlugin(Plugin):
    name = "Gerador QR Code"
    description = "Gera QR Code para qualquer texto ou URL"
    icon = "📱"
    keywords = ["qr code", "qrcode", "codigo qr", "gerar qr"]

    def execute(self, query: str) -> PluginResult:
        try:
            # Extract content
            content = query.lower()
            for kw in self.keywords:
                content = content.replace(kw, "")
            content = content.strip()
            if not content:
                content = "https://github.com"

            # Generate QR code
            try:
                import qrcode
                from io import BytesIO

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(content)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                # Save to temp file
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                img.save(tmp.name)
                tmp.close()

                return PluginResult(
                    True,
                    f"QR Code gerado para: **{content[:50]}**\n"
                    f"Salvo em: `{tmp.name}`\n\n"
                    f"Para criar manualmente: use `qrcode.make('{content}')`",
                    self.name, self.icon
                )
            except ImportError:
                # Fallback: generate SVG-like text
                return PluginResult(
                    True,
                    f"QR Code para: **{content[:50]}**\n\n"
                    f"Instale `pip install qrcode[pil]` para gerar imagem.\n"
                    f"Ou use: https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={content}",
                    self.name, self.icon
                )
        except Exception as e:
            return PluginResult(False, f"Erro ao gerar QR: {e}", self.name, self.icon)


# ═══ TRANSLATOR PLUGIN ═══════════════════════════════════════════════

class TranslatorPlugin(Plugin):
    name = "Tradutor"
    description = "Traduz textos entre idiomas"
    icon = "🌍"
    keywords = ["traduza", "traduzir", "translate", "em ingles", "em espanhol", "em frances"]

    def execute(self, query: str) -> PluginResult:
        try:
            # Detect target language
            query_lower = query.lower()
            target_lang = "en"
            lang_name = "ingles"

            if "espanhol" in query_lower or "espanol" in query_lower:
                target_lang = "es"
                lang_name = "espanhol"
            elif "frances" in query_lower or "francais" in query_lower:
                target_lang = "fr"
                lang_name = "frances"
            elif "alemao" in query_lower or "deutsch" in query_lower:
                target_lang = "de"
                lang_name = "alemao"
            elif "italiano" in query_lower:
                target_lang = "it"
                lang_name = "italiano"
            elif "japones" in query_lower:
                target_lang = "ja"
                lang_name = "japones"
            elif "chines" in query_lower:
                target_lang = "zh"
                lang_name = "chines"
            elif "russo" in query_lower:
                target_lang = "ru"
                lang_name = "russo"
            elif "portugues" in query_lower:
                target_lang = "pt"
                lang_name = "portugues"

            # Extract text to translate
            text = query
            for pattern in [r"traduza\s+", r"traduzir\s+", r"translate\s+",
                          r"em\s+\w+\s+:", r"para\s+\w+\s+:"]:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text = text.strip()

            if not text:
                return PluginResult(False, "Forneça o texto para traduzir.", self.name, self.icon)

            # Try googletrans
            try:
                from googletrans import Translator
                translator = Translator()
                result = translator.translate(text, dest=target_lang)
                return PluginResult(
                    True,
                    f"**Traducao ({lang_name}):**\n\n{result.text}\n\n"
                    f"Original: {text}\nIdioma: {result.src} → {target_lang}",
                    self.name, self.icon
                )
            except ImportError:
                pass

            # Try deep-translator
            try:
                from deep_translator import GoogleTranslator
                result = GoogleTranslator(source='auto', target=target_lang).translate(text)
                return PluginResult(
                    True,
                    f"**Traducao ({lang_name}):**\n\n{result}\n\n"
                    f"Original: {text}",
                    self.name, self.icon
                )
            except ImportError:
                pass

            return PluginResult(
                True,
                f"Para traduzir para {lang_name}, instale:\n"
                f"`pip install deep-translator` ou `pip install googletrans==4.0.0-rc1`\n\n"
                f"Texto original: {text}",
                self.name, self.icon
            )
        except Exception as e:
            return PluginResult(False, f"Erro ao traduzir: {e}", self.name, self.icon)


# ═══ SUMMARIZER PLUGIN ═══════════════════════════════════════════════

class SummarizerPlugin(Plugin):
    name = "Resumidor"
    description = "Resume textos longos em pontos-chave"
    icon = "📝"
    keywords = ["resuma", "resumir", "summarize", "resumo de", "pontos principais"]

    def execute(self, query: str) -> PluginResult:
        try:
            # Extract text
            text = query
            for kw in self.keywords:
                text = text.replace(kw, "")
            text = text.strip()

            if len(text) < 50:
                return PluginResult(
                    False,
                    "Forneça um texto mais longo para resumir (minimo 50 caracteres).",
                    self.name, self.icon
                )

            # Simple extractive summary
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            if not sentences:
                return PluginResult(False, "Nao consegui extrair frases do texto.", self.name, self.icon)

            # Score sentences by position and length
            scored = []
            for i, s in enumerate(sentences):
                score = 0
                # First and last sentences are important
                if i == 0:
                    score += 3
                if i == len(sentences) - 1:
                    score += 2
                # Longer sentences tend to be more informative
                score += min(len(s) / 50, 2)
                # Keywords boost
                keywords = ["importante", "principal", "essencial", "fundamental",
                          "primeiro", "segundo", "terceiro", "conclui", "resulta"]
                for kw in keywords:
                    if kw in s.lower():
                        score += 1
                scored.append((score, s))

            # Take top sentences
            scored.sort(reverse=True)
            top_sentences = [s for _, s in scored[:3]]

            summary = ". ".join(top_sentences) + "."

            return PluginResult(
                True,
                f"**Resumo:**\n\n{summary}\n\n"
                f"(*{len(sentences)} frases originais → {len(top_sentences)} no resumo*)",
                self.name, self.icon
            )
        except Exception as e:
            return PluginResult(False, f"Erro ao resumir: {e}", self.name, self.icon)


# ═══ PLUGIN MANAGER ═══════════════════════════════════════════════

class PluginManager:
    """Manages and dispatches to plugins."""

    def __init__(self):
        self.plugins: List[Plugin] = [
            CalculatorPlugin(),
            CurrencyPlugin(),
            QRCodePlugin(),
            TranslatorPlugin(),
            SummarizerPlugin(),
        ]

    def detect_plugin(self, query: str) -> Optional[Plugin]:
        """Detect which plugin should handle this query."""
        query_lower = query.lower()
        for plugin in self.plugins:
            for kw in plugin.keywords:
                if kw in query_lower:
                    return plugin
        return None

    def execute(self, query: str) -> Optional[PluginResult]:
        """Execute the appropriate plugin for a query."""
        plugin = self.detect_plugin(query)
        if plugin:
            logger.info(f"Plugin detected: {plugin.name}")
            return plugin.execute(query)
        return None

    def list_plugins(self) -> str:
        """List all available plugins."""
        parts = ["**Plugins Disponiveis:**\n"]
        for p in self.plugins:
            parts.append(f"{p.icon} **{p.name}** — {p.description}")
            parts.append(f"   Palavras-chave: {', '.join(p.keywords[:3])}...")
        return "\n".join(parts)
