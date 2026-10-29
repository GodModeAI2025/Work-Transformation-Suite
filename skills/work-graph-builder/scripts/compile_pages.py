#!/usr/bin/env python3
"""
compile_pages.py — übersetzt die Seiten unter 05_pages/ in die JSON-Register.

Aufruf:
    python3 <skill>/scripts/compile_pages.py --project ./mein-projekt [--check]

Ergebnis:
    10_extraction/extract_<cluster>.json   je Jobcluster: Rollen, Skills, Aufgaben, Belege
    20_graph/scores.json                   Bewertungen aller Aufgaben mit sechs score_-Feldern
    20_graph/agents.json                   Agenten mit Verträgen
    05_pages/.compiled.json                welche Dateien dieser Lauf erzeugt hat

Die Seiten sind die Wahrheit, die Register sind abgeleitet: Dieselben Seiten ergeben dieselben
Bytes, und eine Registerdatei, die aus einem früheren Lauf stammt und keine Seite mehr hat,
wird entfernt. run_pipeline.py ruft dieses Skript vor jedem Lauf auf, sobald Seiten existieren.

Was nicht stimmt, wird mit Datei und Zeile gemeldet und es wird nichts geschrieben: unbekannter
Typ, Rolle ohne Cluster, Aufgabe ohne Rolle, doppelte Namen, halbe Bewertungen, kaputter
Vertrags-Block. --check meldet nur.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pages_lib as pl  # noqa: E402
import workgraph_lib as wl  # noqa: E402
from export_pages import SCORE_KEYS  # noqa: E402

COMPILED = ".compiled.json"


def _int(v: Any, where: str, field: str, problems: list[str], lo: int | None = None, hi: int | None = None):
    if v is None or v == "":
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        problems.append(f"{where}: {field} muss eine ganze Zahl sein, ist {v!r}")
        return None
    v = int(v)
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        problems.append(f"{where}: {field}={v} außerhalb {lo}..{hi}")
    return v


def _text(meta: dict, key: str, where: str, problems: list[str], required: bool = False) -> str:
    v = meta.get(key)
    if v is None or str(v).strip() == "":
        if required:
            problems.append(f"{where}: {key} fehlt")
        return ""
    return str(v).strip()


def _list(meta: dict, key: str, where: str, problems: list[str]) -> list[str]:
    v = meta.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        problems.append(f"{where}: {key} muss eine Liste sein")
        return []
    return [str(x).strip() for x in v if x is not None and str(x).strip()]


def compile_pages(project: Path) -> tuple[dict[str, Any], list[str]]:
    pages, problems = pl.read_all_pages(project)
    clusters: dict[str, dict] = {}
    for p in pages["cluster"]:
        w, m = p["path"], p["meta"]
        clu = _text(m, "job_cluster", w, problems, True)
        if clu in clusters:
            problems.append(f"{w}: Jobcluster {clu!r} doppelt ({clusters[clu]['_path']})")
            continue
        s = p["sections"]
        clusters[clu] = {"_path": w, "source": _text(m, "source", w, problems) or w,
                         "job_family": _text(m, "job_family", w, problems, True),
                         "job_family_description": pl.prose(s.get("Jobfamilie", "")),
                         "job_cluster": clu, "job_cluster_description": pl.prose(s.get("Jobcluster", "")), "roles": []}
    roles: dict[str, dict] = {}
    for p in pages["role"]:
        w, m, s = p["path"], p["meta"], p["sections"]
        name = _text(m, "name", w, problems, True)
        clu = _text(m, "cluster", w, problems, True)
        if not name:
            continue
        if name in roles:
            problems.append(f"{w}: Rolle {name!r} doppelt ({roles[name]['_path']})")
            continue
        if clu and clu not in clusters:
            problems.append(f"{w}: cluster {clu!r} hat keine Seite unter clusters/")
            continue
        skills = []
        for row in pl.table_rows(s.get("Skills", "")):
            sname = row.get("Skill", "").strip()
            if not sname:
                continue
            level = _int(_num(row.get("Niveau")), w, "Skills.Niveau", problems, 1, 5)
            skills.append({"name": sname, "kind": row.get("Art", "skill").strip() or "skill",
                           "category": row.get("Kategorie", "").strip(), "level": level if level is not None else 3,
                           "importance": row.get("Bedeutung", "supporting").strip() or "supporting"})
        role = {"_path": w, "name": name, "level": _text(m, "level", w, problems),
                "headcount": _int(m.get("headcount"), w, "headcount", problems, 0),
                "archetype": _text(m, "archetype", w, problems) or None,
                "regulated": bool(m.get("regulated", False)), "is_new": bool(m.get("is_new", False)),
                "time_shares_source": _text(m, "time_shares_source", w, problems) or "estimated",
                "purpose": pl.prose(s.get("Zweck", "")), "description": pl.prose(s.get("Beschreibung", "")),
                "evidence": _list(m, "evidence", w, problems), "skills": skills, "tasks": []}
        if role["time_shares_source"] not in ("source", "estimated"):
            problems.append(f"{w}: time_shares_source muss source oder estimated sein")
        roles[name] = role
        if clu:
            clusters[clu]["roles"].append(role)
    scores: dict[str, dict] = {}
    task_keys: set[tuple[str, str]] = set()
    for p in pages["task"]:
        w, m, s = p["path"], p["meta"], p["sections"]
        name = _text(m, "name", w, problems, True)
        rname = _text(m, "role", w, problems, True)
        if not name or not rname:
            continue
        if rname not in roles:
            problems.append(f"{w}: role {rname!r} hat keine Seite unter roles/")
            continue
        if (rname, name) in task_keys:
            problems.append(f"{w}: Aufgabe {name!r} der Rolle {rname!r} doppelt")
            continue
        task_keys.add((rname, name))
        share = m.get("share_of_time")
        if isinstance(share, bool) or not isinstance(share, (int, float)):
            problems.append(f"{w}: share_of_time fehlt oder ist keine Zahl")
            share = 0
        task = {"name": name, "description": pl.prose(s.get("Beschreibung", "")),
                "workflow_steps": pl.ordered_list(s.get("Schritte", "")), "share_of_time": share,
                "frequency": _text(m, "frequency", w, problems) or "weekly", "nature": _text(m, "nature", w, problems) or "cognitive",
                "confidence": _text(m, "confidence", w, problems) or "inferred",
                "skills": [{"name": x} for x in _list(m, "skills", w, problems)],
                "evidence": _list(m, "evidence", w, problems)}
        roles[rname]["tasks"].append(task)
        present = [k for k in SCORE_KEYS if m.get(f"score_{k}") is not None]
        if present:
            if len(present) < len(SCORE_KEYS):
                problems.append(f"{w}: Bewertung unvollständig, es fehlt: "
                                + ", ".join(f"score_{k}" for k in SCORE_KEYS if k not in present))
                continue
            entry = {k: _int(m.get(f"score_{k}"), w, f"score_{k}", problems, 0, 10) for k in SCORE_KEYS}
            entry["rationale"] = pl.prose(s.get("Begründung der Bewertung", ""))
            for flag in ("interpersonal", "tacit_expertise"):
                v = m.get(f"score_{flag}")
                if v is None:
                    continue
                if isinstance(v, bool):
                    entry[flag] = v
                else:
                    problems.append(f"{w}: score_{flag} muss true oder false sein")
            if not entry["rationale"]:
                problems.append(f"{w}: Bewertung ohne Begründung (Abschnitt „Begründung der Bewertung“)")
            scores[wl.make_id("task", rname, name)] = entry
    task_ids = {f"{r} > {t}": wl.make_id("task", r, t) for r, t in task_keys}
    agents: list[dict] = []
    seen_agents: set[str] = set()
    for p in pages["agent"]:
        w, m, s = p["path"], p["meta"], p["sections"]
        name = _text(m, "name", w, problems, True)
        if not name:
            continue
        if name in seen_agents:
            problems.append(f"{w}: Agent {name!r} doppelt")
            continue
        seen_agents.add(name)
        tids = []
        for ref in _list(m, "tasks", w, problems):
            if ref in task_ids:
                tids.append(task_ids[ref])
            elif ref.startswith("ta_"):
                tids.append(ref)
            else:
                problems.append(f"{w}: tasks-Eintrag {ref!r} nicht gefunden (Form: \"Rolle > Aufgabe\")")
        try:
            contract = pl.json_block(s.get("Vertrag", ""), w)
        except pl.PageError as e:
            problems.append(str(e))
            contract = None
        a = {"name": name, "pattern": _text(m, "pattern", w, problems, True),
             "capability": pl.prose(s.get("Fähigkeit", "")), "specificity": _text(m, "specificity", w, problems) or "domain",
             "status": _text(m, "status", w, problems) or "proposed",
             "complexity": _int(m.get("complexity"), w, "complexity", problems, 1, 5) or 3,
             "existing_system": m.get("existing_system") or None, "oversight": pl.prose(s.get("Aufsicht", "")),
             "prerequisites": _list(m, "prerequisites", w, problems), "task_ids": sorted(set(tids))}
        orch = _list(m, "orchestrates", w, problems)
        if orch:
            a["orchestrates"] = orch
        if contract is not None:
            if not isinstance(contract, dict):
                problems.append(f"{w}: Vertrag muss ein JSON-Objekt sein")
            else:
                a["contract"] = contract
        agents.append(a)
    agents.sort(key=lambda a: a["name"])
    orphan = [r["name"] for r in roles.values() if not any(r in c["roles"] for c in clusters.values())]
    for n in orphan:
        problems.append(f"Rolle {n!r}: ohne Cluster")
    out = {"extractions": {}, "scores": dict(sorted(scores.items())), "agents": agents}
    for clu, c in sorted(clusters.items()):
        ex = {k: v for k, v in c.items() if not k.startswith("_") and k != "roles"}
        ex["roles"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in sorted(c["roles"], key=lambda r: r["name"])]
        out["extractions"][f"extract_{pl.page_slug(clu)}.json"] = ex
    return out, problems


def _num(v):
    try:
        return float(str(v).strip()) if str(v).strip() else None
    except ValueError:
        return v


def write_registers(project: Path, out: dict[str, Any]) -> list[str]:
    written = []
    compiled_path = pl.pages_dir(project) / COMPILED
    previous = set(wl.read_json(compiled_path).get("files", [])) if compiled_path.exists() else set()
    for fname, ex in out["extractions"].items():
        rel = f"{wl.DIR_EXTRACTION}/{fname}"
        wl.write_json(project / rel, ex)
        written.append(rel)
    if out["scores"] or (project / wl.DIR_GRAPH / "scores.json").exists():
        wl.write_json(project / wl.DIR_GRAPH / "scores.json", out["scores"])
        written.append(f"{wl.DIR_GRAPH}/scores.json")
    if out["agents"] or (project / wl.DIR_GRAPH / "agents.json").exists():
        wl.write_json(project / wl.DIR_GRAPH / "agents.json", out["agents"])
        written.append(f"{wl.DIR_GRAPH}/agents.json")
    for rel in sorted(previous - set(written)):
        p = project / rel
        if p.exists() and rel.startswith(f"{wl.DIR_EXTRACTION}/extract_"):
            p.unlink()
            print(f"Entfernt: {rel} (keine Seite mehr dafür)")
    wl.write_json(compiled_path, {"files": sorted(written)})
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--check", action="store_true", help="nur prüfen, nichts schreiben")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    if not pl.has_pages(project):
        print(f"Keine Seiten unter {wl.relpath(pl.pages_dir(project))}; nichts zu übersetzen "
              "(export_pages.py erzeugt sie aus vorhandenen Registern).")
        return 3
    out, problems = compile_pages(project)
    for p in problems:
        print(f"FEHLER   {p}")
    if problems:
        wl.fail("Seiten nicht übersetzt; erst die Meldungen oben beheben")
    n_roles = sum(len(e["roles"]) for e in out["extractions"].values())
    n_tasks = sum(len(r["tasks"]) for e in out["extractions"].values() for r in e["roles"])
    if args.check:
        print(f"Seiten in Ordnung: Cluster={len(out['extractions'])} Rollen={n_roles} Aufgaben={n_tasks} "
              f"Bewertungen={len(out['scores'])} Agenten={len(out['agents'])}")
        return 0
    written = write_registers(project, out)
    print(f"Übersetzt: Cluster={len(out['extractions'])} Rollen={n_roles} Aufgaben={n_tasks} "
          f"Bewertungen={len(out['scores'])} Agenten={len(out['agents'])} → {', '.join(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
