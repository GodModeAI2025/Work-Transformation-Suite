#!/usr/bin/env python3
"""
export_pages.py — erzeugt die Markdown-Seiten unter 05_pages/ aus den JSON-Registern.

Aufruf:
    python3 <skill>/scripts/export_pages.py --project ./mein-projekt [--force]

Liest 10_extraction/extract_*.json, 20_graph/scores.json und 20_graph/agents.json und schreibt
je Jobcluster, Rolle, Aufgabe und Agent eine Seite. Das ist der Weg für Projekte, die vor den
Seiten entstanden sind: einmal exportieren, danach sind die Seiten die Wahrheit und
compile_pages.py erzeugt die Register daraus.

Gibt es schon Seiten, schreibt das Skript nichts (sie könnten bearbeitet sein); --force
überschreibt sie. Prozesse, Blueprints und Experimente bleiben JSON: Ihre Struktur ist
verschachtelt, und ein flaches Frontmatter würde sie verfälschen.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pages_lib as pl  # noqa: E402
import workgraph_lib as wl  # noqa: E402

SCORE_KEYS = ["automation_ai", "automation_physical", "human_judgment", "productivity_boost",
              "data_readiness", "consequence_of_error"]
README = """# Seiten: die kanonische Fassung

Jede Datei hier ist eine Rolle, eine Aufgabe, ein Agent oder ein Jobcluster. Der Kopf zwischen den
`---`-Zeilen trägt die Felder, der Rumpf die Texte. `compile_pages.py` übersetzt die Seiten in die
JSON-Register (`10_extraction/`, `20_graph/scores.json`, `20_graph/agents.json`); die Pipeline tut
das vor jedem Lauf. Wer etwas ändern will, ändert die Seite, nicht das Register.

Regeln für den Kopf: eine Ebene, Zeichenketten in Anführungszeichen oder nackt, Zahlen, true, false,
null, flache Listen (`- "x"` je Zeile oder `["a", "b"]`). Keine Einrückung, keine Objekte, keine
Tabulatoren. Fehler nennt `compile_pages.py` mit Datei und Zeile.

| Ordner | Seite | Pflichtfelder im Kopf | Abschnitte im Rumpf |
|---|---|---|---|
| clusters/ | Jobcluster | type, job_family, job_cluster | Jobfamilie, Jobcluster |
| roles/ | Rolle | type, name, cluster | Zweck, Beschreibung, Skills (Tabelle) |
| tasks/ | Aufgabe | type, name, role, share_of_time | Beschreibung, Schritte (Liste), Begründung der Bewertung |
| agents/ | Agent | type, name, pattern | Fähigkeit, Aufsicht, Vertrag (JSON-Block) |

Belege stehen als Liste `evidence` im Kopf (`src-<hash>@<fundstelle>`), Bewertungen als
`score_<feld>` in der Aufgabenseite. Aufgaben eines Agenten als `"Rolle > Aufgabe"`.
"""


def role_slug(name: str) -> str:
    return pl.page_slug(name)


def task_slug(role: str, task: str) -> str:
    return f"{pl.page_slug(role)}--{pl.page_slug(task)}"[:120]


def cluster_page(ex: dict) -> tuple[Path, dict, str]:
    fam, clu = str(ex.get("job_family") or "Ohne Zuordnung"), str(ex.get("job_cluster") or ex.get("job_family") or "Ohne Zuordnung")
    meta = {"type": "cluster", "job_family": fam, "job_cluster": clu, "source": str(ex.get("source") or "")}
    body = (f"## Jobfamilie\n\n{ex.get('job_family_description') or ''}\n\n"
            f"## Jobcluster\n\n{ex.get('job_cluster_description') or ''}\n")
    return Path("clusters") / f"{pl.page_slug(clu)}.md", meta, body


def role_page(r: dict, cluster: str) -> tuple[Path, dict, str]:
    meta = {"type": "role", "name": r["name"], "cluster": cluster, "level": r.get("level") or "",
            "headcount": r.get("headcount"), "archetype": r.get("archetype") or "",
            "regulated": bool(r.get("regulated", False)), "is_new": bool(r.get("is_new", False)),
            "time_shares_source": r.get("time_shares_source") or "estimated",
            "evidence": [str(x) for x in (r.get("evidence") or [])]}
    rows = []
    for s in r.get("skills", []):
        if isinstance(s, dict):
            rows.append([s.get("name", ""), s.get("kind", "skill"), s.get("category", ""), s.get("level", 3),
                         s.get("importance", "supporting")])
        else:
            rows.append([str(s), "skill", "", 3, "supporting"])
    body = (f"## Zweck\n\n{r.get('purpose') or ''}\n\n## Beschreibung\n\n{r.get('description') or ''}\n\n"
            f"## Skills\n\n{pl.md_table(['Skill', 'Art', 'Kategorie', 'Niveau', 'Bedeutung'], rows)}\n")
    return Path("roles") / f"{role_slug(r['name'])}.md", meta, body


def task_page(t: dict, role_name: str, scores: dict | None) -> tuple[Path, dict, str]:
    skills = [s.get("name") if isinstance(s, dict) else str(s) for s in t.get("skills", [])]
    meta = {"type": "task", "name": t["name"], "role": role_name, "share_of_time": t.get("share_of_time"),
            "frequency": t.get("frequency") or "weekly", "nature": t.get("nature") or "cognitive",
            "confidence": t.get("confidence") or "inferred", "skills": [s for s in skills if s],
            "evidence": [str(x) for x in (t.get("evidence") or [])]}
    rationale = ""
    if scores:
        for k in SCORE_KEYS:
            if scores.get(k) is not None:
                meta[f"score_{k}"] = scores[k]
        for flag in ("interpersonal", "tacit_expertise"):
            if isinstance(scores.get(flag), bool):
                meta[f"score_{flag}"] = scores[flag]
        rationale = str(scores.get("rationale") or "")
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(t.get("workflow_steps") or [], start=1))
    body = (f"## Beschreibung\n\n{t.get('description') or ''}\n\n## Schritte\n\n{steps}\n\n"
            f"## Begründung der Bewertung\n\n{rationale}\n")
    return Path("tasks") / f"{task_slug(role_name, t['name'])}.md", meta, body


def agent_page(a: dict, task_names: dict[str, str]) -> tuple[Path, dict, str]:
    meta = {"type": "agent", "name": a["name"], "pattern": a.get("pattern") or "", "specificity": a.get("specificity") or "domain",
            "status": a.get("status") or "proposed", "complexity": a.get("complexity", 3),
            "existing_system": a.get("existing_system"),
            "prerequisites": [str(x) for x in (a.get("prerequisites") or [])],
            "orchestrates": [str(x) for x in (a.get("orchestrates") or [])],
            "tasks": sorted(task_names.get(t, t) for t in (a.get("task_ids") or []))}
    contract = a.get("contract")
    cblock = f"```json\n{json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)}\n```" if isinstance(contract, dict) else ""
    body = (f"## Fähigkeit\n\n{a.get('capability') or ''}\n\n## Aufsicht\n\n{a.get('oversight') or ''}\n\n"
            f"## Vertrag\n\n{cblock}\n")
    return Path("agents") / f"{pl.page_slug(a['name'])}.md", meta, body


def export(project: Path, force: bool = False) -> int:
    base = pl.pages_dir(project)
    if pl.has_pages(project) and not force:
        wl.fail(f"{wl.relpath(base)} enthält schon Seiten; sie sind die Wahrheit. Überschreiben nur mit --force.")
    exdir = project / wl.DIR_EXTRACTION
    files = sorted(exdir.glob("extract_*.json"))
    if not files:
        wl.fail(f"Keine Extraktionsdateien in {wl.relpath(exdir)}; nichts zu exportieren")
    scores_path = project / wl.DIR_GRAPH / "scores.json"
    scores = wl.read_json(scores_path) if scores_path.exists() else {}
    agents_path = project / wl.DIR_GRAPH / "agents.json"
    agents = wl.read_json(agents_path) if agents_path.exists() else []
    pages: list[tuple[Path, dict, str]] = []
    task_names: dict[str, str] = {}
    for f in files:
        ex = wl.read_json(f)
        cl_path, cl_meta, cl_body = cluster_page(ex)
        pages.append((cl_path, cl_meta, cl_body))
        for r in ex.get("roles", []):
            if not r.get("name"):
                continue
            pages.append(role_page(r, cl_meta["job_cluster"]))
            for t in r.get("tasks", []):
                if not t.get("name"):
                    continue
                tid = wl.make_id("task", r["name"], t["name"])
                task_names[tid] = f"{r['name']} > {t['name']}"
                pages.append(task_page(t, r["name"], scores.get(tid)))
    for a in agents:
        if a.get("name"):
            pages.append(agent_page(a, task_names))
    seen = set()
    for rel, meta, body in pages:
        if rel in seen:
            wl.fail(f"Zwei Seiten hätten denselben Namen: {rel} (Namen eindeutig machen)")
        seen.add(rel)
        pl.write_page(base / rel, meta, body)
    if not (base / "README.md").exists():
        wl.write_text(base / "README.md", README)
    return len(pages)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    n = export(project, args.force)
    print(f"Exportiert: {n} Seiten nach {wl.relpath(pl.pages_dir(project))}. Ab jetzt sind die Seiten die Wahrheit; "
          "compile_pages.py erzeugt die Register daraus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
