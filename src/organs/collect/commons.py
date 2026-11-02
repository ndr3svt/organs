"""Wikimedia Commons: bitmap files only, license read from extmetadata."""
import re
from collections.abc import Iterator

from .. import http
from .base import JUNK, Candidate, norm_license

API = "https://commons.wikimedia.org/w/api.php"


def search(query: str, cls: str, limit: int) -> Iterator[Candidate]:
    offset = 0
    yielded = 0
    while yielded < limit:
        r = http.get(
            API,
            params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                "gsrlimit": 50, "gsroffset": offset, "gsrsearch": f"{query} filetype:bitmap",
                "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1024,
                "iiextmetadatafilter": "LicenseShortName|Artist",
            },
        ).json()
        pages = r.get("query", {}).get("pages", {})
        for p in sorted(pages.values(), key=lambda p: p["index"]):
            title = p["title"].removeprefix("File:")
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = norm_license(meta.get("LicenseShortName", {}).get("value"))
            if not lic or JUNK.search(title) or info.get("mime") not in {"image/jpeg", "image/png"}:
                continue
            author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            yield Candidate(
                source="commons", source_id=str(p["pageid"]), url=info.get("thumburl") or info["url"],
                landing_url=info["descriptionurl"] if "descriptionurl" in info
                else f"https://commons.wikimedia.org/wiki/{p['title'].replace(' ', '_')}",
                title=title, author=author, license=lic, cls=cls, query=query,
            )
            yielded += 1
            if yielded >= limit:
                return
        nxt = r.get("continue", {}).get("gsroffset")
        if nxt is None:
            return
        offset = nxt
