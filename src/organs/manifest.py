"""Private manifest: one JSON object per line, keyed by `id`.

Several processes write it at once (collector, cutout, review server), so every write is a
read-modify-write under an exclusive file lock and touches only the records it owns.
"""
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

from . import paths


@contextmanager
def locked():
    paths.DATA.mkdir(parents=True, exist_ok=True)
    with (paths.DATA / ".manifest.lock").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load(path: Path = paths.MANIFEST) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["id"]: r for r in map(json.loads, filter(str.strip, f))}


def _save(records: dict[str, dict], path: Path = paths.MANIFEST) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in records.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def add(new: dict[str, dict]) -> None:
    """Insert records that do not exist yet. Existing records are never overwritten."""
    with locked():
        records = load()
        records.update({k: v for k, v in new.items() if k not in records})
        _save(records)


def update(record_id: str, expect: str | None = None, **fields) -> bool:
    """Set fields on one record. With `expect`, only if its status still equals it (so a slow
    job cannot overwrite a decision made meanwhile). Returns whether it was written."""
    with locked():
        records = load()
        rec = records.get(record_id)
        if rec is None or (expect is not None and rec["status"] != expect):
            return False
        rec.update(fields)
        _save(records)
        return True
