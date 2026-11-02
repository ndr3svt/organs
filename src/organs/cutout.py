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


def cut(img: Image.Image, session, cls: str) -> tuple[Image.Image, Image.Image, str | None]:
    from rembg import remove

    img = img.convert("RGB")
    img.thumbnail((MAX_IN, MAX_IN), Image.LANCZOS)
    alpha = np.asarray(remove(img, session=session, only_mask=True), dtype=np.float32) / 255.0

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


def process(model: str = "isnet-general-use", limit: int | None = None, redo: bool = False) -> None:
    from rembg import new_session

    paths.ensure_dirs()
    records = manifest.load()
    todo = [r for r in records.values() if r["status"] == "raw" or (redo and r["status"] in {"cut", "auto_reject"})]
    todo = todo[:limit]
    session = new_session(model)
    for i, r in enumerate(tqdm(todo, desc="cutout"), 1):
        try:
            out, mask, reason = cut(Image.open(paths.DATA / r["path"]), session, r["class"])
        except Exception as e:  # corrupt file, decode error, etc.
            r.update(status="auto_reject", reason=f"error:{type(e).__name__}")
            continue
        out.save(paths.CUTOUTS / f"{r['id']}.jpg", quality=95)
        mask.save(paths.MASKS / f"{r['id']}.png")
        r.update(status="auto_reject" if reason else "cut", reason=reason or "",
                 fg_frac=round(float((np.asarray(mask) > 0).mean()), 3))
        if i % 20 == 0:
            manifest.save(records)
    manifest.save(records)
