"""Run collectors over queries.yaml and append downloaded images to the private manifest."""
import yaml
from tqdm import tqdm

from .. import manifest, paths
from . import commons, inaturalist, wellcome
from .base import download

SOURCES = {"commons": commons, "inat": inaturalist, "wellcome": wellcome}


def run(source: str | None = None, cls: str | None = None, limit: int = 40) -> None:
    """Collect up to `limit` new images per query. Skips known ids and duplicate bytes."""
    paths.ensure_dirs()
    plan = yaml.safe_load(paths.QUERIES.read_text())
    records = manifest.load()
    seen = {r["sha1"] for r in records.values() if "sha1" in r}

    for c, by_source in plan.items():
        if cls and c != cls:
            continue
        for src, queries in by_source.items():
            if source and src != source:
                continue
            for q in queries:
                got = 0
                bar = tqdm(desc=f"{c}/{src}/{q}", total=limit, leave=False)
                for cand in SOURCES[src].search(q, c, limit * 4):
                    rec = download(cand, records, seen)
                    if rec:
                        records[rec["id"]] = rec
                        got += 1
                        bar.update(1)
                        if got % 10 == 0:
                            manifest.save(records)
                    if got >= limit:
                        break
                bar.close()
                manifest.save(records)
                print(f"{c:9} {src:9} {q:32} +{got}")


def ingest_inbox() -> int:
    """Register your own images from data/inbox/<class>/ (license 'own'). Returns number added."""
    paths.ensure_dirs()
    records = manifest.load()
    added = 0
    for cdir in sorted(p for p in paths.INBOX.iterdir() if p.is_dir()):
        for f in sorted(cdir.iterdir()):
            if f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            rid = f"inbox_{cdir.name}_{f.stem}"
            if rid in records:
                continue
            records[rid] = {
                "id": rid, "source": "inbox", "landing_url": "", "title": f.stem, "author": "own",
                "license": "own", "class": cdir.name, "query": "", "path": str(f.relative_to(paths.DATA)),
                "status": "raw",
            }
            added += 1
    manifest.save(records)
    return added
