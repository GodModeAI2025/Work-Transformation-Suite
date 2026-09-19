#!/usr/bin/env python3
"""
sync_shared.py — kopiert die gemeinsam genutzten Bibliotheksdateien aus ihrer
Quelle in alle Skills, die sie brauchen.

Die Suite legt diese Dateien bewusst als identische Kopien in jedem Skill ab,
damit jeder Skill einzeln installierbar bleibt (siehe README). Diese Kopien von
Hand gleichzuhalten ist fehleranfällig; check_suite.py meldet den Drift, dieses
Werkzeug behebt ihn.

Aufruf (aus dem Repository-Wurzelverzeichnis):
    python3 tools/sync_shared.py [--check]

--check  schreibt nichts, meldet nur Abweichungen (Exit-Code 1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# Datei -> (Quelle, Ziele). Die Quelle ist der Skill, in dem die Datei fachlich zu Hause ist.
SHARED = {
    "workgraph_lib.py": (
        "work-transformation",
        ["work-graph-builder", "task-scorer", "agent-mapper", "process-redesigner", "transformation-dashboard"],
    ),
    "validate_graph.py": (
        "work-graph-builder",
        ["task-scorer", "agent-mapper", "process-redesigner", "transformation-dashboard"],
    ),
    "apply_overrides.py": ("work-graph-builder", ["task-scorer"]),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    drift = 0
    copied = 0
    for name, (source_skill, targets) in SHARED.items():
        src = SKILLS / source_skill / "scripts" / name
        if not src.exists():
            print(f"FEHLER   Quelle fehlt: {src.relative_to(ROOT)}")
            return 2
        data = src.read_bytes()
        for target in targets:
            dst = SKILLS / target / "scripts" / name
            if not dst.parent.is_dir():
                print(f"FEHLER   Zielordner fehlt: {dst.parent.relative_to(ROOT)}")
                return 2
            if dst.exists() and dst.read_bytes() == data:
                continue
            drift += 1
            if args.check:
                print(f"ABWEICHUNG {dst.relative_to(ROOT)} != {src.relative_to(ROOT)}")
            else:
                dst.write_bytes(data)
                copied += 1
                print(f"kopiert  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
    if args.check:
        print("Bibliothekskopien identisch" if not drift else f"{drift} Abweichung(en)")
        return 1 if drift else 0
    print(f"Fertig: {copied} Datei(en) aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
