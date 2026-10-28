#!/usr/bin/env python3
"""
import_usecases.py — liest das Register der eigenen Use Cases und ordnet sie Aufgaben zu.

Aufruf:
    python3 <skill>/scripts/import_usecases.py --project ./mein-projekt [--file 00_input/usecases.csv]

CSV (Trennzeichen ;), Standardpfad 00_input/usecases.csv:
    name;description;owner;status;value_eur_per_year;tasks
    Zählerausbau prüfen;Marktlokation gegen Ausbau abgleichen;IT Forderungsmanagement;pilot;120000;Forderungsmanager > Zählerausbau mit Marktlokationsdaten vergleichen

tasks   Aufgaben, mit | getrennt. Form „Rolle > Aufgabe“ (Namen wie im Graphen) oder die
        Aufgaben-ID ta_…. Unbekannte Einträge werden gemeldet und übersprungen.
status  idea | building | pilot | live (Freitext, wird nur angezeigt)
value_eur_per_year  vom Use-Case-Team genannter Wert. Er bleibt eine Angabe des Teams;
        die Suite rechnet daneben ihren eigenen Schätzwert (reach.md).

Das Register beantwortet zwei Fragen: Für wie viele Rollen und FTE gilt dieser Use Case,
und welche hochwertigen Prozesse hat bisher niemand angefragt (Blindflecken).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", default=None)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / (args.file or f"{wl.DIR_INPUT}/usecases.csv")
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt")
    roles = wl.index_by_id(graph["roles"])
    tasks = wl.index_by_id(graph["tasks"])
    by_name = {(wl.normalize_name(roles[t["role_id"]]["name"]), wl.normalize_name(t["name"])): t["id"]
               for t in graph["tasks"] if t["role_id"] in roles}
    problems: list[str] = []
    usecases = []
    for i, row in enumerate(wl.read_csv(src), start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        task_ids = []
        for ref in (row.get("tasks") or "").split("|"):
            ref = ref.strip()
            if not ref:
                continue
            if ref in tasks:
                task_ids.append(ref)
                continue
            role, _, task = ref.partition(">")
            tid = by_name.get((wl.normalize_name(role), wl.normalize_name(task)))
            if tid:
                task_ids.append(tid)
            else:
                problems.append(f"Zeile {i}: Aufgabe {ref!r} nicht im Graphen")
        value = None
        raw = (row.get("value_eur_per_year") or "").strip().replace(",", ".")
        if raw:
            try:
                value = float(raw)
            except ValueError:
                problems.append(f"Zeile {i}: value_eur_per_year {raw!r} keine Zahl")
        usecases.append({
            "id": wl.make_id("usecase", name),
            "name": name,
            "description": (row.get("description") or "").strip(),
            "owner": (row.get("owner") or "").strip(),
            "status": (row.get("status") or "").strip() or "idea",
            "value_eur_per_year": value,
            "task_ids": sorted(set(task_ids)),
            "agent_ids": [],
        })
    graph["usecases"] = usecases
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "usecases")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Use Cases={len(usecases)} Hinweise={len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
