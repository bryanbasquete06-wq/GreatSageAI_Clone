# -*- coding: utf-8 -*-
"""
Elívea — Task Scheduler
================================
Agendamento de tarefas com lembretes e automacoes.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional


class TaskScheduler:
    """Agendador de tarefas e lembretes."""

    _TASKS_FILE = Path(__file__).resolve().parent.parent / "config" / "scheduled_tasks.json"
    _tasks: list = []
    _running = False
    _thread: Optional[threading.Thread] = None
    _callbacks: dict[str, Callable] = {}

    @classmethod
    def _ensure_file(cls):
        cls._TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not cls._TASKS_FILE.exists():
            cls._TASKS_FILE.write_text("[]", encoding="utf-8")

    @classmethod
    def _load_tasks(cls) -> list:
        cls._ensure_file()
        try:
            return json.loads(cls._TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    @classmethod
    def _save_tasks(cls):
        cls._ensure_file()
        cls._TASKS_FILE.write_text(
            json.dumps(cls._tasks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def add_reminder(cls, message: str, minutes: int = 0, hours: int = 0,
                     daily_at: str = None, callback: Callable = None) -> dict:
        """
        Adiciona um lembrete.
        - minutes/hours: relativo ao momento atual
        - daily_at: horario diario no formato "HH:MM"
        """
        task = {
            "id": f"task_{int(time.time()*1000)}",
            "type": "reminder",
            "message": message,
            "created": datetime.now().isoformat(),
            "active": True,
            "fired_count": 0,
        }

        if daily_at:
            h, m = map(int, daily_at.split(":"))
            now = datetime.now()
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            task["daily_at"] = daily_at
            task["next_fire"] = target.isoformat()
        else:
            delta = timedelta(hours=hours, minutes=minutes)
            task["next_fire"] = (datetime.now() + delta).isoformat()

        cls._tasks.append(task)
        cls._save_tasks()
        if callback:
            cls._callbacks[task["id"]] = callback
        return task

    @classmethod
    def add_recurring(cls, name: str, command: str, interval_minutes: int = 60,
                      callback: Callable = None) -> dict:
        """Adiciona uma tarefa recorrente."""
        task = {
            "id": f"task_{int(time.time()*1000)}",
            "type": "recurring",
            "name": name,
            "command": command,
            "interval_minutes": interval_minutes,
            "created": datetime.now().isoformat(),
            "active": True,
            "next_fire": (datetime.now() + timedelta(minutes=interval_minutes)).isoformat(),
        }
        cls._tasks.append(task)
        cls._save_tasks()
        if callback:
            cls._callbacks[task["id"]] = callback
        return task

    @classmethod
    def add_shutdown(cls, minutes: int = 60) -> dict:
        """Agenda desligamento do PC."""
        task = {
            "id": f"task_{int(time.time()*1000)}",
            "type": "system",
            "action": "shutdown",
            "created": datetime.now().isoformat(),
            "active": True,
            "next_fire": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
        }
        cls._tasks.append(task)
        cls._save_tasks()
        return task

    @classmethod
    def add_sleep(cls, minutes: int = 60) -> dict:
        """Agenda suspensao do PC."""
        task = {
            "id": f"task_{int(time.time()*1000)}",
            "type": "system",
            "action": "sleep",
            "created": datetime.now().isoformat(),
            "active": True,
            "next_fire": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
        }
        cls._tasks.append(task)
        cls._save_tasks()
        return task

    @classmethod
    def remove_task(cls, task_id: str) -> bool:
        cls._tasks = [t for t in cls._tasks if t["id"] != task_id]
        cls._save_tasks()
        return True

    @classmethod
    def list_tasks(cls) -> list:
        return [t for t in cls._tasks if t.get("active")]

    @classmethod
    def start(cls):
        if cls._running:
            return
        cls._tasks = cls._load_tasks()
        cls._running = True
        cls._thread = threading.Thread(target=_scheduler_loop, daemon=True, name="task-scheduler")
        cls._thread.start()

    @classmethod
    def stop(cls):
        cls._running = False

    @classmethod
    def get_status(cls) -> str:
        tasks = cls.list_tasks()
        if not tasks:
            return "Nenhuma tarefa agendada."
        lines = [f"Tarefas agendadas ({len(tasks)}):"]
        for t in tasks:
            ttype = t.get("type", "unknown")
            if ttype == "reminder":
                lines.append(f"  - Lembrete: {t['message']} (dispara em {t.get('next_fire', 'N/A')})")
            elif ttype == "recurring":
                lines.append(f"  - Recorrente: {t.get('name', 'sem nome')} (a cada {t.get('interval_minutes', 60)} min)")
            elif ttype == "system":
                action = "desligar" if t.get("action") == "shutdown" else "suspender"
                lines.append(f"  - Sistema: {action} em {t.get('next_fire', 'N/A')}")
        return "\n".join(lines)


def _scheduler_loop():
    """Loop principal do agendador."""
    while TaskScheduler._running:
        now = datetime.now()
        for task in TaskScheduler._tasks[:]:
            if not task.get("active"):
                continue
            next_fire_str = task.get("next_fire")
            if not next_fire_str:
                continue
            try:
                next_fire = datetime.fromisoformat(next_fire_str)
            except Exception:
                continue

            if now >= next_fire:
                task["active"] = False
                ttype = task.get("type")
                if ttype == "reminder":
                    cb = TaskScheduler._callbacks.get(task["id"])
                    if cb:
                        cb(task.get("message", "Lembrete"))
                    else:
                        print(f"[Scheduler] Lembrete: {task.get('message', '')}")
                elif ttype == "recurring":
                    cb = TaskScheduler._callbacks.get(task["id"])
                    if cb:
                        cb(task.get("command", ""))
                    task["active"] = True
                    task["next_fire"] = (now + timedelta(minutes=task.get("interval_minutes", 60))).isoformat()
                elif ttype == "system":
                    action = task.get("action", "shutdown")
                    if action == "shutdown":
                        os.system("shutdown /s /t 30")
                    elif action == "sleep":
                        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        TaskScheduler._save_tasks()
        time.sleep(15)
