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
    """Append-only audit log with hash chain for tamper detection."""

    def __init__(self):
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self._current_file = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y%m')}.jsonl"
        self._prev_hash = self._compute_chain_hash()

    def _compute_chain_hash(self) -> str:
        """Compute hash of all existing entries for chain integrity."""
        import hashlib
        h = hashlib.sha256()
        try:
            for line in self._current_file.read_text(encoding="utf-8").strip().split("\n"):
                if line:
                    h.update(line.encode("utf-8"))
        except FileNotFoundError:
            pass
        return h.hexdigest()[:16]

    def log(self, action: str, details: str = "", level: ActionLevel = ActionLevel.INFO,
            module: str = "", success: bool = True):
        import hashlib
        entry = {
            "ts": datetime.now().isoformat(),
            "level": level.value,
            "action": action,
            "details": details,
            "module": module,
            "success": success,
            "prev_hash": self._prev_hash,
        }
        line = json.dumps(entry, ensure_ascii=False)
        # Compute hash of this entry for chain
        entry_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]
        entry["hash"] = entry_hash
        line_with_hash = json.dumps(entry, ensure_ascii=False)
        try:
            # Append-only: never truncate, never overwrite
            with open(self._current_file, "a", encoding="utf-8") as f:
                f.write(line_with_hash + "\n")
            self._prev_hash = entry_hash
        except Exception as e:
            logger.error(f"Erro ao escrever audit log: {e}")

    def verify_integrity(self) -> dict:
        """Verify the hash chain hasn't been tampered with."""
        import hashlib
        lines = []
        try:
            lines = self._current_file.read_text(encoding="utf-8").strip().split("\n")
        except FileNotFoundError:
            return {"valid": True, "entries": 0, "message": "No audit log yet"}

        prev = ""
        valid_count = 0
        invalid_count = 0
        for line in lines:
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Check chain link
                if entry.get("prev_hash") != prev:
                    invalid_count += 1
                    continue
                # Recompute hash (without hash field)
                check = {k: v for k, v in entry.items() if k != "hash"}
                check_line = json.dumps(check, ensure_ascii=False)
                expected = hashlib.sha256(check_line.encode("utf-8")).hexdigest()[:16]
                if entry.get("hash") == expected:
                    valid_count += 1
                    prev = entry["hash"]
                else:
                    invalid_count += 1
            except Exception:
                invalid_count += 1

        return {
            "valid": invalid_count == 0,
            "entries": valid_count,
            "invalid": invalid_count,
            "message": f"{valid_count} valid, {invalid_count} tampered" if invalid_count else f"{valid_count} entries, all valid"
        }

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
