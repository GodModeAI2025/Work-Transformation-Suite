#!/usr/bin/env python3
"""
import_levels.py — ordnet Rollen über ihr Level einen Kostensatz zu und hält die Level-Struktur fest.

Aufruf:
    python3 <skill>/scripts/import_levels.py --project ./mein-projekt [--file 00_input/levels.csv]

CSV (Trennzeichen ;), Standardpfad 00_input/levels.csv:
    level;label;day_rate_eur;description
    Sachbearbeitung;EG 7–9;420;Ausführende Fachaufgaben
    Teamleitung;EG 12;640;Fachliche und disziplinarische Führung

level          wie `roles[].level` im Graphen (Groß-/Kleinschreibung egal)
day_rate_eur   Planwert Vollkosten je Arbeitstag. Keine Gehälter einzelner Personen.

Wirkung: Jede Rolle mit passendem Level und ohne eigenen `day_rate_eur` bekommt den Satz des Levels. Ein gesetzter
Wert (Override) bleibt unberührt. Daraus rechnet die Suite den geschätzten Jahreswert der Reichweite und der
auffangbaren FTE — als Schätzung gekennzeichnet. Level ohne Treffer und Rollen ohne Level werden gemeldet.

Der Import schreibt `meta.levels` (Struktur) und `roles[].day_rate_source: "level"`, damit erkennbar bleibt, woher
der Satz kommt. Der Graph ist danach ein Stand wie jeder andere (neue Version).
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
    src = project / (args.file or f"{wl.DIR_INPUT}/levels.csv")
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt")
    problems: list[str] = []
    levels: dict[str, dict] = {}
    for i, row in enumerate(wl.read_csv(src), start=2):
        name = (row.get("level") or "").strip()
        if not name:
            continue
        raw = (row.get("day_rate_eur") or "").strip().replace(",", ".")
        rate = None
        if raw:
            try:
                rate = float(raw)
            except ValueError:
                problems.append(f"Zeile {i}: day_rate_eur {raw!r} keine Zahl")
                continue
            if rate < 0:
                problems.append(f"Zeile {i}: day_rate_eur negativ")
                continue
        levels[wl.normalize_name(name)] = {"level": name, "label": (row.get("label") or "").strip(),
                                           "day_rate_eur": rate, "description": (row.get("description") or "").strip()}
    set_n = kept = nolevel = nomatch = 0
    unmatched = set()
    for r in graph["roles"]:
        lv = (r.get("level") or "").strip()
        if not lv:
            nolevel += 1
            continue
        hit = levels.get(wl.normalize_name(lv))
        if not hit or hit["day_rate_eur"] is None:
            nomatch += 1
            unmatched.add(lv)
            continue
        if r.get("day_rate_eur") is not None and r.get("day_rate_source") != "level":
            kept += 1
            continue
        r["day_rate_eur"] = hit["day_rate_eur"]
        r["day_rate_source"] = "level"
        set_n += 1
    graph["meta"]["levels"] = [levels[k] for k in sorted(levels)]
    for p in problems:
        print(f"HINWEIS  {p}")
    if nolevel:
        print(f"HINWEIS  {nolevel} Rollen ohne Level — kein Satz zugeordnet")
    if unmatched:
        print("HINWEIS  Level ohne Eintrag in der Tabelle: " + ", ".join(sorted(unmatched)))
    errors, _w = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "levels")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Level={len(levels)} Sätze gesetzt={set_n} "
          f"eigene Werte behalten={kept} ohne Treffer={nomatch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
