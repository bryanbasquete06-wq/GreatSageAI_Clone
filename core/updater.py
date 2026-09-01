# -*- coding: utf-8 -*-
"""
Elívea — Auto-Updater
==============================
Verificacao automatica de atualizacoes.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional


class AutoUpdater:
    """Sistema de auto-atualizacao."""

    _VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
    _CURRENT_VERSION = "1.0.0"
    _REPO_URL = ""
    _GITHUB_API = "https://api.github.com/repos"

    @classmethod
    def get_current_version(cls) -> str:
        if cls._VERSION_FILE.exists():
            return cls._VERSION_FILE.read_text(encoding="utf-8").strip()
        return cls._CURRENT_VERSION

    @classmethod
    def check_update(cls, repo: str = None) -> dict:
        """
        Verifica se ha atualizacoes disponiveis.
        repo: "owner/repo" no GitHub
        """
        if not repo and not cls._REPO_URL:
            return {"available": False, "message": "Repositorio nao configurado."}
        repo = repo or cls._REPO_URL
        try:
            url = f"{cls._GITHUB_API}/{repo}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Elívea"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "").lstrip("v")
            current = cls.get_current_version()
            return {
                "available": latest != current,
                "current": current,
                "latest": latest,
                "name": data.get("name", ""),
                "url": data.get("html_url", ""),
                "body": data.get("body", "")[:500],
            }
        except Exception as e:
            return {"available": False, "message": f"Erro ao verificar: {e}"}

    @classmethod
    def set_version(cls, version: str):
        cls._VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls._VERSION_FILE.write_text(version, encoding="utf-8")
        cls._CURRENT_VERSION = version

    @classmethod
    def get_status(cls) -> str:
        current = cls.get_current_version()
        return f"Elívea v{current}"
