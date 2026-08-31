# -*- coding: utf-8 -*-
"""Sistema de logging estruturado do Elívea."""
import logging
import sys
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "config" / "logs"

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "ts": datetime.now().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)

_initialized = False

def get_logger(name: str = "elvea") -> logging.Logger:
    global _initialized
    root = logging.getLogger(name)
    if not _initialized:
        root.setLevel(logging.DEBUG)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(ch)
        fh = logging.FileHandler(LOG_DIR / "elvea.jsonl", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)
        _initialized = True
    return root
