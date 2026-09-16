#!/usr/bin/env python3
"""
check_suite.py — prüft die Installation der Suite: sind alle vier Skills da,
sind die gemeinsamen Bibliotheksdateien in allen Kopien identisch, läuft Python 3.9+.

Aufruf:
    python3 <skill>/scripts/check_suite.py [--skills ../]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

SHARED = {
    "workgraph_lib.py": ["work-graph-builder", "task-scorer", "agent-mapper", "transformation-dashboard", "work-transformation"],
    "validate_graph.py": ["work-graph-builder", "task-scorer", "agent-mapper", "transformation-dashboard"],
    "apply_overrides.py": ["work-graph-builder", "task-scorer"],
}
REQUIRED = {
    "work-graph-builder": ["init_project.py", "build_graph.py", "make_review_list.py", "apply_overrides.py", "validate_graph.py", "import_positions.py"],
    "task-scorer": ["export_scoring_sheet.py", "score_roles.py", "calibrate.py"],
    "agent-mapper": ["export_agent_candidates.py", "compute_coverage.py"],
    "transformation-dashboard": ["build_dashboard.py"],
    "work-transformation": ["run_pipeline.py", "check_suite.py"],
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", default=None)
    args = ap.parse_args()
    here = Path(__file__).resolve().parent.parent
    skills = Path(args.skills).resolve() if args.skills else here.parent
    ok = True
    if sys.version_info < (3, 9):
        print(f"FEHLER   Python {sys.version.split()[0]} zu alt, mindestens 3.9")
        ok = False
    for skill, files in REQUIRED.items():
        d = skills / skill
        if not (d / "SKILL.md").exists():
            print(f"FEHLER   Skill fehlt: {skill} (erwartet unter {d})")
            ok = False
            continue
        for f in files:
            if not (d / "scripts" / f).exists():
                print(f"FEHLER   {skill}/scripts/{f} fehlt")
                ok = False
    for f, owners in SHARED.items():
        hashes = {}
        for s in owners:
            p = skills / s / "scripts" / f
            if p.exists():
                hashes[s] = sha(p)
        if len(set(hashes.values())) > 1:
            print(f"FEHLER   {f} unterscheidet sich zwischen Skills: {hashes}")
            ok = False
    print("Suite OK" if ok else "Suite unvollständig")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
