#!/usr/bin/env python3
"""
import_adoption.py — liest den Nutzungsstand je Agent oder Use Case und Rolle und
speichert ihn nur aggregiert.

Aufruf:
    python3 <skill>/scripts/import_adoption.py --project ./mein-projekt [--file 00_input/adoption.csv] [--min-group 5]

CSV (Trennzeichen ;), Standardpfad 00_input/adoption.csv:
    agent;role;prioritized;building;in_use
    Mahnwesen-Agent;Forderungsmanager;12;6;4

agent   Name eines Agenten oder Use Cases (oder seine ID)
role    Rollenname (oder ID)
prioritized / building / in_use   Anzahl Stellen je Stand. Eine Stelle zählt im höchsten
        erreichten Stand. Keine Namen, keine Einzelwerte.

Datenschutz als Regel, nicht als Hinweis: Hat die Rolle weniger als --min-group Stellen
(Standard: ADOPTION_MIN_GROUP = 5), wird der Satz unterdrückt gespeichert — ohne Zahlen,
nur mit dem Vermerk „unterdrückt“. Eine Quote für drei Stellen ist eine Aussage über drei
Menschen, und das wäre Leistungskontrolle. Der Validator lehnt jeden nicht unterdrückten
Satz unter der Grenze ab. Die Suite wertet nur Rolle × Agent aus, nie Person × Agent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402


def _count(raw: str):
    s = (raw or "").strip()
    if not s:
        return 0
    return int(float(s.replace(",", ".")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", default=None)
    ap.add_argument("--min-group", type=int, default=wl.ADOPTION_MIN_GROUP)
    args = ap.parse_args()
    if args.min_group < wl.ADOPTION_MIN_GROUP:
        wl.fail(f"--min-group darf {wl.ADOPTION_MIN_GROUP} nicht unterschreiten")
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / (args.file or f"{wl.DIR_INPUT}/adoption.csv")
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt")
    roles_by_name = {wl.normalize_name(r["name"]): r for r in graph["roles"]}
    roles_by_id = wl.index_by_id(graph["roles"])
    agents_by_name = {wl.normalize_name(a["name"]): a for a in graph["agents"]}
    agents_by_id = wl.index_by_id(graph["agents"])
    uc_by_name = {wl.normalize_name(u["name"]): u for u in graph["usecases"]}
    uc_by_id = wl.index_by_id(graph["usecases"])
    problems: list[str] = []
    merged: dict[tuple, dict] = {}
    for i, row in enumerate(wl.read_csv(src), start=2):
        an, rn = (row.get("agent") or "").strip(), (row.get("role") or "").strip()
        if not an or not rn:
            continue
        role = roles_by_id.get(rn) or roles_by_name.get(wl.normalize_name(rn))
        agent = agents_by_id.get(an) or agents_by_name.get(wl.normalize_name(an))
        usecase = None if agent else (uc_by_id.get(an) or uc_by_name.get(wl.normalize_name(an)))
        if not role:
            problems.append(f"Zeile {i}: Rolle {rn!r} nicht im Graphen")
            continue
        if not agent and not usecase:
            problems.append(f"Zeile {i}: {an!r} ist weder Agent noch Use Case")
            continue
        try:
            counts = {k: _count(row.get(k)) for k in ("prioritized", "building", "in_use")}
        except ValueError:
            problems.append(f"Zeile {i}: Zahlen nicht lesbar")
            continue
        if min(counts.values()) < 0:
            problems.append(f"Zeile {i}: negative Anzahl")
            continue
        key = (agent["id"] if agent else None, usecase["id"] if usecase else None, role["id"])
        cur = merged.setdefault(key, {k: 0 for k in counts})
        for k, v in counts.items():
            cur[k] += v

    out, suppressed = [], 0
    for (aid, uid, rid), counts in sorted(merged.items(), key=lambda kv: tuple(x or "" for x in kv[0])):
        role = roles_by_id[rid]
        population = role.get("positions_count") or wl.role_headcount(role)
        population = int(round(float(population))) if population is not None else sum(counts.values())
        entry = {"id": wl.make_id("adoption", aid or uid, rid), "role_id": rid,
                 "agent_id": aid, "usecase_id": uid, "group_size": population}
        if population < args.min_group or sum(counts.values()) > population:
            if sum(counts.values()) > population:
                problems.append(f"Rolle {role['name']!r}: mehr gemeldete Stellen als vorhanden — Satz unterdrückt")
            entry["suppressed"] = True
            suppressed += 1
        else:
            entry.update(counts)
        out.append(entry)
    graph["adoption"] = out
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "adoption")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Sätze={len(out)} unterdrückt={suppressed} Hinweise={len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
