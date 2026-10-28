#!/usr/bin/env python3
"""
check_completeness.py — prüft jede Rolle gegen die Rollenvorlage (assets/role-template.json) und
nennt je Lücke, woher sie zu füllen wäre.

Aufruf:
    python3 <skill>/scripts/check_completeness.py --project ./mein-projekt [--template eigene-vorlage.json]

Ausgabe:
    30_review/vollstaendigkeit_vNNN.md    je Rolle Füllgrad und Lücken
    30_review/vollstaendigkeit_vNNN.csv   dieselben Zeilen

Das ist die Qualitätsschranke vor der Bewertung: Eine Rolle mit zwei Aufgaben und geschätzten
Zeitanteilen wird bewertet, aber das Ergebnis ist eine plausible Geschichte, keine Messung. Die Vorlage
bestimmt, was „vollständig“ heißt. Lücken werden nicht still aufgefüllt; die Suite nennt sie und sagt,
welche Quelle sie schließen würde (innen vor außen: Eine interne Quelle schlägt eine Stellenanzeige).

Die Prüfung ändert den Graphen nicht.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "role-template.json"


def collaboration_roles(graph: dict[str, Any]) -> dict[str, set[str]]:
    """Rolle -> Rollen, mit denen sie nach Prozessdaten oder Positionen zusammenarbeitet."""
    steps = wl.index_by_id(graph.get("process_steps", []))
    out: dict[str, set[str]] = {}
    for e in graph.get("process_edges", []):
        a, b = steps.get(e.get("from_step_id")), steps.get(e.get("to_step_id"))
        if not a or not b:
            continue
        ra, rb = a.get("role_id"), b.get("role_id")
        if ra and rb and ra != rb:
            out.setdefault(ra, set()).add(rb)
            out.setdefault(rb, set()).add(ra)
    by_unit: dict[str, set[str]] = {}
    for p in graph.get("positions", []):
        if p.get("org_unit"):
            for rs in p.get("role_shares", []):
                by_unit.setdefault(p["org_unit"], set()).add(rs["role_id"])
    for roles in by_unit.values():
        for r in roles:
            out.setdefault(r, set()).update(roles - {r})
    return out


def check_role(sec: dict[str, Any], role: dict[str, Any], tasks: list[dict[str, Any]], collab: dict[str, set[str]]) -> tuple[bool, str]:
    kind = sec["check"]
    if kind == "text_min":
        n = len((role.get(sec["key"]) or "").strip())
        return n >= sec["min_chars"], f"{n} von mindestens {sec['min_chars']} Zeichen"
    if kind == "tasks_min":
        return len(tasks) >= sec["min_tasks"], f"{len(tasks)} von mindestens {sec['min_tasks']} Aufgaben"
    if kind == "time_shares_source":
        ok = role.get("time_shares_source") == "source"
        return ok, "Zeitanteile stammen aus der Quelle" if ok else "Zeitanteile geschätzt"
    if kind == "skills_min":
        n = len(role.get("skills", []))
        return n >= sec["min_skills"], f"{n} von mindestens {sec['min_skills']} Skills"
    if kind == "field_present":
        ok = bool(role.get(sec["field"]))
        return ok, "gesetzt" if ok else "fehlt"
    if kind == "headcount_known":
        ok = wl.role_headcount(role) is not None
        return ok, "bekannt" if ok else "unbekannt"
    if kind == "collaboration":
        n = len(collab.get(role["id"], set()))
        return n > 0, f"{n} Rollen mit Beleg" if n else "kein Beleg für Zusammenarbeit"
    if kind == "regulated_decided":
        ok = "regulated" in role and "regulated" in (role.get("overrides_applied") or []) or role.get("status") in ("reviewed", "approved")
        return bool(ok), "durch Experten geprüft" if ok else "nur angenommen"
    return False, f"Prüfart '{kind}' unbekannt"


def run(graph: dict[str, Any], template: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    tasks_by_role: dict[str, list] = {}
    for t in graph["tasks"]:
        tasks_by_role.setdefault(t["role_id"], []).append(t)
    collab = collaboration_roles(graph)
    secs = template["sections"]
    total_w = sum(s["weight"] for s in secs) or 1
    rows = []
    for r in sorted(graph["roles"], key=lambda r: (r["name"], r["id"])):
        gaps, got = [], 0
        for s in secs:
            ok, detail = check_role(s, r, tasks_by_role.get(r["id"], []), collab)
            if ok:
                got += s["weight"]
            else:
                gaps.append({"section": s["label"], "detail": detail, "fill_from": s["fill_from"]})
        rows.append({"role_id": r["id"], "role": r["name"], "score": wl.round1(100.0 * got / total_w),
                     "complete": 100.0 * got / total_w >= template.get("complete_at", 80), "gaps": gaps})
    return rows, [s["label"] for s in secs]


def render(rows: list[dict[str, Any]], template: dict[str, Any], version: int) -> str:
    threshold = template.get("complete_at", 80)
    n_ok = sum(1 for r in rows if r["complete"])
    lines = ["# Vollständigkeit der Rollenbeschreibungen", "",
             f"Vorlage Version {template.get('config_version')}, vollständig ab {threshold} %. "
             f"**{n_ok} von {len(rows)} Rollen** erreichen die Schwelle.", "",
             "Eine Lücke ist keine Kritik an der Quelle, sondern ein Hinweis, wie belastbar die Bewertung darauf ist. "
             "Gefüllt wird in dieser Reihenfolge: erst aus einer internen Quelle, dann aus einer externen, dann bleibt sie "
             "als geschätzt gekennzeichnet.", "",
             "| Rolle | Füllgrad | Lücken |", "|---|---:|---|"]
    for r in sorted(rows, key=lambda r: (r["score"], r["role"])):
        gaps = "; ".join(g["section"] for g in r["gaps"]) or "keine"
        lines.append(f"| {r['role']} | {r['score']:.0f} % | {gaps} |")
    lines += ["", "## Lücken im Einzelnen", ""]
    for r in sorted(rows, key=lambda r: (r["score"], r["role"])):
        if not r["gaps"]:
            continue
        lines += [f"### {r['role']} ({r['score']:.0f} %)", ""]
        for g in r["gaps"]:
            lines.append(f"- **{g['section']}** — {g['detail']}. Füllen aus: {g['fill_from']}.")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--template", default=None)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    tpath = Path(args.template) if args.template else DEFAULT_TEMPLATE
    if not tpath.is_absolute():
        tpath = Path.cwd() / tpath
    if not tpath.exists():
        wl.fail(f"Vorlage nicht gefunden: {wl.relpath(tpath)}")
    template = wl.read_json(tpath)
    rows, _labels = run(graph, template)
    version = int(graph["meta"].get("version", 0))
    md = project / wl.DIR_REVIEW / f"vollstaendigkeit_v{version:03d}.md"
    wl.write_text(md, render(rows, template, version))
    csv = project / wl.DIR_REVIEW / f"vollstaendigkeit_v{version:03d}.csv"
    wl.write_csv(csv, [{"role_id": r["role_id"], "role": r["role"], "score": r["score"],
                        "gaps": "; ".join(g["section"] for g in r["gaps"])} for r in rows],
                 ["role_id", "role", "score", "gaps"])
    print(f"Geschrieben: {wl.relpath(md)} | Rollen={len(rows)} vollständig={sum(1 for r in rows if r['complete'])} "
          f"mittlerer Füllgrad={wl.round1(sum(r['score'] for r in rows) / len(rows)) if rows else 0:.0f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
