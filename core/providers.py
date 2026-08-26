# -*- coding: utf-8 -*-
"""Provedores de LLM GRATUITOS para a Ala de Programação (CodeDock).

Estrategia 100% GRATUITA:
  0. 9Router (local)    — proxy universal, 60+ providers, fallback automático
  1. Ollama (local)      — offline, custo zero, sem limite de quota
  2. Groq                — free tier generoso (120B models)
  3. Google Gemini       — free tier generoso (1M context)
  4. OpenRouter          — modelos gratuitos (Llama, Mistral, etc)

TODOS sao gratuitos. Nenhum gasto necessario.

Chaves (env primeiro, depois .env):
  GROQ_API_KEY           GOOGLE_API_KEY       OPENROUTER_API_KEY

  CodeProvider.complete(messages, model=None, max_tokens=None, reasoning=False) -> LLMResult
  content   : str        resposta bruta (o prompt do agente exige JSON)
  reasoning : str        raciocinio em voz alta do modelo
  model     : str        modelo que respondeu
  usage     : dict       {prompt_tokens, completion_tokens, total_tokens}
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore

SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.json"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

if not os.environ.get("OLLAMA_MODELS"):
    os.environ["OLLAMA_MODELS"] = r"F:\programação\ollama\models"

_ollama_cache: dict = {"up": False, "last_check": 0.0}
_OLLAMA_CACHE_TTL = 30.0
_token_usage: dict[str, dict] = {}


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_env() -> dict:
    env_vars = {}
    try:
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and value:
                        env_vars[key] = value
    except Exception:
        pass
    return env_vars


def _key(name: str) -> str:
    val = os.environ.get(name)
    if val and val.strip():
        return val.strip()
    env_vars = _load_env()
    if name in env_vars:
        return env_vars[name]
    s = _load_settings()
    for k in (name, name.lower(), name.upper()):
        v = s.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _track_usage(provider_name: str, usage: dict):
    if provider_name not in _token_usage:
        _token_usage[provider_name] = {
            "total_prompt": 0,
            "total_completion": 0,
            "total_requests": 0,
        }
    stats = _token_usage[provider_name]
    stats["total_requests"] += 1
    stats["total_prompt"] += usage.get("prompt_tokens", 0)
    stats["total_completion"] += usage.get("completion_tokens", 0)


def get_usage_stats() -> dict:
    return dict(_token_usage)


@dataclass
class LLMResult:
    content: str
    reasoning: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)


class CodeProvider:
    name = "base"
    quality_score: float = 0.0

    def available(self) -> bool:
        return bool(getattr(self, "api_key", None) or getattr(self, "_offline", False))

    def complete(self, messages, model=None, max_tokens=None, reasoning=False) -> LLMResult:
        raise NotImplementedError

    def _retry_request(self, func, *args, max_retries=3, **kwargs):
        last_err = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * 0.5)
        raise last_err


class OllamaProvider(CodeProvider):
    name = "ollama"
    base_url = "http://localhost:11434"
    _offline = True
    default_models = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:32b",
        "qwq",
        "deepseek-r1:8b",
        "llama3.1:8b",
    ]
    quality_score = 10.0

    def __init__(self, base_url=None, models=None):
        self.api_key = "local"
        self.base_url = (base_url or self.base_url).rstrip("/")
        if models:
            self.default_models = list(models)
        if not os.environ.get("OLLAMA_MODELS"):
            os.environ["OLLAMA_MODELS"] = r"F:\programação\ollama\models"

    def available(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return len(models) > 0
        except Exception:
            pass
        return False

    def _check_alive(self):
        now = time.time()
        if now - _ollama_cache["last_check"] < _OLLAMA_CACHE_TTL:
            return _ollama_cache["up"]
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            _ollama_cache["up"] = r.status_code == 200
        except Exception:
            _ollama_cache["up"] = False
        _ollama_cache["last_check"] = now
        return _ollama_cache["up"]

    def _list_available_models(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if r.status_code == 200:
                data = r.json()
                installed_names = [m.get("name", "") for m in data.get("models", [])]
                if not installed_names:
                    return []
                installed_base = {n.split(":")[0] for n in installed_names}
                matched = [m for m in self.default_models
                           if m.split(":")[0] in installed_base or m in installed_names]
                return matched if matched else installed_names[:1]
        except Exception:
            pass
        return []

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[ollama] requests nao instalado")
        if not self._check_alive():
            raise RuntimeError("[ollama] servidor offline")
        available = self._list_available_models()
        chain = [model] + [m for m in available if m and not model] if model else available
        last_err = None
        for m in chain:
            try:
                payload = {
                    "model": m,
                    "messages": [{"role": x["role"], "content": x["content"]} for x in messages],
                    "options": {
                        "temperature": 0.2,
                        "num_predict": max_tokens if max_tokens and max_tokens > 0 else 8192,
                    },
                    "stream": False,
                }
                if reasoning and "qwq" in m.lower():
                    payload["options"]["think"] = True
                t0 = time.perf_counter()
                r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=600)
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                msg = d.get("message", {})
                usage = {"eval_count": d.get("eval_count") or 0}
                _track_usage(self.name, usage)
                usage["latency"] = round(latency, 2)
                return LLMResult(content=msg.get("content") or "",
                                 reasoning=msg.get("thinking", "") or "",
                                 model=m, usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[ollama] falha: {last_err}")
        raise RuntimeError("[ollama] modelo nao disponivel")


class GroqProvider(CodeProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"
    default_models = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-20b",
        "groq/compound-mini",
    ]
    quality_score = 20.0

    def __init__(self, api_key, models=None):
        self.api_key = api_key
        self.default_models = list(models or self.default_models)

    def available(self):
        if not self.api_key:
            return False
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            return r.status_code == 200
        except Exception:
            return False

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[groq] requests nao instalado")
        if not self.api_key:
            raise RuntimeError("[groq] sem API key")
        chain = [model] + [m for m in self.default_models if m and not model]
        chain = [m for m in chain if m]
        last_err = None
        for m in chain:
            payload = {
                "model": m,
                "messages": messages,
                "temperature": 0.2,
                "stream": False,
            }
            if max_tokens and max_tokens > 0:
                effective_mt = min(max_tokens, 4096) if reasoning else max_tokens
                payload["max_tokens"] = effective_mt
            if reasoning and "gpt-oss" in m:
                payload["reasoning_effort"] = "high"
                payload["reasoning_format"] = "hidden"
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json=payload, timeout=120,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                _track_usage(self.name, usage)
                usage["latency"] = round(latency, 2)
                content = msg.get("content") or ""
                reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
                if not content and reasoning:
                    content = reasoning
                return LLMResult(content=content,
                                 reasoning=reasoning,
                                 model=d.get("model", m), usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[groq] todos os modelos falharam: {last_err}")
        raise RuntimeError("[groq] nenhum modelo disponivel")


class GeminiProvider(CodeProvider):
    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    default_models = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
    quality_score = 25.0

    def __init__(self, api_key, models=None):
        self.api_key = api_key
        self.default_models = list(models or self.default_models)

    def available(self):
        return bool(self.api_key)

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[gemini] requests nao instalado")
        if not self.api_key:
            raise RuntimeError("[gemini] sem API key")
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        chain = [model] + [m for m in self.default_models if m and not model]
        chain = [m for m in chain if m]
        last_err = None
        for m in chain:
            effective_mt = max(max_tokens or 8192, 512)
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": effective_mt,
                },
            }
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/models/{m}:generateContent?key={self.api_key}",
                        headers={"Content-Type": "application/json"},
                        json=payload, timeout=180,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                content = ""
                for cand in d.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if part.get("text"):
                            content += part["text"]
                usage = d.get("usageMetadata") or {}
                _track_usage(self.name, {
                    "prompt_tokens": usage.get("promptTokenCount", 0),
                    "completion_tokens": usage.get("candidatesTokenCount", 0),
                })
                usage["latency"] = round(latency, 2)
                return LLMResult(content=content, model=m, usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[gemini] todos os modelos falharam: {last_err}")
        raise RuntimeError("[gemini] nenhum modelo disponivel")


class OpenRouterProvider(CodeProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    default_models = [
        "nvidia/nemotron-3.5-lightning:free",
        "dots-studio/dots-3-note-preview:free",
        "thinkingmachines/inkling-small:free",
        "liquid/lfm-2.5-2.6b:free",
    ]
    quality_score = 30.0

    def __init__(self, api_key, models=None):
        self.api_key = api_key
        self.base_url = self.base_url
        self.default_models = list(models or self.default_models)

    def available(self):
        return bool(self.api_key)

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[openrouter] requests nao instalado")
        if not self.api_key:
            raise RuntimeError("[openrouter] sem API key")
        chain = [model] + [m for m in self.default_models if m and not model]
        chain = [m for m in chain if m]
        last_err = None
        for m in chain:
            payload = {
                "model": m,
                "messages": messages,
                "temperature": 0.2,
                "stream": False,
            }
            if max_tokens and max_tokens > 0:
                payload["max_tokens"] = max_tokens
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json",
                                 "HTTP-Referer": "https://greatsage.local",
                                 "X-Title": "GreatSage CodeDock"},
                        json=payload, timeout=120,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                _track_usage(self.name, usage)
                usage["latency"] = round(latency, 2)
                return LLMResult(content=msg.get("content") or "",
                                 model=d.get("model", m), usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[openrouter] todos os modelos falharam: {last_err}")
        raise RuntimeError("[openrouter] nenhum modelo disponivel")


_9router_cache: dict = {"up": False, "last_check": 0.0}
_9ROUTER_CACHE_TTL = 15.0


class NineRouterProvider(CodeProvider):
    """9Router — proxy local universal com 60+ providers e fallback automático.

    Roda em localhost:20128 (Next.js). Não precisa de API key —
    o 9Router gerencia as keys dos providers que você configurar no dashboard dele.
    Suporta OpenAI-compatible API, formatação automática e RTK token saver.
    """
    name = "9router"
    base_url = "http://localhost:20128/v1"
    default_models = [
        "auto",
        "kr/claude-sonnet-4.5",
        "oc/auto",
        "glm/glm-4.7",
        "vertex/gemini-3.1-pro-preview",
    ]
    quality_score = 50.0  # Highest — 9Router has auto-fallback to best available

    def __init__(self, base_url=None, models=None):
        self.api_key = "no-key-needed"
        self._offline = True
        self.base_url = (base_url or self.base_url).rstrip("/")
        if models:
            self.default_models = list(models)

    def available(self):
        now = time.time()
        if now - _9router_cache["last_check"] < _9ROUTER_CACHE_TTL:
            return _9router_cache["up"]
        try:
            r = requests.get(f"{self.base_url}/models", timeout=3.0)
            _9router_cache["up"] = r.status_code == 200
        except Exception:
            _9router_cache["up"] = False
        _9router_cache["last_check"] = now
        return _9router_cache["up"]

    def _list_remote_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/models", timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return [m for m in models if m]
        except Exception:
            pass
        return []

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[9router] requests nao instalado")
        if not self.available():
            raise RuntimeError("[9router] servidor offline (localhost:20128)")

        remote_models = self._list_remote_models()
        chain = []
        if model:
            chain.append(model)
        else:
            chain = list(self.default_models)
            if remote_models:
                for m in remote_models[:5]:
                    if m not in chain:
                        chain.append(m)

        last_err = None
        for m in chain:
            payload = {
                "model": m,
                "messages": messages,
                "temperature": 0.2,
                "stream": False,
            }
            if max_tokens and max_tokens > 0:
                payload["max_tokens"] = max_tokens
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload, timeout=180,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                _track_usage(self.name, usage)
                usage["latency"] = round(latency, 2)
                return LLMResult(content=msg.get("content") or "",
                                 reasoning=msg.get("reasoning_content") or "",
                                 model=d.get("model", m), usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[9router] todos os modelos falharam: {last_err}")
        raise RuntimeError("[9router] nenhum modelo disponivel")


# ---------------------------------------------------------------------------
# Generic OpenAI-compatible provider (used by many free providers)
# ---------------------------------------------------------------------------

class _OpenAICompatProvider(CodeProvider):
    """Base class for providers that expose an OpenAI-compatible /v1/chat/completions endpoint."""
    name = "compat"
    base_url = ""
    api_key_env = ""          # env var name for the API key
    default_models: list[str] = []
    quality_score = 15.0
    _headers_extra: dict = {} # extra headers (e.g. HTTP-Referer)

    def __init__(self, api_key: str | None = None, models: list[str] | None = None):
        self.api_key = api_key or _key(self.api_key_env)
        self.default_models = list(models or self.default_models)

    def available(self) -> bool:
        return bool(self.api_key)

    def _auth_headers(self) -> dict:
        h = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        h.update(self._headers_extra)
        return h

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError(f"[{self.name}] requests nao instalado")
        if not self.api_key:
            raise RuntimeError(f"[{self.name}] sem API key ({self.api_key_env})")
        chain = [model] + [m for m in self.default_models if m and not model]
        chain = [m for m in chain if m]
        last_err = None
        for m in chain:
            payload = {
                "model": m,
                "messages": messages,
                "temperature": 0.2,
                "stream": False,
            }
            if max_tokens and max_tokens > 0:
                payload["max_tokens"] = max_tokens
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._auth_headers(),
                        json=payload, timeout=120,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                _track_usage(self.name, usage)
                usage["latency"] = round(latency, 2)
                return LLMResult(content=msg.get("content") or "",
                                 reasoning=msg.get("reasoning_content") or "",
                                 model=d.get("model", m), usage=usage)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[{self.name}] todos os modelos falharam: {last_err}")
        raise RuntimeError(f"[{self.name}] nenhum modelo disponivel")


# ---------------------------------------------------------------------------
# Free Providers — permanently free tiers, no credit card needed
# ---------------------------------------------------------------------------

class CerebrasProvider(_OpenAICompatProvider):
    """Cerebras — free tier, ultra-fast inference, OpenAI-compatible."""
    name = "cerebras"
    base_url = "https://api.cerebras.ai/v1"
    api_key_env = "CEREBRAS_API_KEY"
    default_models = [
        "gemma-4-31b",
        "gpt-oss-120b",
    ]
    quality_score = 35.0


class SambaNovaProvider(_OpenAICompatProvider):
    """SambaNova — free tier, fast inference, OpenAI-compatible."""
    name = "sambanova"
    base_url = "https://api.sambanova.ai/v1"
    api_key_env = "SAMBANOVA_API_KEY"
    default_models = [
        "Meta-Llama-3.3-70B-Instruct",
        "DeepSeek-V3-0324",
        "QwQ-32B",
    ]
    quality_score = 33.0


class MistralProvider(_OpenAICompatProvider):
    """Mistral — free tier (La Plateforme), OpenAI-compatible."""
    name = "mistral"
    base_url = "https://api.mistral.ai/v1"
    api_key_env = "MISTRAL_API_KEY"
    default_models = [
        "mistral-small-latest",
        "mistral-medium-latest",
        "open-mixtral-8x22b",
    ]
    quality_score = 32.0


class TogetherProvider(_OpenAICompatProvider):
    """Together AI — free credits ($25), OpenAI-compatible."""
    name = "together"
    base_url = "https://api.together.xyz/v1"
    api_key_env = "TOGETHER_API_KEY"
    default_models = [
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "deepseek-ai/DeepSeek-V3",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
    ]
    quality_score = 31.0


class FireworksProvider(_OpenAICompatProvider):
    """Fireworks AI — free credits, fast inference, OpenAI-compatible."""
    name = "fireworks"
    base_url = "https://api.fireworks.ai/inference/v1"
    api_key_env = "FIREWORKS_API_KEY"
    default_models = [
        "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "accounts/fireworks/models/deepseek-r1",
        "accounts/fireworks/models/qwen-2.5-72b-instruct",
    ]
    quality_score = 28.0


class CohereProvider(CodeProvider):
    """Cohere — free tier, command models."""
    name = "cohere"
    base_url = "https://api.cohere.com/v2"
    api_key_env = "COHERE_API_KEY"
    default_models = [
        "command-r-08-2024",
        "command-r-plus-08-2024",
        "command-light",
    ]
    quality_score = 22.0

    def __init__(self, api_key, models=None):
        self.api_key = api_key
        self.default_models = list(models or self.default_models)

    def available(self):
        return bool(self.api_key)

    def complete(self, messages, model=None, max_tokens=None, reasoning=False):
        if requests is None:
            raise RuntimeError("[cohere] requests nao instalado")
        if not self.api_key:
            raise RuntimeError("[cohere] sem API key")
        chain = [model] + [m for m in self.default_models if m and not model]
        chain = [m for m in chain if m]
        last_err = None
        for m in chain:
            payload = {
                "model": m,
                "messages": messages,
            }
            try:
                t0 = time.perf_counter()
                r = self._retry_request(
                    lambda: requests.post(
                        f"{self.base_url}/chat",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json=payload, timeout=120,
                    ))
                latency = time.perf_counter() - t0
                r.raise_for_status()
                d = r.json()
                content = ""
                msg = d.get("message", {})
                for item in msg.get("content", []):
                    if item.get("type") == "text":
                        content += item.get("text", "")
                usage = d.get("usage") or {}
                _track_usage(self.name, {
                    "prompt_tokens": usage.get("billed_units", {}).get("input_tokens", 0),
                    "completion_tokens": usage.get("billed_units", {}).get("output_tokens", 0),
                })
                return LLMResult(content=content, model=m, usage={"latency": round(latency, 2)})
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise RuntimeError(f"[cohere] todos os modelos falharam: {last_err}")
        raise RuntimeError("[cohere] nenhum modelo disponivel")


class DeepSeekProvider(_OpenAICompatProvider):
    """DeepSeek — free tier (registration credits), OpenAI-compatible."""
    name = "deepseek"
    base_url = "https://api.deepseek.com/v1"
    api_key_env = "DEEPSEEK_API_KEY"
    default_models = [
        "deepseek-chat",
        "deepseek-reasoner",
    ]
    quality_score = 34.0


class NvidiaNimProvider(_OpenAICompatProvider):
    """NVIDIA NIM — free tier (40 RPM), OpenAI-compatible."""
    name = "nvidia_nim"
    base_url = "https://integrate.api.nvidia.com/v1"
    api_key_env = "NVIDIA_API_KEY"
    default_models = [
        "nvidia/llama-3.1-70b-instruct",
        "nvidia/llama-3.3-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "mistralai/mistral-7b-instruct-v0.3",
    ]
    quality_score = 36.0


class ZhipuProvider(_OpenAICompatProvider):
    """Zhipu AI (GLM-4) — free tier, OpenAI-compatible."""
    name = "zhipu"
    base_url = "https://open.bigmodel.cn/api/paas/v4"
    api_key_env = "ZHIPUAI_API_KEY"
    default_models = [
        "glm-4-flash",
        "glm-4-flashx",
        "glm-4-air",
        "glm-4-airx",
    ]
    quality_score = 35.5


class HuggingFaceProvider(_OpenAICompatProvider):
    """Hugging Face Inference — free tier, OpenAI-compatible."""
    name = "huggingface"
    base_url = "https://api-inference.huggingface.co/v1"
    api_key_env = "HUGGINGFACE_API_KEY"
    default_models = [
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "Qwen/Qwen2.5-72B-Instruct",
        "google/gemma-2-27b-it",
    ]
    quality_score = 34.5


class AI21Provider(_OpenAICompatProvider):
    """AI21 Labs — free credits ($10), OpenAI-compatible."""
    name = "ai21"
    base_url = "https://api.ai21.com/v1"
    api_key_env = "AI21_API_KEY"
    default_models = [
        "jamba-1.5-mini",
        "jamba-1.5-large",
        "jamba-instruct",
    ]
    quality_score = 33.5


class RekaProvider(_OpenAICompatProvider):
    """Reka — free tier ($10/month), OpenAI-compatible."""
    name = "reka"
    base_url = "https://api.reka.ai/v1"
    api_key_env = "REKA_API_KEY"
    default_models = [
        "reka-core-20240904",
        "reka-flash-20240904",
    ]
    quality_score = 32.5


class GitHubModelsProvider(_OpenAICompatProvider):
    """GitHub Models — free tier (GPT-4o, Grok-3, o3), OpenAI-compatible."""
    name = "github_models"
    base_url = "https://models.github.ai/inference"
    api_key_env = "GITHUB_TOKEN"
    default_models = [
        "gpt-4o-mini",
        "gpt-4o",
        "o3-mini",
    ]
    quality_score = 37.0


class AlibabaProvider(_OpenAICompatProvider):
    """Alibaba Cloud (Qwen) — free tier, OpenAI-compatible."""
    name = "alibaba"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env = "DASHSCOPE_API_KEY"
    default_models = [
        "qwen-max",
        "qwen-plus",
        "qwen-turbo",
        "qwen2.5-72b-instruct",
        "qwen2.5-32b-instruct",
        "qwen2.5-14b-instruct",
    ]
    quality_score = 34.0


class SiliconFlowProvider(_OpenAICompatProvider):
    """SiliconFlow — free tier (open-source models), OpenAI-compatible."""
    name = "siliconflow"
    base_url = "https://api.siliconflow.cn/v1"
    api_key_env = "SILICONFLOW_API_KEY"
    default_models = [
        "Qwen/Qwen2.5-7B-Instruct",
        "THUDM/glm-4-9b-chat",
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "deepseek-ai/DeepSeek-V3",
    ]
    quality_score = 30.0


class XAIProvider(_OpenAICompatProvider):
    """xAI (Grok) — $25 free credits, OpenAI-compatible."""
    name = "xai"
    base_url = "https://api.x.ai/v1"
    api_key_env = "XAI_API_KEY"
    default_models = [
        "grok-4",
        "grok-4-fast",
        "grok-3",
        "grok-3-mini",
    ]
    quality_score = 36.5


# ---------------------------------------------------------------------------
# Provider registry — all available providers
# ---------------------------------------------------------------------------

ALL_FREE_PROVIDERS = [
    # (name, ProviderClass, quality_score, env_key)
    # --- Tested & working ---
    ("openrouter",   OpenRouterProvider,     30.0, "OPENROUTER_API_KEY"),
    ("groq",         GroqProvider,           20.0, "GROQ_API_KEY"),
    ("gemini",       GeminiProvider,         25.0, "GOOGLE_API_KEY"),
    ("mistral",      MistralProvider,        32.0, "MISTRAL_API_KEY"),
    ("reka",         RekaProvider,           32.5, "REKA_API_KEY"),
    ("cohere",       CohereProvider,         22.0, "COHERE_API_KEY"),
    # --- Need credits / setup ---
    ("9router",      NineRouterProvider,     50.0, None),
    ("ollama",       OllamaProvider,         10.0, None),
    ("github_models",GitHubModelsProvider,   37.0, "GITHUB_TOKEN"),
    ("xai",          XAIProvider,            36.5, "XAI_API_KEY"),
    ("nvidia_nim",   NvidiaNimProvider,      36.0, "NVIDIA_API_KEY"),
    ("cerebras",     CerebrasProvider,       35.0, "CEREBRAS_API_KEY"),
    ("zhipu",        ZhipuProvider,          35.5, "ZHIPUAI_API_KEY"),
    ("alibaba",      AlibabaProvider,        34.0, "DASHSCOPE_API_KEY"),
    ("huggingface",  HuggingFaceProvider,    34.5, "HUGGINGFACE_API_KEY"),
    ("deepseek",     DeepSeekProvider,       34.0, "DEEPSEEK_API_KEY"),
    ("sambanova",    SambaNovaProvider,      33.0, "SAMBANOVA_API_KEY"),
    ("together",     TogetherProvider,       31.0, "TOGETHER_API_KEY"),
    ("siliconflow",  SiliconFlowProvider,    30.0, "SILICONFLOW_API_KEY"),
    ("fireworks",    FireworksProvider,      28.0, "FIREWORKS_API_KEY"),
    ("ai21",         AI21Provider,           33.5, "AI21_API_KEY"),
]


def _ollama_up():
    now = time.time()
    if now - _ollama_cache["last_check"] < _OLLAMA_CACHE_TTL:
        return _ollama_cache["up"]
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.0) as r:
            _ollama_cache["up"] = r.status == 200
    except Exception:
        _ollama_cache["up"] = False
    _ollama_cache["last_check"] = now
    return _ollama_cache["up"]


def resolve_code_provider(llm=None):
    """Resolve the best available provider from the registry."""
    for name, prov_cls, score, env_key in ALL_FREE_PROVIDERS:
        try:
            if name == "9router":
                p = prov_cls()
                if p.available():
                    return p
            elif name == "ollama":
                p = prov_cls()
                if p.available():
                    return p
            elif env_key:
                k = _key(env_key)
                if k:
                    p = prov_cls(k)
                    if p.available():
                        return p
        except Exception:
            continue
    return None


def get_provider_info():
    info = {"providers": [], "best": None, "usage": get_usage_stats()}
    all_providers = []
    for name, prov_cls, score, env_key in ALL_FREE_PROVIDERS:
        try:
            if name in ("9router", "ollama"):
                p = prov_cls()
            elif env_key:
                k = _key(env_key)
                if not k:
                    continue
                p = prov_cls(k)
            else:
                continue
            avail = p.available()
            all_providers.append((name, p, score))
            info["providers"].append({
                "name": name,
                "quality_score": score,
                "available": avail,
                "models": getattr(p, "default_models", []),
            })
        except Exception:
            continue
    if all_providers:
        info["best"] = all_providers[0][0]
    return info