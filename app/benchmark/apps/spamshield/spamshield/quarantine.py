"""Quarantine store on an encrypted PersistentVolume; messages are purged after the configured days."""

from __future__ import annotations

import json
import time
from pathlib import Path


class Quarantine:
    def __init__(self, path: str) -> None:
        self.root = Path(path)
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, msg: dict) -> None:
        (self.root / f"{int(time.time())}-{abs(hash(msg['message_id']))}.json").write_text(json.dumps(msg))

    def purge(self, retention_days: int) -> int:
        cutoff = time.time() - retention_days * 86400
        removed = 0
        for f in self.root.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        return removed
