#!/usr/bin/env python3
"""
build_target_roles.py — leitet aus der Aufgabenbewertung ein Zielbild je Rolle ab:
welche Aufgaben bleiben, wie viel Kapazität technisch frei wird, wie viel davon die
Organisation auffangen kann, und welche Rollen sich zusammenlegen ließen.

Aufruf:
    python3 <skill>/scripts/build_target_roles.py --project ./mein-projekt

Voraussetzung: score_roles.py ist gelaufen. Headcounts (headcount oder positions.csv)
machen aus Anteilen FTE; ohne sie bleibt das Zielbild bei Prozentanteilen.

Das Ergebnis ist ein **Entwurf**: Es sagt, was die Bewertung hergibt, wenn alle delegierbaren
Aufgaben tatsächlich übernommen würden — nicht, was geschehen wird oder soll. Welche
Stellen, Verträge und Altersstrukturen das auffangen, steht in `absorption` je Rolle
(Overrides: Felder `absorption` und `absorption_pct`). Fehlt sie, bleibt
`fte_realisable` leer. „Nicht bewertet“ ist eine andere Aussage als „null“.

Zusammenlegen: Zwei Rollen im selben Jobcluster werden als Kandidaten genannt, wenn bei
beiden weniger als MERGE_FTE_MAX Vollzeitäquivalente bleiben (oder die Rolle eliminiert
ist). Das ist ein Hinweis zur Prüfung, kein Organigramm.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

MERGE_FTE_MAX = 1.0


def build(graph: dict[str, Any]) -> list[dict[str, Any]]:
    tasks_by_role: dict[str, list] = {}
    for t in graph["tasks"]:
        tasks_by_role.setdefault(t["role_id"], []).append(t)

    rows: list[dict[str, Any]] = []
    for r in graph["roles"]:
        an = r.get("analysis") or {}
        if not an.get("scored"):
            continue
        rt = tasks_by_role.get(r["id"], [])
        delegated = sorted(t["id"] for t in rt if t.get("mode") == "agent_delegated")
        retained = sorted(t["id"] for t in rt if t.get("mode") != "agent_delegated")
        hc = an.get("headcount_basis")
        technical = an.get("fte_released_technical")
        remaining = None
        if hc is not None:
            remaining = wl.round1(max(0.0, hc - (technical or 0.0)))
        realisable = an.get("fte_realisable")
        rows.append({
            "id": wl.make_id("target_role", r["id"]),
            "role_id": r["id"],
            "name": r["name"],
            "cluster_id": r.get("cluster_id"),
            "disruption_type": an.get("disruption_type"),
            "retained_task_ids": retained,
            "delegated_task_ids": delegated,
            "retained_share_pct": wl.round1(100.0 - float(an.get("share_agent_delegated") or 0.0)),
            "fte_current": hc,
            "fte_released_technical": technical,
            "fte_realisable": realisable,
            "fte_remaining": remaining,
            "absorption": an.get("absorption"),
            "value_eur_estimated": wl.day_value(r, realisable),
            "merge_with_role_ids": [],
            "basis": "estimated",
            "status": "draft",
        })

    # Zusammenlegungskandidaten je Jobcluster
    def small(row: dict[str, Any]) -> bool:
        if row["disruption_type"] == "eliminated":
            return True
        return row["fte_remaining"] is not None and row["fte_remaining"] < MERGE_FTE_MAX

    by_cluster: dict[str, list] = {}
    for row in rows:
        if small(row):
            by_cluster.setdefault(row["cluster_id"], []).append(row)
    for group in by_cluster.values():
        if len(group) < 2:
            continue
        for row in group:
            row["merge_with_role_ids"] = sorted(o["role_id"] for o in group if o is not row)

    for row in rows:
        row["summary"] = summary(row)
        row.pop("cluster_id")
    rows.sort(key=lambda x: x["id"])
    return rows


def summary(row: dict[str, Any]) -> str:
    parts = [f"Bleibt: {row['retained_share_pct']:.0f} % der heutigen Arbeitszeit ({len(row['retained_task_ids'])} Aufgaben)"]
    if row["fte_current"] is not None:
        parts.append(f"{row['fte_current']:.1f} → {row['fte_remaining']:.1f} FTE technisch")
    if row["fte_realisable"] is not None:
        parts.append(f"davon {row['fte_realisable']:.1f} FTE auffangbar")
    else:
        parts.append("Auffangbarkeit nicht bewertet")
    if row["merge_with_role_ids"]:
        parts.append("Zusammenlegung prüfen")
    return "; ".join(parts) + "."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    if not any((r.get("analysis") or {}).get("scored") for r in graph["roles"]):
        wl.fail("Keine bewerteten Rollen, zuerst score_roles.py ausführen")
    graph["target_roles"] = build(graph)
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "target")
    verb = "Geschrieben" if changed else "Unverändert"
    n_unassessed = sum(1 for t in graph["target_roles"]
                       if t["fte_released_technical"] is not None and t["fte_realisable"] is None)
    n_merge = sum(1 for t in graph["target_roles"] if t["merge_with_role_ids"])
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Zielrollen={len(graph['target_roles'])} "
          f"Auffangbarkeit offen={n_unassessed} Zusammenlegung prüfen={n_merge}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
