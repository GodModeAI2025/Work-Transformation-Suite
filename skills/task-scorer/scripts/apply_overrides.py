#!/usr/bin/env python3
"""
apply_overrides.py — spielt Expertenkorrekturen aus 30_review/overrides.csv
deterministisch in den aktuellen Graphen ein und schreibt eine neue Version.

Aufruf:
    python3 <skill>/scripts/apply_overrides.py --project ./mein-projekt

CSV-Format (Trennzeichen ;):
    entity_type;entity_id;field;value;reviewer;comment

entity_type: role | task | skill | agent
field:       beliebiges Feld des Objekts, z. B. headcount, share_of_time, status,
             regulated, archetype, name, description, level (nur skill in Rolle: role;<id>;skill_level:<skill_id>;4)
             Für Scores: scores.automation_ai usw. (Punktnotation).
             Sonderfall field=delete, value=true: Objekt entfernen (Task: auch aus Rolle).
value:       Zahlen werden als Zahl übernommen, true/false als Bool, sonst Text.

Regeln:
- Overrides gewinnen immer über generierte Werte. Sie werden bei jedem Lauf erneut
  angewendet (idempotent), damit ein neuer Architekt-Lauf sie nicht verliert.
- Zeilen werden in Dateireihenfolge angewendet; die letzte Zeile zu einem Feld gewinnt.
- Unbekannte IDs/Felder werden gemeldet, brechen aber nicht ab.
- Objekte mit mindestens einem Override erhalten status=reviewed, falls noch generated.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

COLL = {"role": "roles", "task": "tasks", "skill": "skills", "agent": "agents"}


def parse_value(v: str) -> Any:
    s = (v or "").strip()
    if s.lower() in ("true", "ja", "yes"):
        return True
    if s.lower() in ("false", "nein", "no"):
        return False
    try:
        if "." in s or "," in s:
            return float(s.replace(",", "."))
        return int(s)
    except ValueError:
        return s


def apply(graph: dict[str, Any], rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    applied = 0
    problems: list[str] = []
    to_delete: list[tuple[str, str]] = []
    for i, row in enumerate(rows, start=2):
        et = (row.get("entity_type") or "").strip().lower()
        eid = (row.get("entity_id") or "").strip()
        field = (row.get("field") or "").strip()
        if not et or not eid or not field:
            continue
        coll = COLL.get(et)
        if not coll:
            problems.append(f"Zeile {i}: entity_type '{et}' unbekannt")
            continue
        idx = wl.index_by_id(graph[coll])
        obj = idx.get(eid)
        if not obj:
            problems.append(f"Zeile {i}: {et} {eid} nicht gefunden")
            continue
        value = parse_value(row.get("value", ""))
        if field == "delete":
            if value is True:
                to_delete.append((coll, eid))
                applied += 1
            continue
        if field.startswith("skill_level:") and et == "role":
            sid = field.split(":", 1)[1]
            hit = False
            for s in obj.get("skills", []):
                if s["skill_id"] == sid:
                    s["level"] = int(wl.clamp(int(value), 1, 5))
                    hit = True
            if not hit:
                problems.append(f"Zeile {i}: Skill {sid} nicht in Rolle {eid}")
                continue
        elif "." in field:
            head, sub = field.split(".", 1)
            obj.setdefault(head, {})
            if not isinstance(obj[head], dict):
                problems.append(f"Zeile {i}: Feld {head} ist kein Objekt")
                continue
            obj[head][sub] = value
        else:
            obj[field] = value
        if obj.get("status") == "generated":
            obj["status"] = "reviewed"
        obj.setdefault("overrides_applied", [])
        if field not in obj["overrides_applied"]:
            obj["overrides_applied"].append(field)
            obj["overrides_applied"].sort()
        applied += 1

    for coll, eid in to_delete:
        graph[coll] = [o for o in graph[coll] if o["id"] != eid]
        if coll == "tasks":
            for r in graph["roles"]:
                r["task_ids"] = [t for t in r.get("task_ids", []) if t != eid]
            for a in graph["agents"]:
                a["task_ids"] = [t for t in a.get("task_ids", []) if t != eid]
        if coll == "agents":
            for t in graph["tasks"]:
                t["agent_ids"] = [a for a in t.get("agent_ids", []) if a != eid]

    # Zeitanteile je Rolle nach Overrides neu normalisieren
    tasks = wl.index_by_id(graph["tasks"])
    for r in graph["roles"]:
        rt = [tasks[t] for t in r["task_ids"] if t in tasks]
        total = sum(float(t["share_of_time"]) for t in rt)
        if rt and total > 0 and abs(total - 100) > 0.51:
            for t in rt:
                t["share_of_time"] = wl.round1(float(t["share_of_time"]) * 100.0 / total)
            diff = wl.round1(100.0 - sum(t["share_of_time"] for t in rt))
            if abs(diff) >= 0.05:
                biggest = sorted(rt, key=lambda t: (-t["share_of_time"], t["id"]))[0]
                biggest["share_of_time"] = wl.round1(biggest["share_of_time"] + diff)
    return applied, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    ov = project / wl.DIR_REVIEW / "overrides.csv"
    if not ov.exists():
        print(f"Keine overrides.csv in {wl.relpath(ov.parent)}, nichts zu tun")
        return 0
    rows = wl.read_csv(ov)
    applied, problems = apply(graph, rows)
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Overrides erzeugen ungültigen Graphen, nicht geschrieben")
    if args.dry_run:
        print(f"Dry-Run: {applied} Overrides anwendbar, {len(problems)} Hinweise")
        return 0
    if applied == 0:
        print("Keine anwendbaren Overrides, Graph unverändert")
        return 0
    path, version, changed = wl.save_graph_version(project, graph, "review")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Overrides angewendet={applied} Hinweise={len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
