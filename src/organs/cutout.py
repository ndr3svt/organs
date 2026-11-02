"""Raw image -> subject on a neutral ground + class-index mask, with automatic quality checks.

Output per image id:
  data/cutouts/<id>.jpg  512px square, subject composited on GROUND
  data/masks/<id>.png    512px, mode L, values 0 (background) or the class index

Status written to the manifest: `cut` (passed checks) or `auto_reject` with a `reason`.
"""
import numpy as np
from PIL import Image
from scipy import ndimage
from tqdm import tqdm

from . import manifest, paths
from .classes import CLASS_INDEX

GROUND = (236, 236, 232)
SIZE = 512
MARGIN = 0.08  # fraction of the subject box kept as space around it
MAX_IN = 1024  # downscale input before segmentation, for speed
MAX_OUT = 2048  # cap on the working image the cutout pixels are taken from


def _largest_filled(fg: np.ndarray) -> tuple[np.ndarray, float]:
    """Keep the largest connected region, fill its holes. Returns (mask, share of fg it holds)."""
    lab, n = ndimage.label(fg)
    if n == 0:
        return fg, 0.0
    sizes = ndimage.sum(fg, lab, range(1, n + 1))
    keep = lab == (int(np.argmax(sizes)) + 1)
    return ndimage.binary_fill_holes(keep), float(sizes.max() / sizes.sum())


def _checks(fg: np.ndarray, share: float) -> str | None:
    """Return a reject reason or None. Thresholds are deliberately loose; a human reviews the rest."""
    frac = fg.mean()
    if frac < 0.03:
        return "tiny_subject"
    if frac > 0.92:
        return "no_background"
    if share < 0.85:
        return "multiple_objects"
    edge = np.concatenate([fg[0], fg[-1], fg[:, 0], fg[:, -1]])
    if edge.mean() > 0.15:
        return "touches_frame"
    return None


_sessions: dict[str, object] = {}


def get_session(name: str):
    """Load a rembg model once per process. 'sam' is the click-prompted segmenter."""
    if name not in _sessions:
        from rembg import new_session

        _sessions[name] = new_session(name)
    return _sessions[name]


def _prompted_alpha(img: Image.Image, points: list[tuple[float, float, int]]) -> np.ndarray:
    """SAM mask from clicks. points are (x, y, label) with x, y in 0..1 of the image; label 1 = organ, 0 = not organ."""
    prompt = [
        {"type": "point", "label": int(lab), "data": [int(x * img.width), int(y * img.height)]}
        for x, y, lab in points
    ]
    mask = np.asarray(get_session("sam").predict(img, sam_prompt=prompt)[0], dtype=np.float32) / 255.0
    return ndimage.gaussian_filter(mask, 1.0)  # SAM masks are binary and low-res; soften the edge


def cut(
    img: Image.Image, session, cls: str, points: list[tuple[float, float, int]] | None = None
) -> tuple[Image.Image, Image.Image, str | None]:
    """Cut the subject out. With `points` the subject is chosen by clicks (SAM); otherwise it is automatic."""
    from rembg import remove

    img = img.convert("RGB")
    img.thumbnail((MAX_OUT, MAX_OUT), Image.LANCZOS)  # pixels come from here, so small subjects stay sharp
    seg = img.copy()
    seg.thumbnail((MAX_IN, MAX_IN), Image.LANCZOS)  # the segmenter only needs the small version
    if points:
        alpha = _prompted_alpha(seg, points)
    else:
        alpha = np.asarray(remove(seg, session=session, only_mask=True), dtype=np.float32) / 255.0
    if seg.size != img.size:
        alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR),
                           dtype=np.float32) / 255.0

    fg, share = _largest_filled(alpha > 0.5)
    reason = _checks(fg, share)
    if not fg.any():
        return img, Image.new("L", (SIZE, SIZE)), reason

    # crop to the subject with a margin, pad to a square with the ground color
    ys, xs = np.where(fg)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = int(max(y1 - y0, x1 - x0) * (1 + 2 * MARGIN))
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)

    soft = np.where(fg, np.clip((alpha - 0.1) / 0.8, 0, 1), 0)  # drops the halo; confined to the kept region
    rgba = np.dstack([np.asarray(img), (soft * 255).astype(np.uint8)])
    sub = Image.fromarray(rgba, "RGBA")
    layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    layer.paste(sub.crop((max(box[0], 0), max(box[1], 0), min(box[2], sub.width), min(box[3], sub.height))),
                (max(-box[0], 0), max(-box[1], 0)))
    layer = layer.resize((SIZE, SIZE), Image.LANCZOS)

    ground = Image.new("RGBA", (SIZE, SIZE), GROUND + (255,))
    out = Image.alpha_composite(ground, layer).convert("RGB")
    mask = (np.asarray(layer)[..., 3] > 127).astype(np.uint8) * CLASS_INDEX[cls]
    return out, Image.fromarray(mask, "L"), reason


def _write(rec: dict, out: Image.Image, mask: Image.Image, reason: str | None) -> None:
    out.save(paths.CUTOUTS / f"{rec['id']}.jpg", quality=95)
    mask.save(paths.MASKS / f"{rec['id']}.png")
    rec.update(status="auto_reject" if reason else "cut", reason=reason or "",
               fg_frac=round(float((np.asarray(mask) > 0).mean()), 3))


def recut(rec: dict, points: list[tuple[float, float, int]], model: str = "isnet-general-use") -> None:
    """Redo one image from clicks (or automatically when `points` is empty). Updates `rec` in place.

    A manual cut is the user's call, so it always lands as `cut`; the automatic checks are only advice.
    """
    out, mask, reason = cut(Image.open(paths.DATA / rec["path"]), get_session(model), rec["class"], points or None)
    _write(rec, out, mask, reason if not points else None)
    rec["points"] = [list(p) for p in points]
    if points:
        rec["reason"] = "manual" + (f" (checks said {reason})" if reason else "")


def process(model: str = "isnet-general-use", limit: int | None = None, redo: bool = False) -> None:
    paths.ensure_dirs()
    records = manifest.load()
    todo = [r for r in records.values() if r["status"] == "raw" or (redo and r["status"] in {"cut", "auto_reject"})]
    todo = todo[:limit]
    for i, r in enumerate(tqdm(todo, desc="cutout"), 1):
        try:  # saved clicks are re-applied, so --redo never undoes a manual cut
            recut(r, [tuple(p) for p in r.get("points") or []], model)
        except Exception as e:  # corrupt file, decode error, etc.
            r.update(status="auto_reject", reason=f"error:{type(e).__name__}")
            continue
        if i % 20 == 0:
            manifest.save(records)
    manifest.save(records)
