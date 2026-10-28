#!/usr/bin/env python3
"""
import_process_house.py — übernimmt ein vorhandenes Prozesshaus (z. B. IT-Betrieb nach
ITIL) als Prozessextraktion, damit Rollen und Automatisierungspotenzial je Prozessschritt
sichtbar werden.

Aufruf:
    python3 <skill>/scripts/import_process_house.py --project ./mein-projekt [--file 00_input/prozesshaus.csv] [--source "Prozesshaus IT"]

CSV (Trennzeichen ;), Standardpfad 00_input/prozesshaus.csv, eine Zeile je Schritt in Reihenfolge:
    process;step;role;aufgabe;handling_time_min;wait_time_min;system
    Incident Management;Störung erfassen;Service Desk Agent;Störungen annehmen;10;0;ITSM
    Incident Management;Störung klassifizieren;Service Desk Agent;Störungen klassifizieren;5;30;ITSM

process   Prozessname (Zeilen mit gleichem Namen bilden einen Prozess)
step      Schrittname, Verb-Objekt
role      Rolle exakt wie im Graphen — Zeilen mit unbekannter Rolle werden gemeldet
aufgabe   optional: Aufgabe der Rolle, die der Schritt ausführt (Name wie im Graphen)
handling_time_min / wait_time_min / system   optional

Ergebnis: 10_extraction/process_<source>.json im Format von references/process-format.md;
danach build_processes.py. Alle Zeiten sind `estimated`, solange niemand sie belegt. Das
Prozesshaus liefert die Struktur, nicht die gemessene Wirklichkeit — Abweichungen vom
gelebten Ablauf sind der Normalfall und gehören in die Prozessaufnahme.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def _num(raw):
    s = (raw or "").strip().replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", default=None)
    ap.add_argument("--source", default="Prozesshaus")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst build_graph.py ausführen")
    src = project / (args.file or f"{wl.DIR_INPUT}/prozesshaus.csv")
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt")
    role_names = {wl.normalize_name(r["name"]): r["name"] for r in graph["roles"]}
    task_names = {(wl.normalize_name(next((r["name"] for r in graph["roles"] if r["id"] == t["role_id"]), "")),
                   wl.normalize_name(t["name"])): t["name"] for t in graph["tasks"]}
    processes: dict[str, dict] = {}
    problems: list[str] = []
    systems: dict[str, dict] = {}
    for i, row in enumerate(wl.read_csv(src), start=2):
        pname, sname, rname = (row.get(k, "").strip() for k in ("process", "step", "role"))
        if not pname or not sname:
            continue
        role = role_names.get(wl.normalize_name(rname))
        if not role:
            problems.append(f"Zeile {i}: Rolle {rname!r} nicht im Graphen — Schritt übersprungen")
            continue
        proc = processes.setdefault(pname, {"name": pname, "trigger": "", "outcome": "",
                                            "owner_role": role, "steps": []})
        step = {"name": sname, "executor": {"type": "human", "role": role},
                "handling_time_min": _num(row.get("handling_time_min")) or 0.0,
                "wait_time_min": _num(row.get("wait_time_min")) or 0.0}
        aufgabe = (row.get("aufgabe") or "").strip()
        if aufgabe:
            canon = task_names.get((wl.normalize_name(role), wl.normalize_name(aufgabe)))
            if canon:
                step["tasks"] = [canon]
            else:
                problems.append(f"Zeile {i}: Aufgabe {aufgabe!r} bei {role!r} nicht im Graphen")
        sysname = (row.get("system") or "").strip()
        if sysname:
            step["systems"] = [sysname]
            systems.setdefault(sysname, {"name": sysname, "kind": "application", "system_of_record": False})
        proc["steps"].append(step)
    if not processes:
        wl.fail("Keine verwertbaren Zeilen")
    out = {"source": args.source,
           "note": "Aus einem Prozesshaus übernommen. Zeiten und Auslöser sind Platzhalter und "
                   "müssen mit der gelebten Praxis abgeglichen werden.",
           "outcomes": [], "systems": [systems[k] for k in sorted(systems)],
           "controls": [], "processes": [processes[k] for k in sorted(processes)]}
    slug = re.sub(r"[^a-z0-9]+", "-", wl.normalize_name(args.source)).strip("-") or "prozesshaus"
    path = project / wl.DIR_EXTRACTION / f"process_{slug}.json"
    wl.write_json(path, out)
    for p in problems:
        print(f"HINWEIS  {p}")
    print(f"Geschrieben: {wl.relpath(path)} | Prozesse={len(processes)} "
          f"Schritte={sum(len(p['steps']) for p in processes.values())} Hinweise={len(problems)}")
    print("Nächster Schritt: Auslöser und Ergebnis je Prozess ergänzen, dann build_processes.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
