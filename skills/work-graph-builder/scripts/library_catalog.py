#!/usr/bin/env python3
"""
library_catalog.py — zeigt, was die Referenzbibliothek enthält.

Aufruf:
    python3 <skill>/scripts/library_catalog.py                       Branchen mit Rollen- und Aufgabenzahl
    python3 <skill>/scripts/library_catalog.py --branche <id>        Cluster und Rollen einer Branche
    python3 <skill>/scripts/library_catalog.py --rechtsraum DE       Themen des Rechtsrahmens
    python3 <skill>/scripts/library_catalog.py --plattform microsoft Dienste je Agentenmuster
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pages_lib as pl  # noqa: E402
import workgraph_lib as wl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branche", default=None)
    ap.add_argument("--rechtsraum", default=None)
    ap.add_argument("--plattform", default=None)
    args = ap.parse_args()
    lib = wl.library_dir()
    if lib is None:
        wl.fail("Referenzbibliothek nicht gefunden")
    if args.rechtsraum:
        data = wl.load_library_json("rechtsraeume", f"{args.rechtsraum}.json")
        if not data:
            wl.fail(f"Rechtsraum {args.rechtsraum!r} nicht in der Bibliothek")
        print(f"Rechtsraum {data['label']}: {len(data['themen'])} Themen")
        for t in data["themen"]:
            print(f"  {t['id']:<24} {t['thema']} ({t['gesetz']}; {t['fundstelle']})")
        return 0
    if args.plattform:
        data = wl.load_library_json("plattformen", f"{args.plattform}.json")
        if not data:
            wl.fail(f"Plattformprofil {args.plattform!r} nicht in der Bibliothek ({', '.join(wl.ENUM_PLATFORM)})")
        print(f"Plattformprofil {data['label']}")
        for g in data["grundsaetze"]:
            print(f"  - {g}")
        for pat, v in sorted(data["muster"].items()):
            print(f"  {pat:<26} {', '.join(v['dienste'])}")
        return 0
    index = wl.load_library_json("branchen", "index.json") or {}
    if args.branche:
        if args.branche not in index:
            wl.fail(f"Branche {args.branche!r} unbekannt. Bekannt: {', '.join(sorted(index))}")
        b = index[args.branche]
        print(f"{b['label']}: {b['beschreibung']}")
        bdir = lib / "branchen" / args.branche
        roles = []
        for p in sorted((bdir / "roles").glob("*.md")):
            meta, _ = pl.parse_frontmatter(p.read_text(encoding="utf-8"), p.name)
            roles.append((meta.get("cluster", ""), meta.get("name", ""), meta.get("level", ""), bool(meta.get("regulated"))))
        current = None
        for cl, name, level, reg in sorted(roles):
            if cl != current:
                print(f"\n  {cl}")
                current = cl
            print(f"    {name} ({level}{', reguliert' if reg else ''})")
        print(f"\nRechtsthemen: {', '.join(b['rechtsthemen'])}\nSysteme: {', '.join(b['systeme'])}")
        return 0
    print("Referenzbibliothek:")
    for bid, b in sorted(index.items()):
        print(f"  {bid:<20} {b['label']:<36} {b['rollen']:>3} Rollen, {b['aufgaben']:>3} Aufgaben")
    print("Details: --branche <id>; Rechtsrahmen: --rechtsraum DE; Plattform: --plattform microsoft|google|mischbetrieb|unabhaengig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
