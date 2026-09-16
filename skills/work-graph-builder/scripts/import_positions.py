#!/usr/bin/env python3
"""
import_positions.py — ordnet Stellen (Positionen) den Rollen des Graphen zu und
leitet daraus Headcounts je Rolle ab. Löst das Problem, dass Prozessrollen keine
Stellen sind: Eine Person trägt oft mehrere Rollen mit Anteilen.

Aufruf:
    python3 <skill>/scripts/import_positions.py --project ./mein-projekt [--file 00_input/positions.csv]

CSV-Format (Trennzeichen ;), Standardpfad 00_input/positions.csv:
    position_id;title;org_unit;role;share
    P0001;Systembetreuer SAP;IT Betrieb;Administrator;70
    P0001;Systembetreuer SAP;IT Betrieb;Anforderer;30
    P0002;Servicemanager ERP;IT Service;Service Manager;100

role   = Rollenname exakt wie im Graphen (oder Rollen-ID ro_...)
share  = Anteil der Stelle, der auf diese Rolle entfällt (Prozent). Zeilen einer
         Position werden auf 100 normalisiert, wenn die Summe abweicht.

Ergebnis:
- positions[] im Graphen (deterministische IDs aus position_id)
- roles[].headcount_from_positions = Σ share/100 über alle Positionen (Vollzeitäquivalent)
- roles[].headcount wird gesetzt, wenn er leer ist (Override-Werte bleiben unberührt)
- roles[].positions_count = Anzahl Stellen, die die Rolle tragen
Keine Personennamen: Die Datei enthält Stellen, keine Inhaber.
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
    ap.add_argument("--file", default=None, help="CSV relativ zum Projektordner (Standard 00_input/positions.csv)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / (args.file or f"{wl.DIR_INPUT}/positions.csv")
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt")
    rows = wl.read_csv(src)
    roles_by_name = {wl.normalize_name(r["name"]): r for r in graph["roles"]}
    roles_by_id = wl.index_by_id(graph["roles"])
    problems: list[str] = []

    # Zeilen je Position sammeln
    per_pos: dict[str, dict] = {}
    for i, row in enumerate(rows, start=2):
        pid = (row.get("position_id") or "").strip()
        rname = (row.get("role") or "").strip()
        if not pid or not rname:
            continue
        role = roles_by_id.get(rname) or roles_by_name.get(wl.normalize_name(rname))
        if not role:
            problems.append(f"Zeile {i}: Rolle '{rname}' nicht im Graphen")
            continue
        try:
            share = float(str(row.get("share", "100")).replace(",", "."))
        except ValueError:
            problems.append(f"Zeile {i}: share '{row.get('share')}' keine Zahl")
            continue
        pos = per_pos.setdefault(pid, {"id": wl.make_id("position", pid), "position_id": pid,
                                        "title": (row.get("title") or "").strip(),
                                        "org_unit": (row.get("org_unit") or "").strip(), "roles": {}})
        pos["roles"][role["id"]] = pos["roles"].get(role["id"], 0.0) + share

    positions = []
    fte: dict[str, float] = {}
    count: dict[str, int] = {}
    for pid in sorted(per_pos):
        pos = per_pos[pid]
        total = sum(pos["roles"].values())
        if total <= 0:
            continue
        shares = {rid: wl.round1(v * 100.0 / total) for rid, v in pos["roles"].items()} if abs(total - 100) > 0.51 else {rid: wl.round1(v) for rid, v in pos["roles"].items()}
        positions.append({"id": pos["id"], "position_id": pid, "title": pos["title"], "org_unit": pos["org_unit"],
                          "role_id": sorted(shares, key=lambda r: (-shares[r], r))[0],
                          "role_shares": [{"role_id": rid, "share": shares[rid]} for rid in sorted(shares)]})
        for rid, sh in shares.items():
            fte[rid] = fte.get(rid, 0.0) + sh / 100.0
            count[rid] = count.get(rid, 0) + 1

    graph["positions"] = positions
    set_hc = 0
    for r in graph["roles"]:
        if r["id"] in fte:
            r["headcount_from_positions"] = wl.round1(fte[r["id"]])
            r["positions_count"] = count[r["id"]]
            if r.get("headcount") is None:
                r["headcount"] = int(round(fte[r["id"]])) if fte[r["id"]] >= 0.5 else 1
                set_hc += 1
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "positions")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Positionen={len(positions)} Rollen mit Headcount aus Positionen={set_hc} Hinweise={len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
