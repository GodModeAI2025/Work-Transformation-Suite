#!/usr/bin/env python3
"""
run_pipeline.py — führt die deterministischen Schritte der Suite in fester
Reihenfolge aus und meldet, wo Claude (oder ein Mensch) als Nächstes eingreifen muss.

Aufruf:
    python3 <skill>/scripts/run_pipeline.py --project ./mein-projekt --skills ../
        [--until builder|processes|scorer|mapper|redesign|dashboard] [--stamp "..."]

--skills  Ordner, in dem die Skills liegen (work-graph-builder, task-scorer, agent-mapper,
          process-redesigner, transformation-dashboard). Standard: Elternordner dieses Skills.

Der Ablauf hält an, wenn ein Eingabe-Artefakt fehlt, das nur Claude erzeugen kann
(Extraktionsdateien, scores.json, agents.json, blueprints.json, process_value.json), und
sagt genau, was fehlt. So bleibt die Pipeline reproduzierbar: Skripte rechnen, Claude
urteilt, nichts vermischt sich.

Zwei Modi, ein Ablauf:

- **Diagnosemodus** (Schema 1.0 und 1.1): Rollen, Aufgaben, Skills, Bewertung, Agenten,
  Dashboard. Das ist der vollständige Ablauf, wenn keine Prozesse erfasst sind.
- **Redesignmodus** (ab Schema 1.1, sobald 10_extraction/process_*.json vorliegt):
  zusätzlich Prozessebene, Soll-Szenarien, Prozesswert, Piloten und Ist/Soll-Dashboard.

Der Redesignmodus schaltet sich selbst ein, sobald es Prozesse gibt. Ohne sie läuft alles
wie bisher — ein Projekt darf in der Diagnose bleiben.
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
    ap.add_argument("--skills", default=None, help="Ordner mit den Skills (Standard: ../ relativ zu diesem Skill)")
    ap.add_argument("--until", choices=["builder", "processes", "scorer", "mapper", "redesign", "dashboard"],
                    default="dashboard")
    ap.add_argument("--skip-redesign", action="store_true",
                    help="Prozessredesign überspringen, auch wenn Prozesse erfasst sind")
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
    order = ["builder", "processes", "scorer", "mapper", "redesign", "dashboard"]
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

    # 1b Prozessebene (optional). Ohne process_*.json bleibt das Projekt im Diagnosemodus.
    process_files = sorted((project / wl.DIR_EXTRACTION).glob("process_*.json"))
    if process_files:
        if run([py, script("work-graph-builder", "build_processes.py"), "--project", proj], cwd):
            return 2
    if stop == 1:
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
    if stop == 2:
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
    graph = wl.load_latest_graph(project)
    cmd = [py, script("agent-mapper", "compute_coverage.py"), "--project", proj]
    if graph.get("processes"):
        # Im Redesignmodus darf ein Prozessschritt mehrere Fähigkeiten kombinieren.
        cmd.append("--shared-tasks")
    if run(cmd, cwd):
        return 2
    if stop == 3:
        return 0

    # 4 Redesign (nur mit Prozessebene)
    graph = wl.load_latest_graph(project)
    if not graph.get("processes"):
        print("HINWEIS: Keine Prozesse erfasst — das Projekt läuft im Diagnosemodus. "
              "Für den Redesignmodus Prozesse aufnehmen "
              "(work-graph-builder/references/process-format.md) und erneut starten.")
    elif args.skip_redesign:
        print("HINWEIS: Prozessredesign übersprungen (--skip-redesign).")
    else:
        blueprints = project / wl.DIR_GRAPH / "blueprints.json"
        if not blueprints.exists():
            run([py, script("process-redesigner", "export_process_candidates.py"), "--project", proj], cwd)
            print(f"STOPP: keine {wl.relpath(blueprints)}. Nächster Schritt für Claude: Skill "
                  "process-redesigner, je priorisiertem Prozess drei Szenarien entwerfen "
                  "(references/redesign-rules.md, references/blueprint-format.md).")
            return 3
        if run([py, script("process-redesigner", "build_blueprints.py"), "--project", proj], cwd):
            return 2
        rc = run([py, script("process-redesigner", "validate_blueprints.py"), "--project", proj], cwd)
        if rc >= 2:
            print("STOPP: Die Soll-Entwürfe verstoßen gegen die Redesign-Regeln. "
                  "Nächster Schritt für Claude: Meldungen abarbeiten, blueprints.json korrigieren.")
            return 3
        value = project / wl.DIR_GRAPH / "process_value.json"
        rc = run([py, script("process-redesigner", "score_processes.py"), "--project", proj], cwd)
        if rc == 3:
            print(f"STOPP: {wl.relpath(value)} fehlt. Nächster Schritt für Claude: Skill "
                  "process-redesigner, die neun Faktoren je Prozess bewerten "
                  "(references/value-rubric.md).")
            return 3
        if rc:
            return 2
        # Pilotplanung hält die Pipeline nicht an: Sie braucht einen geprüften Blueprint,
        # und der entsteht erst nach dem Fachreview. Fehlt sie, gibt es nur einen Hinweis.
        rc = run([py, script("process-redesigner", "make_experiments.py"), "--project", proj], cwd)
        if rc == 3:
            print("HINWEIS: Pilotplanung offen. 20_graph/experiments_todo.json schärfen und als "
                  "experiments.json speichern (references/experiment-format.md).")
        elif rc:
            return 2
        run([py, script("process-redesigner", "compare_scenarios.py"), "--project", proj], cwd)

    # Verträge erst hier prüfen, nicht schon beim Mapper: validate_contracts.py hält einen
    # Vertrag gegen die Schritte, die der Agent ausführt — und Blueprint-Schritte gibt es
    # erst nach dem Redesign. Beim ersten Lauf eines Projekts meldete die Prüfung sonst für
    # jeden Pilot-Agenten, ihm sei keine Arbeit zugewiesen, obwohl der Entwurf das gleich
    # darauf tut.
    graph = wl.load_latest_graph(project)
    if any(isinstance(a.get("contract"), dict) for a in graph.get("agents", [])):
        run([py, script("agent-mapper", "validate_contracts.py"), "--project", proj], cwd)
        run([py, script("agent-mapper", "export_contracts.py"), "--project", proj], cwd)

    # Freigaben zuletzt: decisions.csv ist die Wahrheit über Status, und build_blueprints.py
    # baut die Blueprints vorher aus blueprints.json neu auf. Liefe die Governance davor,
    # würde jede Freigabe beim nächsten Lauf still überschrieben.
    if (project / wl.DIR_REVIEW / "decisions.csv").exists():
        if run([py, script("work-graph-builder", "apply_governance.py"), "--project", proj], cwd):
            return 2
    if stop == 4:
        return 0

    # 5 Dashboard
    cmd = [py, script("transformation-dashboard", "build_dashboard.py"), "--project", proj]
    if args.stamp:
        cmd += ["--stamp", args.stamp]
    if args.title:
        cmd += ["--title", args.title]
    return run(cmd, cwd)


if __name__ == "__main__":
    sys.exit(main())
