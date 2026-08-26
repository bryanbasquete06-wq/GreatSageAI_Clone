"""
Great Sage AI - Daily Productivity Module
Manages reminders, quick notes, timers, date/time queries, and daily tasks for the user.
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from pathlib import Path


class ProductivityModule:
    NOTES_FILE = Path(__file__).resolve().parent.parent / "config" / "notes.json"
    _lock = threading.Lock()

    @classmethod
    def get_current_datetime(cls) -> str:
        """Returns formatted current date, time, and day of week."""
        now = datetime.now()
        weekdays = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        day_str = weekdays[now.weekday()]
        return f"[Aviso] Hoje é {day_str}, {now.strftime('%d/%m/%Y')}. Horário atual: {now.strftime('%H:%M:%S')}."

    @classmethod
    def save_note(cls, text: str) -> str:
        """Saves a quick note to persistent JSON storage."""
        cls.NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with cls._lock:
            notes = []
            if cls.NOTES_FILE.exists():
                try:
                    notes = json.loads(cls.NOTES_FILE.read_text(encoding="utf-8"))
                except Exception:
                    notes = []

            note_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "content": text.strip()
            }
            notes.append(note_entry)
            cls.NOTES_FILE.write_text(json.dumps(notes, indent=4, ensure_ascii=False), encoding="utf-8")
        return f"[Ação] Nota salva com sucesso: '{text.strip()}'"

    @classmethod
    def list_notes(cls) -> str:
        """Lists all saved quick notes."""
        if not cls.NOTES_FILE.exists():
            return "[Aviso] Nenhuma nota salva encontrada."
        with cls._lock:
            try:
                notes = json.loads(cls.NOTES_FILE.read_text(encoding="utf-8"))
                if not notes:
                    return "[Aviso] Lista de notas está vazia."
                lines = ["[Relatório de Notas Salvas]"]
                for i, n in enumerate(notes[-10:], 1):
                    lines.append(f" {i}. [{n['timestamp']}] {n['content']}")
                return "\n".join(lines)
            except Exception as e:
                return f"[Erro] Falha ao ler notas: {e}"

    @classmethod
    def set_timer_reminder(cls, minutes: float, message: str, callback_speak=None) -> str:
        """Schedules an asynchronous timer reminder."""
        sec = max(1.0, minutes * 60.0)

        def _worker():
            time.sleep(sec)
            alert_msg = f"Aviso! Lembrete do Grande Sábio: {message}"
            print(f"\n {alert_msg}\n")
            if callback_speak:
                callback_speak(alert_msg)

        threading.Thread(target=_worker, daemon=True).start()
        return f"[Ação] Lembrete agendado para daqui a {minutes} minuto(s): '{message}'"
