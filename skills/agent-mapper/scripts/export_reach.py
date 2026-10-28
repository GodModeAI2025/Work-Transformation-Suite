#!/usr/bin/env python3
"""
export_reach.py — „Für wie viele Stellen gilt diese Automatisierung?“ und „Wo fragt
niemand an?“

Aufruf:
    python3 <skill>/scripts/export_reach.py --project ./mein-projekt

Ausgaben (NNN = Graph-Version):
    40_output/reach_vNNN.md    je Agent und Use Case: betroffene Rollen, Zeitanteil, FTE, Wert
    40_output/reach_vNNN.csv   dieselben Zeilen, maschinenlesbar

Der Wert je Rolle entsteht nur, wo ein Tagessatz (`day_rate_eur`) gesetzt ist, und bleibt eine
Schätzung: gebundene Arbeitszeit der abgedeckten Aufgaben × Tagessatz, nicht die Ersparnis.
Blindflecken sind Prozesse im Band „Jetzt“ oder „Als Nächstes“, deren Aufgaben kein Agent
und kein Use Case abdeckt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def _n(x, nd=1):
    return "–" if x is None else f"{x:,.{nd}f}".replace(",", " ")


def render(graph) -> tuple[str, list[dict]]:
    reach = wl.agent_reach(graph)
    spots = wl.blind_spots(graph)
    lines = ["# Reichweite und Blindflecken", "",
             "Je Agent und Use Case die Rollen, deren Aufgaben er abdeckt. „Zeitanteil“ ist die "
             "heute gebundene Arbeitszeit der abgedeckten Aufgaben an der Rolle, „FTE“ der "
             "daraus folgende Umfang bei bekanntem Headcount. Beides beschreibt, **wen es "
             "betrifft** — nicht, was es spart.", ""]
    if not reach:
        lines.append("Noch keine Agenten oder Use Cases.")
    else:
        lines += ["| Typ | Name | Rollen | FTE betroffen | Wert/Jahr (Suite, geschätzt) | Wert/Jahr (Team) |",
                  "|---|---|---:|---:|---:|---:|"]
        for r in reach:
            lines.append(f"| {'Agent' if r['kind'] == 'agent' else 'Use Case'} | {r['name']} | {len(r['roles'])} "
                         f"| {_n(r['fte_total'])} | {_n(r['value_eur_estimated'], 0)} | {_n(r['value_eur_declared'], 0)} |")
        for r in reach:
            if not r["roles"]:
                continue
            lines += ["", f"## {r['name']}", "", "| Rolle | Headcount | Zeitanteil | FTE |", "|---|---:|---:|---:|"]
            for ro in r["roles"]:
                lines.append(f"| {ro['name']} | {_n(ro['headcount'], 0)} | {_n(ro['time_share_pct'])} % | {_n(ro['fte'])} |")
    lines += ["", "## Blindflecken", ""]
    if spots:
        lines += ["Prozesse mit hohem Wert, für die weder ein Agent noch ein Use Case Aufgaben abdeckt. "
                  "Wer nur bedient, was angefragt wird, sieht sie nicht.", "",
                  "| Prozess | Band | Wert | Aufgaben |", "|---|---|---:|---:|"]
        for s in spots:
            lines.append(f"| {s['name']} | {'Jetzt' if s['band'] == 'now' else 'Als Nächstes'} | {_n(s['score'])} | {s['tasks']} |")
    else:
        lines.append("Keine: Jeder Prozess im Band „Jetzt“ oder „Als Nächstes“ hat mindestens einen Agenten "
                     "oder Use Case." if graph.get("processes") else
                     "Ohne erfasste Prozesse lässt sich diese Liste nicht bilden.")
    rows = [{"kind": r["kind"], "id": r["id"], "name": r["name"], "role": ro["name"],
             "headcount": ro["headcount"], "time_share_pct": ro["time_share_pct"], "fte": ro["fte"]}
            for r in reach for ro in r["roles"]]
    return "\n".join(lines) + "\n", rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    version = int(graph.get("meta", {}).get("version", 0))
    md, rows = render(graph)
    out = project / wl.DIR_OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"reach_v{version:03d}.md"
    wl.write_text(md_path, md)
    csv_path = out / f"reach_v{version:03d}.csv"
    wl.write_csv(csv_path, rows, ["kind", "id", "name", "role", "headcount", "time_share_pct", "fte"])
    print(f"Geschrieben: {wl.relpath(md_path)}, {wl.relpath(csv_path)} | Einträge={len(rows)} "
          f"Blindflecken={len(wl.blind_spots(graph))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
