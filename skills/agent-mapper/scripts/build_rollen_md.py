#!/usr/bin/env python3
"""
build_rollen_md.py — erzeugt die Rollen.md, die ein Agenten-Harness als Kontext lädt, für eine oder mehrere Rollen.

Aufruf:
    python3 <skill>/scripts/build_rollen_md.py --project ./mein-projekt --role "Forderungsmanager"
    python3 <skill>/scripts/build_rollen_md.py --project ./mein-projekt --role "Forderungsmanager" --role "Kreditprüfer"
    python3 <skill>/scripts/build_rollen_md.py --project ./mein-projekt --role "Forderungsmanager;Kreditprüfer"
    python3 <skill>/scripts/build_rollen_md.py --project ./mein-projekt --all [--split]

Ausgabe:
    40_output/rollen_md/Rollen.md             eine Datei, Firmenprofil einmal, dann je Rolle die Abschnitte 2 bis 5
    40_output/rollen_md/Rollen_<rolle>.md     mit --split: je Rolle eine eigene Datei (mit Firmenprofil)

Die fünf Abschnitte: 1) Firmenprofil, 2) Rollenprofil, 3) Team-Kontext, 4) Prioritäten & Ziele, 5) Arbeits- & Kommunikationsstil.
Vorbelegt ist, was der Arbeitsgraph weiß; alles andere steht als „❓ offen“ und wird nicht erfunden. Ein erneuter Lauf
überschreibt keine Datei, die inzwischen bearbeitet wurde (neuer Stand als `.vorschlag`). Das Interview, das die offenen
Felder füllt, liefert `build_role_setup.py` im Setup-Paket.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import export_skill as es  # noqa: E402
import build_role_setup as brs  # noqa: E402
import rollen_md as rm  # noqa: E402


def resolve(graph, refs):
    found, missing = [], []
    for ref in refs:
        for part in ref.split(";"):
            part = part.strip()
            if not part:
                continue
            r = brs.find_role(graph, part)
            if r is None:
                missing.append(part)
            elif r not in found:
                found.append(r)
    return found, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--role", action="append", default=[], help="Rollenname oder ID; mehrfach oder mit ; getrennt")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--split", action="store_true", help="je Rolle eine eigene Datei")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    if args.all:
        roles = list(graph["roles"])
    elif args.role:
        roles, missing = resolve(graph, args.role)
        if missing:
            hints = []
            for m in missing:
                sim = brs.similar_roles(graph, m)
                hints.append(f"{m!r}" + (f" (meinst du: {', '.join(sim)}?)" if sim else ""))
            wl.fail("Rolle nicht eindeutig gefunden: " + "; ".join(hints) + ". Mit build_role_setup.py --list siehst du alle Rollen.")
    else:
        wl.fail("Rolle angeben (--role \"Name\", mehrfach möglich), oder --all")
    if not roles:
        wl.fail("Keine Rollen im Graphen")
    files: dict[str, str] = {}
    filled = open_n = 0
    if args.split:
        for r in roles:
            text, f, o = rm.compose(graph, [r], title=f"Rollen — {r['name']}")
            files[f"Rollen_{es.slug(r['name'])}.md"] = text
            filled += f
            open_n += o
    else:
        text, filled, open_n = rm.compose(graph, roles)
        files["Rollen.md"] = text
    files["_meta"] = json.dumps({"filled": filled, "open": open_n, "roles": [r["name"] for r in sorted(roles, key=lambda r: r["name"])]}, sort_keys=True)
    out = project / wl.DIR_OUTPUT / "rollen_md"
    written, proposed, unchanged = brs.write_package(out, files)
    print(f"Geschrieben: {wl.relpath(out)} | Rollen={len(roles)} Dateien={len([k for k in files if not k.startswith('_')])} "
          f"vorbelegt={filled} offen={open_n} neu={len(written)} unverändert={len(unchanged)} Vorschläge={len(proposed)}")
    for rel in proposed:
        print(f"HINWEIS  {rel} wurde bearbeitet — neuer Stand als {rel}.vorschlag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
