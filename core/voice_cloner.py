# -*- coding: utf-8 -*-
"""
Great Sage AI — Voice Cloner
==============================
Permite upload de audio para clonar voz customizada.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


class VoiceCloner:
    """Sistema de clonagem de voz via upload de audio."""

    _VOICES_DIR = Path(__file__).resolve().parent.parent / "config" / "custom_voices"
    _VOICES_FILE = Path(__file__).resolve().parent.parent / "config" / "custom_voices.json"

    @classmethod
    def _ensure_dirs(cls):
        cls._VOICES_DIR.mkdir(parents=True, exist_ok=True)
        if not cls._VOICES_FILE.exists():
            cls._VOICES_FILE.write_text("{}", encoding="utf-8")

    @classmethod
    def register_voice(cls, name: str, audio_path: str,
                       description: str = "") -> dict:
        """
        Registra uma voz customizada a partir de um arquivo de audio.
        O audio deve ser uma amostra de 5-30 segundos da voz desejada.
        """
        cls._ensure_dirs()
        src = Path(audio_path)
        if not src.exists():
            return {"error": "Arquivo de audio nao encontrado."}

        ext = src.suffix.lower()
        if ext not in (".wav", ".mp3", ".ogg", ".m4a", ".flac"):
            return {"error": f"Formato nao suportado: {ext}. Use WAV, MP3, OGG, M4A ou FLAC."}

        voice_id = name.lower().replace(" ", "_")
        dest = cls._VOICES_DIR / f"{voice_id}{ext}"
        shutil.copy2(str(src), str(dest))

        try:
            voices = json.loads(cls._VOICES_FILE.read_text(encoding="utf-8"))
        except Exception:
            voices = {}

        voices[voice_id] = {
            "name": name,
            "file": str(dest),
            "description": description,
            "format": ext,
            "registered": str(Path(src).stat().st_size),
        }
        cls._VOICES_FILE.write_text(json.dumps(voices, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "voice_id": voice_id, "name": name}

    @classmethod
    def list_voices(cls) -> list:
        """Lista vozes customizadas disponiveis."""
        cls._ensure_dirs()
        try:
            voices = json.loads(cls._VOICES_FILE.read_text(encoding="utf-8"))
            return [
                {"id": vid, "name": v["name"], "description": v.get("description", "")}
                for vid, v in voices.items()
            ]
        except Exception:
            return []

    @classmethod
    def get_voice_path(cls, voice_id: str) -> Optional[str]:
        """Retorna o caminho do arquivo de uma voz."""
        cls._ensure_dirs()
        try:
            voices = json.loads(cls._VOICES_FILE.read_text(encoding="utf-8"))
            if voice_id in voices:
                path = voices[voice_id].get("file")
                if path and os.path.exists(path):
                    return path
        except Exception:
            pass
        return None

    @classmethod
    def remove_voice(cls, voice_id: str) -> bool:
        """Remove uma voz customizada."""
        cls._ensure_dirs()
        try:
            voices = json.loads(cls._VOICES_FILE.read_text(encoding="utf-8"))
            if voice_id in voices:
                path = voices[voice_id].get("file")
                if path and os.path.exists(path):
                    os.remove(path)
                del voices[voice_id]
                cls._VOICES_FILE.write_text(
                    json.dumps(voices, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return True
        except Exception:
            pass
        return False

    @classmethod
    def get_status(cls) -> str:
        voices = cls.list_voices()
        if not voices:
            return "Nenhuma voz customizada registrada."
        lines = [f"Vozes customizadas ({len(voices)}):"]
        for v in voices:
            lines.append(f"  - {v['name']} ({v['id']}): {v['description'] or 'sem descricao'}")
        return "\n".join(lines)
