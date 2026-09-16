#!/usr/bin/env python3
"""
run_pipeline.py — führt die deterministischen Schritte der Suite in fester
Reihenfolge aus und meldet, wo Claude (oder ein Mensch) als Nächstes eingreifen muss.

Aufruf:
    python3 <skill>/scripts/run_pipeline.py --project ./mein-projekt --skills ../ [--until scorer|mapper|dashboard] [--stamp "..."]

--skills  Ordner, in dem die vier Skills liegen (work-graph-builder, task-scorer,
          agent-mapper, transformation-dashboard). Standard: Elternordner dieses Skills.

Der Ablauf hält an, wenn ein Eingabe-Artefakt fehlt, das nur Claude erzeugen kann
(Extraktionsdateien, scores.json, agents.json), und sagt genau, was fehlt.
So bleibt die Pipeline reproduzierbar: Skripte rechnen, Claude urteilt, nichts vermischt sich.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def run(cmd: list[str], cwd: Path) -> int:
    print("$ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=str(cwd))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--skills", default=None, help="Ordner mit den vier Skills (Standard: ../ relativ zu diesem Skill)")
    ap.add_argument("--until", choices=["builder", "scorer", "mapper", "dashboard"], default="dashboard")
    ap.add_argument("--stamp", default=None)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent  # Skill-Ordner work-transformation
    skills = Path(args.skills).resolve() if args.skills else here.parent
    project = wl.resolve_project(args.project)
    cwd = Path.cwd()
    py = sys.executable

    def script(skill: str, name: str) -> str:
        p = skills / skill / "scripts" / name
        if not p.exists():
            wl.fail(f"Skript fehlt: {wl.relpath(p)} (--skills prüfen)")
        return wl.relpath(p, cwd)

    proj = wl.relpath(project, cwd)
    order = ["builder", "scorer", "mapper", "dashboard"]
    stop = order.index(args.until)

    # 1 Architekt
    ex = sorted((project / wl.DIR_EXTRACTION).glob("extract_*.json"))
    if not ex:
        print(f"STOPP: keine Extraktionsdateien in {wl.relpath(project / wl.DIR_EXTRACTION)}. "
              "Nächster Schritt für Claude: Skill work-graph-builder, Quellen aus 00_input/ extrahieren.")
        return 3
    if run([py, script("work-graph-builder", "build_graph.py"), "--project", proj], cwd):
        return 2
    if (project / wl.DIR_REVIEW / "overrides.csv").exists():
        if run([py, script("work-graph-builder", "apply_overrides.py"), "--project", proj], cwd):
            return 2
    if (project / wl.DIR_INPUT / "positions.csv").exists():
        if run([py, script("work-graph-builder", "import_positions.py"), "--project", proj], cwd):
            return 2
    run([py, script("work-graph-builder", "make_review_list.py"), "--project", proj], cwd)
    if stop == 0:
        return 0

    # 2 Scorer
    graph = wl.load_latest_graph(project)
    unscored = [t for t in graph["tasks"] if not t.get("scores")]
    scores = project / wl.DIR_GRAPH / "scores.json"
    covered = set(wl.read_json(scores).keys()) if scores.exists() else set()
    missing = [t for t in unscored if t["id"] not in covered]
    if missing:
        run([py, script("task-scorer", "export_scoring_sheet.py"), "--project", proj], cwd)
        print(f"STOPP: {len(missing)} Aufgaben ohne Bewertung, die auch nicht in {wl.relpath(scores)} stehen. "
              "Nächster Schritt für Claude: Skill task-scorer, 20_graph/scores_todo.json ausfüllen und die Einträge in scores.json ergänzen.")
        return 3
    if run([py, script("task-scorer", "score_roles.py"), "--project", proj], cwd):
        return 2
    if stop == 1:
        return 0

    # 3 Mapper
    agents = project / wl.DIR_GRAPH / "agents.json"
    graph = wl.load_latest_graph(project)
    automatable = {t["id"] for t in graph["tasks"] if t.get("mode") in ("ai_assisted", "agent_delegated")}
    assigned: set[str] = set()
    if agents.exists():
        for a in wl.read_json(agents):
            assigned.update(a.get("task_ids", []))
    open_tasks = sorted(automatable - assigned)
    if not agents.exists() or open_tasks:
        run([py, script("agent-mapper", "export_agent_candidates.py"), "--project", proj], cwd)
        what = f"keine {wl.relpath(agents)}" if not agents.exists() else f"{len(open_tasks)} automatisierbare Aufgaben ohne Agent in {wl.relpath(agents)}"
        print(f"STOPP: {what}. Nächster Schritt für Claude: Skill agent-mapper, "
              "Kandidaten aus 20_graph/agents_todo.json zu Agenten bündeln bzw. bestehenden Agenten zuordnen.")
        return 3
    if run([py, script("agent-mapper", "compute_coverage.py"), "--project", proj], cwd):
        return 2
    if stop == 2:
        return 0

    # 4 Dashboard
    cmd = [py, script("transformation-dashboard", "build_dashboard.py"), "--project", proj]
    if args.stamp:
        cmd += ["--stamp", args.stamp]
    if args.title:
        cmd += ["--title", args.title]
    return run(cmd, cwd)


if __name__ == "__main__":
    sys.exit(main())
