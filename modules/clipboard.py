# -*- coding: utf-8 -*-
"""
Great Sage AI — Clipboard Awareness
====================================
Detecta o que o usuario copiou e contextualiza automaticamente.
"""
from __future__ import annotations

import hashlib
import time
import threading
from typing import Optional


class ClipboardMonitor:
    """Monitora o clipboard em background e detecta mudancas."""

    def __init__(self):
        self._last_content = ""
        self._last_hash = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.on_change = None  # callback(content: str)
        self._interval = 1.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="clipboard-monitor")
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                content = self._read_clipboard()
                h = hashlib.md5(content.encode()).hexdigest()
                if h != self._last_hash and content.strip():
                    self._last_hash = h
                    self._last_content = content
                    if self.on_change:
                        self.on_change(content)
            except Exception:
                pass
            time.sleep(self._interval)

    @staticmethod
    def _read_clipboard() -> str:
        try:
            return ClipboardMonitor._read_clipboard_fallback()
        except Exception:
            return ""

    @staticmethod
    def _read_clipboard_win32() -> str:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            if not user32.OpenClipboard(0):
                return ""
            try:
                if user32.IsClipboardFormatAvailable(13):
                    handle = user32.GetClipboardData(13)
                    if handle:
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            try:
                                text = ctypes.c_wchar_p(ptr).value
                                return text or ""
                            finally:
                                kernel32.GlobalUnlock(handle)
                return ""
            finally:
                user32.CloseClipboard()
        except Exception:
            return ""

    @staticmethod
    def _read_clipboard_fallback() -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    @classmethod
    def get_content(cls) -> str:
        """Le o clipboard atual uma vez."""
        return cls._read_clipboard()

    @classmethod
    def is_code(cls, text: str = None) -> bool:
        """Detecta se o conteudo do clipboard parece codigo."""
        if text is None:
            text = cls.get_content()
        if not text or len(text) < 5:
            return False
        code_indicators = [
            "def ", "class ", "import ", "function ", "const ", "let ", "var ",
            "if (", "for (", "while (", "return ", "print(", "console.log",
            "#include", "public ", "private ", "void ", "int ", "string ",
            "SELECT ", "FROM ", "WHERE ", "CREATE TABLE",
            "<div", "<html", "<script", "<style",
            "SELECT ", "FROM ", "WHERE ",
        ]
        return any(ind in text for ind in code_indicators)

    @classmethod
    def is_error(cls, text: str = None) -> bool:
        """Detecta se o conteudo parece uma mensagem de erro."""
        if text is None:
            text = cls.get_content()
        if not text:
            return False
        error_indicators = [
            "error", "erro", "exception", "traceback", "failed", "falhou",
            "cannot", "nao pode", "undefined", "null", "none", "NaN",
            "stack trace", "line ", "column ", "syntaxerror", "typeerror",
            "runtimeerror", "importerror", "file not found",
        ]
        t = text.lower()
        return any(ind in t for ind in error_indicators)

    @classmethod
    def analyze(cls) -> dict:
        """Analisa o clipboard e retorna contexto."""
        content = cls.get_content()
        if not content:
            return {"empty": True, "content": "", "type": "empty"}

        result = {
            "empty": False,
            "content": content[:2000],
            "length": len(content),
            "type": "text",
            "language": None,
            "is_error": False,
        }

        if cls.is_code(content):
            result["type"] = "code"
            result["language"] = cls._detect_language(content)
        elif cls.is_error(content):
            result["type"] = "error"
            result["is_error"] = True

        return result

    @staticmethod
    def _detect_language(text: str) -> str:
        indicators = {
            "python": ["def ", "import ", "print(", "class ", "__init__", "self."],
            "javascript": ["function ", "const ", "let ", "var ", "console.log", "=>" ],
            "typescript": ["interface ", "type ", ": string", ": number", ": any"],
            "html": ["<div", "<html", "<body", "<head"],
            "css": ["{", "}", "px", "rem", "flex", "grid"],
            "sql": ["SELECT", "FROM", "WHERE", "INSERT", "CREATE TABLE"],
            "powershell": ["Get-", "Set-", "New-", "Remove-", "$"],
            "batch": ["@echo", "echo ", "pause", "cls", "if exist"],
        }
        t = text.lower()
        scores = {}
        for lang, keywords in indicators.items():
            scores[lang] = sum(1 for kw in keywords if kw.lower() in t)
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "unknown"
