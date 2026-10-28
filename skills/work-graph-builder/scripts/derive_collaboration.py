#!/usr/bin/env python3
"""
derive_collaboration.py — leitet aus Prozesskanten und Positionslisten ab, welche Rollen
miteinander arbeiten, und womit das belegt ist.

Aufruf:
    python3 <skill>/scripts/derive_collaboration.py --project ./mein-projekt

Ausgabe:
    30_review/zusammenarbeit_vNNN.md    Rollenpaare mit Belegen
    30_review/zusammenarbeit_vNNN.csv   dieselben Zeilen

Drei Belege, nach Stärke geordnet:
1. **Übergabe im Prozess** — eine Prozesskante zwischen Schritten zweier Rollen. Der stärkste Beleg:
   Hier wird Arbeit tatsächlich weitergereicht (Art der Übergabe steht dabei).
2. **Gemeinsame Stelle** — dieselbe Position trägt beide Rollen.
3. **Gleiche Organisationseinheit** — beide Rollen sitzen in derselben Einheit. Der schwächste Beleg: Er zeigt
   Nähe, nicht Zusammenarbeit.

Warum: Eine Stellenbeschreibung nennt selten, mit wem man arbeitet, und Prozesshäuser zeigen nur einen
Teil. Aus einer Positionsliste lässt sich Zusammenarbeit zumindest wahrscheinlich machen. Die Ausgabe ist
eine Vorlage für das Gespräch mit dem Fachbereich („Arbeitet ihr wirklich mit denen?“), kein Befund. Der
Graph bleibt unverändert.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

HANDOVER_LABEL = {"none": "keine", "system": "System", "document": "Dokument", "email": "E-Mail", "ticket": "Ticket",
                   "call": "Telefon", "meeting": "Meeting"}
W_HANDOVER, W_POSITION, W_UNIT = 3, 2, 1


def derive(graph: dict[str, Any]) -> list[dict[str, Any]]:
    roles = wl.index_by_id(graph["roles"])
    steps = wl.index_by_id(graph.get("process_steps", []))
    pairs: dict[tuple[str, str], dict[str, Any]] = {}

    def entry(a: str, b: str) -> dict[str, Any]:
        key = (a, b) if a < b else (b, a)
        return pairs.setdefault(key, {"a": key[0], "b": key[1], "handovers": 0, "types": {}, "processes": set(),
                                      "positions": set(), "units": set()})

    for e in graph.get("process_edges", []):
        s1, s2 = steps.get(e.get("from_step_id")), steps.get(e.get("to_step_id"))
        if not s1 or not s2:
            continue
        r1, r2 = s1.get("role_id"), s2.get("role_id")
        if r1 in roles and r2 in roles and r1 != r2:
            p = entry(r1, r2)
            p["handovers"] += 1
            ht = e.get("handover") or "none"
            p["types"][ht] = p["types"].get(ht, 0) + 1
            p["processes"].add(e.get("process_id"))
    processes = wl.index_by_id(graph.get("processes", []))
    units: dict[str, set[str]] = {}
    for pos in graph.get("positions", []):
        rids = sorted(rs["role_id"] for rs in pos.get("role_shares", []) if rs["role_id"] in roles)
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                entry(rids[i], rids[j])["positions"].add(pos.get("position_id") or pos["id"])
        if pos.get("org_unit"):
            units.setdefault(pos["org_unit"], set()).update(rids)
    for unit, rids in units.items():
        rl = sorted(rids)
        for i in range(len(rl)):
            for j in range(i + 1, len(rl)):
                entry(rl[i], rl[j])["units"].add(unit)

    out = []
    for p in pairs.values():
        strength = W_HANDOVER * p["handovers"] + W_POSITION * len(p["positions"]) + W_UNIT * len(p["units"])
        out.append({
            "role_a": roles[p["a"]]["name"], "role_b": roles[p["b"]]["name"], "role_a_id": p["a"], "role_b_id": p["b"],
            "handovers": p["handovers"],
            "handover_types": ", ".join(f"{HANDOVER_LABEL.get(k, k)} {v}×" for k, v in sorted(p["types"].items())),
            "processes": "; ".join(sorted(processes[x]["name"] for x in p["processes"] if x in processes)),
            "shared_positions": len(p["positions"]), "shared_units": "; ".join(sorted(p["units"])),
            "strength": strength,
        })
    out.sort(key=lambda r: (-r["strength"], r["role_a"], r["role_b"]))
    return out


def render(rows: list[dict[str, Any]], graph: dict[str, Any]) -> str:
    lines = ["# Zusammenarbeit der Rollen", "",
             "Abgeleitet aus Prozesskanten und Positionslisten. Eine Übergabe im Prozess ist der stärkste Beleg, eine gleiche "
             "Organisationseinheit der schwächste (Nähe, nicht Zusammenarbeit). Das ist eine Vorlage für das Gespräch mit dem "
             "Fachbereich, kein Befund.", ""]
    if not rows:
        lines += ["Keine Belege: Es gibt weder Prozesskanten zwischen verschiedenen Rollen noch Positionen mit Organisationseinheit. "
                  "Eine Positionsliste (`00_input/positions.csv`) oder eine Prozessaufnahme würde das ändern.", ""]
        return "\n".join(lines) + "\n"
    lines += ["| Rolle A | Rolle B | Übergaben | Art | Prozesse | Gemeinsame Stellen | Gleiche Einheit |", "|---|---|---:|---|---|---:|---|"]
    for r in rows:
        lines.append(f"| {r['role_a']} | {r['role_b']} | {r['handovers']} | {r['handover_types'] or '–'} | {r['processes'] or '–'} "
                     f"| {r['shared_positions']} | {r['shared_units'] or '–'} |")
    have = {r["role_a_id"] for r in rows} | {r["role_b_id"] for r in rows}
    alone = [r["name"] for r in sorted(graph["roles"], key=lambda r: r["name"]) if r["id"] not in have]
    lines += ["", "## Rollen ohne jeden Beleg", ""]
    lines.append(", ".join(alone) if alone else "Keine.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    rows = derive(graph)
    version = int(graph["meta"].get("version", 0))
    md = project / wl.DIR_REVIEW / f"zusammenarbeit_v{version:03d}.md"
    wl.write_text(md, render(rows, graph))
    csv = project / wl.DIR_REVIEW / f"zusammenarbeit_v{version:03d}.csv"
    wl.write_csv(csv, [{k: r[k] for k in ("role_a", "role_b", "handovers", "handover_types", "processes", "shared_positions", "shared_units", "strength")} for r in rows],
                 ["role_a", "role_b", "handovers", "handover_types", "processes", "shared_positions", "shared_units", "strength"])
    print(f"Geschrieben: {wl.relpath(md)} | Rollenpaare={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
