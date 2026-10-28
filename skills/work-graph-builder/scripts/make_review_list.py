#!/usr/bin/env python3
"""
make_review_list.py — erzeugt aus dem aktuellen Graphen eine Review-Liste für
Fachexperten (Markdown) plus ein Overrides-Template (CSV).

Aufruf:
    python3 <skill>/scripts/make_review_list.py --project ./mein-projekt [--cluster "Name"]

Ausgabe:
    30_review/review_vNNN.md      Je Rolle: Beschreibung, Aufgaben mit Zeitanteil, Skills,
                                  Ja/Nein-Fragen, Platz für Korrekturen
    30_review/overrides.csv       Wird angelegt, falls nicht vorhanden (Spaltenkopf)

Die Idee: Ein Experte soll pro Rolle in fünf Minuten bestätigen oder korrigieren
können. Korrekturen trägt er in overrides.csv ein (oder Claude überträgt sie aus
seinen Notizen dorthin); apply_overrides.py spielt sie deterministisch ein.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

OVERRIDE_HEADER = "entity_type;entity_id;field;value;reviewer;comment\n"

# Granularitätsprüfung: Eine Rolle, in der viele fachfremde Aufgaben zusammengepresst sind,
# verliert beim Bewerten Kontext. Der Hinweis ist deterministisch und nur eine Frage an
# den Fachexperten, kein Urteil.
SPLIT_TASKS_MAX = 10
SPLIT_MIN_TASKS_FOR_OVERLAP = 6
SPLIT_DISJOINT_SHARE = 0.6


def split_hint(task_list: list[dict]) -> str | None:
    n = len(task_list)
    if n >= SPLIT_TASKS_MAX:
        return f"{n} Aufgaben in einer Rolle (ab {SPLIT_TASKS_MAX} prüfen)"
    with_skills = [set(t.get("skill_ids", [])) for t in task_list if t.get("skill_ids")]
    if n >= SPLIT_MIN_TASKS_FOR_OVERLAP and len(with_skills) >= SPLIT_MIN_TASKS_FOR_OVERLAP:
        pairs = disjoint = 0
        for i in range(len(with_skills)):
            for j in range(i + 1, len(with_skills)):
                pairs += 1
                disjoint += 0 if with_skills[i] & with_skills[j] else 1
        if pairs and disjoint / pairs >= SPLIT_DISJOINT_SHARE:
            return (f"{round(100 * disjoint / pairs)} % der Aufgabenpaare teilen keinen Skill — "
                    "mehrere Berufsbilder in einer Rolle?")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--cluster", default=None, help="Nur Rollen dieses Jobclusters")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst build_graph.py ausführen")

    version = graph["meta"].get("version", 0)
    skills = wl.index_by_id(graph["skills"])
    tasks = wl.index_by_id(graph["tasks"])
    clusters = wl.index_by_id(graph["job_clusters"])
    families = wl.index_by_id(graph["job_families"])

    roles = sorted(graph["roles"], key=lambda r: (clusters[r["cluster_id"]]["name"], r["name"], r["id"]))
    if args.cluster:
        want = wl.normalize_name(args.cluster)
        roles = [r for r in roles if wl.normalize_name(clusters[r["cluster_id"]]["name"]) == want]

    lines = [
        f"# Review-Liste Arbeitsgraph — Version {version}",
        "",
        f"Projekt: {graph['meta'].get('project', '')} | Bereich: {graph['meta'].get('scope', '')}",
        "",
        "Bitte je Rolle die Fragen beantworten. Korrekturen kommen in `30_review/overrides.csv`",
        "(Format: entity_type;entity_id;field;value;reviewer;comment). Beispiele:",
        "",
        "```",
        "role;ro_1a2b3c4d5e6f;headcount;14;M. Muster;laut Stellenplan 2026",
        "task;ta_0f9e8d7c6b5a;share_of_time;35;M. Muster;ist eher ein Drittel",
        "task;ta_0f9e8d7c6b5a;status;reviewed;M. Muster;",
        "task;ta_0f9e8d7c6b5a;delete;true;M. Muster;gehört zu anderer Rolle",
        "role;ro_1a2b3c4d5e6f;absorption;attrition;M. Muster;Altersteilzeit, 6 Stellen bis 2028",
        "role;ro_1a2b3c4d5e6f;absorption_pct;60;M. Muster;Rest nicht auffangbar",
        "role;ro_1a2b3c4d5e6f;day_rate_eur;640;M. Muster;Planwert Controlling",
        "```",
        "",
        "`absorption` sagt, wie frei werdende Kapazität aufgefangen wird: `growth` (Wachstum), `attrition` "
        "(Fluktuation, Altersteilzeit), `redeployment` (Umbesetzung) oder `none`. Ohne Angabe bleibt das "
        "realisierbare Potenzial leer — „nicht bewertet“ ist nicht „null“.",
        "",
    ]
    for r in roles:
        cl = clusters[r["cluster_id"]]
        fam = families[cl["family_id"]]
        lines += [
            "---",
            "",
            f"## {r['name']}  `{r['id']}`",
            "",
            f"Jobfamilie: {fam['name']} › Cluster: {cl['name']} | Level: {r.get('level') or '–'} | "
            f"Headcount: {r.get('headcount') if r.get('headcount') is not None else '–'} | Status: {r['status']}",
            "",
            f"**Zweck:** {r.get('purpose') or '–'}",
            "",
            f"**Beschreibung:** {r.get('description') or '–'}",
            "",
            "### Aufgaben",
            "",
            "| ID | Aufgabe | Zeitanteil | Häufigkeit | Art | Quelle |",
            "|---|---|---:|---|---|---|",
        ]
        for tid in sorted(r["task_ids"], key=lambda t: (-tasks[t]["share_of_time"], tasks[t]["name"])):
            t = tasks[tid]
            lines.append(
                f"| `{t['id']}` | {t['name']} | {t['share_of_time']:.0f} % | {t['frequency']} | {t['nature']} | {t['confidence']} |"
            )
        lines += ["", "### Skills", ""]
        for s in sorted(r["skills"], key=lambda s: (s["importance"] != "core", skills[s["skill_id"]]["name"])):
            sk = skills[s["skill_id"]]
            lines.append(f"- {sk['name']} (Niveau {s['level']}/5, {s['importance']}) `{sk['id']}`")
        lines += [
            "",
            "### Fragen an den Fachexperten",
            "",
            "1. Beschreibt die Aufgabenliste die Rolle vollständig? Fehlt eine Aufgabe mit mehr als 5 % Zeitanteil?",
            "2. Stimmen die Zeitanteile grob (±10 Prozentpunkte)?",
            "3. Gibt es Aufgaben, die in Wirklichkeit eine andere Rolle erledigt?",
            "4. Fehlt ein Kern-Skill, oder ist ein Niveau deutlich zu hoch/zu niedrig?",
            "5. Ist die Rolle reguliert (Netzbetrieb, Handel, Arbeitssicherheit, Datenschutz)? Aktuell: "
            + ("ja" if r.get("regulated") else "nein"),
            "",
            "6. Wenn Kapazität frei wird: Wie wird sie aufgefangen (Wachstum, Fluktuation/Altersteilzeit, "
            "Umbesetzung, gar nicht)? Eintrag `absorption` in overrides.csv.",
            "",
            "Notizen:",
            "",
            "",
        ]
        hint = split_hint([tasks[t] for t in r["task_ids"] if t in tasks])
        if hint:
            lines.insert(lines.index("### Aufgaben"), f"**Split prüfen:** {hint}. Besser in zwei Rollen schneiden? "
                                                       "Gesamtgrößen und Kontext gehen sonst im Mittelwert unter.")
            lines.insert(lines.index("### Aufgaben"), "")

    out = project / wl.DIR_REVIEW / f"review_v{version:03d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(out, "\n".join(lines))
    ov = project / wl.DIR_REVIEW / "overrides.csv"
    if not ov.exists():
        wl.write_text(ov, OVERRIDE_HEADER, newline="")
    print(f"Geschrieben: {wl.relpath(out)} ({len(roles)} Rollen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
