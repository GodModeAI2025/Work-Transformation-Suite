#!/usr/bin/env python3
"""
apply_governance.py — überträgt das Entscheidungslog aus 30_review/decisions.csv in den
Graphen und setzt daraus die Freigabestände von Blueprints, Prozessen und Rollen.

Aufruf:
    python3 <skill>/scripts/apply_governance.py --project ./mein-projekt [--check]

Warum eine CSV und nicht ein Feld im Graphen: Freigaben treffen Menschen, nicht Skripte.
Die CSV liegt neben den Overrides in 30_review/, ist in jeder Tabellenkalkulation lesbar
und wird bei jedem Lauf erneut angewendet. So überlebt eine Freigabe jede Neuberechnung,
und es bleibt nachvollziehbar, wer wann was freigegeben hat — statt dass ein Status
irgendwann im Graphen steht, ohne dass jemand dafür geradesteht.

Spalten (Semikolon getrennt):
    subject_type;subject_id;decision;rationale;decided_by;role;date;supersedes

    subject_type   Sammlung: blueprints, processes, roles, tasks, agents, experiments
    subject_id     ID oder Name des Gegenstands
    decision       approve | reject | defer | revoke
    decided_by     Name der Person, die entschieden hat (Pflicht)
    date           ISO-Datum (Pflicht)
    supersedes     optional die ID einer früheren Entscheidung, die dadurch hinfällig wird

Wirkung von `approve`: blueprints -> status approved, processes/roles/tasks -> approved,
experiments -> ready. `reject` setzt blueprints auf rejected, `revoke` nimmt eine frühere
Freigabe zurück (zurück auf reviewed beziehungsweise generated).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

DECISIONS_FILE = "decisions.csv"
HEADER = "subject_type;subject_id;decision;rationale;decided_by;role;date;supersedes\n"
SUBJECT_TYPES = ["blueprints", "processes", "roles", "tasks", "agents", "experiments"]

APPROVE_STATUS = {
    "blueprints": "approved",
    "processes": "approved",
    "roles": "approved",
    "tasks": "approved",
    "experiments": "ready",
}
REVOKE_STATUS = {
    "blueprints": "reviewed",
    "processes": "reviewed",
    "roles": "reviewed",
    "tasks": "reviewed",
    "experiments": "draft",
}


def apply(graph: dict[str, Any], rows: list) -> tuple[int, list[str]]:
    problems: list[str] = []
    decisions: dict[str, dict] = {}
    applied = 0
    index: dict[str, dict[str, dict]] = {}
    for c in SUBJECT_TYPES:
        table: dict[str, dict] = {}
        for it in graph.get(c, []):
            table[it["id"]] = it
            table[wl.normalize_name(it.get("name", ""))] = it
        index[c] = table

    for n, row in enumerate(rows, start=2):
        stype = str(row.get("subject_type", "")).strip()
        if stype not in SUBJECT_TYPES:
            problems.append(f"Zeile {n}: subject_type {stype!r} unbekannt "
                            f"(erlaubt: {', '.join(SUBJECT_TYPES)})")
            continue
        key = str(row.get("subject_id", "")).strip()
        target = index[stype].get(key) or index[stype].get(wl.normalize_name(key))
        if target is None:
            problems.append(f"Zeile {n}: {stype} {key!r} gibt es nicht")
            continue
        decision = str(row.get("decision", "")).strip()
        if decision not in wl.ENUM_DECISION_TYPE:
            problems.append(f"Zeile {n}: decision {decision!r} ungültig "
                            f"(erlaubt: {', '.join(wl.ENUM_DECISION_TYPE)})")
            continue
        decided_by = str(row.get("decided_by", "")).strip()
        date = str(row.get("date", "")).strip()
        if not decided_by or not date:
            problems.append(f"Zeile {n}: decided_by und date sind Pflicht — eine Freigabe "
                            "ohne Namen und Datum ist keine Freigabe")
            continue
        did = wl.make_id("decision", stype, target["id"], decision, date, decided_by)
        decisions[did] = {
            "id": did,
            "subject_type": stype,
            "subject_id": target["id"],
            "subject_name": target.get("name", ""),
            "decision": decision,
            "rationale": str(row.get("rationale", "")).strip(),
            "decided_by": decided_by,
            "role": str(row.get("role", "")).strip(),
            "date": date,
            "supersedes": str(row.get("supersedes", "")).strip() or None,
        }
        applied += 1

    # Wirkung in zeitlicher Reihenfolge anwenden: die jüngste Entscheidung gewinnt.
    superseded = {d["supersedes"] for d in decisions.values() if d.get("supersedes")}
    effective = [d for d in decisions.values() if d["id"] not in superseded]
    for d in sorted(effective, key=lambda d: (d["date"], d["id"])):
        target = index[d["subject_type"]].get(d["subject_id"])
        if target is None:
            continue
        if d["decision"] == "approve":
            new = APPROVE_STATUS.get(d["subject_type"])
            if new:
                target["status"] = new
        elif d["decision"] == "reject" and d["subject_type"] == "blueprints":
            target["status"] = "rejected"
        elif d["decision"] == "revoke":
            new = REVOKE_STATUS.get(d["subject_type"])
            if new:
                target["status"] = new
        # "defer" ändert keinen Status; es hält nur fest, dass bewusst nicht entschieden wurde.

    graph["decisions"] = sorted(decisions.values(), key=lambda d: d["id"])
    return applied, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--check", action="store_true", help="nur prüfen, nichts schreiben")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    path = project / wl.DIR_REVIEW / DECISIONS_FILE
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        wl.write_text(path, HEADER, newline="")
        print(f"Angelegt: {wl.relpath(path)} (leer). Freigaben dort eintragen, "
              "dann dieses Skript erneut laufen lassen.")
        return 0
    rows = wl.read_csv(path)
    applied, problems = apply(graph, rows)
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    if args.check:
        print(f"Probelauf: {applied} Entscheidung(en) gültig, nichts geschrieben")
        return 0
    out, version, changed = wl.save_graph_version(project, graph, "governance")
    verb = "Geschrieben" if changed else "Unverändert"
    approved = sum(1 for b in graph["blueprints"] if b.get("status") == "approved")
    print(f"{verb}: {wl.relpath(out)} (Version {version}) | Entscheidungen={applied} "
          f"freigegebene Blueprints={approved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
