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

HANDOVER_LABEL = wl.COLLAB_HANDOVER_LABEL
W_HANDOVER, W_POSITION, W_UNIT = wl.COLLAB_W_HANDOVER, wl.COLLAB_W_POSITION, wl.COLLAB_W_UNIT
derive = wl.collaboration_pairs


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
