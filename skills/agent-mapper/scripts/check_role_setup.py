#!/usr/bin/env python3
"""
check_role_setup.py — prüft ein Rollen-Setup-Paket und sagt, wie weit es ist.

Aufruf:
    python3 <skill>/scripts/check_role_setup.py --package 40_output/rollen_setup/<rolle> [--strict]

Je Skill ein Reifegrad:
    entwurf     weniger als fünf echte Testfälle (`real_data: true`)
    im Test     mindestens fünf echte Fälle, aber weniger als zwei Schleifen oder nicht alle bestanden
    live-reif   mindestens fünf echte Fälle, mindestens zwei Schleifen, letzter Lauf alle bestanden

Dazu die Regeln des Playbooks als Prüfungen:
- Der Systemprompt ist schlank (Zeilen- und Zeichengrenze). Ein überladener Prompt macht Ergebnisse unklarer.
- Routinen sind nur für live-reife Skills aktiv. Erst erweitern, dann automatisieren.
- Die Rollen.md nennt, wie viele Felder noch offen sind.
- Jeder Skill hat gültigen Frontmatter und ein Testfallgerüst.
- Die Tool-Tabelle gibt keine Freigabe, solange dort „offen“ steht.

Mit --strict endet das Skript mit Code 2, sobald eine Regel verletzt ist (zum Beispiel eine aktive Routine
für einen unreifen Skill). Ein unfertiges Paket ist kein Fehler; ein Paket, das so tut, als wäre es fertig, schon.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_PROMPT_LINES = 80
MAX_PROMPT_CHARS = 5000
MIN_CASES = 5
MIN_LOOPS = 2
OPEN = "❓ offen"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    meta: dict[str, str] = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            return meta
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", ln)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                try:
                    v = json.loads(v) if v[0] == '"' else v[1:-1]
                except ValueError:
                    v = v[1:-1]
            meta[m.group(1)] = v
    return None


def readiness(cases_doc: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    real = [c for c in cases_doc.get("cases", []) if c.get("real_data") is True]
    loops = int(cases_doc.get("tested_loops") or 0)
    all_pass = bool(real) and all(c.get("last_result") == "pass" for c in real)
    info = {"real_cases": len(real), "loops": loops, "all_pass": all_pass}
    if len(real) < int(cases_doc.get("min_cases") or MIN_CASES):
        return "entwurf", info
    if loops < int(cases_doc.get("min_loops") or MIN_LOOPS) or not all_pass:
        return "im Test", info
    return "live-reif", info


def check(package: Path) -> tuple[list[str], list[str], list[dict[str, Any]], dict[str, Any]]:
    problems: list[str] = []
    notes: list[str] = []
    skills_out: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    for rel in ("README.md", "kontext/Rollen.md", "agent/systemprompt.md", "tools/anbindungen.md", "routinen/routinen.json", "pflege/pflege.md"):
        if not (package / rel).exists():
            problems.append(f"{rel} fehlt")

    prof = package / "kontext" / "Rollen.md"
    if prof.exists():
        n_open = prof.read_text(encoding="utf-8").count(OPEN)
        summary["open_fields"] = n_open
        if n_open:
            notes.append(f"Rollen.md: {n_open} Felder noch offen (Interview in kontext/interview-prompt.md)")

    sp = package / "agent" / "systemprompt.md"
    if sp.exists():
        text = sp.read_text(encoding="utf-8")
        if len(text.splitlines()) > MAX_PROMPT_LINES or len(text) > MAX_PROMPT_CHARS:
            problems.append(f"Systemprompt zu lang ({len(text.splitlines())} Zeilen, {len(text)} Zeichen; "
                            f"Grenze {MAX_PROMPT_LINES} Zeilen / {MAX_PROMPT_CHARS} Zeichen) — Aufgaben gehören in Skills, der Prompt steuert nur die Zusammenarbeit")

    sdir = package / "skills"
    names = sorted(p.name for p in sdir.iterdir() if p.is_dir()) if sdir.is_dir() else []
    if not names:
        problems.append("keine Skills im Paket")
    for name in names:
        d = sdir / name
        md = d / "SKILL.md"
        status = "entwurf"
        info: dict[str, Any] = {"real_cases": 0, "loops": 0, "all_pass": False}
        if not md.exists():
            problems.append(f"skills/{name}/SKILL.md fehlt")
        else:
            fm = frontmatter(md.read_text(encoding="utf-8"))
            if fm is None:
                problems.append(f"skills/{name}/SKILL.md: kein gültiger Frontmatter-Block")
            else:
                if fm.get("name") != name or not NAME_RE.match(name):
                    problems.append(f"skills/{name}/SKILL.md: name '{fm.get('name')}' passt nicht zum Ordner")
                if not fm.get("description"):
                    problems.append(f"skills/{name}/SKILL.md: description fehlt")
                elif len(fm["description"]) > 1024:
                    problems.append(f"skills/{name}/SKILL.md: description über 1024 Zeichen")
        cp = d / "evals" / "cases.json"
        if not cp.exists():
            problems.append(f"skills/{name}/evals/cases.json fehlt — ohne Testfälle ist ein Skill nicht prüfbar")
        else:
            try:
                doc = json.loads(cp.read_text(encoding="utf-8"))
            except ValueError:
                problems.append(f"skills/{name}/evals/cases.json ist kein gültiges JSON")
                doc = {}
            if doc:
                if len(doc.get("cases", [])) < MIN_CASES:
                    problems.append(f"skills/{name}: nur {len(doc.get('cases', []))} Fälle im Gerüst, mindestens {MIN_CASES} nötig")
                status, info = readiness(doc)
        skills_out.append({"name": name, "status": status, **info})
        if status == "entwurf":
            notes.append(f"{name}: Entwurf — {info['real_cases']} von {MIN_CASES} echten Testfällen")
        elif status == "im Test":
            notes.append(f"{name}: im Test — {info['loops']} von {MIN_LOOPS} Schleifen, {'alle bestanden' if info['all_pass'] else 'nicht alle bestanden'}")

    rj = package / "routinen" / "routinen.json"
    if rj.exists():
        try:
            routines = json.loads(rj.read_text(encoding="utf-8")).get("routines", [])
        except ValueError:
            routines = []
            problems.append("routinen/routinen.json ist kein gültiges JSON")
        state = {s["name"]: s["status"] for s in skills_out}
        for r in routines:
            if r.get("active") is True and state.get(r.get("skill")) != "live-reif":
                problems.append(f"Routine „{r.get('trigger')}“ für {r.get('skill')} ist aktiv, der Skill aber {state.get(r.get('skill'), 'unbekannt')} — "
                                "erst erweitern, dann automatisieren")
        summary["routines_active"] = sum(1 for r in routines if r.get("active") is True)

    tp = package / "tools" / "anbindungen.md"
    if tp.exists():
        summary["tools_open"] = tp.read_text(encoding="utf-8").count(OPEN)
        if summary["tools_open"]:
            notes.append(f"Tools: {summary['tools_open']} Anbindungen ohne Freigabe — der Agent hat dort keinen Zugriff")
    return problems, notes, skills_out, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    package = Path(args.package)
    if not package.is_dir():
        print(f"FEHLER   Paket nicht gefunden: {package}")
        return 2
    problems, notes, skills, summary = check(package)
    for s in skills:
        print(f"SKILL    {s['name']}: {s['status']} (echte Fälle {s['real_cases']}, Schleifen {s['loops']})")
    for n in notes:
        print(f"OFFEN    {n}")
    for p in problems:
        print(f"PROBLEM  {p}")
    live = sum(1 for s in skills if s["status"] == "live-reif")
    print(f"Ergebnis: Skills={len(skills)} live-reif={live} Probleme={len(problems)} offene Felder={summary.get('open_fields', '–')}")
    return 2 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
