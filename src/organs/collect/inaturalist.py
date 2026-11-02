"""iNaturalist research-grade observations with open photo licenses.

Plant queries use the 'Flowers and Fruits' annotation so the organ is the subject.
Fungal queries use iconic taxon Fungi (observations are mostly fruiting bodies).
`query` is the iNaturalist filter label: flowers | fruits | fungi.
"""
from collections.abc import Iterator

from .. import http
from .base import Candidate, norm_license

API = "https://api.inaturalist.org/v1/observations"
FILTERS = {
    "flowers": {"iconic_taxa": "Plantae", "term_id": 12, "term_value_id": 13},
    "fruits": {"iconic_taxa": "Plantae", "term_id": 12, "term_value_id": 14},
    "fungi": {"iconic_taxa": "Fungi"},
}


def search(query: str, cls: str, limit: int) -> Iterator[Candidate]:
    params = {
        "photos": "true", "quality_grade": "research", "license": "cc0,cc-by,cc-by-sa,cc-by-nc,cc-by-nc-sa",
        "per_page": 100, "order_by": "votes", "page": 1, **FILTERS[query],
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
