# -*- coding: utf-8 -*-
"""
Elívea — Config Manager (Export/Import)
================================================
Backup e restauracao de configuracoes do usuario.
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Gerencia export/import de configuracoes."""

    _CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
    _EXPORT_DIR = Path(__file__).resolve().parent.parent / "backups"

    @classmethod
    def _ensure_dirs(cls):
        cls._EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def export_config(cls, name: str = None) -> str:
        """
        Exporta todas as configuracoes para um arquivo .zip.
        Retorna o caminho do arquivo criado.
        """
        cls._ensure_dirs()
        if not name:
            name = f"gs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        zip_path = cls._EXPORT_DIR / f"{name}.zip"
        files_to_backup = [
            "settings.json",
            "user_memory.json",
            "emotional_memory.json",
            "scheduled_tasks.json",
            "plugins.json",
            "learning_data.json",
            "app_shortcuts.json",
            "custom_voices.json",
            "code_dock.json",
        ]

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in files_to_backup:
                fpath = cls._CONFIG_DIR / fname
                if fpath.exists():
                    zf.write(str(fpath), fname)
            zf.writestr("export_info.json", json.dumps({
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "name": name,
            }, indent=2))

        return str(zip_path)

    @classmethod
    def import_config(cls, zip_path: str, overwrite: bool = False) -> dict:
        """
        Importa configuracoes de um arquivo .zip.
        Retorna resultado da operacao.
        """
        if not os.path.exists(zip_path):
            return {"error": "Arquivo nao encontrado."}

        restored = []
        skipped = []
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if member == "export_info.json":
                        continue
                    target = cls._CONFIG_DIR / member
                    if target.exists() and not overwrite:
                        skipped.append(member)
                        continue
                    with zf.open(member) as src:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(str(target), "wb") as dst:
                            dst.write(src.read())
                    restored.append(member)
            return {"restored": restored, "skipped": skipped}
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def list_backups(cls) -> list:
        """Lista backups disponiveis."""
        cls._ensure_dirs()
        backups = []
        for f in cls._EXPORT_DIR.glob("gs_backup_*.zip"):
            size = f.stat().st_size
            backups.append({
                "name": f.stem,
                "path": str(f),
                "size_kb": round(size / 1024, 1),
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return sorted(backups, key=lambda x: x["created"], reverse=True)

    @classmethod
    def delete_backup(cls, name: str) -> bool:
        """Deleta um backup."""
        backup = cls._EXPORT_DIR / f"{name}.zip"
        if backup.exists():
            backup.unlink()
            return True
        return False

    @classmethod
    def get_status(cls) -> str:
        backups = cls.list_backups()
        if not backups:
            return "Nenhum backup disponivel."
        lines = [f"Backups disponiveis ({len(backups)}):"]
        for b in backups[:5]:
            lines.append(f"  - {b['name']} ({b['size_kb']} KB, {b['created'][:10]})")
        return "\n".join(lines)
