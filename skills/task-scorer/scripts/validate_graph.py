#!/usr/bin/env python3
"""
validate_graph.py — prüft eine work-graph.json gegen das Schema (Version 1.0).

Aufruf (relativ zum Projektordner):
    python3 <skill>/scripts/validate_graph.py --project ./mein-projekt
    python3 <skill>/scripts/validate_graph.py --file ./mein-projekt/20_graph/work-graph_latest.json

Exit-Code 0 = gültig, 1 = Warnungen, 2 = Fehler.
Die Prüfung ist bewusst streng bei Referenzen und Aufzählungswerten, damit
nachgelagerte Skripte (Scorer, Mapper, Dashboard) nie mit halben Daten laufen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def check_enum(errors: list[str], where: str, field: str, value, allowed: list[str], required=True):
    if value is None or value == "":
        if required:
            errors.append(f"{where}: Feld '{field}' fehlt")
        return
    if value not in allowed:
        errors.append(f"{where}: '{field}'='{value}' nicht erlaubt (erlaubt: {', '.join(allowed)})")


def check_range(errors: list[str], where: str, field: str, value, lo, hi, required=False):
    if value is None:
        if required:
            errors.append(f"{where}: Feld '{field}' fehlt")
        return
    if not isinstance(value, (int, float)) or value < lo or value > hi:
        errors.append(f"{where}: '{field}'={value!r} außerhalb {lo}..{hi}")


def validate(graph: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if graph.get("meta", {}).get("schema_version") != wl.SCHEMA_VERSION:
        warnings.append(
            f"meta.schema_version={graph.get('meta', {}).get('schema_version')!r}, erwartet {wl.SCHEMA_VERSION}"
        )
    for c in wl.COLLECTIONS:
        if c not in graph or not isinstance(graph[c], list):
            errors.append(f"Sammlung '{c}' fehlt oder ist keine Liste")
            graph[c] = graph.get(c) or []

    ids: dict[str, set[str]] = {}
    for c in wl.COLLECTIONS:
        seen: set[str] = set()
        for it in graph[c]:
            iid = it.get("id")
            if not iid:
                errors.append(f"{c}: Eintrag ohne id: {it.get('name')!r}")
                continue
            if iid in seen:
                errors.append(f"{c}: doppelte id {iid}")
            seen.add(iid)
        ids[c] = seen

    fam = ids["job_families"]
    clu = ids["job_clusters"]
    rol = ids["roles"]
    tas = ids["tasks"]
    ski = ids["skills"]
    age = ids["agents"]

    for jc in graph["job_clusters"]:
        if jc.get("family_id") not in fam:
            errors.append(f"job_cluster {jc['id']} ({jc.get('name')}): family_id unbekannt")

    for sk in graph["skills"]:
        check_enum(errors, f"skill {sk['id']} ({sk.get('name')})", "kind", sk.get("kind"), wl.ENUM_SKILL_KIND)
        if not sk.get("name"):
            errors.append(f"skill {sk['id']}: name fehlt")

    task_by_role: dict[str, list[dict]] = {}
    for t in graph["tasks"]:
        task_by_role.setdefault(t.get("role_id", ""), []).append(t)

    for r in graph["roles"]:
        w = f"role {r['id']} ({r.get('name')})"
        if not r.get("name"):
            errors.append(f"{w}: name fehlt")
        if r.get("cluster_id") not in clu:
            errors.append(f"{w}: cluster_id unbekannt")
        check_enum(errors, w, "status", r.get("status"), wl.ENUM_STATUS)
        check_enum(errors, w, "archetype", r.get("archetype"), wl.ENUM_ARCHETYPE, required=False)
        for s in r.get("skills", []):
            if s.get("skill_id") not in ski:
                errors.append(f"{w}: skill_id {s.get('skill_id')} unbekannt")
            check_range(errors, w, "skills[].level", s.get("level"), 1, 5, required=True)
            check_enum(errors, w, "skills[].importance", s.get("importance"), wl.ENUM_SKILL_IMPORTANCE)
        for tid in r.get("task_ids", []):
            if tid not in tas:
                errors.append(f"{w}: task_id {tid} unbekannt")
        rtasks = task_by_role.get(r["id"], [])
        if not rtasks:
            warnings.append(f"{w}: keine Aufgaben")
        else:
            total = sum(float(t.get("share_of_time") or 0) for t in rtasks)
            if abs(total - 100.0) > 0.51:
                warnings.append(f"{w}: Zeitanteile summieren auf {total:.1f} statt 100")
        if r.get("headcount") is not None:
            check_range(errors, w, "headcount", r.get("headcount"), 0, 1_000_000)
        an = r.get("analysis")
        if an and an.get("scored"):
            check_enum(errors, w, "analysis.disruption_type", an.get("disruption_type"), wl.ENUM_DISRUPTION)
            check_range(errors, w, "analysis.disruption_score", an.get("disruption_score"), 0, 10)

    for t in graph["tasks"]:
        w = f"task {t['id']} ({t.get('name')})"
        if not t.get("name"):
            errors.append(f"{w}: name fehlt")
        if t.get("role_id") not in rol:
            errors.append(f"{w}: role_id unbekannt")
        check_enum(errors, w, "frequency", t.get("frequency"), wl.ENUM_FREQUENCY)
        check_enum(errors, w, "nature", t.get("nature"), wl.ENUM_NATURE)
        check_enum(errors, w, "status", t.get("status"), wl.ENUM_STATUS)
        check_range(errors, w, "share_of_time", t.get("share_of_time"), 0, 100, required=True)
        for sid in t.get("skill_ids", []):
            if sid not in ski:
                errors.append(f"{w}: skill_id {sid} unbekannt")
        for aid in t.get("agent_ids", []):
            if aid not in age:
                errors.append(f"{w}: agent_id {aid} unbekannt")
        sc = t.get("scores")
        if sc:
            for f in ["automation_ai", "automation_physical", "human_judgment", "productivity_boost",
                      "data_readiness", "consequence_of_error"]:
                check_range(errors, w, f"scores.{f}", sc.get(f), 0, 10, required=True)
            if not sc.get("rationale"):
                warnings.append(f"{w}: scores.rationale fehlt")
        check_enum(errors, w, "mode", t.get("mode"), wl.ENUM_MODE, required=False)
        check_enum(errors, w, "horizon", t.get("horizon"), wl.ENUM_HORIZON, required=False)
        if t.get("has_level") is not None:
            check_range(errors, w, "has_level", t.get("has_level"), 1, 5)

    for a in graph["agents"]:
        w = f"agent {a['id']} ({a.get('name')})"
        if not a.get("name"):
            errors.append(f"{w}: name fehlt")
        check_enum(errors, w, "status", a.get("status"), wl.ENUM_AGENT_STATUS)
        check_enum(errors, w, "specificity", a.get("specificity"), wl.ENUM_SPECIFICITY)
        check_enum(errors, w, "sourcing", a.get("sourcing"), wl.ENUM_SOURCING, required=False)
        check_enum(errors, w, "horizon", a.get("horizon"), wl.ENUM_HORIZON, required=False)
        for tid in a.get("task_ids", []):
            if tid not in tas:
                errors.append(f"{w}: task_id {tid} unbekannt")
        if not a.get("task_ids"):
            warnings.append(f"{w}: deckt keine Aufgabe ab")

    for p in graph["positions"]:
        if p.get("role_id") not in rol:
            errors.append(f"position {p.get('id')}: role_id unbekannt")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="work-graph.json validieren")
    ap.add_argument("--project", help="Projektordner (relativ)")
    ap.add_argument("--file", help="Alternativ: konkrete Graph-Datei")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = Path.cwd() / path
    elif args.project:
        path = wl.latest_graph_path(wl.resolve_project(args.project))
    else:
        ap.error("--project oder --file angeben")
        return 2
    if not path.exists():
        wl.fail(f"Datei nicht gefunden: {wl.relpath(path)}")
    graph = wl.read_json(path)
    errors, warnings = validate(graph)
    if not args.quiet:
        for e in errors:
            print(f"FEHLER   {e}")
        for w in warnings:
            print(f"WARNUNG  {w}")
    counts = {c: len(graph.get(c, [])) for c in wl.COLLECTIONS}
    print(
        f"Geprüft: {wl.relpath(path)} | "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        + f" | Fehler={len(errors)} Warnungen={len(warnings)}"
    )
    if errors:
        return 2
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
