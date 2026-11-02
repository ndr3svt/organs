"""Wellcome Collection images: open-licensed anatomical specimens via the catalogue + IIIF APIs."""
from collections.abc import Iterator

from .. import http
from .base import JUNK, Candidate, norm_license

API = "https://api.wellcomecollection.org/catalogue/v2/images"


def search(query: str, cls: str, limit: int) -> Iterator[Candidate]:
    page, yielded = 1, 0
    while yielded < limit:
        r = http.get(API, params={"query": query, "pageSize": 100, "page": page}).json()
        for it in r.get("results", []):
            loc = it["locations"][0]
            lic = norm_license(loc.get("license", {}).get("id"))
            title = it["source"]["title"]
            if not lic or JUNK.search(title):
                continue
            yield Candidate(
                source="wellcome", source_id=it["id"],
                url=loc["url"].replace("info.json", "full/!1024,1024/0/default.jpg"),
                landing_url=f"https://wellcomecollection.org/works/{it['source']['id']}/images?id={it['id']}",
                title=title, author=loc.get("credit", ""), license=lic, cls=cls, query=query,
            )
            yielded += 1
            if yielded >= limit:
                return
        if not r.get("nextPage"):
            return
        page += 1
