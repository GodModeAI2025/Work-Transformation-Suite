#!/usr/bin/env python3
"""
check_evidence.py — zeigt, welche Aussagen des Graphen belegt sind, und prüft jede Fundstelle.

Aufruf:
    python3 <skill>/scripts/check_evidence.py --project ./mein-projekt [--strict]

Ausgabe: 30_review/belege_vNNN.md und eine Kurzfassung auf der Konsole.

Drei Belegstände je Eintrag:
    belegt      mindestens ein Beleg src-<hash>@<fundstelle> auf eine registrierte Quelle
    geschätzt   ausdrücklich als Schätzung oder Vorschlag gekennzeichnet (Aufgabe: confidence inferred,
                Rolle: is_new, Kennzahl: baseline.basis estimated)
    unbelegt    weder noch; die Aussage steht ohne Herkunft im Graphen

Fundstellen werden gegen den Quelltext geprüft: ein Anker muss eine Überschrift sein, eine Zeile
im Text liegen. Freitext-Fundstellen (Seite, Folie) gelten als nicht prüfbar und werden gezählt.

Exit-Code 0: nichts zu beanstanden. 1: unbelegte Aussagen oder nicht auflösbare Fundstellen,
nur gemeldet. 3: dasselbe bei strenger Belegpflicht (--strict oder project.json evidence_policy).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

COLLECTIONS = [("roles", "evidence", "Rollen"), ("tasks", "evidence", "Aufgaben"), ("processes", "evidence", "Prozesse"),
               ("process_steps", "evidence", "Prozessschritte"), ("metrics", "evidence", "Kennzahlen"),
               ("controls", "source_evidence", "Kontrollen")]
LABEL = {"sourced": "belegt", "estimated": "geschätzt", "unsourced": "unbelegt"}


def analyse(project: Path, graph: dict) -> dict:
    reg = wl.load_source_register(project)
    bodies: dict[str, str] = {}
    for sid, rec in reg.items():
        path = project / rec.get("file", "")
        if path.exists():
            bodies[sid] = wl.split_frontmatter(path.read_text(encoding="utf-8"))[1]
    rows, bad_locators, free_locators = [], [], 0
    for coll, field, label in COLLECTIONS:
        counts = {"sourced": 0, "estimated": 0, "unsourced": 0}
        unsourced = []
        for it in graph.get(coll, []):
            st = it.get("evidence_status") or wl.evidence_status({"evidence": it.get(field) or []})
            counts[st] = counts.get(st, 0) + 1
            if st == "unsourced":
                unsourced.append(it.get("name") or it["id"])
            for ref in it.get(field) or []:
                ev = wl.parse_evidence(ref)
                if not ev:
                    continue
                sid, loc = ev
                if sid not in bodies:
                    bad_locators.append((label, it.get("name") or it["id"], ref, "Quelle nicht im Register oder Datei fehlt"))
                    continue
                ok, note = wl.resolve_locator(bodies[sid], loc)
                if not ok:
                    bad_locators.append((label, it.get("name") or it["id"], ref, note))
                elif note:
                    free_locators += 1
        rows.append({"collection": coll, "label": label, "total": len(graph.get(coll, [])), **counts, "unsourced_names": unsourced})
    return {"rows": rows, "bad_locators": bad_locators, "free_locators": free_locators, "sources": len(reg),
            "unregistered": sorted(sid for sid in {wl.parse_evidence(r)[0] for coll, field, _ in COLLECTIONS
                                                   for it in graph.get(coll, []) for r in (it.get(field) or [])
                                                   if wl.parse_evidence(r)} if sid not in reg)}


def render(a: dict, version: int, policy: str) -> str:
    lines = [f"# Belege (Graph-Version {version})", "",
             f"Belegpflicht: {policy}. {a['sources']} registrierte Quelle(n). "
             "„belegt“ hat eine Fundstelle in einer registrierten Quelle, „geschätzt“ ist als Schätzung "
             "gekennzeichnet, „unbelegt“ steht ohne Herkunft im Graphen.", "",
             "| Sammlung | Einträge | belegt | geschätzt | unbelegt |", "|---|---:|---:|---:|---:|"]
    for r in a["rows"]:
        lines.append(f"| {r['label']} | {r['total']} | {r['sourced']} | {r['estimated']} | {r['unsourced']} |")
    lines.append("")
    open_rows = [r for r in a["rows"] if r["unsourced_names"]]
    if open_rows:
        lines += ["## Unbelegt", "", "Je Eintrag fehlt ein Beleg. Entweder die Quelle registrieren und die Fundstelle "
                  "eintragen (`evidence` in der Extraktion), oder den Eintrag als Schätzung kennzeichnen.", ""]
        for r in open_rows:
            lines.append(f"- **{r['label']}:** " + ", ".join(r["unsourced_names"]))
        lines.append("")
    if a["bad_locators"]:
        lines += ["## Fundstellen, die nicht aufgehen", ""]
        lines += [f"- {label} „{name}“: `{ref}` ({note})" for label, name, ref, note in a["bad_locators"]]
        lines.append("")
    if a["free_locators"]:
        lines += [f"{a['free_locators']} Fundstelle(n) sind Freitext (Seite, Folie) und wurden nicht geprüft.", ""]
    if a["unregistered"]:
        lines += ["## Verweise auf nicht registrierte Quellen", ""] + [f"- {s}" for s in a["unregistered"]] + [""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    policy = "strict" if args.strict else wl.evidence_policy(project)
    a = analyse(project, graph)
    version = int(graph.get("meta", {}).get("version", 0))
    out = project / wl.DIR_REVIEW / f"belege_v{version:03d}.md"
    wl.write_text(out, render(a, version, policy))
    unsourced = sum(r["unsourced"] for r in a["rows"])
    total = sum(r["total"] for r in a["rows"])
    sourced = sum(r["sourced"] for r in a["rows"])
    print(f"Geschrieben: {wl.relpath(out)} | Einträge={total} belegt={sourced} unbelegt={unsourced} "
          f"Fundstellen fehlerhaft={len(a['bad_locators'])} Quellen={a['sources']}")
    for label, name, ref, note in a["bad_locators"]:
        print(f"FEHLER   {label} „{name}“: {ref} ({note})")
    problems = unsourced or a["bad_locators"] or a["unregistered"]
    if problems and policy == "strict":
        print("STOPP: Belegpflicht strict. Nächster Schritt für Claude: Quellen registrieren und Belege eintragen, "
              "oder Einträge als Schätzung kennzeichnen; siehe Bericht.")
        return 3
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
