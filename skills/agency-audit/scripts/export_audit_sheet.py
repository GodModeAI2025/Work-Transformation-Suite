#!/usr/bin/env python3
"""
export_audit_sheet.py — erzeugt den Fragebogen der Beschäftigtenbefragung je Rolle und eine
Antwortvorlage, die import_audit.py liest.

Aufruf:
    python3 <skill>/scripts/export_audit_sheet.py --project ./mein-projekt [--rollen "Rolle A;Rolle B"]

Ausgabe:
    30_review/befragung/fragebogen_<rolle>.md   Rahmen, offene Fragen, Bewertungsfragen je Aufgabe
    30_review/befragung/antworten_vorlage.csv   eine Zeile je Rolle und Aufgabe, Teilnehmercode leer

Die ausgefüllten Antworten gehören nach 00_input/befragung/*.csv. Jede befragte Person trägt einen
selbst gewählten Code ein (keine Namen, keine Personalnummer) und kopiert die Zeilen ihrer Rolle.

Der Fragebogen folgt dem Auditrahmen von Shao et al. 2025 (Stanford, WORKBank): zuerst ein kurzes
Gespräch über die eigene Arbeit, dann je Aufgabe Vertrautheit, Sorge, Freude, Automatisierungswunsch,
vier Merkmale der Aufgabe und die gewünschte Beteiligung auf der Human Agency Scale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

COLUMNS = ["teilnehmer", "rolle", "aufgabe_id", "aufgabe", "bekannt", "erfahrung", "zeitanteil", "kernfaehigkeit",
           "sorge", "freude", "wunsch", "gruende_wunsch", "koerperlich", "unsicherheit", "fachwissen",
           "zwischenmenschlich", "zusammenarbeit", "gruende_zusammenarbeit"]

OPEN_QUESTIONS = [
    "Beschreiben Sie kurz, was Sie in Ihrer Arbeit tun.",
    "Welche Aufgaben erledigen Sie typischerweise? Denken Sie dabei an die Zeit, die jede braucht.",
    "Welche Werkzeuge und Programme nutzen Sie dafür, nach Häufigkeit geordnet?",
    "Gehen Sie die drei Aufgaben durch, die am meisten Zeit brauchen: Wie erledigen Sie sie Schritt für Schritt?",
    "Wie stellen Sie sich vor, KI in Ihrer täglichen Arbeit zu nutzen?",
]

SCALE5 = "1 gar nicht · 2 etwas · 3 mittel · 4 stark · 5 vollständig"

TASK_QUESTIONS = [
    ("bekannt", "Haben Sie diese Aufgabe schon selbst erledigt?", "ja / nein — bei „nein“ die übrigen Felder leer lassen"),
    ("erfahrung", "Bei dieser Aufgabe bin ich …", "einsteiger / durchschnitt / experte"),
    ("zeitanteil", "Wie viel Ihrer Arbeitszeit geht in diese Aufgabe?", "10 / 30 / 50 / 70 / 100 (Prozent)"),
    ("kernfaehigkeit", "Wie eng hängt die Aufgabe mit Ihren Kernfähigkeiten zusammen?", SCALE5),
    ("sorge", "Wenn KI diese Aufgabe vollständig übernehmen könnte: Wie besorgt wären Sie um Ihren Arbeitsplatz?", SCALE5),
    ("freude", "Unabhängig vom Gehalt: Wie gern erledigen Sie diese Aufgabe?", SCALE5),
    ("wunsch", "Wenn KI diese Aufgabe vollständig für Sie erledigen könnte: Wie sehr möchten Sie das?", SCALE5),
    ("gruende_wunsch", "Warum? (nur bei Wunsch 3 oder höher, mehrere Codes mit | trennen)",
     " · ".join(f"{k} = {v}" for k, v in wl.AUDIT_REASONS_AUTOMATION.items())),
    ("koerperlich", "Wie sehr verlangt die Aufgabe körperliche Tätigkeit?", SCALE5),
    ("unsicherheit", "Wie sehr verlangt sie Umgang mit Unsicherheit oder folgenreiche Entscheidungen?", SCALE5),
    ("fachwissen", "Wie sehr verlangt sie spezielles Fachwissen oder Erfahrung, die nirgends aufgeschrieben ist?", SCALE5),
    ("zwischenmenschlich", "Wie sehr hängt sie an Kommunikation oder Einfühlungsvermögen?", SCALE5),
    ("zusammenarbeit", "Wenn KI bei dieser Aufgabe hilft: Wie viel Zusammenarbeit zwischen Ihnen und der KI braucht es, "
     "damit das Ergebnis gut wird?", " · ".join(wl.HAS_LABEL[i] for i in range(1, 6))),
    ("gruende_zusammenarbeit", "Warum braucht es Zusammenarbeit? (nur bei 3 oder höher, Codes mit | trennen)",
     " · ".join(f"{k} = {v}" for k, v in wl.AUDIT_REASONS_COLLAB.items())),
]


def slug(text: str) -> str:
    return wl.normalize_name(text).replace(" ", "-")[:60] or "rolle"


def legal_hint() -> list[str]:
    de = wl.load_library_json("rechtsraeume", "DE.json") or {}
    topic = next((t for t in de.get("themen", []) if t.get("id") == "beschaeftigtenbefragung"), None)
    if not topic:
        return []
    return [f"Rechtsrahmen ({topic['fundstelle']}): {topic['pflicht']}", ""]


def sheet(graph: dict, role: dict, tasks: list[dict]) -> str:
    lines = [f"# Befragung: {role['name']}", "",
             "## Rahmen", "",
             "Diese Befragung fragt, welche Ihrer Aufgaben Sie gern an KI abgeben würden und wie viel Sie bei den übrigen "
             "selbst beteiligt sein wollen. Ihre Antworten fließen nur zusammengefasst in die Auswertung ein: Gezeigt wird eine "
             f"Aufgabe erst, wenn mindestens {wl.AUDIT_MIN_GROUP} Personen geantwortet haben. Tragen Sie statt Ihres Namens "
             "einen selbst gewählten Code ein. Die Teilnahme ist freiwillig. Es gibt keine richtigen oder falschen Antworten.",
             "", "Vor dem Versand zu klären: Zweck der Befragung, Zustimmung der Beschäftigtenvertretung, wer die Rohdaten "
             "sieht und wann sie gelöscht werden.", ""]
    lines += legal_hint()
    lines += ["## Teil 1: Ihre Arbeit (offen, etwa zehn Minuten)", "",
              "Die Antworten auf diese Fragen gehen nicht in die Tabelle. Wer sie auswerten will, fasst sie ohne Namen "
              "zusammen und registriert die Zusammenfassung als Quelle der Art „interview“.", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(OPEN_QUESTIONS, start=1)]
    lines += ["", "## Teil 2: Ihre Aufgaben", "",
              "Bitte nur Aufgaben bewerten, die Sie selbst erledigen. Fehlt eine Aufgabe, die Sie viel Zeit kostet, "
              "notieren Sie sie bei Teil 1.", ""]
    lines += ["| Feld | Frage | Antwort |", "|---|---|---|"]
    lines += [f"| `{c}` | {q} | {a} |" for c, q, a in TASK_QUESTIONS]
    lines += ["", "### Aufgaben dieser Rolle", ""]
    for i, t in enumerate(tasks, start=1):
        lines.append(f"{i}. {t['name']} (`{t['id']}`)")
    lines += ["", "## Stufen der Beteiligung (Human Agency Scale)", ""]
    lines += [f"- {wl.HAS_LABEL[i]}" for i in range(1, 6)]
    lines += ["", "Höhere Stufen sind nicht besser. Sie beschreiben, wie viel Mensch die Aufgabe nach Ihrer Erfahrung braucht.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--rollen", default=None, help="Rollennamen mit ; getrennt (Standard: alle Rollen)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    roles = sorted(graph["roles"], key=lambda r: (r.get("name") or "", r["id"]))
    if args.rollen:
        wanted = {wl.normalize_name(x) for x in args.rollen.split(";") if x.strip()}
        roles = [r for r in roles if wl.normalize_name(r.get("name")) in wanted]
        known = {wl.normalize_name(r.get("name")) for r in roles}
        missing = sorted(wanted - known)
        if missing:
            wl.fail(f"Rollen nicht gefunden: {', '.join(missing)}")
    out = project / wl.DIR_REVIEW / "befragung"
    rows = []
    written = []
    for r in roles:
        tasks = sorted((t for t in graph["tasks"] if t.get("role_id") == r["id"]),
                       key=lambda t: (-float(t.get("share_of_time") or 0), t.get("name") or "", t["id"]))
        if not tasks:
            continue
        path = out / f"fragebogen_{slug(r['name'])}.md"
        wl.write_text(path, sheet(graph, r, tasks))
        written.append(path)
        for t in tasks:
            rows.append({"teilnehmer": "", "rolle": r["name"], "aufgabe_id": t["id"], "aufgabe": t["name"]})
    if not written:
        wl.fail("Keine Rolle mit Aufgaben gefunden")
    csv_path = out / "antworten_vorlage.csv"
    wl.write_csv(csv_path, rows, COLUMNS)
    for p in written:
        print(f"Geschrieben: {wl.relpath(p)}")
    print(f"Geschrieben: {wl.relpath(csv_path)} ({len(rows)} Zeilen)")
    print("Nächster Schritt: Fragebogen mit der Beschäftigtenvertretung abstimmen, verteilen, Antworten als CSV nach "
          "00_input/befragung/ legen, dann import_audit.py und score_agency.py (oder run_pipeline.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
