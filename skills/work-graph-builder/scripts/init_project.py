#!/usr/bin/env python3
"""
init_project.py — legt die feste Ordnerstruktur eines Arbeitsgraph-Projekts an.

Aufruf:
    python3 <skill>/scripts/init_project.py --project ./projekte/kundenservice \
        --name "Kundenservice Pilot" --organization "Meine Firma" --scope "Kundenservice Vertragsmanagement"

Erzeugt (relativ zum Projektordner):
    project.json
    00_input/        Quelldokumente (Stellenbeschreibungen, Organigramme, Exporte)
    10_extraction/   Extraktionsdateien (eine JSON je Quelle, von Claude geschrieben)
    20_graph/        work-graph_vNNN_<stage>.json und work-graph_latest.json
    30_review/       Review-Listen und overrides.csv (Expertenkorrekturen)
    40_output/       Dashboard, CSV, Bericht
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

README = """# {name}

Projektordner der Work-Transformation-Suite. Alle Skripte werden mit
`--project <dieser Ordner>` aufgerufen; alle Pfade darin sind relativ.

| Ordner | Inhalt | Wer schreibt |
|---|---|---|
| 00_input/ | Quelldokumente | Mensch |
| 10_extraction/ | extract_<quelle>.json | Claude (work-graph-builder) |
| 20_graph/ | work-graph_vNNN_<stage>.json, work-graph_latest.json | Skripte |
| 30_review/ | review_vNNN.md, overrides.csv | Skripte / Fachexperten |
| 40_output/ | dashboard_vNNN.html, roles_vNNN.csv, agents_vNNN.csv, report_vNNN.md | Skripte |

Reihenfolge: work-graph-builder -> task-scorer -> agent-mapper -> transformation-dashboard.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Projektordner (relativ zum Arbeitsverzeichnis)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--organization", default="")
    ap.add_argument("--scope", default="", help="Bereich/Abteilung, die analysiert wird")
    ap.add_argument("--language", default="de")
    args = ap.parse_args()

    project = wl.resolve_project(args.project)
    project.mkdir(parents=True, exist_ok=True)
    wl.ensure_dirs(project)
    meta_path = project / wl.PROJECT_FILE
    if meta_path.exists():
        meta = wl.read_json(meta_path)
        print(f"project.json existiert bereits, Zähler bleibt bei Version {meta.get('graph_version', 0)}")
    else:
        meta = {
            "name": args.name or project.name,
            "organization": args.organization,
            "scope": args.scope,
            "language": args.language,
            "graph_version": 0,
            "schema_version": wl.SCHEMA_VERSION,
        }
        wl.save_project_meta(project, meta)
    readme = project / "README.md"
    if not readme.exists():
        wl.write_text(readme, README.format(name=meta["name"]))
    overrides = project / wl.DIR_REVIEW / "overrides.csv"
    if not overrides.exists():
        wl.write_text(overrides, "entity_type;entity_id;field;value;reviewer;comment\n",
                      newline="")
    print(f"Projekt angelegt: {wl.relpath(project)}")
    for d in wl.project_dirs(project).values():
        print(f"  {wl.relpath(d)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
