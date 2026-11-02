from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INBOX = DATA / "inbox"
CUTOUTS = DATA / "cutouts"
MASKS = DATA / "masks"
MANIFEST = DATA / "manifest.jsonl"
QUERIES = ROOT / "queries.yaml"


def ensure_dirs() -> None:
    for d in (RAW, INBOX, CUTOUTS, MASKS):
        d.mkdir(parents=True, exist_ok=True)
