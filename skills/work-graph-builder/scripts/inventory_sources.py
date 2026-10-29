#!/usr/bin/env python3
"""
inventory_sources.py — sichtet 00_input/, ordnet jede Datei einer Quellenart zu und schlägt
vor, welche Aufbereitung sich lohnt.

Aufruf:
    python3 <skill>/scripts/inventory_sources.py --project ./mein-projekt

Ausgabe: 30_review/quellen_inventar.md und eine Kurzfassung auf der Konsole.

Was der Bericht beantwortet:
1. Welche Quellenarten liegen vor, und was können sie im Modell füllen (Rollen, Aufgaben, Zusammenarbeit,
   Level, Prozesse, Skills, Regeln)?
2. Was fehlt, und woher käme es? Eine Stellenanzeige liefert Aufgaben, aber kein Arbeitsumfeld; eine
   Positionsliste liefert Zusammenarbeit, aber keine Aufgaben.
3. Welche Aufbereitungsmethode der Suite passt dazu — mit Befehl. Das ist der Vorschlag, keine Pflicht.

Die Zuordnung ist eine Heuristik aus Dateiname und Stichwörtern (bei Textdateien auch aus dem Anfang
des Inhalts). PDF, Word und Excel kann dieses Skript nicht lesen: Sie werden nach dem Namen eingeordnet
und mit dem Vermerk „Claude liest“ geführt. Eine falsche Zuordnung kostet nichts; sie steht im Bericht und
lässt sich per Dateiname korrigieren.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".tsv"}
PEEK_CHARS = 20000

# Quellenart -> (Beschriftung, Stichwörter in Name/Inhalt, was sie füllt)
KINDS: dict[str, tuple[str, list[str], list[str]]] = {
    "prozesshaus": ("Prozesshaus", ["prozesshaus"], ["processes", "roles"]),
    "positionsliste": ("Positionsliste / Organigramm", ["position", "organigramm", "stellenplan", "org_unit", "planstelle"],
                       ["headcount", "collaboration"]),
    "levelstruktur": ("Level- und Tarifstruktur", ["tarif", "entgeltgruppe", "eingruppierung", "gehaltsband", "leveling", "levels"],
                      ["level", "day_rate"]),
    "referenzautomatisierungen": ("Register bekannter Automatisierungen (Referenzen)", ["referenzautomatisierung", "automatisierungsregister"],
                                  ["agent_suggestions"]),
    "usecaseregister": ("Register eigener Use Cases", ["usecases", "use-cases", "use cases", "usecase register"], ["use_cases"]),
    "nutzungsstand": ("Nutzungsstand je Rolle und Agent", ["adoption", "nutzungsstand"], ["adoption"]),
    # Material für die Rollen.md: liegt unter 00_input/kontext/ (firma/, <rolle>/texte, transkripte, projekte)
    "kontextmaterial": ("Material für die Rollen.md (Texte, Transkripte, Projektdokumente)", [], ["context", "rules"]),
    "stellenbeschreibung": ("Stellenbeschreibung (intern)", ["stellenbeschreibung", "rollenbeschreibung", "rollenprofil", "funktionsbeschreibung", "tätigkeitsprofil", "taetigkeitsprofil"],
                            ["roles", "tasks", "skills", "level"]),
    "stellenanzeige": ("Stellenanzeige (extern)", ["stellenanzeige", "stellenausschreibung", "jobposting", "wir suchen", "wir bieten", "bewirb", "ihr profil", "dein profil"],
                       ["roles", "tasks", "skills"]),
    "prozessbeschreibung": ("Prozessbeschreibung / -aufnahme", ["prozessaufnahme", "prozessbeschreibung", "ablaufbeschreibung", "workflow", "verfahrensanweisung"],
                            ["processes", "systems", "collaboration"]),
    "qualifizierung": ("Zertifizierung / Kursunterlage", ["zertifizier", "schulung", "curriculum", "lernpfad", "kursinhalt", "training"],
                       ["skills", "systems", "rules"]),
    "geschaeftsbericht": ("Geschäfts- / Jahresbericht", ["jahresbericht", "geschäftsbericht", "geschaeftsbericht", "annual report", "nachhaltigkeitsbericht"],
                          ["context"]),
    "produktbeschreibung": ("Produkt- / Leistungsbeschreibung", ["produktbeschreibung", "leistungskatalog", "produktkatalog"],
                            ["context", "tasks"]),
}
KIND_ORDER = list(KINDS)

# Was das Modell braucht, und was eine Quelle dazu liefern kann.
SECTIONS = {
    "roles": "Rollen und Zweck", "tasks": "Aufgaben mit Zeitanteil", "skills": "Skills",
    "level": "Level / Einstufung", "headcount": "Headcount und Stellen", "collaboration": "Zusammenarbeit der Rollen",
    "processes": "Prozesse und Übergaben", "systems": "Systeme und Werkzeuge", "rules": "Regeln des Hauses (z. B. Systemlandschaft)",
    "day_rate": "Kostensatz je Level", "context": "Unternehmenskontext", "agent_suggestions": "Referenzen für Agentenvorschläge",
    "use_cases": "Eigene Use Cases", "adoption": "Nutzungsstand",
}
CORE_SECTIONS = ["roles", "tasks", "skills", "headcount", "collaboration", "processes"]

# Methoden der Aufbereitung: id, Titel, Befehl, Ergebnis, Bedingung (Funktion von Zustand)
METHODS: list[dict[str, Any]] = [
    {"id": "positions", "title": "Positionen importieren", "cmd": "import_positions.py", "result": "Headcount und FTE je Rolle, Grundlage für Zusammenarbeit",
     "when": lambda s: "positionsliste" in s["kinds"], "why": "Positionsliste vorhanden"},
    {"id": "levels", "title": "Level und Tagessätze zuordnen", "cmd": "import_levels.py", "result": "day_rate_eur je Rolle nach Level",
     "when": lambda s: "levelstruktur" in s["kinds"], "why": "Level-/Tarifstruktur vorhanden"},
    {"id": "process_house", "title": "Prozesshaus als Prozessextraktion übernehmen", "cmd": "import_process_house.py",
     "result": "process_<quelle>.json mit Schritten und Rollen", "when": lambda s: "prozesshaus" in s["kinds"],
     "why": "Prozesshaus vorhanden"},
    {"id": "interview", "title": "Prozesse im Interview aufnehmen", "cmd": "references/interview-leitfaden.md",
     "result": "Schritte, Systeme, Übergaben, pain", "when": lambda s: not ({"prozessbeschreibung", "prozesshaus"} & s["kinds"]),
     "why": "keine Prozessquelle: Stellenbeschreibungen zeigen nur etwa ein Drittel der Wirklichkeit"},
    {"id": "market", "title": "Externe Stellenanzeigen nur als Ergänzung führen", "cmd": "references/extraction-format.md (confidence: inferred)",
     "result": "Aufgaben mit Kennzeichnung „ergänzt“, nicht „aus Quelle“", "when": lambda s: "stellenanzeige" in s["kinds"],
     "why": "externe Anzeigen füllen Lücken, ersetzen aber keine interne Quelle"},
    {"id": "qualification", "title": "Zertifizierungs- und Kursunterlagen auf Systemregeln und Skills lesen", "cmd": "Extraktion durch Claude (extract_*.json: skills, systems)",
     "result": "Belege für Skills und Systemlandschaft", "when": lambda s: "qualifizierung" in s["kinds"],
     "why": "Kursunterlagen zeigen, welche Systeme und Verfahren das Haus wirklich nutzt"},
    {"id": "reference", "title": "Referenzautomatisierungen als Vorschlagsbasis", "cmd": "00_input/referenzautomatisierungen.csv (Format: references/datenaufbereitung.md)",
     "result": "agents_todo.json nennt passende Referenzen je Aufgabe", "when": lambda s: "referenzautomatisierungen" in s["kinds"] or s["have_graph"],
     "why": "bekannte Automatisierungen mit Quelle und Evidenzgrad machen Agentenvorschläge nachprüfbar"},
    {"id": "usecases", "title": "Use-Case-Register importieren", "cmd": "agent-mapper/scripts/import_usecases.py",
     "result": "Reichweite und Blindflecken je Use Case", "when": lambda s: "usecaseregister" in s["kinds"],
     "why": "Use-Case-Register vorhanden"},
    {"id": "adoption", "title": "Nutzungsstand aggregiert importieren", "cmd": "agent-mapper/scripts/import_adoption.py",
     "result": "Stand je Rolle × Agent, unter fünf Stellen unterdrückt", "when": lambda s: "nutzungsstand" in s["kinds"],
     "why": "Nutzungsstand vorhanden"},
    {"id": "context_material", "title": "Vorschläge für die Rollen.md aus vorhandenem Material holen", "cmd": "agent-mapper/scripts/extract_context_evidence.py",
     "result": "Vorschläge mit Quelle und Zitat für Prioritäten, Zeitfresser, Kanäle, Firmenprofil, Stil", "when": lambda s: "kontextmaterial" in s["kinds"],
     "why": "Material unter 00_input/kontext/ vorhanden — spart Fragen im Interview"},
    {"id": "context_offer", "title": "Material ablegen, statt alles per Frage und Antwort zu erfragen", "cmd": "00_input/kontext/ (firma/, <rolle>/texte, transkripte, projekte)",
     "result": "eigene Texte, Meeting-Transkripte und Projektdokumente liefern Stil, Prioritäten und Zeitfresser als Vorschläge",
     "when": lambda s: s["have_graph"] and "kontextmaterial" not in s["kinds"], "why": "noch kein Material für die Rollen.md abgelegt (freiwillig)"},
    {"id": "completeness", "title": "Vollständigkeit gegen die Rollenvorlage prüfen", "cmd": "check_completeness.py",
     "result": "Lückenliste je Rolle, mit Hinweis, woher die Lücke zu füllen wäre", "when": lambda s: s["have_graph"],
     "why": "Graph vorhanden"},
    {"id": "dedupe", "title": "Wiederkehrende Aufgaben über Rollen finden", "cmd": "dedupe_tasks.py",
     "result": "Aufgabencluster mit Rollenzahl und FTE", "when": lambda s: s["have_graph"] and s["roles"] >= 2,
     "why": "mindestens zwei Rollen"},
    {"id": "collaboration", "title": "Zusammenarbeit der Rollen ableiten", "cmd": "derive_collaboration.py",
     "result": "Rollenpaare mit Belegen (Übergaben, gleiche Organisationseinheit)",
     "when": lambda s: s["have_graph"] and (s["positions"] > 0 or s["edges"] > 0), "why": "Positionen oder Prozesskanten vorhanden"},
    {"id": "rules", "title": "Expertenaussagen als allgemeine Regeln erfassen", "cmd": "30_review/overrides.csv mit Selektoren (cluster:, family:, role:, *)",
     "result": "Eine Aussage wirkt auf alle betroffenen Rollen", "when": lambda s: s["have_graph"] and s["roles"] >= 5,
     "why": "ab fünf Rollen lohnt sich die Regelzeile statt Einzelkorrekturen"},
]


def classify(path: Path, peek: str) -> tuple[str, str]:
    """(Quellenart, Grund). Dateiname vor Inhalt; bei Gleichstand die Reihenfolge von KINDS."""
    parts = path.parts
    if "kontext" in parts and "00_input" in parts and parts.index("00_input") < parts.index("kontext"):
        return "kontextmaterial", "liegt unter 00_input/kontext/"
    name = wl.normalize_name(path.name.replace("_", " ").replace("-", " "))
    for kind in KIND_ORDER:
        for kw in KINDS[kind][1]:
            if wl.normalize_name(kw) in name:
                return kind, f"Dateiname enthält „{kw}“"
    if path.suffix.lower() == ".csv":
        head = peek.splitlines()[0].lower() if peek else ""
        if "position_id" in head or "org_unit" in head:
            return "positionsliste", "Spaltenkopf mit position_id/org_unit"
        if "level" in head and ("day_rate" in head or "tarif" in head or "entgelt" in head):
            return "levelstruktur", "Spaltenkopf mit level und Satz"
        if head.startswith("process;step"):
            return "prozesshaus", "Spaltenkopf process;step"
    text = wl.normalize_name(peek)
    scores: dict[str, tuple[int, str]] = {}
    for kind in KIND_ORDER:
        hits = [kw for kw in KINDS[kind][1] if wl.normalize_name(kw) in text]
        if hits:
            scores[kind] = (len(hits), hits[0])
    if scores:
        kind = sorted(scores, key=lambda k: (-scores[k][0], KIND_ORDER.index(k)))[0]
        return kind, f"Inhalt enthält „{scores[kind][1]}“"
    return "unbekannt", "keine Stichwörter gefunden"


def scan(project: Path) -> list[dict[str, Any]]:
    root = project / wl.DIR_INPUT
    rows = []
    if not root.is_dir():
        return rows
    registered = {str(rec.get("origin")) for rec in wl.load_source_register(project).values()}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.lower() == "readme.md" or p.name.startswith("."):
            continue
        if wl.DIR_SOURCES in p.relative_to(root).parts:
            continue  # registrierte Fassungen sind keine zweite Quelle
        readable = p.suffix.lower() in TEXT_SUFFIXES
        peek = ""
        if readable:
            try:
                peek = p.read_text(encoding="utf-8", errors="ignore")[:PEEK_CHARS]
            except OSError:
                readable = False
        kind, why = classify(p, peek)
        rel = p.relative_to(project).as_posix()
        rows.append({"path": rel, "kind": kind, "why": why, "bytes": p.stat().st_size, "readable": readable,
                     "registered": rel in registered})
    return rows


def state(project: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    graph = wl.load_latest_graph(project)
    return {"kinds": {r["kind"] for r in rows}, "have_graph": bool(graph),
            "roles": len(graph["roles"]) if graph else 0,
            "positions": len(graph.get("positions", [])) if graph else 0,
            "edges": len(graph.get("process_edges", [])) if graph else 0}


def render(rows: list[dict[str, Any]], st: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    lines = ["# Quelleninventar", "",
             "Welche Quellen liegen vor, was füllen sie im Modell, was fehlt, und welche Aufbereitung wird vorgeschlagen? "
             "Die Zuordnung ist eine Heuristik aus Dateiname und Stichwörtern; Korrekturen über den Dateinamen.", ""]
    if not rows:
        lines += ["In `00_input/` liegt noch nichts. Anfangen mit Stellenbeschreibungen (je Rolle) und, wenn vorhanden, einer Positionsliste.", ""]
    else:
        lines += ["## Dateien", "", "| Datei | Quellenart | Grund | Lesbar für Skripte | Registriert |", "|---|---|---|---|---|"]
        for r in rows:
            label = KINDS[r["kind"]][0] if r["kind"] in KINDS else "nicht erkannt"
            lines.append(f"| `{r['path']}` | {label} | {r['why']} | {'ja' if r['readable'] else 'nein — Claude liest'} "
                         f"| {'ja' if r.get('registered') else 'nein'} |")
        lines.append("")
        missing = [r["path"] for r in rows if not r.get("registered") and r["kind"] not in ("kontextmaterial", "nutzungsstand", "usecaseregister")]
        if missing:
            lines += ["Noch nicht im Quellenregister: " + ", ".join(f"`{m}`" for m in missing) + ". "
                      "Registrieren mit `register_source.py --file <datei> --title \"…\"`; erst dann lassen sich "
                      "Aussagen im Graphen auf eine Fundstelle beziehen.", ""]
    filled = set()
    for kind in st["kinds"]:
        if kind in KINDS:
            filled.update(KINDS[kind][2])
    lines += ["## Was die Quellen im Modell füllen können", "", "| Teil des Modells | Quelle vorhanden |", "|---|---|"]
    for key in CORE_SECTIONS + [k for k in SECTIONS if k not in CORE_SECTIONS]:
        lines.append(f"| {SECTIONS[key]} | {'ja' if key in filled else 'nein'} |")
    gaps = [k for k in CORE_SECTIONS if k not in filled]
    lines += [""]
    if gaps:
        lines += ["**Lücken in den Kernteilen:** " + ", ".join(SECTIONS[g] for g in gaps) + ". "
                  "Was nicht aus einer Quelle kommt, bleibt in der Suite als „ergänzt“ oder „geschätzt“ gekennzeichnet.", ""]
    picked = [m for m in METHODS if m["when"](st)]
    lines += ["## Vorgeschlagene Aufbereitung", ""]
    if picked:
        lines += ["| Methode | Warum jetzt | Befehl oder Ort | Ergebnis |", "|---|---|---|---|"]
        for m in picked:
            cmd = m["cmd"] if "/" in m["cmd"] or " " in m["cmd"] else f"`<skill>/scripts/{m['cmd']} --project <projekt>`"
            lines.append(f"| {m['title']} | {m['why']} | {cmd} | {m['result']} |")
    else:
        lines.append("Keine — zuerst Quellen ablegen.")
    lines.append("")
    return "\n".join(lines) + "\n", {"picked": [m["id"] for m in picked], "gaps": gaps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    rows = scan(project)
    st = state(project, rows)
    text, summary = render(rows, st)
    out = project / wl.DIR_REVIEW / "quellen_inventar.md"
    wl.write_text(out, text)
    kinds = sorted({r["kind"] for r in rows})
    print(f"Geschrieben: {wl.relpath(out)} | Dateien={len(rows)} Quellenarten={','.join(kinds) or '–'} "
          f"Lücken={','.join(summary['gaps']) or '–'}")
    if summary["picked"]:
        print("Vorschlag: " + ", ".join(summary["picked"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
