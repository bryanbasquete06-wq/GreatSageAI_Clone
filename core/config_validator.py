# -*- coding: utf-8 -*-
"""Configuracao validada com Pydantic (fallback se nao instalado)."""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger("elvea.config")
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

try:
    from pydantic import BaseModel, validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

if HAS_PYDANTIC:
    class AppConfig(BaseModel):
        groq_api_key: Optional[str] = None
        openrouter_api_key: Optional[str] = None
        gemini_api_key: Optional[str] = None
        deepseek_api_key: Optional[str] = None
        elevenlabs_api_key: Optional[str] = None
        default_provider: str = "groq"
        default_model: str = "llama-3.3-70b-versatile"
        language: str = "pt-BR"
        voice: str = "pt-BR-FranciscaNeural"
        theme: str = "tensura_gold"
        wake_word_enabled: bool = True
        wake_word: str = "elívea"
        log_level: str = "INFO"
        max_history: int = 1000

        class Config:
            env_file = str(ENV_PATH)
            env_file_encoding = "utf-8-sig"

        @validator("theme")
        def validate_theme(cls, v):
            valid = ["tensura_gold", "tensura", "gold", "crimson", "matrix", "dark", "light"]
            if v not in valid:
                return "tensura_gold"
            return v

        def has_api_key(self, provider: str = None) -> bool:
            if provider:
                key = getattr(self, f"{provider}_api_key", None)
                return bool(key and len(key) > 5)
            return any([
                self.groq_api_key and len(self.groq_api_key) > 5,
                self.openrouter_api_key and len(self.openrouter_api_key) > 5,
                self.gemini_api_key and len(self.gemini_api_key) > 5,
                self.deepseek_api_key and len(self.deepseek_api_key) > 5,
            ])
else:
    class AppConfig:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def has_api_key(self, provider=None):
            return False

_config_cache = None

def load_config() -> AppConfig:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    load_dotenv(ENV_PATH, encoding="utf-8-sig")
    if HAS_PYDANTIC:
        fields = set(AppConfig.__fields__.keys())
        _config_cache = AppConfig(**{k: v for k, v in os.environ.items() if k.lower() in fields})
    else:
        _config_cache = AppConfig()
    logger.info("Configuracao carregada")
    return _config_cache
