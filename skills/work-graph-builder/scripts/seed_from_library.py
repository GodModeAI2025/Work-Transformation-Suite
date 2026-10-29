#!/usr/bin/env python3
"""
seed_from_library.py — übernimmt ein Branchenpaket der Referenzbibliothek als Seiten ins Projekt.

Aufruf:
    python3 <skill>/scripts/seed_from_library.py --project ./mein-projekt --branche energieversorgung \
        [--cluster "Netzbetrieb"] [--rollen "Netzführer;Netzplaner"] [--date 2026-03-01] [--dry-run]

Was passiert:
1. `library/branchen/<branche>/quelle.md` wird als Quelle der Art „reference“ registriert. Die Seiten
   verweisen mit `src-<hash>@#<rolle>` darauf; der Belegstand solcher Einträge ist „reference“:
   ein Vorrat, der am Haus noch bestätigt werden muss, kein Befund.
2. Die Seiten des Pakets (Cluster, Rollen, Aufgaben) werden nach 05_pages/ kopiert. Eine Seite, die es
   dort schon gibt, bleibt unverändert; das Skript nennt sie. So überschreibt die Bibliothek nie, was
   jemand am Haus angepasst hat.
3. `compile_pages.py` übersetzt die Seiten beim nächsten Pipeline-Lauf in die Register.

Ein Projekt mit Extraktionsdateien, aber ohne Seiten, muss zuerst `export_pages.py` durchlaufen: Sobald
Seiten existieren, sind sie die Wahrheit, und die bisherigen Register würden sonst verloren gehen.

Die Zeitanteile der Bibliothek sind typische Verteilungen (`time_shares_source: estimated`); die
Rechtsgrundlagen in quelle.md gelten für Deutschland und sind Prüfaufträge, keine Rechtsberatung.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pages_lib as pl  # noqa: E402
import register_source as rs  # noqa: E402
import workgraph_lib as wl  # noqa: E402


def branch_dir(branche: str) -> Path:
    lib = wl.library_dir()
    if lib is None:
        wl.fail("Referenzbibliothek nicht gefunden (library/ im Skill work-graph-builder)")
    d = lib / "branchen" / branche
    if not (d / "quelle.md").exists():
        index = wl.load_library_json("branchen", "index.json") or {}
        wl.fail(f"Branche {branche!r} nicht in der Bibliothek. Bekannt: {', '.join(sorted(index))}")
    return d


def select(pages: dict, cluster: str | None, rollen: list[str]) -> tuple[list, list, list]:
    clusters = pages["cluster"]
    roles = pages["role"]
    tasks = pages["task"]
    if cluster:
        want = wl.normalize_name(cluster)
        clusters = [c for c in clusters if wl.normalize_name(c["meta"].get("job_cluster", "")) == want]
        names = {c["meta"]["job_cluster"] for c in clusters}
        roles = [r for r in roles if r["meta"].get("cluster") in names]
    if rollen:
        want = {wl.normalize_name(x) for x in rollen}
        roles = [r for r in roles if wl.normalize_name(r["meta"].get("name", "")) in want]
        names = {r["meta"]["cluster"] for r in roles}
        clusters = [c for c in clusters if c["meta"]["job_cluster"] in names]
    role_names = {r["meta"]["name"] for r in roles}
    tasks = [t for t in tasks if t["meta"].get("role") in role_names]
    return clusters, roles, tasks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--branche", required=True)
    ap.add_argument("--cluster", default=None, help="nur diesen Jobcluster übernehmen")
    ap.add_argument("--rollen", default=None, help="nur diese Rollen (mit ; getrennt)")
    ap.add_argument("--date", default=None, help="Registrierungsdatum der Quelle (Standard: heute)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    if not (project / wl.PROJECT_FILE).exists():
        wl.fail(f"Kein Projekt unter {wl.relpath(project)} (init_project.py)")
    bdir = branch_dir(args.branche)
    has_registers = any((project / wl.DIR_EXTRACTION).glob("extract_*.json"))
    if has_registers and not pl.has_pages(project):
        wl.fail("Das Projekt hat Extraktionsdateien, aber keine Seiten. Erst export_pages.py ausführen, "
                "sonst gehen die bisherigen Register verloren, sobald Seiten die Wahrheit sind.")
    # Seiten der Bibliothek lesen (gleiches Format wie 05_pages)
    lib_pages, problems = _read_lib_pages(bdir)
    if problems:
        for p in problems:
            print(f"FEHLER   {p}")
        wl.fail("Bibliotheksseiten fehlerhaft; bitte melden")
    rollen = [x.strip() for x in (args.rollen or "").split(";") if x.strip()]
    clusters, roles, tasks = select(lib_pages, args.cluster, rollen)
    if not roles:
        wl.fail("Keine Rolle ausgewählt (Cluster- oder Rollenname prüfen: library_catalog.py --branche …)")
    when = args.date or date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", when):
        wl.fail("--date im Format JJJJ-MM-TT")
    label = (wl.load_library_json("branchen", "index.json") or {}).get(args.branche, {}).get("label", args.branche)
    if args.dry_run:
        print(f"Würde registrieren: Referenzbibliothek {label} (quelle.md) und übernehmen: "
              f"{len(clusters)} Cluster, {len(roles)} Rollen, {len(tasks)} Aufgaben")
        for r in roles:
            print(f"  {r['meta']['name']} ({r['meta'].get('cluster')})")
        return 0
    rec = rs.register(project, bdir / "quelle.md", f"Referenzbibliothek: {label}", f"library/branchen/{args.branche}/quelle.md",
                      "reference", "de", "script", "active", when, None, None)
    sid = rec["source_id"]
    written, skipped = [], []
    target = pl.pages_dir(project)
    for page in clusters + roles + tasks:
        rel = Path(page["path"])
        dst = target / rel
        if dst.exists():
            skipped.append(rel.as_posix())
            continue
        meta = dict(page["meta"])
        if isinstance(meta.get("evidence"), list):
            meta["evidence"] = [str(x).replace("lib@", f"{sid}@") for x in meta["evidence"]]
        pl.write_page(dst, meta, page["body"])
        written.append(rel.as_posix())
    print(f"Übernommen aus Referenzbibliothek {label}: {len(written)} Seiten ({len(clusters)} Cluster, {len(roles)} Rollen, "
          f"{len(tasks)} Aufgaben), Quelle {sid}. Belegstand dieser Einträge: „reference“, am Haus zu bestätigen.")
    for s in skipped:
        print(f"  unverändert (existiert schon): {s}")
    print("Nächster Schritt: Stellenzahlen eintragen, Zeitanteile prüfen, dann run_pipeline.py.")
    return 0


def _read_lib_pages(bdir: Path):
    """Seiten eines Bibliothekspakets; Pfade relativ zum Paket (clusters/…, roles/…, tasks/…)."""
    out = {k: [] for k in pl.PAGE_KINDS}
    problems = []
    for path in sorted(bdir.rglob("*.md")):
        if path.name == "quelle.md":
            continue
        try:
            rel = path.relative_to(bdir).as_posix()
            meta, body = pl.parse_frontmatter(path.read_text(encoding="utf-8"), rel)
            kind = meta.get("type")
            if kind not in pl.PAGE_KINDS:
                raise pl.PageError(f"{rel}: type fehlt")
            out[kind].append({"path": rel, "meta": meta, "body": body, "sections": pl.sections(body)})
        except pl.PageError as e:
            problems.append(str(e))
    return out, problems


if __name__ == "__main__":
    sys.exit(main())
