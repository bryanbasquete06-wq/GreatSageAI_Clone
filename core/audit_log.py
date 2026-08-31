# -*- coding: utf-8 -*-
"""Audit log — registra todas as acoes executadas no PC."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from enum import Enum

logger = logging.getLogger("elvea.audit")
AUDIT_DIR = Path(__file__).resolve().parent.parent / "config" / "audit"

class ActionLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    DESTRUCTIVE = "destructive"

class AuditLog:
    def __init__(self):
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self._current_file = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y%m')}.jsonl"

    def log(self, action: str, details: str = "", level: ActionLevel = ActionLevel.INFO,
            module: str = "", success: bool = True):
        entry = {
            "ts": datetime.now().isoformat(),
            "level": level.value,
            "action": action,
            "details": details,
            "module": module,
            "success": success,
        }
        try:
            with open(self._current_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Erro ao escrever audit log: {e}")

    def query(self, limit: int = 50, level: ActionLevel = None) -> List[dict]:
        results = []
        try:
            lines = self._current_file.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines):
                if not line:
                    continue
                entry = json.loads(line)
                if level and entry.get("level") != level.value:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
        except Exception:
            pass
        return results

audit = AuditLog()
