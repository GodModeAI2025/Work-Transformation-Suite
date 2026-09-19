#!/usr/bin/env python3
"""
migrate_graph.py — hebt ein Projekt vom Schema 1.0 auf 1.1, additiv und verlustfrei.

Aufruf:
    python3 <skill>/scripts/migrate_graph.py --project ./mein-projekt [--dry-run]

Was die Migration tut: sie legt die mit Schema 1.1 hinzugekommenen Sammlungen leer an
(outcomes, systems, controls, metrics, processes, process_steps, process_edges,
blueprints, experiments, provenance, decisions) und setzt meta.schema_version.

Was sie ausdrücklich nicht tut: aus workflow_steps Prozesse erraten. Die Textliste in
einer Aufgabe beschreibt den Ablauf innerhalb einer Rolle, nicht den Fluss über Rollen,
Systeme und Übergaben hinweg. Daraus einen End-to-End-Prozess zu generieren, würde eine
Genauigkeit vortäuschen, die die Quelle nicht hergibt. Die Prozessebene entsteht über
build_processes.py aus eigenen Quellen (Prozessbeobachtung, Systemexporte, Interviews).

Der Aufruf ist idempotent: ein bereits migriertes Projekt bleibt unverändert und legt
keine neue Graph-Version an.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true", help="nur zeigen, was sich ändern würde")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    path = wl.latest_graph_path(project)
    if not path.exists():
        wl.fail(f"Kein Graph gefunden: {wl.relpath(path)}")

    graph = wl.read_json(path)
    before = graph.get("meta", {}).get("schema_version")
    # Inhaltsvergleich ohne meta: so erkennen wir, ob die Migration fachlich etwas ändert.
    counts_before = {c: len(graph.get(c, []) or []) for c in wl.COLLECTIONS}
    notes = wl.migrate_graph(graph)
    counts_after = {c: len(graph.get(c, []) or []) for c in wl.COLLECTIONS}
    lost = {c: (counts_before[c], counts_after[c]) for c in wl.COLLECTIONS
            if counts_before.get(c, 0) > counts_after.get(c, 0)}
    if lost:
        wl.fail(f"Migration würde Daten verlieren: {lost} — abgebrochen")

    if not notes:
        print(f"Bereits auf Schema {wl.SCHEMA_VERSION}, nichts zu tun: {wl.relpath(path)}")
        return 0
    for n in notes:
        print(f"MIGRATION {n}")

    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Migrierter Graph ist ungültig, nicht geschrieben")
    if args.dry_run:
        print(f"Probelauf: Schema {before!r} -> {wl.SCHEMA_VERSION!r}, nichts geschrieben")
        return 0
    out, version, changed = wl.save_graph_version(project, graph, "migration")
    meta = wl.load_project_meta(project)
    meta["schema_version"] = wl.SCHEMA_VERSION
    wl.save_project_meta(project, meta)
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(out)} (Version {version}) | Schema {before!r} -> {wl.SCHEMA_VERSION!r} | "
          + ", ".join(f"{c}={counts_after[c]}" for c in wl.COLLECTIONS if counts_after[c]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
