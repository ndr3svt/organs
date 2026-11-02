"""iNaturalist research-grade observations with open photo licenses.

Plant queries use the 'Flowers and Fruits' annotation so the organ is the subject.
Fungal queries use iconic taxon Fungi (observations are mostly fruiting bodies). Top-voted results
skew to a few photogenic species, so `taxon:<Name>` restricts a query to one taxon (order, family, ...)
and spreads the collection across forms: gills, pores, brackets, cups, puffballs, stinkhorns, lichens.
`query` is the filter label: flowers | fruits | fungi | taxon:<Name>.
"""
from collections.abc import Iterator
from functools import cache

from .. import http
from .base import Candidate, norm_license

API = "https://api.inaturalist.org/v1/observations"
FILTERS = {
    "flowers": {"iconic_taxa": "Plantae", "term_id": 12, "term_value_id": 13},
    "fruits": {"iconic_taxa": "Plantae", "term_id": 12, "term_value_id": 14},
    "fungi": {"iconic_taxa": "Fungi"},
}


@cache
def taxon_id(name: str) -> int:
    """Exact-name lookup so 'Agaricales' cannot silently resolve to a different taxon."""
    results = http.get("https://api.inaturalist.org/v1/taxa", params={"q": name, "per_page": 5}).json()["results"]
    hit = next((t for t in results if t["name"].lower() == name.lower()), None)
    if hit is None:
        raise ValueError(f"iNaturalist taxon not found: {name}")
    return hit["id"]


def filters(query: str) -> dict:
    if query.startswith("taxon:"):
        return {"taxon_id": taxon_id(query.removeprefix("taxon:").strip())}
    return FILTERS[query]


def search(query: str, cls: str, limit: int) -> Iterator[Candidate]:
    params = {
        "photos": "true", "quality_grade": "research", "license": "cc0,cc-by,cc-by-sa,cc-by-nc,cc-by-nc-sa",
        "per_page": 100, "order_by": "votes", "page": 1, **filters(query),
    }
    yielded = 0
    while yielded < limit:
        r = http.get(API, params=params, delay=1.0).json()
        results = r.get("results", [])
        if not results:
            return
        for o in results:
            photo = next((p for p in o.get("photos", []) if not p.get("hidden")), None)
            lic = norm_license(photo and photo.get("license_code"))
            if not lic:
                continue
            yield Candidate(
                source="inat", source_id=str(photo["id"]), url=photo["url"].replace("square", "large"),
                landing_url=o["uri"], title=(o.get("taxon") or {}).get("name", "unknown"),
                author=o["user"]["login"], license=lic, cls=cls, query=query,
            )
            yielded += 1
            if yielded >= limit:
                return
        params["page"] += 1
