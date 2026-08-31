#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Agendamento e Lembretes
========================================
Sistema de lembretes e tarefas agendadas.
"""

import json
import time
import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger("elvea.scheduler")


@dataclass
class Reminder:
    """A scheduled reminder."""
    id: str
    message: str
    trigger_time: str  # ISO format
    recurring: bool = False
    interval_minutes: int = 0
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class Scheduler:
    """Manages reminders and scheduled tasks."""

    def __init__(self, data_dir: str = "memory"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.reminders_file = self.dir / "reminders.json"
        self.reminders: List[Dict] = self._load_reminders()
        self._callback: Optional[Callable] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _load_reminders(self) -> List[Dict]:
        try:
            if self.reminders_file.exists():
                return json.loads(self.reminders_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_reminders(self):
        try:
            self.reminders_file.write_text(
                json.dumps(self.reminders, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Error saving reminders: {e}")

    def set_callback(self, callback: Callable[[str], None]):
        """Set callback for when a reminder fires."""
        self._callback = callback

    def add_reminder(self, message: str, minutes: int = 60,
                     recurring: bool = False) -> str:
        """Add a new reminder."""
        trigger_time = datetime.now() + timedelta(minutes=minutes)
        reminder = {
            "id": f"r_{int(time.time())}",
            "message": message,
            "trigger_time": trigger_time.isoformat(),
            "recurring": recurring,
            "interval_minutes": minutes if recurring else 0,
            "active": True,
            "created_at": datetime.now().isoformat(),
        }
        self.reminders.append(reminder)
        self._save_reminders()

        return (f"Lembrete criado!\n"
                f"Mensagem: {message}\n"
                f"Quando: {trigger_time.strftime('%d/%m/%Y %H:%M')}\n"
                f"Recorrente: {'Sim' if recurring else 'Nao'}")

    def add_reminder_at(self, message: str, time_str: str) -> str:
        """Add a reminder at a specific time (HH:MM or YYYY-MM-DD HH:MM)."""
        try:
            now = datetime.now()
            if len(time_str) == 5:  # HH:MM
                h, m = map(int, time_str.split(":"))
                trigger = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if trigger <= now:
                    trigger += timedelta(days=1)
            else:  # YYYY-MM-DD HH:MM
                trigger = datetime.strptime(time_str, "%Y-%m-%d %H:%M")

            minutes = int((trigger - now).total_seconds() / 60)
            return self.add_reminder(message, minutes)
        except Exception as e:
            return f"Erro ao criar lembrete: {e}"

    def remove_reminder(self, reminder_id: str) -> str:
        """Remove a reminder by ID."""
        for i, r in enumerate(self.reminders):
            if r["id"] == reminder_id:
                removed = self.reminders.pop(i)
                self._save_reminders()
                return f"Lembrete removido: {removed['message']}"
        return "Lembrete nao encontrado."

    def list_reminders(self) -> str:
        """List all active reminders."""
        active = [r for r in self.reminders if r.get("active", True)]
        if not active:
            return "Nenhum lembrete ativo."

        parts = ["**Lembretes Ativos:**\n"]
        for r in active:
            trigger = r.get("trigger_time", "")
            try:
                dt = datetime.fromisoformat(trigger)
                when = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                when = trigger
            recurring = " (recorrente)" if r.get("recurring") else ""
            parts.append(f"• {r['message']} — {when}{recurring}")
            parts.append(f"  ID: `{r['id']}`")

        return "\n".join(parts)

    def check_reminders(self) -> List[str]:
        """Check for due reminders and return their messages."""
        now = datetime.now()
        fired = []

        for r in self.reminders:
            if not r.get("active", True):
                continue

            try:
                trigger = datetime.fromisoformat(r["trigger_time"])
                if now >= trigger:
                    fired.append(r["message"])

                    if r.get("recurring") and r.get("interval_minutes", 0) > 0:
                        # Reschedule
                        r["trigger_time"] = (now + timedelta(
                            minutes=r["interval_minutes"])).isoformat()
                    else:
                        # Mark as inactive
                        r["active"] = False
            except Exception:
                continue

        if fired:
            self._save_reminders()

        return fired

    def start_checker(self, interval: int = 30):
        """Start background reminder checker."""
        if self._running:
            return

        self._running = True

        def _check_loop():
            while self._running:
                try:
                    messages = self.check_reminders()
                    for msg in messages:
                        if self._callback:
                            self._callback(msg)
                        logger.info(f"Reminder fired: {msg}")
                except Exception as e:
                    logger.error(f"Reminder check error: {e}")
                time.sleep(interval)

        self._thread = threading.Thread(target=_check_loop, daemon=True)
        self._thread.start()

    def stop_checker(self):
        """Stop the background checker."""
        self._running = False

    def get_upcoming(self, count: int = 5) -> str:
        """Get upcoming reminders."""
        now = datetime.now()
        upcoming = []

        for r in self.reminders:
            if not r.get("active", True):
                continue
            try:
                trigger = datetime.fromisoformat(r["trigger_time"])
                if trigger > now:
                    upcoming.append((trigger, r))
            except Exception:
                continue

        upcoming.sort(key=lambda x: x[0])

        if not upcoming:
            return "Nenhum lembrete futuro."

        parts = ["**Proximos Lembretes:**\n"]
        for dt, r in upcoming[:count]:
            parts.append(f"• {r['message']} — {dt.strftime('%d/%m %H:%M')}")

        return "\n".join(parts)
