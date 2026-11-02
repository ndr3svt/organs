"""Run collectors over queries.yaml and append downloaded images to the private manifest."""
import yaml
from tqdm import tqdm

from .. import manifest, paths
from ..classes import CLASS_INDEX
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
                try:
                    for cand in SOURCES[src].search(q, c, limit * 4):
                        rec = download(cand, records, seen)
                        if rec:
                            records[rec["id"]] = rec  # local dedupe cache
                            manifest.add({rec["id"]: rec})  # locked, touches only this record
                            got += 1
                            bar.update(1)
                        if got >= limit:
                            break
                except Exception as e:  # one bad query must not end a long run; what was saved stays saved
                    print(f"{c:9} {src:9} {q:32} +{got}  FAILED: {type(e).__name__}: {str(e)[:80]}")
                    bar.close()
                    continue
                bar.close()
                print(f"{c:9} {src:9} {q:32} +{got}")


def ingest_inbox() -> int:
    """Register your own images from data/inbox/<class>/ (license 'own'). Returns number added."""
    paths.ensure_dirs()
    new = {}
    for cdir in sorted(p for p in paths.INBOX.iterdir() if p.is_dir() and p.name in CLASS_INDEX):
        for f in sorted(cdir.iterdir()):
            if f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            rid = f"inbox_{cdir.name}_{f.stem}"
            new[rid] = {
                "id": rid, "source": "inbox", "landing_url": "", "title": f.stem, "author": "own",
                "license": "own", "class": cdir.name, "query": "", "path": str(f.relative_to(paths.DATA)),
                "status": "raw",
            }
    before = len(manifest.load())
    manifest.add(new)
    return len(manifest.load()) - before
