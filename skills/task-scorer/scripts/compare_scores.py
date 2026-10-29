#!/usr/bin/env python3
"""
compare_scores.py — vergleicht zwei unabhängige Bewertungsläufe derselben Aufgaben und legt vor,
wo sie mehr als einen Punkt auseinanderliegen.

Aufruf:
    python3 <skill>/scripts/compare_scores.py --project ./mein-projekt \
        [--first 20_graph/scores.json] [--second 20_graph/scores_zweitbewertung.json] [--max-diff 1]

Die Stanford-Erhebung (Shao et al. 2025) lässt jede Aufgabe von mindestens zwei Fachleuten bewerten
und holt weitere Urteile ein, bis die Streuung höchstens einen Punkt beträgt. Dieses Skript ist der
Vergleich dazu: Eine zweite Person oder ein zweiter, unabhängiger Claude-Lauf füllt dieselbe Vorlage
(`export_scoring_sheet.py --all`), das Skript zeigt Übereinstimmung je Feld und die Aufgaben, die eine
Klärung brauchen. Es ändert keine Bewertung.

Ausgabe: 30_review/zweitbewertung_vNNN.md (NNN = Graph-Version).

Kennzahlen je Feld: Anteil der Aufgaben innerhalb von ±max-diff, mittlere absolute Abweichung,
Krippendorffs Alpha (Intervallskala, zwei Bewertende). Alpha ab 0,8 gilt als belastbar, ab 0,667 als
vorläufig tragfähig; darunter ist die Rubrik für dieses Feld nicht eindeutig genug.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from score_roles import NUMERIC, automation_potential, derive_has  # noqa: E402

LABEL = {"automation_ai": "Maschinenanteil (KI/Software)", "automation_physical": "Robotikanteil",
         "human_judgment": "Urteilsbedarf", "productivity_boost": "Tandemgewinn", "data_readiness": "Datenreife",
         "consequence_of_error": "Fehlergewicht"}
ALPHA_GOOD = 0.8
ALPHA_TENTATIVE = 0.667


def alpha_interval(pairs: list[tuple[float, float]]) -> float | None:
    """Krippendorffs Alpha für zwei Bewertende ohne fehlende Werte, Intervallmetrik."""
    if len(pairs) < 2:
        return None
    values = [v for p in pairs for v in p]
    n = len(values)
    do = sum((a - b) ** 2 for a, b in pairs) / len(pairs)
    de = 2.0 * (n * sum(v * v for v in values) - sum(values) ** 2) / (n * (n - 1))
    if de <= 0:
        return None
    return round(1.0 - do / de, 3)


def resolve(project: Path, arg: str | None, default: str) -> Path:
    p = Path(arg) if arg else project / wl.DIR_GRAPH / default
    if not p.is_absolute() and arg:
        p = (Path.cwd() / p) if (Path.cwd() / p).exists() else project / p
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--first", default=None, help="erste Bewertung (Standard 20_graph/scores.json)")
    ap.add_argument("--second", default=None, help="zweite Bewertung (Standard 20_graph/scores_zweitbewertung.json)")
    ap.add_argument("--max-diff", type=float, default=1.0)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    first_p = resolve(project, args.first, "scores.json")
    second_p = resolve(project, args.second, "scores_zweitbewertung.json")
    for p in (first_p, second_p):
        if not p.exists():
            wl.fail(f"{wl.relpath(p)} fehlt. Zweite Bewertung: export_scoring_sheet.py --all, unabhängig ausfüllen, "
                    "als scores_zweitbewertung.json speichern.", code=3)
    a, b = wl.read_json(first_p), wl.read_json(second_p)
    tasks = wl.index_by_id(graph["tasks"])
    roles = wl.index_by_id(graph["roles"])

    def complete(e):
        return isinstance(e, dict) and all(isinstance(e.get(f), (int, float)) and not isinstance(e.get(f), bool) for f in NUMERIC)

    common = sorted(t for t in set(a) & set(b) if t in tasks and complete(a[t]) and complete(b[t]))
    only = len([t for t in set(a) ^ set(b) if t in tasks])
    if not common:
        wl.fail("Keine Aufgabe ist in beiden Bewertungen vollständig bewertet")
    rows, disputed = [], []
    for f in NUMERIC:
        pairs = [(float(a[t][f]), float(b[t][f])) for t in common]
        within = sum(1 for x, y in pairs if abs(x - y) <= args.max_diff)
        mad = sum(abs(x - y) for x, y in pairs) / len(pairs)
        al = alpha_interval(pairs)
        reading = ("nicht berechenbar (keine Streuung)" if al is None else "belastbar" if al >= ALPHA_GOOD
                   else "vorläufig tragfähig" if al >= ALPHA_TENTATIVE else "uneinheitlich: Anker der Rubrik schärfen")
        rows.append(f"| {LABEL[f]} | {100.0 * within / len(pairs):.0f} % | {mad:.2f} | {'–' if al is None else f'{al:.2f}'} | {reading} |")
    has_diff = 0
    for t in common:
        diffs = {f: float(b[t][f]) - float(a[t][f]) for f in NUMERIC if abs(float(b[t][f]) - float(a[t][f])) > args.max_diff}
        nature = tasks[t].get("nature") or "cognitive"
        ha = derive_has(automation_potential({k: float(a[t][k]) for k in NUMERIC}, nature), float(a[t]["human_judgment"]), a[t])
        hb = derive_has(automation_potential({k: float(b[t][k]) for k in NUMERIC}, nature), float(b[t]["human_judgment"]), b[t])
        if ha != hb:
            has_diff += 1
        if diffs or ha != hb:
            disputed.append((t, diffs, ha, hb))
    version = int(graph["meta"].get("version", 0))
    out = [f"# Zweitbewertung — Version {version}", "",
           f"Verglichen: {wl.relpath(first_p, project)} und {wl.relpath(second_p, project)}. {len(common)} Aufgaben in beiden "
           f"vollständig bewertet, {only} nur in einer. Schwelle für Klärung: Abstand über {args.max_diff:g} Punkt(e) "
           "oder unterschiedliche HAS-Stufe.", "",
           "## Übereinstimmung je Feld", "",
           f"| Feld | innerhalb ±{args.max_diff:g} | Ø Abstand | Alpha | Lesart |", "|---|---:|---:|---:|---|"] + rows
    out += ["", f"HAS-Stufe gleich bei {len(common) - has_diff} von {len(common)} Aufgaben.", "",
            "## Aufgaben mit Klärungsbedarf", "",
            "Beide Bewertenden lesen die Begründung des anderen und einigen sich, oder eine dritte Person bewertet. "
            "Das Ergebnis geht über `overrides.csv` mit Name und Begründung in den Graphen.", "",
            "| Rolle | Aufgabe | Felder (zweite − erste) | HAS erste | HAS zweite |", "|---|---|---|---|---|"]
    for t, diffs, ha, hb in sorted(disputed, key=lambda x: (roles[tasks[x[0]]["role_id"]]["name"], tasks[x[0]]["name"])):
        fields = ", ".join(f"{LABEL[f]} {d:+.0f}" for f, d in diffs.items()) or "–"
        out.append(f"| {roles[tasks[t]['role_id']]['name']} | {tasks[t]['name']} | {fields} | H{ha} | H{hb} |")
    if not disputed:
        out.append("| – | Keine | – | – | – |")
    path = project / wl.DIR_REVIEW / f"zweitbewertung_v{version:03d}.md"
    wl.write_text(path, "\n".join(out) + "\n")
    print(f"Geschrieben: {wl.relpath(path)} | Aufgaben={len(common)} Klärungsbedarf={len(disputed)} HAS abweichend={has_diff}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
