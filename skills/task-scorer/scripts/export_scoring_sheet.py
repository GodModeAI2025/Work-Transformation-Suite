#!/usr/bin/env python3
"""
export_scoring_sheet.py — schreibt alle (noch) unbewerteten Aufgaben als
Bewertungsvorlage nach 20_graph/scores_todo.json, in fester Reihenfolge.

Aufruf:
    python3 <skill>/scripts/export_scoring_sheet.py --project ./mein-projekt [--all]

Claude füllt die Vorlage aus (jede Aufgabe: sechs Zahlen 0..10 und eine Begründung)
und speichert sie als 20_graph/scores.json. Danach: score_roles.py.

--all  exportiert auch bereits bewertete Aufgaben (für eine Neubewertung mit --force).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

TEMPLATE = {
    "automation_ai": None,
    "automation_physical": None,
    "human_judgment": None,
    "productivity_boost": None,
    "data_readiness": None,
    "consequence_of_error": None,
    "rationale": "",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    roles = wl.index_by_id(graph["roles"])
    clusters = wl.index_by_id(graph["job_clusters"])
    skills = wl.index_by_id(graph["skills"])

    todo = {}
    tasks = sorted(
        graph["tasks"],
        key=lambda t: (clusters[roles[t["role_id"]]["cluster_id"]]["name"], roles[t["role_id"]]["name"], -t["share_of_time"], t["name"]),
    )
    for t in tasks:
        if t.get("scores") and not args.all:
            continue
        r = roles[t["role_id"]]
        todo[t["id"]] = {
            "_context": {
                "role": r["name"],
                "cluster": clusters[r["cluster_id"]]["name"],
                "archetype": r.get("archetype"),
                "regulated": r.get("regulated", False),
                "task": t["name"],
                "description": t.get("description", ""),
                "workflow_steps": t.get("workflow_steps", []),
                "share_of_time": t["share_of_time"],
                "frequency": t["frequency"],
                "nature": t["nature"],
                "skills": sorted(skills[s]["name"] for s in t.get("skill_ids", []) if s in skills),
            },
            **dict(TEMPLATE),
        }
    out = project / wl.DIR_GRAPH / "scores_todo.json"
    # Reihenfolge der Aufgaben bewusst NICHT nach ID sortieren: Claude soll rollenweise bewerten.
    import json

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(todo, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Geschrieben: {wl.relpath(out)} ({len(todo)} Aufgaben zu bewerten, {len(graph['tasks']) - len(todo)} bereits bewertet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
