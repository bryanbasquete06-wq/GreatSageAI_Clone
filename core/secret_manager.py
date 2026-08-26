# -*- coding: utf-8 -*-
"""Gerenciamento seguro de secrets com encriptacao XOR. Armazenamento preferencial em F:\\GreatSageTemp."""
import os
import json
import base64
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger("greatsage.secrets")

def _resolve_secret_dir() -> Path:
    """Resolve diretório de secrets: prioriza F:\\GreatSageTemp, fallback para config."""
    candidates = []
    for env_key in ("GREAT_SAGE_TEMP", "GREATSAGE_TEMP"):
        v = os.getenv(env_key)
        if v:
            candidates.append(Path(v))
    # Primary on F disk (obrigatório per spec: tudo em F)
    candidates.append(Path("F:/GreatSageTemp"))
    candidates.append(Path("F:\\GreatSageTemp"))
    for cand in candidates:
        if cand is None:
            continue
        s = str(cand).strip()
        if not s or s in (".", "\\", "/"):
            continue
        try:
            if cand.drive:
                drive_root = Path(cand.drive + "\\")
                if not drive_root.exists():
                    continue
            cand.mkdir(parents=True, exist_ok=True)
            test = cand / ".write_test"
            try:
                test.write_text("ok", encoding="utf-8")
                test.unlink(missing_ok=True)
            except Exception:
                continue
            return cand
        except Exception:
            continue
    fallback = Path(__file__).resolve().parent.parent / "config"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return fallback

_SECRET_DIR: Path = _resolve_secret_dir()
SECRETS_PATH: Path = _SECRET_DIR / "secrets.enc"
KEY_FILE: Path = _SECRET_DIR / ".key"

# Legados para migração automática
_LEGACY_SECRETS = Path(__file__).resolve().parent.parent / "config" / "secrets.enc"
_LEGACY_KEY = Path(__file__).resolve().parent.parent / "config" / ".key"

# .env path para migrate_env_keys (fix ENV_PATH undefined bug)
ENV_PATH: Path = Path(__file__).resolve().parent.parent / ".env"

def get_secret_dir() -> Path:
    return _SECRET_DIR

class SecretManager:
    def __init__(self):
        self._key = self._load_or_create_key()
        self._secrets = self._load()

    def _load_or_create_key(self) -> bytes:
        # 1) tenta primary em F:\\GreatSageTemp\\.key
        if KEY_FILE.exists():
            try:
                return base64.b64decode(KEY_FILE.read_text(encoding="utf-8").strip())
            except Exception as e:
                logger.warning(f"Falha ao ler KEY_FILE {KEY_FILE}: {e}")
        # 2) tenta legado config/.key e migra
        if _LEGACY_KEY.exists() and _LEGACY_KEY != KEY_FILE:
            try:
                data = _LEGACY_KEY.read_text(encoding="utf-8").strip()
                # valida base64
                key = base64.b64decode(data)
                # migra para novo local
                try:
                    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
                    KEY_FILE.write_text(data, encoding="utf-8")
                    logger.info(f"Chave migrada de {_LEGACY_KEY} -> {KEY_FILE}")
                except Exception as e:
                    logger.debug(f"Falha ao migrar chave: {e}")
                return key
            except Exception as e:
                logger.warning(f"Falha ao migrar chave legada: {e}")
        # 3) cria nova em F
        key = os.urandom(32)
        try:
            KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_text(base64.b64encode(key).decode(), encoding="utf-8")
            logger.info(f"Nova chave criada em {KEY_FILE}")
        except Exception as e:
            logger.error(f"Falha ao criar chave em {KEY_FILE}: {e}")
            # fallback para legado
            try:
                _LEGACY_KEY.parent.mkdir(parents=True, exist_ok=True)
                _LEGACY_KEY.write_text(base64.b64encode(key).decode(), encoding="utf-8")
            except Exception:
                pass
        return key

    def _xor_encrypt(self, data: bytes) -> bytes:
        key_len = len(self._key)
        return bytes(b ^ self._key[i % key_len] for i, b in enumerate(data))

    def _load(self) -> dict:
        # tenta primary em F
        for p in [SECRETS_PATH, _LEGACY_SECRETS]:
            if p.exists():
                try:
                    raw = p.read_bytes()
                    if not raw:
                        continue
                    dec = self._xor_encrypt(raw).decode("utf-8")
                    data = json.loads(dec)
                    if p != SECRETS_PATH and data:
                        # migra para F
                        try:
                            self._secrets = data
                            self._save()
                            logger.info(f"Secrets migrados de {p} -> {SECRETS_PATH} ({len(data)} chaves)")
                        except Exception:
                            pass
                    return data
                except Exception as e:
                    logger.error(f"Erro ao carregar secrets de {p}: {e}")
                    continue
        return {}

    def _save(self):
        data = json.dumps(self._secrets, ensure_ascii=False).encode("utf-8")
        try:
            SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SECRETS_PATH.write_bytes(self._xor_encrypt(data))
        except Exception as e:
            logger.error(f"Erro ao salvar secrets em {SECRETS_PATH}: {e}")
            # fallback legado
            try:
                _LEGACY_SECRETS.parent.mkdir(parents=True, exist_ok=True)
                _LEGACY_SECRETS.write_bytes(self._xor_encrypt(data))
            except Exception as e2:
                logger.error(f"Falha fallback salvar secrets: {e2}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # suporta alias GOOGLE_API_KEY <-> GEMINI_API_KEY automaticamente
        v = self._secrets.get(key)
        if v is not None:
            return v
        # aliases comuns
        aliases = {
            "GEMINI_API_KEY": ["GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"],
            "GOOGLE_API_KEY": ["GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"],
            "HUGGINGFACE_API_KEY": ["HF_API_KEY", "HF_TOKEN"],
            "HF_API_KEY": ["HUGGINGFACE_API_KEY", "HF_TOKEN"],
        }
        for alt in aliases.get(key, []):
            if alt in self._secrets and self._secrets[alt]:
                return self._secrets[alt]
        return default

    def set(self, key: str, value: str):
        self._secrets[key] = value
        self._save()

    def delete(self, key: str):
        if key in self._secrets:
            del self._secrets[key]
            self._save()

    def list_keys(self) -> List[str]:
        return list(self._secrets.keys())

    def has(self, key: str) -> bool:
        return key in self._secrets and bool(self._secrets[key])

    def migrate_env_keys(self) -> int:
        """Migra chaves do .env para SecretManager (se ainda não existirem)."""
        try:
            from dotenv import load_dotenv
            if ENV_PATH.exists():
                load_dotenv(ENV_PATH, encoding="utf-8-sig", override=False)
            else:
                load_dotenv(override=False)
        except Exception:
            pass
        migrated = 0
        for key in ["GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                      "DEEPSEEK_API_KEY", "ELEVENLABS_API_KEY", "HUGGINGFACE_API_KEY", "HF_API_KEY",
                      "CEREBRAS_API_KEY", "TOGETHER_API_KEY", "COHERE_API_KEY", "MISTRAL_API_KEY",
                      "XAI_API_KEY", "GITHUB_TOKEN"]:
            val = os.environ.get(key) or os.getenv(key)
            # também tenta ler direto do .env se load_dotenv não carregou
            if not val and ENV_PATH.exists():
                try:
                    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
                        line=line.strip()
                        if line.startswith(key+"="):
                            val=line.split("=",1)[1].strip().strip("\"'")
                            break
                except Exception:
                    pass
            if val and not self.get(key):
                self.set(key, val)
                migrated += 1
                logger.info(f"Migrado {key} do .env -> SecretManager")
        return migrated

    def get_with_fallback(self, key: str, fallback_env: dict = None) -> str:
        """Helper: SecretManager primeiro, depois dict env, depois os.environ."""
        v = self.get(key)
        if v:
            return v
        if fallback_env and fallback_env.get(key):
            return fallback_env[key]
        return os.getenv(key, "") or ""

# Instância global
secrets = SecretManager()
# Tenta migrar automaticamente na importação (não falha se não houver .env)
try:
    secrets.migrate_env_keys()
except Exception:
    pass
