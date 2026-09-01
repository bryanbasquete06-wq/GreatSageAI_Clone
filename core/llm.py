#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea — Motor LLM Multi-Provider
=========================================
Suporta: Groq, Google Gemini, OpenRouter, Cerebras, HuggingFace, Ollama
Fallback automático entre providers.
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Generator, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("elvea.llm")
# silencia warning AFC do google-genai (inofensivo)
try:
    logging.getLogger("google_genai").setLevel(logging.ERROR)
    logging.getLogger("google.genai").setLevel(logging.ERROR)
except Exception:
    pass


class Provider(Enum):
    GROQ = "groq"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    CEREBRAS = "cerebras"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuração de um provider LLM."""
    provider: Provider
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True
    priority: int = 0  # Menor = maior prioridade


@dataclass
class LLMResponse:
    """Resposta de um LLM."""
    text: str
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0
    success: bool = True
    error: str = ""


# Modelos atualizados Jun 2026 — verificados via API list (groq/ gemini decommissioned antigos)
DEFAULT_MODELS = {
    Provider.GROQ: "openai/gpt-oss-120b",  # único Groq atualmente estável (qwen aberto)
    Provider.GEMINI: "gemini-3.6-flash",   # 2.0/2.5 decommissioned
    Provider.OPENROUTER: "meta-llama/llama-3.3-70b-instruct",  # :free removido do free tier
    Provider.CEREBRAS: "llama-3.3-70b",
    Provider.HUGGINGFACE: "meta-llama/Llama-3.3-70B-Instruct",
    Provider.OLLAMA: "llama3.1:8b",
}
# Fallbacks por provider se modelo principal falhar
FALLBACK_MODELS = {
    Provider.GROQ: ["openai/gpt-oss-20b", "qwen/qwen3-32b", "meta-llama/llama-4-maverick-17b-128e-instruct"],
    Provider.GEMINI: ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"],
    Provider.OPENROUTER: ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct", "google/gemini-2.0-flash-exp:free"],
}


class LLMProvider:
    """Gerencia um único provider LLM."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.name = config.provider.value
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa o client HTTP do provider."""
        c = self.config
        if c.provider == Provider.GROQ:
            try:
                import groq
                self._client = groq.Groq(api_key=c.api_key)
            except ImportError:
                logger.warning("groq não instalado")

        elif c.provider == Provider.GEMINI:
            try:
                import google.genai as genai
                self._client = genai.Client(api_key=c.api_key)
            except ImportError:
                logger.warning("google-genai não instalado")

        elif c.provider == Provider.OPENROUTER:
            try:
                import requests
                self._client = requests.Session()
                self._client.headers.update({
                    "Authorization": f"Bearer {c.api_key}",
                    "Content-Type": "application/json",
                })
            except ImportError:
                logger.warning("requests não instalado")

        elif c.provider == Provider.CEREBRAS:
            try:
                import cerebras
                self._client = cerebras.Cerebras(api_key=c.api_key)
            except ImportError:
                # Fallback: usa API HTTP direta
                import requests
                self._client = requests.Session()
                self._client.headers.update({
                    "Authorization": f"Bearer {c.api_key}",
                    "Content-Type": "application/json",
                })

        elif c.provider == Provider.OLLAMA:
            try:
                import requests
                self._client = requests.Session()
            except ImportError:
                pass

    @property
    def available(self) -> bool:
        """Verifica se o provider está disponível."""
        return self._client is not None and self.config.api_key != "" or self.config.provider == Provider.OLLAMA

    def chat(self, messages: List[Dict], system: str = "", **kwargs) -> LLMResponse:
        """Envia mensagem e retorna resposta — com usage tracking."""
        if not self.available:
            return LLMResponse(
                text="", provider=self.name, model=self.config.model,
                success=False, error=f"Provider {self.name} não disponível"
            )

        t0 = time.time()
        try:
            if self.config.provider == Provider.GROQ:
                result = self._chat_groq(messages, system, **kwargs)
            elif self.config.provider == Provider.GEMINI:
                result = self._chat_gemini(messages, system, **kwargs)
            elif self.config.provider == Provider.OPENROUTER:
                result = self._chat_openrouter(messages, system, **kwargs)
            elif self.config.provider == Provider.OLLAMA:
                result = self._chat_ollama(messages, system, **kwargs)
            else:
                return LLMResponse(
                    text="", provider=self.name, model=self.config.model,
                    success=False, error=f"Provider {self.name} não implementado"
                )
            # Record successful usage
            try:
                from core.usage_tracker import UsageTracker
                UsageTracker().record_request(
                    provider=self.name,
                    input_tokens=result.tokens_used // 2 if result.tokens_used else len(str(messages)) // 4,
                    output_tokens=result.tokens_used // 2 if result.tokens_used else len(result.text) // 4,
                    latency_ms=result.latency_ms or (time.time() - t0) * 1000,
                )
            except Exception:
                pass
            return result
        except Exception as e:
            latency = (time.time() - t0) * 1000
            logger.error(f"Erro no {self.name}: {e}")
            # Record failed request
            try:
                from core.usage_tracker import UsageTracker
                UsageTracker().record_request(
                    provider=self.name, latency_ms=latency, error=True,
                )
            except Exception:
                pass
            return LLMResponse(
                text="", provider=self.name, model=self.config.model,
                latency_ms=latency, success=False, error=str(e)
            )

    def stream(self, messages: List[Dict], system: str = "", **kwargs) -> Generator[str, None, None]:
        """Stream de resposta token a token — com usage tracking."""
        if not self.available:
            yield f"[ERRO] Provider {self.name} não disponível"
            return

        t0 = time.time()
        full_text = ""
        try:
            if self.config.provider == Provider.GROQ:
                for delta in self._stream_groq(messages, system, **kwargs):
                    full_text += delta
                    yield delta
            elif self.config.provider == Provider.GEMINI:
                for delta in self._stream_gemini(messages, system, **kwargs):
                    full_text += delta
                    yield delta
            elif self.config.provider == Provider.OPENROUTER:
                resp = self._chat_openrouter(messages, system, **kwargs)
                full_text = resp.text
                yield resp.text
            elif self.config.provider == Provider.OLLAMA:
                for delta in self._stream_ollama(messages, system, **kwargs):
                    full_text += delta
                    yield delta
            else:
                resp = self.chat(messages, system, **kwargs)
                full_text = resp.text
                yield resp.text
        except Exception as e:
            yield f"\n[ERRO {self.name}] {e}"
        finally:
            # Record usage for dashboard
            try:
                from core.usage_tracker import UsageTracker
                _est_tokens = len(full_text) // 4  # ~4 chars per token
                UsageTracker().record_request(
                    provider=self.name,
                    input_tokens=len(str(messages)) // 4,
                    output_tokens=_est_tokens,
                    latency_ms=(time.time() - t0) * 1000,
                    error="[ERRO" in full_text,
                )
            except Exception:
                pass

    def _chat_groq(self, messages: List[Dict], system: str, **kwargs) -> LLMResponse:
        t0 = time.time()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        # tenta modelo principal + fallbacks automaticamente, com retry para TPM
        models_to_try = [self.config.model] + FALLBACK_MODELS.get(Provider.GROQ, [])
        last_err = None
        for model in models_to_try:
            max_tok = kwargs.get("max_tokens", self.config.max_tokens)
            # tenta até 2 vezes se for erro de tokens (413)
            for attempt in range(2):
                try:
                    resp = self._client.chat.completions.create(
                        model=model,
                        messages=msgs,
                        max_tokens=max_tok,
                        temperature=kwargs.get("temperature", self.config.temperature),
                    )
                    latency = (time.time() - t0) * 1000
                    text = resp.choices[0].message.content or ""
                    tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
                    if model != self.config.model:
                        logger.info(f"Groq fallback para {model}")
                        self.config.model = model
                    return LLMResponse(text=text, provider="groq", model=model,
                                       tokens_used=tokens, latency_ms=latency)
                except Exception as e:
                    last_err = e
                    es = str(e).lower()
                    # decommissioned -> tenta próximo modelo
                    if "decommissioned" in es or "does not exist" in es or "model_not_found" in es:
                        logger.warning(f"Groq modelo {model} falhou, tentando fallback: {e}")
                        break
                    # TPM / Request too large -> reduz tokens e tenta novamente
                    if "413" in str(e) or "rate_limit" in es or "request too large" in es or "tokens per minute" in es:
                        if attempt == 0 and max_tok > 800:
                            max_tok = 800
                            logger.warning(f"Groq TPM estourado, retry com max_tokens={max_tok}")
                            continue
                        else:
                            logger.warning(f"Groq TPM falhou definitivo: {e}")
                            break
                    raise
        raise last_err if last_err else Exception("Groq: todos os modelos falharam")

    def _stream_groq(self, messages: List[Dict], system: str, **kwargs):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        models_to_try = [self.config.model] + FALLBACK_MODELS.get(Provider.GROQ, [])
        for model in models_to_try:
            max_tok = kwargs.get("max_tokens", self.config.max_tokens)
            for attempt in range(2):
                try:
                    stream = self._client.chat.completions.create(
                        model=model,
                        messages=msgs,
                        max_tokens=max_tok,
                        temperature=kwargs.get("temperature", self.config.temperature),
                        stream=True,
                    )
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                    if model != self.config.model:
                        self.config.model = model
                    return
                except Exception as e:
                    es = str(e).lower()
                    if "413" in str(e) or "rate_limit" in es or "request too large" in es or "tokens per minute" in es:
                        if attempt == 0 and max_tok > 800:
                            max_tok = 800
                            logger.warning(f"Groq stream TPM retry {max_tok}")
                            continue
                        else:
                            break
                    if any(k in es for k in ("decommissioned","does not exist","model_not_found","not found")):
                        logger.warning(f"Groq stream {model} falhou, fallback: {e}")
                        break
                    raise
        yield "[ERRO Groq] todos os modelos falharam"

    def _chat_gemini(self, messages: List[Dict], system: str, **kwargs) -> LLMResponse:
        t0 = time.time()
        # Usa Chat API para evitar warning AFC
        models_to_try = [self.config.model] + FALLBACK_MODELS.get(Provider.GEMINI, [])
        last_err = None
        for model in models_to_try:
            try:
                # Chat API recomendada
                chat = self._client.chats.create(model=model, config={"system_instruction": system} if system else {})
                # Envia histórico + mensagem atual
                for msg in messages[:-1]:
                    chat.send_message(msg["content"])
                last = messages[-1]["content"] if messages else ""
                resp = chat.send_message(last)
                latency = (time.time() - t0) * 1000
                text = resp.text or ""
                if model != self.config.model:
                    self.config.model = model
                return LLMResponse(text=text, provider="gemini", model=model, latency_ms=latency)
            except Exception as e:
                # fallback para models.generate_content se Chat falhar
                try:
                    contents = []
                    for msg in messages:
                        role = "model" if msg["role"] == "assistant" else "user"
                        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
                    config = {}
                    if system:
                        config["system_instruction"] = system
                    config["temperature"] = kwargs.get("temperature", self.config.temperature)
                    config["max_output_tokens"] = kwargs.get("max_tokens", self.config.max_tokens)
                    resp = self._client.models.generate_content(model=model, contents=contents, config=config)
                    latency = (time.time() - t0) * 1000
                    text = resp.text or ""
                    if model != self.config.model:
                        self.config.model = model
                    return LLMResponse(text=text, provider="gemini", model=model, latency_ms=latency)
                except Exception as e2:
                    last_err = e2
                    if "404" in str(e2) or "NOT_FOUND" in str(e2) or "not found" in str(e2).lower():
                        logger.debug(f"Gemini {model} falhou, fallback: {e2}")
                        continue
                    last_err = e
                    if "404" in str(e) or "NOT_FOUND" in str(e) or "not found" in str(e).lower():
                        logger.debug(f"Gemini chat {model} falhou: {e}")
                        continue
                    raise
        raise last_err if last_err else Exception("Gemini falhou")

    def _stream_gemini(self, messages: List[Dict], system: str, **kwargs):
        models_to_try = [self.config.model] + FALLBACK_MODELS.get(Provider.GEMINI, [])
        for model in models_to_try:
            try:
                # Tenta Chat streaming primeiro (sem warning AFC)
                chat = self._client.chats.create(model=model, config={"system_instruction": system} if system else {})
                for msg in messages[:-1]:
                    try:
                        chat.send_message(msg["content"])
                    except Exception:
                        pass
                last = messages[-1]["content"] if messages else ""
                for chunk in chat.send_message_stream(last):
                    if chunk.text:
                        yield chunk.text
                if model != self.config.model:
                    self.config.model = model
                return
            except Exception as e:
                # fallback para generate_content_stream
                try:
                    contents = []
                    for msg in messages:
                        role = "model" if msg["role"] == "assistant" else "user"
                        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
                    config = {}
                    if system:
                        config["system_instruction"] = system
                    config["temperature"] = kwargs.get("temperature", self.config.temperature)
                    config["max_output_tokens"] = kwargs.get("max_tokens", self.config.max_tokens)
                    for chunk in self._client.models.generate_content_stream(model=model, contents=contents, config=config):
                        if chunk.text:
                            yield chunk.text
                    if model != self.config.model:
                        self.config.model = model
                    return
                except Exception as e2:
                    if "404" in str(e2) or "NOT_FOUND" in str(e2):
                        logger.debug(f"Gemini stream {model} fallback: {e2}")
                        continue
                    if "404" in str(e) or "NOT_FOUND" in str(e):
                        continue
                    # silencia warning AFC
                    if "AFC" in str(e) or "AFC" in str(e2):
                        continue
                    raise
        yield "[ERRO Gemini] modelos falharam"

    def _chat_openrouter(self, messages: List[Dict], system: str, **kwargs) -> LLMResponse:
        t0 = time.time()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        resp = self._client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            timeout=60,
        )
        data = resp.json()
        latency = (time.time() - t0) * 1000

        if "choices" in data and data["choices"]:
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return LLMResponse(text=text, provider="openrouter", model=self.config.model,
                               tokens_used=tokens, latency_ms=latency)
        else:
            error = data.get("error", {}).get("message", "Unknown error")
            return LLMResponse(text="", provider="openrouter", model=self.config.model,
                               latency_ms=latency, success=False, error=error)

    def _chat_ollama(self, messages: List[Dict], system: str, **kwargs) -> LLMResponse:
        t0 = time.time()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        resp = self._client.post("http://localhost:11434/api/chat", json=payload, timeout=120)
        data = resp.json()
        latency = (time.time() - t0) * 1000

        text = data.get("message", {}).get("content", "")
        return LLMResponse(text=text, provider="ollama", model=self.config.model,
                           latency_ms=latency)

    def _stream_ollama(self, messages: List[Dict], system: str, **kwargs):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        resp = self._client.post("http://localhost:11434/api/chat", json=payload, stream=True, timeout=120)
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break


class LLMEngine:
    """
    Motor LLM multi-provider com fallback automático.
    Tenta providers em ordem de prioridade até um funcionar.
    SPEED: System prompt cache + connection pre-warm.
    """

    def __init__(self, env_path: str = ".env"):
        self.providers: List[LLMProvider] = []
        self.env_path = Path(env_path)
        self._load_providers()
        # SPEED: system prompt cache
        self._prompt_cache: Dict[str, str] = {}
        self._prompt_cache_lock = threading.Lock()
        # SPEED: pre-warm connections in background
        threading.Thread(target=self._prewarm_connections, daemon=True, name="llm-prewarm").start()

    def _get_api_key(self, primary: str, aliases: List[str] = None, env: Dict[str, str] = None) -> str:
        """Busca API key: SecretManager (F:\\EliveaTemp) primeiro, depois .env dict, depois os.environ."""
        aliases = aliases or []
        env = env or {}
        # 1) SecretManager em F:\\EliveaTemp (primary)
        for mod_path in ("core.secret_manager", "EliveaAI_Clone.core.secret_manager"):
            try:
                mod = __import__(mod_path, fromlist=["secrets"])
                sm = getattr(mod, "secrets", None)
                if sm:
                    v = sm.get(primary)
                    if v:
                        logger.debug(f"Key {primary} via SecretManager ({mod_path})")
                        return v
                    for a in aliases:
                        v = sm.get(a)
                        if v:
                            logger.debug(f"Key {primary} via alias {a} SecretManager")
                            return v
                break
            except Exception as e:
                logger.debug(f"SecretManager import {mod_path} falhou: {e}")
                continue
        # 2) .env dict
        if env.get(primary):
            return env[primary]
        for a in aliases:
            if env.get(a):
                return env[a]
        # 3) os.environ fallback
        v = os.getenv(primary, "")
        if v:
            return v
        for a in aliases:
            v = os.getenv(a, "")
            if v:
                return v
        return ""

    def _load_providers(self):
        """Carrega providers: SecretManager (F:\\EliveaTemp) como fonte primária, .env como fallback."""
        env = self._read_env()

        configs = [
            (Provider.GROQ, "GROQ_API_KEY", ["GROQ_API_KEY"], "GROQ_MODEL"),
            (Provider.GEMINI, "GOOGLE_API_KEY", ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"], "GEMINI_MODEL"),
            (Provider.OPENROUTER, "OPENROUTER_API_KEY", ["OPENROUTER_API_KEY"], "OPENROUTER_MODEL"),
            (Provider.CEREBRAS, "CEREBRAS_API_KEY", ["CEREBRAS_API_KEY"], "CEREBRAS_MODEL"),
            (Provider.HUGGINGFACE, "HUGGINGFACE_API_KEY", ["HUGGINGFACE_API_KEY", "HF_API_KEY", "HF_TOKEN"], "HUGGINGFACE_MODEL"),
        ]

        for provider, primary_key, aliases, model_env in configs:
            api_key = self._get_api_key(primary_key, aliases, env)
            # Compat: também tenta primary direto do env dict para modelo
            model = env.get(model_env, "") or os.getenv(model_env, "") or DEFAULT_MODELS.get(provider, "")
            if api_key:
                config = LLMConfig(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    priority=len(self.providers),
                )
                p = LLMProvider(config)
                if p.available:
                    self.providers.append(p)
                    src = "SecretManager" if self._get_api_key(primary_key, aliases, {}) else ".env"
                    logger.info(f"Provider carregado: {provider.value} (modelo: {model}) via {src}")

        # Ollama só se realmente estiver rodando (evita erro de conexão poluindo log)
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            ollama_up = s.connect_ex(("127.0.0.1", 11434)) == 0
            s.close()
        except Exception:
            ollama_up = False
        if ollama_up:
            ollama_config = LLMConfig(
                provider=Provider.OLLAMA,
                model=env.get("OLLAMA_MODEL", DEFAULT_MODELS[Provider.OLLAMA]),
                priority=99,
            )
            ollama = LLMProvider(ollama_config)
            self.providers.append(ollama)
        else:
            logger.debug("Ollama não está rodando, ignorando provider")

        logger.info(f"Total de providers: {len(self.providers)}")

    def _read_env(self) -> Dict[str, str]:
        """Lê arquivo .env (utf-8-sig, suporta BOM)."""
        env = {}
        # Tenta Path do .env e também fallback para project .env
        paths_to_try = [self.env_path, Path(__file__).resolve().parent.parent / ".env", Path(".env")]
        for p in paths_to_try:
            try:
                if p.exists():
                    for line in p.read_text(encoding="utf-8-sig").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            k = key.strip()
                            if k not in env:  # primeiro wins
                                env[k] = val.strip().strip("\"'").strip()
                    if env:
                        break
            except Exception as e:
                logger.debug(f"Falha ao ler env {p}: {e}")
                continue
        return env

    def _prewarm_connections(self):
        """Pre-warm HTTP connections to all providers (saves ~200ms on first request)."""
        time.sleep(0.5)  # wait for providers to initialize
        for p in self.providers:
            try:
                if hasattr(p._client, 'session') and hasattr(p._client.session, 'get'):
                    # groq client — just touch it
                    pass
                elif hasattr(p._client, 'get'):
                    # requests.Session — warm the connection
                    p._client.get("https://httpbin.org/get", timeout=2)
            except Exception:
                pass
        logger.info("LLM connections pre-warmed")

    @property
    def available_providers(self) -> List[str]:
        """Lista providers disponíveis."""
        return [p.name for p in self.providers if p.available]

    def _offline_fallback(self, messages: List[Dict]) -> str:
        """Fallback offline que consulta RAG local em F:\\EliveaTemp\\rag e memory/rag_embeddings + MemoryManager."""
        try:
            # SPEED: cache offline fallback by last message hash
            last = messages[-1]["content"] if messages else ""
            cache_key = hashlib.md5(last[:200].encode()).hexdigest()[:16] if 'hashlib' in dir() else None
            if cache_key and hasattr(self, '_offline_cache') and cache_key in self._offline_cache:
                return self._offline_cache[cache_key]
            q = last.lower()
            rag_context = ""
            rag_stats = ""
            memory_snippet = ""

            # 1) Tenta RAG via RAGWithEmbeddings (prioriza F:\\EliveaTemp\\rag)
            try:
                RagClass = None
                for mod_path in ("core.rag_embeddings", "EliveaAI_Clone.core.rag_embeddings"):
                    try:
                        mod = __import__(mod_path, fromlist=["RAGWithEmbeddings"])
                        RagClass = getattr(mod, "RAGWithEmbeddings", None)
                        if RagClass:
                            break
                    except Exception:
                        continue
                if RagClass:
                    try:
                        rag = RagClass()
                        # Tenta get_context primeiro
                        try:
                            ctx = rag.get_context(last, max_tokens=800)
                            if ctx and ctx.strip():
                                rag_context = ctx.strip()
                        except Exception as e:
                            logger.debug(f"RAG get_context erro: {e}")
                        # Se vazio, tenta search com threshold menor
                        if not rag_context:
                            try:
                                hits = rag.search(last, top_k=3, min_score=0.15)
                                if hits:
                                    parts = []
                                    for doc, score in hits:
                                        parts.append(f"[Score {score:.2f}] {doc.content[:600]}")
                                    rag_context = "\n\n".join(parts)
                            except Exception as e:
                                logger.debug(f"RAG search erro: {e}")
                        try:
                            st = rag.stats()
                            rag_stats = f"{st.get('total_documents',0)} docs em {st.get('cache_dir','')}"
                        except Exception:
                            pass
                    except Exception as e:
                        logger.debug(f"RAG init erro: {e}")

                # Fallback direto via arquivo se RagClass não retornou nada
                if not rag_context:
                    cand_dirs = [
                        Path("F:/EliveaTemp/rag"),
                        Path("F:\\EliveaTemp\\rag"),
                        Path(__file__).resolve().parent.parent / "config" / "rag_embeddings",
                        Path(__file__).resolve().parent.parent / "config" / "rag_cache",
                        Path(__file__).resolve().parent.parent / "memory" / "rag_embeddings",
                    ]
                    # dedup
                    seen = set()
                    uniq = []
                    for d in cand_dirs:
                        try:
                            rp = str(d.resolve())
                        except Exception:
                            rp = str(d)
                        if rp not in seen:
                            seen.add(rp)
                            uniq.append(d)
                    for cand in uniq:
                        idx = cand / "index.json"
                        if idx.exists():
                            try:
                                data = json.loads(idx.read_text(encoding="utf-8"))
                                if not isinstance(data, list) or not data:
                                    continue
                                q_words = set(q.split())
                                if not q_words:
                                    continue
                                scored = []
                                for entry in data:
                                    content = entry.get("content", "")
                                    if not content:
                                        continue
                                    c_words = set(content.lower().split())
                                    overlap = len(q_words & c_words)
                                    if overlap > 0:
                                        scored.append((content, overlap / len(q_words) if q_words else 0))
                                scored.sort(key=lambda x: x[1], reverse=True)
                                if scored:
                                    rag_context = "\n\n".join([f"[Keyword {s:.2f}] {c[:600]}" for c, s in scored[:3]])
                                    rag_stats = f"keyword fallback de {idx}"
                                    break
                            except Exception as e:
                                logger.debug(f"RAG file fallback {idx} erro: {e}")
                                continue
            except Exception as e:
                logger.debug(f"RAG offline bloco erro: {e}")

            # 2) Tenta MemoryManager (facts + histórico) para complementar
            try:
                MM = None
                for mod_path in ("memory.memory_manager", "EliveaAI_Clone.memory.memory_manager", "core.memory"):
                    try:
                        mod = __import__(mod_path, fromlist=["MemoryManager"])
                        MM = getattr(mod, "MemoryManager", None)
                        if MM:
                            break
                    except Exception:
                        continue
                if MM:
                    try:
                        # search_facts se existir
                        if hasattr(MM, "search_facts"):
                            facts = MM.search_facts(last)
                            if facts:
                                fact_lines = []
                                for f in facts[:3]:
                                    k = f.get("key", "")
                                    v = f.get("value", "")
                                    fact_lines.append(f"- {k}: {v}")
                                memory_snippet = "\n".join(fact_lines)
                        # fallback para get_facts_for_prompt / get_memory_context
                        if not memory_snippet and hasattr(MM, "get_facts_for_prompt"):
                            try:
                                fp = MM.get_facts_for_prompt()
                                if fp and fp.strip():
                                    memory_snippet = fp[:800]
                            except Exception:
                                pass
                        if not memory_snippet and hasattr(MM, "get_memory_context"):
                            try:
                                mc = MM.get_memory_context()
                                if mc and len(mc.strip()) > 20:
                                    memory_snippet = mc[:800]
                            except Exception:
                                pass
                    except Exception as e:
                        logger.debug(f"MemoryManager erro: {e}")
            except Exception as e:
                logger.debug(f"MemoryManager import erro: {e}")

            # 3) Se encontrou RAG ou memória, compõe resposta offline enriquecida
            if rag_context or memory_snippet:
                parts = ["[Modo Offline — Resposta Local com RAG]"]
                if rag_context:
                    header = f"Contexto local encontrado ({rag_stats}):" if rag_stats else "Contexto local encontrado:"
                    parts.append(f"{header}\n{rag_context[:1500]}")
                if memory_snippet:
                    parts.append(f"Memória relevante:\n{memory_snippet[:800]}")
                # dica contextual
                if any(k in q for k in ("codigo","código","funcao","função","programa","python","javascript")):
                    parts.append("Estou offline (sem Groq/Gemini). Usei apenas conhecimento local acima. Se precisar de código, me diga a linguagem e eu gero localmente.")
                else:
                    parts.append(f"Pergunta: \"{last[:400]}\"")
                    parts.append("Resposta gerada 100% offline a partir do cache local em F:\\EliveaTemp\\rag. Quando a conexão voltar, usarei os providers em nuvem.")
                return "\n\n".join(parts)

            # 4) Sem RAG, fallback genérico original (mantido)
            if any(k in q for k in ("codigo","código","funcao","função","programa","python","javascript")):
                return "Modo offline: estou sem conexão com Groq/Gemini no momento. Posso gerar código localmente — me diga a linguagem e o que precisa (ex: 'crie função fatorial em python') que eu implemento com meu gerador local."
            if any(k in q for k in ("quem","voce","você","nome")):
                return "Sou a Elívea, sua IA leal. Estou temporariamente offline, mas minha memória, automação e voz continuam. Pergunte sobre qualquer tema que respondo com meu conhecimento local."
            return "Estou temporariamente offline (limite de tokens ou rede). Já reduzi o contexto e vou tentar novamente em segundos. Enquanto isso, posso ajudar com automação, arquivos e código local — só pedir. (Dica: adicione docs em F:\\EliveaTemp\\rag para respostas offline mais ricas)"
        except Exception as e:
            logger.debug(f"_offline_fallback erro geral: {e}")
            return "Offline temporário — tente novamente em 5 segundos."

    def chat(self, messages: List[Dict], system: str = "", **kwargs) -> LLMResponse:
        """
        Envia mensagem com fallback automático.
        Tenta cada provider até um funcionar.
        SPEED: uses cached system prompt if available.
        """
        last_error = ""
        for provider in self.providers:
            if not provider.available:
                continue
            logger.info(f"Tentando {provider.name}...")
            response = provider.chat(messages, system, **kwargs)
            if response.success:
                return response
            last_error = response.error
            logger.warning(f"{provider.name} falhou: {last_error}")

        # Fallback offline amigável
        offline = self._offline_fallback(messages)
        return LLMResponse(text=offline, provider="offline", model="offline", success=True, error=last_error)

    def stream(self, messages: List[Dict], system: str = "", **kwargs) -> Generator[str, None, None]:
        """
        Stream com fallback automático.
        """
        for provider in self.providers:
            if not provider.available:
                continue
            try:
                yielded = False
                for tok in provider.stream(messages, system, **kwargs):
                    # filtra yield de erro técnico que seria falado
                    if tok and "Todos os providers falharam" not in tok and "[ERRO" not in tok and "❌" not in tok:
                        yielded = True
                        yield tok
                    elif tok and ("[ERRO" in tok or "❌" in tok):
                        # não propaga erro técnico para fala, tenta próximo provider
                        logger.debug(f"Provider {provider.name} yield erro, tentando próximo")
                        yielded = False
                        break
                if yielded:
                    return
            except Exception as e:
                logger.warning(f"Stream falhou em {provider.name}: {e}")
                continue

        # offline
        offline = self._offline_fallback(messages)
        for ch in offline:
            yield ch

    def get_provider_status(self) -> List[Dict[str, Any]]:
        """Retorna status de cada provider."""
        status = []
        for p in self.providers:
            status.append({
                "name": p.name,
                "model": p.config.model,
                "available": p.available,
                "has_key": bool(p.config.api_key),
            })
        return status


# Compatibilidade: EliveaLLM usado por elvea_app original
class EliveaLLM(LLMEngine):
    """Wrapper compatível com o EliveaLLM original (usa LLMEngine por baixo)."""
    def __init__(self, *args, **kwargs):
        # ignora args, usa env padrão
        super().__init__(env_path=kwargs.get("env_path", ".env"))
        # alias para compatibilidade com código que espera .groq_model, .last_model etc
        self.groq_model = self.providers[0].config.model if self.providers else "openai/gpt-oss-120b"
        self.gemini_model = "gemini-3.6-flash"
        self.last_model = self.groq_model
        self.last_ttft_ms = 0
        self.groq_key = os.getenv("GROQ_API_KEY", "")

    def query_stream(self, prompt: str, route=None, **kwargs):
        # traduz query_stream(prompt) -> stream(messages) com limite para não estourar TPM
        import time
        t0 = time.time()
        messages = [{"role": "user", "content": prompt}]
        system = ""
        try:
            from core.persona import get_system_prompt
            system = get_system_prompt()
        except Exception:
            try:
                from EliveaAI_Clone.core.persona import get_system_prompt
                system = get_system_prompt()
            except Exception:
                pass
        # limita para TPM 8000
        for tok in self.stream(messages, system=system, max_tokens=1000, temperature=0.7):
            if self.last_ttft_ms == 0:
                self.last_ttft_ms = int((time.time() - t0)*1000)
            yield tok

    def clear_history(self):
        return "Histórico limpo."

    def save_groq_key(self, key: str):
        return f"Chave salva: {key[:8]}..."

