import argparse
from collections import Counter

from . import manifest
from .classes import CLASSES


def stats() -> None:
    rows = manifest.load().values()
    by = Counter((r["class"], r["status"]) for r in rows)
    classes = sorted({c for c, _ in by})
    statuses = sorted({s for _, s in by})
    print(f"{'class':10}" + "".join(f"{s:>12}" for s in statuses) + f"{'total':>8}")
    for c in classes:
        print(f"{c:10}" + "".join(f"{by[(c, s)]:>12}" for s in statuses) + f"{sum(by[(c, s)] for s in statuses):>8}")


def main() -> None:
    p = argparse.ArgumentParser(prog="organs")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="download images from the open sources in queries.yaml")
    c.add_argument("--source", choices=["commons", "inat", "wellcome"])
    c.add_argument("--cls", choices=CLASSES)
    c.add_argument("--limit", type=int, default=40, help="new images per query")

    sub.add_parser("ingest-inbox", help="register your own images from data/inbox/<class>/")

    k = sub.add_parser("cutout", help="remove backgrounds, build masks, run automatic checks")
    k.add_argument("--model", default="isnet-general-use")
    k.add_argument("--limit", type=int)
    k.add_argument("--redo", action="store_true", help="reprocess already cut images")

    v = sub.add_parser("review", help="local keep/reject review of cutouts")
    v.add_argument("--status", default="cut", choices=["cut", "auto_reject", "keep", "reject"])
    v.add_argument("--port", type=int, default=8765)

    s = sub.add_parser("showcase", help="build the static showcase from the manifest, optionally preview it")
    s.add_argument("--per-class", type=int, default=80, help="specimens shown per realm")
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--skip-build", action="store_true", help="only serve what was built before")
    s.add_argument("--serve", action="store_true", help="preview on 127.0.0.1 after building")
    s.add_argument("--port", type=int, default=4180)

    sub.add_parser("stats", help="per class and status counts")

    a = p.parse_args()
    if a.cmd == "collect":
        from . import collect
        collect.run(a.source, a.cls, a.limit)
    elif a.cmd == "ingest-inbox":
        from . import collect
        print(f"added {collect.ingest_inbox()}")
    elif a.cmd == "cutout":
        from . import cutout
        cutout.process(a.model, a.limit, a.redo)
    elif a.cmd == "review":
        from . import review
        review.serve(a.status, a.port)
    elif a.cmd == "showcase":
        from . import showcase
        if not a.skip_build:
            showcase.build(a.per_class, a.seed)
        if a.serve or a.skip_build:
            showcase.serve(a.port)
    elif a.cmd == "stats":
        stats()


if __name__ == "__main__":
    main()
