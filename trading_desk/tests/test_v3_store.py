"""Desk records survive reloads and reject stale writes."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import v3_store  # noqa: E402


def test_store_round_trip_and_conflict(tmp_path):
    store = v3_store.DeskStore(tmp_path / "desk.json")
    assert store.read() == {"revision": 0, "data": v3_store.empty_data()}
    data = v3_store.empty_data()
    data["decisions"].append({"decision": "Review the case", "outcome": "pending"})
    saved = store.update(0, data)
    assert saved["revision"] == 1
    assert store.read() == saved
    assert (tmp_path / "desk.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(v3_store.ConflictError):
        store.update(0, data)
    assert store.read() == saved


def test_store_rejects_invalid_shape_without_writing(tmp_path):
    store = v3_store.DeskStore(tmp_path / "desk.json")
    with pytest.raises(ValueError):
        store.update(0, {"reports": []})
    with pytest.raises(ValueError):
        store.update(True, v3_store.empty_data())
    assert not (tmp_path / "desk.json").exists()
