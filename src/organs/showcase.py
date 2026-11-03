"""Build and preview the static showcase in data_for_the_arts_showcase/.

Reads the private manifest and writes:
  data/showcase.json   credits for every shown specimen, plus aggregates over the whole dataset
  img/                 thumbnails, masks and contact sheets (gitignored: other people's photos)
  index.html, js/      cache-busting version stamped from a content hash

Only CC0, public domain, CC BY and CC BY-SA images are ever shown. Non-commercial ones are excluded.
"""
import hashlib
import html
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import manifest, paths
from .classes import CLASS_INDEX, CLASSES, SWATCH
from .cutout import GROUND

ROOT = paths.ROOT / "data_for_the_arts_showcase"
IMG = ROOT / "img"
DATA_JSON = ROOT / "data" / "showcase.json"
CURATION = ROOT / "curation.json"

SHOWN = {"cc0", "pdm", "by", "by-sa"}  # licenses safe to display on a portfolio that also sells services
STAGE = 400  # px, side of the specimen plates
TILE = 128  # px, side of the realm-strip tiles
QUALITY = 68
PORTFOLIO = paths.ROOT.parent / "avt_web_portfolio"


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _clean(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _title(rec: dict) -> str:
    title = re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", rec["title"], flags=re.I)
    return _clean(title.replace("_", " "), 90)


def _curation() -> dict:
    if not CURATION.exists():
        ROOT.mkdir(parents=True, exist_ok=True)
        CURATION.write_text(json.dumps({"exclude": [], "include": []}, indent=2) + "\n")
    return json.loads(CURATION.read_text())


def _eligible(rec: dict) -> bool:
    return (
        rec["status"] in {"keep", "cut"}
        and rec["license"] in SHOWN
        and (paths.CUTOUTS / f"{rec['id']}.jpg").exists()
        and (paths.MASKS / f"{rec['id']}.png").exists()
    )


def select(records: dict[str, dict], per_class: int, seed: int) -> list[dict]:
    """Balanced, license-safe sample per realm: kept images first, then round-robin over queries for variety."""
    cur = _curation()
    banned = [re.compile(p, re.I) for p in cur.get("exclude_titles", [])]  # e.g. a painter who shares a query word
    out: list[dict] = []
    for cls in CLASSES:
        pool = [
            r for r in records.values()
            if r["class"] == cls and _eligible(r) and r["id"] not in cur["exclude"]
            and r["source"] not in cur.get("exclude_sources", [])
            and not any(p.search(r["title"]) for p in banned)
        ]
        rng = random.Random(f"{seed}:{cls}")
        forced = [r for r in pool if r["id"] in cur["include"]]
        forced_ids = {r["id"] for r in forced}
        by_query: dict[str, list[dict]] = defaultdict(list)
        for r in sorted(pool, key=lambda r: (r["status"] != "keep", r["id"])):
            if r["id"] not in forced_ids:
                by_query[r["query"]].append(r)
        queues = list(by_query.values())
        rng.shuffle(queues)
        for q in queues:  # kept images lead each queue; shuffle only the rest
            kept = [r for r in q if r["status"] == "keep"]
            rest = [r for r in q if r["status"] != "keep"]
            rng.shuffle(rest)
            q[:] = kept + rest
        picked = list(forced)
        while len(picked) < per_class and any(queues):
            for q in queues:
                if q and len(picked) < per_class:
                    picked.append(q.pop(0))
        out += picked[:per_class]
    return out


def _plate(img: Image.Image) -> Image.Image:
    """Fit an image inside a square plate of the cutout ground color."""
    img = ImageOps.contain(img.convert("RGB"), (STAGE, STAGE), Image.LANCZOS)
    plate = Image.new("RGB", (STAGE, STAGE), GROUND)
    plate.paste(img, ((STAGE - img.width) // 2, (STAGE - img.height) // 2))
    return plate


def _mask_image(rec: dict) -> Image.Image:
    m = np.asarray(Image.open(paths.MASKS / f"{rec['id']}.png"))
    out = np.empty((*m.shape, 3), dtype=np.uint8)
    out[:] = GROUND
    out[m > 0] = SWATCH[rec["class"]]
    return Image.fromarray(out).resize((STAGE, STAGE), Image.LANCZOS)


def render(rec: dict) -> None:
    cutout = Image.open(paths.CUTOUTS / f"{rec['id']}.jpg")
    jobs = {
        "cutout": _plate(cutout),
        "source": _plate(Image.open(paths.DATA / rec["path"])),
        "mask": _mask_image(rec),
        "tile": ImageOps.fit(cutout.convert("RGB"), (TILE, TILE), Image.LANCZOS),
    }
    for kind, img in jobs.items():
        d = IMG / kind
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / f"{rec['id']}.webp", "WEBP", quality=QUALITY if kind != "mask" else 80, method=6)


def contact_sheets(specimens: list[dict]) -> None:
    """One sheet per realm with ids under the tiles, so junk can be listed in curation.json."""
    cols, label = 10, 14
    for cls in CLASSES:
        items = [s for s in specimens if s["realm"] == cls]
        rows = -(-len(items) // cols)
        sheet = Image.new("RGB", (cols * TILE, rows * (TILE + label)), (244, 242, 236))
        draw = ImageDraw.Draw(sheet)
        for i, s in enumerate(items):
            x, y = (i % cols) * TILE, (i // cols) * (TILE + label)
            sheet.paste(Image.open(IMG / "tile" / f"{s['id']}.webp"), (x, y))
            draw.text((x + 2, y + TILE + 2), s["id"].replace("commons_", "c_").replace("inat_", "i_"), fill=(11, 11, 22))
        sheet.save(IMG / f"_contact_{cls}.jpg", quality=80)


def aggregates(records: dict[str, dict]) -> dict:
    """Counts over the whole dataset, not only the shown sample."""
    rows = list(records.values())
    funnel = {}
    for cls in CLASSES:
        r = [x for x in rows if x["class"] == cls]
        funnel[cls] = {
            "collected": len(r),
            "passed": sum(x["status"] != "auto_reject" for x in r),
            "kept": sum(x["status"] == "keep" for x in r),
        }
    def mix(field: str) -> dict:
        return {cls: dict(Counter(x[field] for x in rows if x["class"] == cls)) for cls in CLASSES}
    nc = sum("nc" in x["license"] for x in rows)
    return {
        "total": len(rows),
        "funnel": funnel,
        "license": mix("license"),
        "source": mix("source"),
        "non_commercial": nc,
    }


def build(per_class: int = 80, seed: int = 7) -> None:
    records = manifest.load()
    specimens = select(records, per_class, seed)
    if IMG.exists():
        shutil.rmtree(IMG)
    for i, rec in enumerate(specimens, 1):
        render(rec)
        if i % 50 == 0:
            print(f"  rendered {i}/{len(specimens)}", flush=True)
    items = [
        {
            "id": r["id"],
            "realm": r["class"],
            "title": _title(r),
            "author": _clean(r.get("author", ""), 90) or "unknown author",
            "license": r["license"],
            "source": r["source"],
            "url": r["landing_url"],
            "kept": r["status"] == "keep",
        }
        for r in specimens
    ]
    contact_sheets(items)
    shown = Counter(s["realm"] for s in items)
    payload = {
        "generated": date.today().isoformat(),
        # changes whenever the shown set changes; the page appends it to image URLs
        "v": hashlib.sha1("".join(i["id"] for i in items).encode()).hexdigest()[:8],
        "ground": _hex(GROUND),
        "realms": [
            {"id": c, "index": CLASS_INDEX[c], "color": _hex(SWATCH[c]), "shown": shown[c]} for c in CLASSES
        ],
        "aggregates": aggregates(records),
        "specimens": items,
    }
    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    size = sum(f.stat().st_size for f in IMG.rglob("*.webp")) / 1e6
    stamp()
    print(f"{len(items)} specimens, {size:.1f} MB of images; credits in {DATA_JSON.relative_to(paths.ROOT)}")
    print("shown per realm:", dict(shown))
    print(f"contact sheets: {IMG.relative_to(paths.ROOT)}/_contact_*.jpg (list junk ids in curation.json, then rebuild)")


# ---- cache busting ----------------------------------------------------------------------------------------------

_VERSIONED = re.compile(r"((?:css/showcase\.css|js/[\w-]+\.js|\./[\w-]+\.js|data/showcase\.json))\?v=\w+")


def _web_files() -> list[Path]:
    return [ROOT / "index.html", ROOT / "css" / "showcase.css", *sorted((ROOT / "js").glob("*.js"))]


def stamp() -> None:
    """Static pieces are copied as-is by the portfolio build, so version the asset URLs ourselves.
    The hash is taken with version tokens neutralised, so it only changes when the content does."""
    files = [f for f in _web_files() if f.exists()]
    digest = hashlib.sha1()
    for f in files:
        digest.update(_VERSIONED.sub(r"\1?v=x", f.read_text()).encode())
    digest.update(DATA_JSON.read_bytes())
    version = digest.hexdigest()[:8]
    for f in files:
        text = f.read_text()
        new = _VERSIONED.sub(rf"\1?v={version}", text)
        if new != text:
            f.write_text(new)


# ---- preview server ---------------------------------------------------------------------------------------------


class _Handler(SimpleHTTPRequestHandler):
    """Serves the folder. /fonts/, /avatar.gif and /favicon.png are mapped read-only to the portfolio,
    so the licensed font is never copied here, and the page looks as it will on ndr3svt.art."""

    fonts = PORTFOLIO / "fonts"
    site_files = {"/avatar.gif", "/favicon.png"}

    def translate_path(self, path: str) -> str:
        clean = path.split("?")[0].split("#")[0]
        if clean.startswith("/fonts/") and self.fonts.is_dir():
            return str(self.fonts / Path(clean).name)
        if clean in self.site_files and (PORTFOLIO / "site" / clean.lstrip("/")).exists():
            return str(PORTFOLIO / "site" / clean.lstrip("/"))
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def serve(port: int = 4180) -> None:
    handler = lambda *a, **k: _Handler(*a, directory=str(ROOT), **k)  # noqa: E731
    font = "mapped from the portfolio" if _Handler.fonts.is_dir() else "not found, system sans fallback"
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"showcase at http://127.0.0.1:{port}/  (font: {font}; Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
