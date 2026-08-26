# -*- coding: utf-8 -*-
"""CodeIndex v2 — indexador semântico leve com CACHE PERSISTENTE.

Permite que o agente manipule um codebase ARBITRARIAMENTE GRANDE dentro de um
contexto finito (→ "tokens ilimitados" na prática):

  - TF-IDF inverted index (sem dependências: sem numpy/sklearn)
  - Walk recursivo ignorando .git / __pycache__ / venv / node_modules
  - Chunking por janela de caracteres com overlap + número de linha
  - Busca por similaridade cosseno
  - CACHE PERSISTENTE: index serializado em disco, rebuild incremental
    (só re-indexa arquivos modificados desde o último build)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import re
import time
from pathlib import Path
from dataclasses import dataclass
from collections import Counter

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".c", ".h", ".hpp", ".cpp", ".cc",
    ".cs", ".go", ".rs", ".java", ".kt", ".swift", ".m", ".mm",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".html", ".htm", ".css", ".scss", ".less", ".svg",
    ".sql", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".lock", ".xml", ".proto", ".graphql", ".vue", ".svelte", ".rb",
    ".php", ".pl", ".lua", ".r", ".jl",
}

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".next", ".nuxt", "site-packages", "dist", "build",
    ".turbo", ".parcel-cache",
}

_STOP = {
    "a", "às", "o", "ó", "e", "é", "as", "os", "à", "ao", "aos",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "por",
    "para", "com", "sem", "sobre", "que", "qual", "um", "uma", "uns", "umas",
    "como", "se", "mais", "menos", "ou", "e", "não",
    "the", "an", "of", "in", "on", "at", "to", "for", "by", "with",
    "from", "and", "or", "is", "are", "this", "that", "it", "its",
    "if", "else", "return", "def", "class", "import", "from", "self",
    "true", "false", "none", "new", "use", "set", "get", "file", "path",
    "line", "code", "data", "type", "str", "int", "list", "dict", "len",
}
_TOK = re.compile(r"[a-z0-9_]+")

# Cache directory
_CACHE_DIR = Path(__file__).resolve().parent.parent / "config" / "agent_memory"


@dataclass
class Chunk:
    path: str
    line: int
    text: str
    terms: list[str]


class CodeIndex:
    """Inverted index TF-IDF minimalista com cache persistente."""

    def __init__(self, root: Path | str, chunk_size: int = 320, overlap: int = 120,
                 max_files: int = 4000, use_cache: bool = True):
        self.root = Path(root).resolve()
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_files = max_files
        self.use_cache = use_cache
        self._chunks: list[Chunk] = []
        self._doc_freq: dict[str, int] = {}
        self._built = False
        self._file_hashes: dict[str, str] = {}  # path -> hash para incremental
        self._term_sets: list[set[str]] = []  # precomputed term sets for fast scoring
        self._term_freqs: list[Counter] = []  # precomputed term frequencies

    # --------------------------------------------------------------- tokens

    def _tokens(self, text: str) -> list[str]:
        return [t for t in _TOK.findall(text.lower()) if t not in _STOP and len(t) > 1]

    def _file_hash(self, path: Path) -> str:
        """Hash rápido (tamanho + mtime) — não lê o conteúdo."""
        try:
            stat = path.stat()
            return f"{stat.st_size}:{int(stat.st_mtime)}"
        except Exception:
            return ""

    def _precompute_chunk_data(self, chunk: Chunk):
        """Precompute term set and term frequency for faster query scoring."""
        term_set = set(chunk.terms)
        term_freq = Counter(chunk.terms)
        self._term_sets.append(term_set)
        self._term_freqs.append(term_freq)

    # --------------------------------------------------------------- walk

    def _walk(self):
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                p = Path(dirpath) / f
                try:
                    if p.suffix.lower() not in CODE_EXTS:
                        continue
                    if p.stat().st_size > 300_000:
                        continue
                except Exception:
                    continue
                yield p
                self.max_files -= 1
                if self.max_files <= 0:
                    return

    # --------------------------------------------------------------- build

    def _cache_path(self) -> Path:
        """Path do cache serializado."""
        name = hashlib.md5(str(self.root).encode()).hexdigest()[:12]
        return _CACHE_DIR / f"codeindex_{name}.pkl"

    def _save_cache(self):
        """Salva index em disco para reuso rápido."""
        if not self.use_cache:
            return
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "chunks": self._chunks,
                "doc_freq": self._doc_freq,
                "file_hashes": self._file_hashes,
                "built_at": time.time(),
                "root": str(self.root),
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
            }
            self._cache_path().write_bytes(pickle.dumps(data))
        except Exception:
            pass

    def _load_cache(self) -> bool:
        """Carrega index do cache se válido."""
        if not self.use_cache:
            return False
        cp = self._cache_path()
        if not cp.exists():
            return False
        try:
            data = pickle.loads(cp.read_bytes())
            if (data.get("root") == str(self.root) and
                    data.get("chunk_size") == self.chunk_size and
                    data.get("overlap") == self.overlap):
                # verifica se algum arquivo mudou
                old_hashes = data.get("file_hashes", {})
                all_current = {}
                for p in self._walk_reduced():
                    h = self._file_hash(p)
                    all_current[str(p.relative_to(self.root).as_posix())] = h
                # se nenhum arquivo mudou, usa o cache
                changed = {k for k, v in all_current.items()
                           if old_hashes.get(k) != v}
                new_files = set(all_current.keys()) - set(old_hashes.keys())
                if not changed and not new_files:
                    self._chunks = data.get("chunks", [])
                    self._doc_freq = data.get("doc_freq", {})
                    self._file_hashes = old_hashes
                    self._built = True
                    # Rebuild precomputed data from cached chunks
                    self._term_sets = [set(ch.terms) for ch in self._chunks]
                    self._term_freqs = [Counter(ch.terms) for ch in self._chunks]
                    return True
                # rebuild incremental: remove chunks de arquivos modificados
                changed_files = changed | new_files
                self._chunks = [c for c in data.get("chunks", [])
                                if c.path not in changed_files]
                self._doc_freq = {}
                self._file_hashes = {k: v for k, v in old_hashes.items()
                                      if k not in changed_files}
                # re-indexa só os modificados
                self._build_incremental(changed_files)
                self._save_cache()
                return True
        except Exception:
            pass
        return False

    def _walk_reduced(self):
        """Walk reduzido (só para checar hashes)."""
        saved = self.max_files
        for p in self._walk():
            yield p
        self.max_files = saved

    def _build_incremental(self, changed_files: set[str]):
        """Re-indexa apenas arquivos modificados."""
        for rel_path in changed_files:
            fp = self.root / rel_path
            if not fp.exists():
                # arquivo deletado — chunks já removidos acima
                self._file_hashes.pop(rel_path, None)
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # remove chunks antigos deste arquivo
            self._chunks = [c for c in self._chunks if c.path != rel_path]
            # adiciona novos chunks
            start = 0
            while start < len(text):
                chunk_text = text[start:start + self.chunk_size]
                line_no = text.count("\n", 0, start) + 1
                terms = self._tokens(chunk_text)
                chunk = Chunk(path=rel_path, line=line_no, text=chunk_text, terms=terms)
                self._chunks.append(chunk)
                start += self.chunk_size - self.overlap
            self._file_hashes[rel_path] = self._file_hash(fp)
        # reconstrói term_sets, term_freqs e doc_freq do zero
        self._term_sets = []
        self._term_freqs = []
        for ch in self._chunks:
            self._precompute_chunk_data(ch)
        self._doc_freq = {}
        for ch in self._chunks:
            seen = set()
            for t in ch.terms:
                if t not in seen:
                    self._doc_freq[t] = self._doc_freq.get(t, 0) + 1
                    seen.add(t)

    def build(self) -> int:
        """Constrói o index — tenta cache primeiro, senão rebuild completo."""
        # tenta carregar cache
        if self._load_cache():
            return len(self._chunks)

        # rebuild completo
        self._chunks = []
        self._term_sets = []
        self._term_freqs = []
        self._doc_freq = {}
        self._file_hashes = {}
        for p in self._walk():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = p.relative_to(self.root).as_posix()
            start = 0
            while start < len(text):
                chunk_text = text[start:start + self.chunk_size]
                line_no = text.count("\n", 0, start) + 1
                terms = self._tokens(chunk_text)
                chunk = Chunk(path=rel, line=line_no, text=chunk_text, terms=terms)
                self._chunks.append(chunk)
                self._precompute_chunk_data(chunk)
                seen = set()
                for t in terms:
                    if t not in seen:
                        self._doc_freq[t] = self._doc_freq.get(t, 0) + 1
                        seen.add(t)
                start += self.chunk_size - self.overlap
            self._file_hashes[rel] = self._file_hash(p)
            self._built = True

        # salva cache
        self._save_cache()
        return len(self._chunks)

    # --------------------------------------------------------------- query

    def _idf(self, t: str) -> float:
        df = self._doc_freq.get(t, 0)
        n = len(self._chunks) or 1
        return math.log((1 + n) / (1 + df)) + 1.0

    def _chunk_norm(self, terms: list[str]) -> float:
        c = Counter(terms)
        return math.sqrt(sum((c[t] * self._idf(t)) ** 2 for t in c)) or 1.0

    def query(self, text: str, k: int = 8, max_chars: int = 2800) -> str:
        """Devolve `k` trechos mais relevantes formatados como contexto."""
        if not self._built:
            self.build()
        if not self._chunks:
            return ""
        qterms = self._tokens(text)
        if not qterms:
            return ""
        qset = set(qterms)
        qdf = Counter(qterms)
        qnorm = math.sqrt(sum((qdf[t] * self._idf(t)) ** 2 for t in qdf)) or 1.0
        scored = []
        # Fast path: use precomputed term sets for scoring
        for i, ch_term_set in enumerate(self._term_sets):
            dot = sum(self._term_freqs[i].get(t, 0) * self._idf(t) for t in qset if t in ch_term_set)
            if dot <= 0:
                continue
            scored.append((dot / (self._chunk_norm(self._chunks[i].terms) * qnorm), i))
        if not scored:
            for i, ch_term_set in enumerate(self._term_sets):
                hits = len(qset & ch_term_set)
                if hits:
                    scored.append((float(hits), i))
        scored.sort(reverse=True)
        out, used = [], 0
        for _, i in scored[:k]:
            ch = self._chunks[i]
            frag = f"# {ch.path}:{ch.line}\n{ch.text.strip()[:300]}"
            if used + len(frag) > max_chars and out:
                break
            out.append(frag)
            used += len(frag)
        return "\n\n".join(out)
