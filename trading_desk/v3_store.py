"""Local, revisioned storage for AI Trading Desk v3 research records."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

LIST_FIELDS = ("reports", "opportunities", "decisions", "healthReviews", "observations")
MAX_DOCUMENT_BYTES = 1024 * 1024


def empty_data() -> dict:
    return {**{field: [] for field in LIST_FIELDS}, "thesisReviews": {}}


class DeskStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {"revision": 0, "data": empty_data()}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("revision"), int):
            raise ValueError("invalid desk data file")
        self._validate(payload.get("data"))
        return payload

    @staticmethod
    def _validate(data: object) -> None:
        if not isinstance(data, dict):
            raise ValueError("data must be a JSON object")
        for field in LIST_FIELDS:
            rows = data.get(field)
            if not isinstance(rows, list) or len(rows) > 5000 or not all(isinstance(row, dict) for row in rows):
                raise ValueError(f"{field} must be an array of at most 5000 objects")
        theses = data.get("thesisReviews")
        if not isinstance(theses, dict) or len(theses) > 100:
            raise ValueError("thesisReviews must be an object")
        if not all(isinstance(name, str) and isinstance(rows, list) and len(rows) <= 5000
                   and all(isinstance(row, dict) for row in rows) for name, rows in theses.items()):
            raise ValueError("each thesis review history must be an array of objects")

    def read(self) -> dict:
        with self.lock:
            return self._read()

    def update(self, expected_revision: object, data: object) -> dict:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expectedRevision must be a non-negative integer")
        self._validate(data)
        with self.lock:
            current = self._read()
            if expected_revision != current["revision"]:
                raise ConflictError(current["revision"])
            payload = {"revision": expected_revision + 1, "data": data}
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(encoded) > MAX_DOCUMENT_BYTES:
                raise ValueError("desk data exceeds 1 MB")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix="v3_state.", suffix=".tmp", dir=self.path.parent)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return payload


class ConflictError(Exception):
    def __init__(self, revision: int):
        self.revision = revision
        super().__init__(f"desk data changed in another session (revision {revision})")
