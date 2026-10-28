#!/usr/bin/env python3
"""
dedupe_tasks.py — findet dieselbe Arbeit in mehreren Rollen und fasst sie zu Aufgabenclustern
zusammen.

Aufruf:
    python3 <skill>/scripts/dedupe_tasks.py --project ./mein-projekt [--min-similarity 0.6]

Warum: Wer Stellenbeschreibungen einzeln zerlegt, bekommt dieselbe Tätigkeit unter drei
Formulierungen in drei Rollen. Als Cluster zeigt sich, wie oft sie vorkommt und wie viel Arbeit
daran hängt — und damit, welche Aufgabe sich als wiederverwendbarer Agent lohnt. „Diese Aufgabe
steckt in zwanzig Rollen“ ist ein stärkeres Argument als zwanzig Einzelfunde.

Wie: Rein lexikalisch, ohne Modell. Aufgabennamen (und Beschreibungen mit halbem Gewicht)
werden normalisiert, in Wortstämme zerlegt (erste fünf Zeichen) und per Jaccard-Ähnlichkeit
verglichen. Gleich benannte Aufgaben verschiedener Rollen sind immer ein Treffer. Aufgaben
derselben Rolle werden nie zusammengelegt. Das Verfahren findet gleiche Wörter, keine gleiche
Bedeutung: „Rechnung prüfen“ und „Beleg kontrollieren“ erkennt es nicht. Deshalb sind alle
Cluster zunächst `candidate`. Eine Entscheidung steht in 30_review/task_clusters.csv:

    cluster_id;decision;reviewer;comment
    tc_1a2b3c4d5e6f;confirmed;M. Muster;gleiche Prüfung
    tc_9f8e7d6c5b4a;rejected;M. Muster;nur ähnlich geschrieben

Entscheidungen bleiben über Neuläufe erhalten (die Cluster-ID folgt der kleinsten Aufgaben-ID).
Zusammenlegen verändert den Graphen sonst nicht: Aufgaben bleiben je Rolle bestehen.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

DEFAULT_MIN_SIMILARITY = 0.6
STEM_LEN = 5
DESCRIPTION_WEIGHT = 0.5
STOPWORDS = {
    "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einer", "von", "vom", "zum",
    "zur", "mit", "für", "fur", "auf", "aus", "bei", "nach", "im", "in", "an", "zu", "the", "and", "of", "for",
    "ist", "sind", "wird", "werden", "sowie", "inkl", "ggf", "ca",
}


def stems(text: str) -> set[str]:
    out = set()
    for tok in re.split(r"[^a-z0-9]+", wl.normalize_name(text)):
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        out.add(tok[:STEM_LEN])
    return out


def similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    if a["norm"] == b["norm"]:
        return 1.0
    na, nb = a["name_stems"], b["name_stems"]
    if len(na & nb) < 2 and not (len(na) == 1 and na == nb):
        return 0.0
    name_j = len(na & nb) / len(na | nb) if na | nb else 0.0
    da, db = a["desc_stems"], b["desc_stems"]
    desc_j = len(da & db) / len(da | db) if da and db and da | db else name_j
    return round((1 - DESCRIPTION_WEIGHT * 0.5) * name_j + DESCRIPTION_WEIGHT * 0.5 * desc_j, 3)


def find_clusters(graph: dict[str, Any], threshold: float) -> list[dict[str, Any]]:
    roles = wl.index_by_id(graph["roles"])
    items = []
    for t in sorted(graph["tasks"], key=lambda t: t["id"]):
        if t.get("role_id") not in roles:
            continue
        items.append({"t": t, "norm": wl.normalize_name(t["name"]), "name_stems": stems(t["name"]),
                      "desc_stems": stems(t.get("description", ""))})
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    sims: dict[tuple[int, int], float] = {}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i]["t"]["role_id"] == items[j]["t"]["role_id"]:
                continue
            s = similarity(items[i], items[j])
            if s >= threshold:
                sims[(i, j)] = s
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for members in groups.values():
        if len(members) < 2:
            continue
        tasks = [items[i]["t"] for i in members]
        if len({t["role_id"] for t in tasks}) < 2:
            continue
        pair_sims = [s for (i, j), s in sims.items() if i in members and j in members]
        head = sorted(tasks, key=lambda t: (-float(t.get("share_of_time") or 0), t["id"]))[0]
        fte = 0.0
        known = True
        for t in tasks:
            hc = wl.role_headcount(roles[t["role_id"]])
            if hc is None:
                known = False
                break
            fte += float(hc) * float(t.get("share_of_time") or 0) / 100.0
        clusters.append({
            "id": wl.make_id("task_cluster", min(t["id"] for t in tasks)),
            "name": head["name"],
            "task_ids": sorted(t["id"] for t in tasks),
            "role_ids": sorted({t["role_id"] for t in tasks}),
            "tasks_count": len(tasks),
            "roles_count": len({t["role_id"] for t in tasks}),
            "share_sum": wl.round1(sum(float(t.get("share_of_time") or 0) for t in tasks)),
            "fte": wl.round1(fte) if known else None,
            "similarity_min": min(pair_sims) if pair_sims else 1.0,
            "basis": "heuristic",
            "status": "candidate",
        })
    clusters.sort(key=lambda c: (-c["roles_count"], -(c["fte"] or 0), c["name"], c["id"]))
    return clusters


def apply_decisions(clusters: list[dict[str, Any]], rows: list[dict[str, str]]) -> list[str]:
    problems = []
    by_id = {c["id"]: c for c in clusters}
    for i, row in enumerate(rows, start=2):
        cid, dec = (row.get("cluster_id") or "").strip(), (row.get("decision") or "").strip().lower()
        if not cid:
            continue
        if dec not in ("confirmed", "rejected"):
            problems.append(f"Zeile {i}: decision '{dec}' unbekannt (confirmed|rejected)")
        elif cid not in by_id:
            problems.append(f"Zeile {i}: Cluster {cid} gibt es nicht mehr (Zusammensetzung geändert?)")
        elif not (row.get("reviewer") or "").strip():
            problems.append(f"Zeile {i}: Entscheidung ohne reviewer — eine Bestätigung ohne Namen ist keine")
        else:
            by_id[cid]["status"] = dec
            by_id[cid]["reviewer"] = row["reviewer"].strip()
            if (row.get("comment") or "").strip():
                by_id[cid]["comment"] = row["comment"].strip()
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--min-similarity", type=float, default=DEFAULT_MIN_SIMILARITY)
    args = ap.parse_args()
    if not 0.3 <= args.min_similarity <= 1.0:
        wl.fail("--min-similarity muss zwischen 0,3 und 1,0 liegen")
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    clusters = find_clusters(graph, args.min_similarity)
    problems: list[str] = []
    dec = project / wl.DIR_REVIEW / "task_clusters.csv"
    if dec.exists():
        problems = apply_decisions(clusters, wl.read_csv(dec))
    graph["task_clusters"] = clusters
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, _warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "dedupe")
    verb = "Geschrieben" if changed else "Unverändert"
    counts: dict[str, int] = {}
    for c in clusters:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Cluster={len(clusters)} "
          + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f" Hinweise={len(problems)}")
    if not dec.exists() and clusters:
        print("Nächster Schritt: Kandidaten prüfen und in 30_review/task_clusters.csv "
              "(cluster_id;decision;reviewer;comment) bestätigen oder verwerfen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
