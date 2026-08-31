# -*- coding: utf-8 -*-
"""RAG melhorado com embeddings locais (sentence-transformers). Tudo em F:\\EliveaTemp\\rag"""
import logging
import json
import hashlib
import os
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger("elvea.rag")

def _resolve_rag_dir() -> Path:
    """Resolve RAG cache dir: prioriza F:\\EliveaTemp\\rag, fallback para config/rag_embeddings."""
    candidates: List[Path] = []
    # Env var override
    for env_key in ("ELIVEA_TEMP", "ELIVEA_TEMP", "ELIVEA_RAG"):
        v = os.getenv(env_key)
        if v:
            p = Path(v)
            # if env points to base temp, append rag
            if p.name.lower() != "rag":
                candidates.append(p / "rag")
            else:
                candidates.append(p)
    # Primary required location on F disk
    candidates.append(Path("F:/EliveaTemp/rag"))
    candidates.append(Path("F:\\EliveaTemp\\rag"))
    # Try each candidate if F drive exists and writable
    for cand in candidates:
        if cand is None:
            continue
        try:
            s = str(cand).strip()
            if not s or s in (".", "rag", "/rag", "\\rag"):
                continue
            # Check drive exists (Windows)
            if cand.drive:
                drive_root = Path(cand.drive + "\\")
                if not drive_root.exists():
                    continue
            cand.mkdir(parents=True, exist_ok=True)
            # test writable
            test_file = cand / ".write_test"
            try:
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink(missing_ok=True)
            except Exception:
                continue
            return cand
        except Exception:
            continue
    # Fallback legacy (project on F still, but keep as last resort)
    fallback = Path(__file__).resolve().parent.parent / "config" / "rag_embeddings"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return fallback

CACHE_DIR: Path = _resolve_rag_dir()

# Legacy dirs for migration / fallback reading (inclui memory/rag_embeddings per spec)
LEGACY_DIRS: List[Path] = [
    Path(__file__).resolve().parent.parent / "config" / "rag_embeddings",
    Path(__file__).resolve().parent.parent / "config" / "rag_cache",
    Path(__file__).resolve().parent.parent / "memory" / "rag_embeddings",
    Path("F:/EliveaTemp/rag_embeddings"),
]

def get_rag_cache_dir() -> Path:
    """Retorna diretório atual de RAG (sempre em F se disponível)."""
    return CACHE_DIR

@dataclass
class Document:
    id: str
    content: str
    metadata: Dict = None
    embedding: list = None

class RAGWithEmbeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._documents: List[Document] = []
        self._index_path = CACHE_DIR / "index.json"
        # Garante que CACHE_DIR existe e está em F
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Falha ao criar CACHE_DIR {CACHE_DIR}: {e}")
        self._load_index()

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            return True
        except ImportError:
            logger.warning("sentence-transformers nao instalado")
            return False
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return False

    def _load_index(self):
        """Carrega índice do CACHE_DIR principal, com fallback/migração de dirs legados e F:\\EliveaTemp\\rag."""
        loaded = False
        # 1) tenta primary
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                self._documents = [Document(**d) for d in data]
                if self._documents:
                    loaded = True
                    logger.debug(f"RAG carregado de {self._index_path}: {len(self._documents)} docs")
            except Exception as e:
                logger.warning(f"Falha ao carregar {self._index_path}: {e}")

        # 2) se primary vazio, tenta legados (inclui F:\\EliveaTemp\\rag se CACHE_DIR diferente, memory/rag_embeddings, etc)
        if not loaded:
            for legacy in LEGACY_DIRS:
                if legacy.resolve() == CACHE_DIR.resolve():
                    continue
                p = legacy / "index.json"
                if p.exists():
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        docs = [Document(**d) for d in data]
                        if docs:
                            self._documents = docs
                            logger.info(f"RAG migrado de legado {p} -> {self._index_path} ({len(docs)} docs)")
                            # persiste no novo local F:\\EliveaTemp\\rag
                            self._save_index()
                            loaded = True
                            break
                    except Exception as e:
                        logger.debug(f"Falha legado {p}: {e}")
                        continue

        # 3) se ainda vazio, tenta varredura direta de F:\\EliveaTemp\\rag (caso CACHE_DIR fallback)
        if not loaded:
            # tenta F explicitamente mesmo se CACHE_DIR falhou
            for cand in [Path("F:/EliveaTemp/rag"), Path("F:\\EliveaTemp\\rag")]:
                if cand.resolve() == CACHE_DIR.resolve():
                    continue
                p = cand / "index.json"
                if p.exists():
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        docs = [Document(**d) for d in data]
                        if docs:
                            self._documents = docs
                            logger.info(f"RAG carregado de F fallback {p}")
                            # garante que salva no CACHE_DIR atual
                            self._save_index()
                            break
                    except Exception:
                        continue

    def _save_index(self):
        try:
            # Garante dir em F
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = [{"id": d.id, "content": d.content, "metadata": d.metadata or {}}
                    for d in self._documents]
            self._index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.debug(f"RAG indice salvo em {self._index_path} ({len(self._documents)} docs)")
        except Exception as e:
            logger.error(f"Erro ao salvar indice em {self._index_path}: {e}")

    def add_document(self, content: str, metadata: Dict = None) -> str:
        doc_id = hashlib.md5(content.encode()).hexdigest()[:12]
        for d in self._documents:
            if d.id == doc_id:
                return doc_id
        doc = Document(id=doc_id, content=content, metadata=metadata or {})
        if self._ensure_model():
            try:
                doc.embedding = self._model.encode(content).tolist()
            except Exception as e:
                logger.error(f"Erro ao gerar embedding: {e}")
        self._documents.append(doc)
        self._save_index()
        return doc_id

    def search(self, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Tuple[Document, float]]:
        if not self._documents:
            return []
        if self._ensure_model():
            try:
                import numpy as np
                query_emb = np.array(self._model.encode(query))
                scores = []
                for doc in self._documents:
                    if doc.embedding:
                        doc_emb = np.array(doc.embedding)
                        norm_a = np.linalg.norm(query_emb)
                        norm_b = np.linalg.norm(doc_emb)
                        if norm_a > 0 and norm_b > 0:
                            score = float(np.dot(query_emb, doc_emb) / (norm_a * norm_b))
                            if score >= min_score:
                                scores.append((doc, score))
                scores.sort(key=lambda x: x[1], reverse=True)
                if scores:
                    return scores[:top_k]
            except Exception as e:
                logger.error(f"Erro na busca semantica: {e}")
        # Fallback: keyword search (funciona offline sem modelo)
        query_words = set(query.lower().split())
        if not query_words:
            return []
        scores = []
        for doc in self._documents:
            doc_words = set(doc.content.lower().split())
            overlap = len(query_words & doc_words)
            if overlap > 0:
                # score normalizado por query len, com bonus por tamanho
                scores.append((doc, overlap / len(query_words)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_context(self, query: str, max_tokens: int = 2000) -> str:
        results = self.search(query, top_k=5)
        parts, current = [], 0
        for doc, score in results:
            doc_tokens = len(doc.content) // 4
            if current + doc_tokens > max_tokens:
                break
            parts.append(f"[Score: {score:.2f}] {doc.content}")
            current += doc_tokens
        return "\n\n".join(parts)

    def clear(self):
        self._documents.clear()
        self._save_index()

    def stats(self) -> Dict:
        return {
            "total_documents": len(self._documents),
            "with_embeddings": sum(1 for d in self._documents if d.embedding),
            "model": self.model_name,
            "model_loaded": self._model is not None,
            "cache_dir": str(CACHE_DIR),
            "index_path": str(self._index_path),
        }

# Instância global opcional para compatibilidade
rag = RAGWithEmbeddings()
