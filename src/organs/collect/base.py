"""Shared collector pieces: candidate record, license gate, download + validate."""
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass

from PIL import Image

from .. import http, paths

# canonical license -> allowed for the private training set. ND and unknown are skipped.
ALLOWED = {"cc0", "pdm", "by", "by-sa", "by-nc", "by-nc-sa"}
MIN_SIDE = 384
# titles that signal a diagram, collage, or drawing rather than a photographed subject
JUNK = re.compile(
    r"diagram|schema|drawing|illustration|\bmap\b|logo|icon|svg|collage|chart|plate|engraving|lithograph|print\b|"
    r"woodcut|etching|watercolou?r|painting|sketch|poster|cartoon",
    re.I,
)


@dataclass
class Candidate:
    source: str
    source_id: str
    url: str  # direct image url to download
    landing_url: str
    title: str
    author: str
    license: str  # canonical, see norm_license
    cls: str
    query: str

    @property
    def id(self) -> str:
        return f"{self.source}_{re.sub(r'[^A-Za-z0-9_.-]', '_', str(self.source_id))}"


def norm_license(raw: str | None) -> str | None:
    """Map free-form license text to a canonical code, or None if unusable."""
    if not raw:
        return None
    s = re.sub(r"[\s_]+", "-", raw.lower().strip())
    if "cc0" in s:
        return "cc0"
    if "public-domain" in s or s in {"pdm", "pd"} or s.startswith("pd-"):
        return "pdm"
    m = re.fullmatch(r"(?:cc-)?by(-nc)?(-sa)?(-nd)?(?:-.*)?", s)
    if not m or m.group(3):  # not a CC-BY family license, or NoDerivatives
        return None
    return "by" + (m.group(1) or "") + (m.group(2) or "")


SKIPS: Counter = Counter()  # why candidates were not saved; printed per query so silent failures show up


def download(c: Candidate, known: dict[str, dict], seen_hashes: set[str]) -> dict | None:
    """Download one candidate. Returns a manifest record, or None if skipped (reason counted in SKIPS)."""
    if c.license not in ALLOWED:
        SKIPS["license"] += 1
        return None
    if c.id in known:
        SKIPS["known"] += 1
        return None
    try:
        r = http.get(c.url)
        img = Image.open(io.BytesIO(r.content))
        img.load()
    except Exception as e:
        SKIPS[f"error:{type(e).__name__}"] += 1
        return None
    if min(img.size) < MIN_SIDE:
        SKIPS["too_small"] += 1
        return None
    digest = hashlib.sha1(r.content).hexdigest()
    if digest in seen_hashes:
        SKIPS["duplicate"] += 1
        return None
    seen_hashes.add(digest)

    rgb = img.convert("RGB")
    out = paths.RAW / c.cls / f"{c.id}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(out, quality=95)
    return {
        "id": c.id,
        "source": c.source,
        "landing_url": c.landing_url,
        "title": c.title,
        "author": c.author,
        "license": c.license,
        "class": c.cls,
        "query": c.query,
        "path": str(out.relative_to(paths.DATA)),
        "width": rgb.width,
        "height": rgb.height,
        "sha1": digest,
        "status": "raw",
    }
