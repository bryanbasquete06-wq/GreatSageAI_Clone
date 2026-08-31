# -*- coding: utf-8 -*-
"""
Elívea — Multi-language Support
=======================================
Permite que a IA responda em varios idiomas.
"""
from __future__ import annotations

import re


class MultiLang:
    """Suporte a multiplos idiomas."""

    _LANG_MAP = {
        "pt": "portugues",
        "en": "ingles",
        "es": "espanhol",
        "fr": "frances",
        "de": "alemao",
        "it": "italiano",
        "ja": "japones",
        "zh": "chines",
        "ko": "coreano",
        "ru": "russo",
        "ar": "arabe",
    }

    _DETECT_PATTERNS = {
        "pt": r"\b(obrigado|obrigada|por favor|nao|sim|como|onde|quando|por que|voce|eu|ele|ela|nos|voces|bom dia|boa tarde|boa noite|mestre|grande sabio)\b",
        "en": r"\b(thank you|please|yes|no|how|where|when|why|you|i|he|she|we|they|good morning|good afternoon|good evening|hello|hey)\b",
        "es": r"\b(gracias|por favor|si|no|como|donde|cuando|por que|tu|yo|el|ella|nosotros|ustedes|buenos dias|buenas tardes|hola)\b",
        "fr": r"\b(merci|s'il vous plait|oui|non|comment|ou|quand|pourquoi|vous|je|il|elle|nous|bonjour|bonsoir)\b",
        "de": r"\b(danke|bitte|ja|nein|wie|wo|wann|warum|du|ich|er|sie|wir|hallo|guten morgen|guten tag)\b",
        "it": r"\b(grazie|per favore|si|no|come|dove|quando|perche|tu|io|lui|lei|noi|ciao|buongiorno|buonasera)\b",
        "ja": r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]",
        "zh": r"[\u4e00-\u9fff]",
        "ko": r"[\uac00-\ud7af]",
        "ru": r"[а-яА-ЯёЁ]",
        "ar": r"[\u0600-\u06ff]",
    }

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Detecta o idioma do texto."""
        if not text:
            return "pt"
        t = text.lower().strip()

        scores = {}
        for lang, pattern in cls._DETECT_PATTERNS.items():
            matches = re.findall(pattern, t, re.IGNORECASE)
            scores[lang] = len(matches)

        if max(scores.values(), default=0) > 0:
            return max(scores, key=scores.get)
        return "pt"

    @classmethod
    def get_language_instruction(cls, lang_code: str) -> str:
        """Retorna instrucao para o LLM responder no idioma correto."""
        lang_name = cls._LANG_MAP.get(lang_code, "portugues")
        if lang_code == "pt":
            return ""
        return (
            f"\n\nIMPORTANTE: O usuario esta escrevendo em {lang_name}. "
            f"Responda em {lang_name}, mas mantenha sua personalidade como Elívea. "
            f"Se o usuario pedir para voltar ao portugues, obedeça."
        )

    @classmethod
    def translate_response(cls, text: str, target_lang: str) -> str:
        """Traduz uma frase para o idioma alvo (basico)."""
        translations = {
            "en": {
                "Mestre": "Master",
                "Grand Sage": "Grand Sage",
                "entendido": "understood",
                "concluido": "completed",
                "sucesso": "success",
                "erro": "error",
                "aviso": "notice",
            },
            "es": {
                "Mestre": "Maestro",
                "Grand Sage": "Gran Sabio",
                "entendido": "entendido",
                "concluido": "completado",
                "sucesso": "exito",
                "erro": "error",
                "aviso": "aviso",
            },
        }
        if target_lang == "pt":
            return text
        mapping = translations.get(target_lang, {})
        result = text
        for pt_word, translated in mapping.items():
            result = result.replace(pt_word, translated)
        return result

    @classmethod
    def format_multilingual_prompt(cls, text: str, detected_lang: str) -> str:
        """Formata o prompt com instrucoes de idioma."""
        instruction = cls.get_language_instruction(detected_lang)
        return text + instruction
