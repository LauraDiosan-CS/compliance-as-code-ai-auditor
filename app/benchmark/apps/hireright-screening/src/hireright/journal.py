"""DecisionJournal: append-only record of what the ranker produced and what humans did with it.

Each entry is one JSON line written to an object-locked S3 prefix (WORM). Entries are never updated;
corrections are new entries referencing the original `entry_id`. See docs/adr/0002-decision-journal.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class Sink(Protocol):
    def append(self, line: str) -> None: ...


@dataclass
class JournalEntry:
    event: str  # "ranked" | "reviewer_decision" | "override" | "suspended" | "resumed"
    application_id: str
    requisition_id: str | None = None
    model_version: str | None = None
    input_digest: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    actor: str = "system"
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DecisionJournal:
    def __init__(self, sink: Sink) -> None:
        self._sink = sink

    @staticmethod
    def digest(payload: dict[str, Any]) -> str:
        """Reference to the input without storing the CV itself in the journal."""
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()

    def record(self, entry: JournalEntry) -> str:
        self._sink.append(json.dumps(asdict(entry), separators=(",", ":")))
        return entry.entry_id


class S3WormSink:
    """Writes journal lines to a bucket with Object Lock (compliance mode)."""

    def __init__(self, client: Any, bucket: str, prefix: str = "journal/") -> None:
        self.client, self.bucket, self.prefix = client, bucket, prefix

    def append(self, line: str) -> None:
        key = f"{self.prefix}{datetime.now(timezone.utc):%Y/%m/%d}/{uuid.uuid4().hex}.json"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=line.encode(), ServerSideEncryption="aws:kms")
