#!/usr/bin/env python3
"""
build_graph.py — führt alle Extraktionsdateien aus 10_extraction/ zu einem
work-graph zusammen, vergibt deterministische IDs, dedupliziert Skills,
normalisiert Zeitanteile und übernimmt vorhandene Bewertungen aus dem
letzten Graphen (damit ein erneuter Architekt-Lauf keine Scores löscht).

Aufruf:
    python3 <skill>/scripts/build_graph.py --project ./mein-projekt

Eingabeformat je Datei 10_extraction/extract_<quelle>.json:
siehe references/extraction-format.md im Skill work-graph-builder.

Determinismus:
- Dateien werden in alphabetischer Reihenfolge verarbeitet.
- IDs: Hash aus (Familie|Cluster|Rolle) bzw. (Rolle|Aufgabe) bzw. (Skillname).
- Bei Konflikten (gleiche Rolle in zwei Dateien) gewinnt die alphabetisch
  erste Datei für Beschreibungstexte; Aufgaben und Skills werden vereinigt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402
from apply_overrides import apply as apply_overrides  # noqa: E402

SCORE_FIELDS = [
    "automation_ai",
    "automation_physical",
    "human_judgment",
    "productivity_boost",
    "data_readiness",
    "consequence_of_error",
    "rationale",
]


def _str(x: Any, default: str = "") -> str:
    return str(x).strip() if x is not None else default


def _int_or_none(x: Any):
    if x is None or x == "":
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def load_extractions(project: Path) -> list[tuple[str, dict[str, Any]]]:
    exdir = project / wl.DIR_EXTRACTION
    files = sorted(p for p in exdir.glob("extract_*.json"))
    if not files:
        wl.fail(f"Keine Extraktionsdateien in {wl.relpath(exdir)} (erwartet extract_*.json)")
    out = []
    for f in files:
        try:
            out.append((f.name, wl.read_json(f)))
        except Exception as e:  # noqa: BLE001
            wl.fail(f"{f.name}: kein gültiges JSON ({e})")
    return out


def build(project: Path, keep_scores: bool = True) -> tuple[dict[str, Any], dict[str, int]]:
    previous = wl.load_latest_graph(project)
    prev_tasks = wl.index_by_id(previous.get("tasks", [])) if previous else {}
    prev_roles = wl.index_by_id(previous.get("roles", [])) if previous else {}
    prev_agents = previous.get("agents", []) if previous else []

    graph = wl.empty_graph()
    families: dict[str, dict] = {}
    clusters: dict[str, dict] = {}
    roles: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    skills: dict[str, dict] = {}
    stats = {"files": 0, "roles_new": 0, "roles_merged": 0, "tasks": 0, "skills": 0, "scores_kept": 0}

    def get_skill(name: str, kind: str = "skill", category: str = "") -> str:
        sid = wl.make_id("skill", name)
        if sid not in skills:
            skills[sid] = {
                "id": sid,
                "name": name.strip(),
                "kind": kind if kind in wl.ENUM_SKILL_KIND else "skill",
                "category": category.strip(),
                "esco_uri": None,
            }
            stats["skills"] += 1
        else:
            # Kategorie nur füllen, wenn leer (erste Datei gewinnt)
            if not skills[sid]["category"] and category:
                skills[sid]["category"] = category.strip()
        return sid

    for fname, ex in load_extractions(project):
        stats["files"] += 1
        fam_name = _str(ex.get("job_family")) or "Ohne Zuordnung"
        clu_name = _str(ex.get("job_cluster")) or fam_name
        source = _str(ex.get("source")) or fname
        fid = wl.make_id("job_family", fam_name)
        families.setdefault(fid, {"id": fid, "name": fam_name, "description": _str(ex.get("job_family_description"))})
        cid = wl.make_id("job_cluster", fam_name, clu_name)
        clusters.setdefault(cid, {"id": cid, "name": clu_name, "family_id": fid,
                                  "description": _str(ex.get("job_cluster_description"))})

        for r in ex.get("roles", []):
            rname = _str(r.get("name"))
            if not rname:
                continue
            rid = wl.make_id("role", fam_name, clu_name, rname)
            if rid in roles:
                role = roles[rid]
                stats["roles_merged"] += 1
                role["source_refs"] = sorted(set(role["source_refs"] + [source]))
            else:
                stats["roles_new"] += 1
                archetype = _str(r.get("archetype")) or None
                role = {
                    "id": rid,
                    "name": rname,
                    "cluster_id": cid,
                    "level": _str(r.get("level")),
                    "description": _str(r.get("description")),
                    "purpose": _str(r.get("purpose")),
                    "headcount": _int_or_none(r.get("headcount")),
                    "archetype": archetype if archetype in wl.ENUM_ARCHETYPE else None,
                    "regulated": bool(r.get("regulated", False)),
                    "is_new": bool(r.get("is_new", False)),
                    "time_shares_source": _str(r.get("time_shares_source")) if _str(r.get("time_shares_source")) in ("source", "estimated") else "estimated",
                    "status": "generated",
                    "source_refs": [source],
                    "skills": [],
                    "task_ids": [],
                }
                prev = prev_roles.get(rid)
                if prev:
                    # Reviewstatus und Analyse aus Vorversion behalten
                    role["status"] = prev.get("status", "generated")
                    if prev.get("analysis"):
                        role["analysis"] = prev["analysis"]
                roles[rid] = role

            seen_skill_ids = {s["skill_id"] for s in role["skills"]}
            for s in r.get("skills", []):
                sname = _str(s.get("name")) if isinstance(s, dict) else _str(s)
                if not sname:
                    continue
                sid = get_skill(sname, _str(s.get("kind", "skill")) if isinstance(s, dict) else "skill",
                                _str(s.get("category", "")) if isinstance(s, dict) else "")
                if sid in seen_skill_ids:
                    continue
                seen_skill_ids.add(sid)
                level = _int_or_none(s.get("level")) if isinstance(s, dict) else None
                importance = _str(s.get("importance")) if isinstance(s, dict) else ""
                role["skills"].append({
                    "skill_id": sid,
                    "level": int(wl.clamp(level if level is not None else 3, 1, 5)),
                    "importance": importance if importance in wl.ENUM_SKILL_IMPORTANCE else "supporting",
                })

            for t in r.get("tasks", []):
                tname = _str(t.get("name"))
                if not tname:
                    continue
                tid = wl.make_id("task", rname, tname)
                if tid in tasks:
                    continue
                task_skill_ids = []
                for sn in t.get("skills", []):
                    sname = _str(sn.get("name")) if isinstance(sn, dict) else _str(sn)
                    if sname:
                        task_skill_ids.append(get_skill(sname))
                freq = _str(t.get("frequency")) or "weekly"
                nature = _str(t.get("nature")) or "cognitive"
                share = t.get("share_of_time")
                try:
                    share = float(share) if share is not None else 0.0
                except (TypeError, ValueError):
                    share = 0.0
                task = {
                    "id": tid,
                    "role_id": rid,
                    "name": tname,
                    "description": _str(t.get("description")),
                    "workflow_steps": [_str(x) for x in t.get("workflow_steps", []) if _str(x)],
                    "share_of_time_raw": share,
                    "share_of_time": share,
                    "frequency": freq if freq in wl.ENUM_FREQUENCY else "weekly",
                    "nature": nature if nature in wl.ENUM_NATURE else "cognitive",
                    "confidence": _str(t.get("confidence")) or "inferred",
                    "skill_ids": sorted(set(task_skill_ids)),
                    "status": "generated",
                    "agent_ids": [],
                }
                prev = prev_tasks.get(tid)
                if prev:
                    task["status"] = prev.get("status", "generated")
                    if keep_scores and prev.get("scores"):
                        task["scores"] = prev["scores"]
                        for k in ("mode", "horizon", "has_level", "automation_potential"):
                            if k in prev:
                                task[k] = prev[k]
                        stats["scores_kept"] += 1
                    if prev.get("agent_ids"):
                        task["agent_ids"] = prev["agent_ids"]
                tasks[tid] = task
                role["task_ids"].append(tid)
                stats["tasks"] += 1

    # Zeitanteile je Rolle auf 100 normalisieren (deterministisch, Rest auf größte Aufgabe)
    for role in roles.values():
        rtasks = [tasks[t] for t in role["task_ids"]]
        if not rtasks:
            continue
        total = sum(t["share_of_time_raw"] for t in rtasks)
        if total <= 0:
            equal = wl.round1(100.0 / len(rtasks))
            for t in rtasks:
                t["share_of_time"] = equal
        else:
            for t in rtasks:
                t["share_of_time"] = wl.round1(t["share_of_time_raw"] * 100.0 / total)
        diff = wl.round1(100.0 - sum(t["share_of_time"] for t in rtasks))
        if abs(diff) >= 0.05:
            biggest = sorted(rtasks, key=lambda t: (-t["share_of_time"], t["id"]))[0]
            biggest["share_of_time"] = wl.round1(biggest["share_of_time"] + diff)

    # Agenten aus Vorversion behalten, aber nur mit noch existierenden Aufgaben
    agents = []
    for a in prev_agents:
        a = dict(a)
        a["task_ids"] = sorted(t for t in a.get("task_ids", []) if t in tasks)
        agents.append(a)
    valid_agent_ids = {a["id"] for a in agents}
    for t in tasks.values():
        t["agent_ids"] = sorted(a for a in t.get("agent_ids", []) if a in valid_agent_ids)

    graph["job_families"] = list(families.values())
    graph["job_clusters"] = list(clusters.values())
    graph["roles"] = list(roles.values())
    graph["tasks"] = list(tasks.values())
    graph["skills"] = list(skills.values())
    graph["agents"] = agents
    graph["positions"] = list(previous.get("positions", [])) if previous else []
    graph["courses"] = list(previous.get("courses", [])) if previous else []
    wl.sort_graph(graph)
    return graph, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--no-keep-scores", action="store_true",
                    help="Bewertungen aus Vorversion NICHT übernehmen")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    wl.ensure_dirs(project)
    graph, stats = build(project, keep_scores=not args.no_keep_scores)
    # Overrides sofort anwenden, damit jede Graph-Version die Expertenkorrekturen enthält
    ov = project / wl.DIR_REVIEW / "overrides.csv"
    ov_applied = 0
    if ov.exists():
        ov_applied, ov_problems = apply_overrides(graph, wl.read_csv(ov))
        for pmsg in ov_problems:
            print(f"HINWEIS  {pmsg}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Graph nicht geschrieben, bitte Extraktionsdateien korrigieren")
    path, version, changed = wl.save_graph_version(project, graph, "builder")
    verb = "Geschrieben" if changed else "Unverändert"
    print(
        f"{verb}: {wl.relpath(path)} (Version {version}) | Dateien={stats['files']} "
        f"Rollen={stats['roles_new']} (zusammengeführt {stats['roles_merged']}) "
        f"Aufgaben={stats['tasks']} Skills={stats['skills']} Bewertungen übernommen={stats['scores_kept']} Overrides={ov_applied}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
