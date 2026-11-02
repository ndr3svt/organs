"""Private manifest: one JSON object per line, keyed by `id`. Rewritten atomically on update."""
import json
import os
from pathlib import Path

from . import paths


def load(path: Path = paths.MANIFEST) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["id"]: r for r in map(json.loads, filter(str.strip, f))}


def save(records: dict[str, dict], path: Path = paths.MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for r in records.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def update(record_id: str, **fields) -> None:
    records = load()
    records[record_id].update(fields)
    save(records)
