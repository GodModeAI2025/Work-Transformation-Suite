#!/usr/bin/env python3
"""
build_role_setup.py — baut für eine bestimmte Rolle das Setup-Paket, das ein persönlicher Arbeitsagent
braucht: Rollen.md, schlanker Agenten-Prompt, drei bis fünf Skills mit Testfall-Gerüst, Tool-Anbindungen
und Routinen. Soweit der Arbeitsgraph etwas weiß, ist es vorbelegt; was er nicht wissen kann, steht als „offen“.

Aufruf:
    python3 <skill>/scripts/build_role_setup.py --project ./mein-projekt --list
    python3 <skill>/scripts/build_role_setup.py --project ./mein-projekt --role "Forderungsmanager" [--skills 4]
    python3 <skill>/scripts/build_role_setup.py --project ./mein-projekt --all

Ausgabe: 40_output/rollen_setup/<rolle>/
    README.md                         Reihenfolge, was vorbelegt und was offen ist
    kontext/Rollen.md                 fünf Abschnitte; jede Zeile mit Herkunft (Graph) oder „offen“
    kontext/interview-prompt.md       Interview, das die offenen Felder füllt
    agent/systemprompt.md             schlank: steuert die Zusammenarbeit, enthält keine Aufgaben
    skills/<skill>/SKILL.md           je Skill eine Anleitung (Entwurf, ungetestet)
    skills/<skill>/evals/cases.json   Testfall-Gerüst: mindestens fünf Fälle, echte Daten fehlen noch
    skills/<skill>/evals/protokoll.md Testschleifen
    tools/anbindungen.md              Systeme der Rolle, Datenklassen, offene Freigaben
    routinen/routinen.json und .md    Vorschläge, alle inaktiv
    pflege/pflege.md                  wie das Setup lebendig bleibt
    manifest.json                     Herkunft und Prüfsummen

Prinzipien (aus einem öffentlichen Playbook zum persönlichen KI-Setup, siehe references/rollen-setup.md):
Kontext zuerst; ein zentraler Agent statt vieler; Skills für wiederkehrende Aufgaben; jeder Skill mit echten
Testfällen; Werkzeuge anbinden, soweit Datenschutz es erlaubt; Routinen erst nach bestandenem Test;
erst erweitern, dann automatisieren.

Was das Skript ausdrücklich NICHT tut: Es erfindet keinen Kontext (Geschäftsmodell, Ziele, Arbeitsweise bleiben
„offen“), es schreibt keine echten Testfälle, es gibt keine Systemfreigabe und aktiviert keine Routine. Ein
Skill, der aus Rollendaten entsteht, ist ein Startpunkt. Läuft das Skript erneut, überschreibt es keine Datei,
die jemand inzwischen bearbeitet hat; der neue Stand liegt dann als `<datei>.vorschlag` daneben.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import export_skill as es  # noqa: E402
import export_contracts as ec  # noqa: E402
import rollen_md as rm  # noqa: E402

DEFAULT_SKILLS, MIN_SKILLS, MAX_SKILLS = 4, 3, 5
MIN_CASES = 5
MIN_LOOPS = 2
OPEN = rm.OPEN
GRAPH = rm.GRAPH
HAS_LABEL = {1: "H1 — der Agent kann es allein", 2: "H2 — Mensch prüft stichprobenartig", 3: "H3 — Mensch und Agent gleichberechtigt",
             4: "H4 — Mensch führt, Agent unterstützt", 5: "H5 — Mensch unverzichtbar"}
FREQ_LABEL = {"daily": "täglich", "weekly": "wöchentlich", "monthly": "monatlich", "quarterly": "quartalsweise", "adhoc": "bei Bedarf"}
TIME_TRIGGER = {"daily": "werktags morgens", "weekly": "wöchentlich, z. B. Montagmorgen", "monthly": "monatlich zum Monatsanfang",
                "quarterly": "quartalsweise"}
VISIBILITY = ["als Browser-Startseite", "auf einem reservierten zweiten Bildschirm", "als Desktop-App",
              "eingebettet in den Chat des Hauses"]
GENERIC_TOOLS = ["E-Mail", "Kalender", "Projektmanagement", "Wissensmanagement", "CRM"]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Rolle finden, Aufgaben ordnen, Skills zuschneiden
# ---------------------------------------------------------------------------

def find_role(graph: dict[str, Any], ref: str) -> dict[str, Any] | None:
    by_id = wl.index_by_id(graph["roles"])
    if ref in by_id:
        return by_id[ref]
    key = wl.normalize_name(ref)
    exact = [r for r in graph["roles"] if wl.normalize_name(r["name"]) == key]
    if len(exact) == 1:
        return exact[0]
    return None


def similar_roles(graph: dict[str, Any], ref: str) -> list[str]:
    key = wl.normalize_name(ref)
    hits = [r["name"] for r in graph["roles"] if key and (key in wl.normalize_name(r["name"]) or wl.normalize_name(r["name"]) in key)]
    return sorted(hits)[:5]


def task_weight(t: dict[str, Any]) -> float:
    """Gebundene Zeit × Automatisierbarkeit; unbewertete Aufgaben zählen mit Potenzial 5."""
    ap = t.get("automation_potential")
    return float(t.get("share_of_time") or 0) * (float(ap) / 10.0 if ap is not None else 0.5)


def skill_groups(graph: dict[str, Any], role: dict[str, Any], n: int) -> tuple[list[dict[str, Any]], str]:
    """Aufgaben der Rolle zu Skill-Gruppen bündeln. Gleicher Agent → ein Skill, sonst eine Aufgabe je Skill."""
    agents = wl.index_by_id(graph["agents"])
    tasks = [t for t in graph["tasks"] if t.get("role_id") == role["id"]]
    eligible = [t for t in tasks if t.get("mode") in ("ai_assisted", "agent_delegated") or not t.get("mode")]
    note = ""
    if not eligible:
        eligible = tasks
        note = ("Alle Aufgaben dieser Rolle sind im Kern menschlich (Bewertung: manuell). Die Skills unten unterstützen nur; "
                "die Entscheidung bleibt beim Menschen.")
    groups: dict[str, dict[str, Any]] = {}
    for t in eligible:
        aid = next((a for a in sorted(t.get("agent_ids", [])) if a in agents and isinstance(agents[a].get("contract"), dict)), None)
        key = aid or t["id"]
        g = groups.setdefault(key, {"key": key, "agent": agents.get(aid) if aid else None, "tasks": [], "weight": 0.0})
        g["tasks"].append(t)
        g["weight"] += task_weight(t)
    ordered = sorted(groups.values(), key=lambda g: (-g["weight"], g["agent"]["name"] if g["agent"] else g["tasks"][0]["name"], g["key"]))
    return ordered[:max(MIN_SKILLS, min(MAX_SKILLS, n))] if len(ordered) >= MIN_SKILLS else ordered, note


def steps_of_role(graph: dict[str, Any], role: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in graph["process_steps"] if s.get("role_id") == role["id"]]


def names(graph: dict[str, Any], coll: str, ids: list[str]) -> list[str]:
    idx = wl.index_by_id(graph[coll])
    return sorted(idx[i]["name"] for i in ids if i in idx)


# ---------------------------------------------------------------------------
# Rollen.md (Kontext der Rolle)
# ---------------------------------------------------------------------------

def kontextprofil(graph: dict[str, Any], role: dict[str, Any], groups: list[dict[str, Any]],
                  evidence: dict[str, Any] | None = None) -> tuple[str, int, int]:
    """Rollen.md für diese eine Rolle. Gleicher Text wie `build_rollen_md.py --role`, damit es eine Quelle gibt."""
    return rm.compose(graph, [role], title=f"Rollen — {role['name']}", evidence=evidence)


def interview_prompt(role: dict[str, Any], open_n: int) -> str:
    return f"""# Interview: Rollen.md für die Rolle „{role['name']}“

Kopiere den Text unten in dein KI-Werkzeug, hänge `Rollen.md` an und beantworte die Fragen per Spracheingabe oder Text.
Ein Durchlauf dauert erfahrungsgemäß rund eine Stunde, weniger, wenn Vorschläge aus Dokumenten (✎) schon dastehen. In der Datei sind {open_n} Felder offen.

---

Du bist mein Interviewer. Ich arbeite in der Rolle „{role['name']}“. Im Anhang steht meine Rollen.md mit fünf Abschnitten:
1) Firmenprofil, 2) Rollenprofil, 3) Team-Kontext, 4) Prioritäten & Ziele, 5) Arbeits- & Kommunikationsstil. Felder mit „❓ offen“ fehlen noch.

Regeln:
1. Stelle genau eine Frage auf einmal, und zwar zu einem offenen Feld. Beginne mit dem Abschnitt, der am meisten fehlt.
2. Frage nach, wenn eine Antwort vage ist („Woran würdest du das merken?“, „Kannst du ein Beispiel aus der letzten Woche nennen?“).
3. Erfinde nichts. Wenn ich etwas nicht weiß, schreibe „offen“ und frage später noch einmal.
4. Gib mir keine Ratschläge, solange das Interview läuft. Sammle nur.
5. Widerspricht eine Antwort dem, was schon dasteht (Zeilen mit „✓ Graph“), sag es mir und frage, was gilt. Ändere Graph-Zeilen nicht ohne meine Bestätigung. Zeilen mit „abgeleitet“ oder „✎ Vorschlag aus Dokument“ sind Vorschläge mit Quelle: Lies sie mir vor und frage, ob sie stimmen. Bestätigte Vorschläge übernimmst du ohne Markierung, abgelehnte löschst du.
6. Bei Abschnitt 5 frage nach echten Beispielen: ein Text, den ich selbst geschrieben habe und gut finde; eine Formulierung, die ich nie schreiben würde.
7. Am Ende: Gib mir die vollständige Rollen.md in derselben Gliederung zurück. Lass „❓ offen“ stehen, wo ich keine Antwort hatte, und liste die noch offenen Felder am Schluss auf.

Beginne jetzt mit der ersten Frage.
"""


def skill_ideen_prompt(role: dict[str, Any]) -> str:
    return f"""# Skill-Ideen für die Rolle „{role['name']}“

Erst nach dem Interview verwenden, wenn die Rollen.md weitgehend gefüllt ist. Du brauchst keine eigene Liste: Die KI liest die Rollen.md und schlägt vor.

---

Lies die angehängte Rollen.md. Schlage mir fünf wiederkehrende Aufgaben vor, die sich als Skill lohnen (ein Skill ist eine verschriftlichte Anleitung für eine
bestimmte Aufgabe, damit gute Ergebnisse nicht von einem zufällig gelungenen Prompt abhängen).

Gib eine Tabelle: Aufgabe · Wie oft · Was es heute kostet (Zeit, Ärger) · Nutzen (hoch/mittel/niedrig) · Umsetzbarkeit (hoch/mittel/niedrig, mit Begründung:
welche Daten und Systeme braucht es, wo entscheidet ein Mensch) · Risiko bei Fehlern.

Regeln:
1. Nur Aufgaben, die wirklich wiederkehren und spürbar Zeit kosten. Keine Seltenheiten.
2. Sortiere nach Nutzen und Umsetzbarkeit zusammen. Die ersten drei sind die, mit denen ich anfange.
3. Stütze dich auf Zeilen, die in der Rollen.md stehen. Wenn dir Information fehlt, sag es, statt etwas anzunehmen.
4. Nenne bei jedem Vorschlag, welche Testfälle ich bräuchte (mindestens fünf, mit einem Randfall und einem Fall, der an einen Menschen gehen muss).
5. Schlage nichts vor, das sofort automatisch laufen soll. Erst im Chat gut machen, dann automatisieren.
"""


def teamstart(entries: list[dict[str, Any]]) -> str:
    L = ["# Teamstart — Mini-Hackathon", "",
         "Ein gemeinsamer Termin, an dessen Ende jede Person mit eigener Rollen.md, einem eingerichteten Agenten und den ersten Skills arbeitet. "
         "Der Zeitrahmen ist ein Richtwert aus einem öffentlichen Playbook (rund vier konzentrierte Stunden), keine Messung. Der schwierigste Teil ist die Gewohnheit, nicht die Technik.", "",
         "## Vorher", "",
         "- [ ] Rahmen klären und sagen: Wozu das Ganze, was passiert nicht (keine Leistungsbewertung einzelner Personen), ist die Beschäftigtenvertretung beteiligt.",
         "- [ ] Material je Person ablegen (freiwillig): eigene Texte, Transkripte, Projektdokumente unter `00_input/kontext/<rolle>/`; Firmentexte unter `firma/`. "
         "Transkripte enthalten Daten Dritter — nur mit Einverständnis aller Beteiligten.",
         "- [ ] `extract_context_evidence.py` laufen lassen und `build_role_setup.py` für alle Rollen.",
         "- [ ] Wahl der Plattform ist entschieden und nicht Thema des Tages (permanentes Tool-Hopping erzeugt wenig Wert).", "",
         "## Ablauf", "",
         "| Zeit (Richtwert) | Schritt | Datei |", "|---|---|---|",
         "| 15 Min | Rahmen, Ziel, Datenschutz | – |",
         "| 60 Min | Rollen.md vervollständigen: Vorschläge (✎) bestätigen, offene Felder im Interview füllen | `kontext/interview-prompt.md` |",
         "| 30 Min | Agenten einrichten: Systemprompt, Rollen.md ablegen, wo er sie lesen und aktualisieren kann | `agent/systemprompt.md` |",
         "| 30 Min | Skill-Ideen vorschlagen lassen, drei auswählen | `skills/skill-ideen-prompt.md` |",
         "| 75 Min | Ersten Skill mit mindestens fünf echten Fällen testen, zwei bis drei Schleifen | `skills/<skill>/evals/` |",
         "| 30 Min | Erfolgsmoment: ein kurzer Auftrag, ein brauchbares Ergebnis; Agent sichtbar machen | `routinen/routinen.md` |", "",
         "## Danach", "",
         "- [ ] Abschnitt 4 (Prioritäten & Ziele) einmal im Monat aktualisieren.",
         "- [ ] Systeme erst nach Freigabe durch Datenschutz und IT anbinden, erst lesend.",
         "- [ ] Routinen erst aktivieren, wenn ein Skill live-reif ist (`check_role_setup.py`).", "",
         "## Rollen im Team", "", "| Rolle | Skills (Entwurf) | Zeilen aus dem Graphen | Vorschläge aus Dokumenten | Noch offen |", "|---|---:|---:|---:|---:|"]
    for e in entries:
        L.append(f"| {e['role']} | {e['skills']} | {e['filled']} | {e['proposed']} | {e['open']} |")
    L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def group_name(g: dict[str, Any]) -> str:
    return es.slug(g["agent"]["name"]) if g["agent"] else es.slug(g["tasks"][0]["name"])


def group_title(g: dict[str, Any]) -> str:
    return g["agent"]["name"] if g["agent"] else g["tasks"][0]["name"]


def generic_skill_md(graph: dict[str, Any], role: dict[str, Any], g: dict[str, Any], name: str) -> str:
    roles = wl.index_by_id(graph["roles"])
    steps_all = steps_of_role(graph, role)
    tids = {t["id"] for t in g["tasks"]}
    steps = [s for s in steps_all if tids & set(s.get("task_ids", []))]
    procs = wl.index_by_id(graph["processes"])
    systems = names(graph, "systems", sorted({sid for s in steps for sid in s.get("system_ids", [])}))
    inputs = sorted({x for s in steps for x in s.get("inputs", [])})
    outputs = sorted({x for s in steps for x in s.get("outputs", [])})
    triggers = sorted({procs[s["process_id"]]["trigger"] for s in steps if s.get("process_id") in procs and procs[s["process_id"]].get("trigger")})
    gates = []
    for s in steps:
        hg = s.get("human_gate")
        if isinstance(hg, dict) and hg.get("when"):
            gates.append(f"{hg['when']} → {roles.get(hg.get('role_id'), {}).get('name', 'Mensch')}")
    t0 = g["tasks"][0]
    desc = (t0.get("description") or t0["name"]).replace("\n", " ").strip()
    freq = ", ".join(sorted({FREQ_LABEL.get(t.get("frequency"), t.get("frequency") or "") for t in g["tasks"]} - {""}))
    description = f"{desc} Verwenden bei: {', '.join(t['name'] for t in g['tasks'])}."
    coe = max((float((t.get("scores") or {}).get("consequence_of_error", 0)) for t in g["tasks"]), default=0.0)
    has = min((t.get("has_level") for t in g["tasks"] if t.get("has_level")), default=None)
    mode = ", ".join(sorted({wl_mode(t.get("mode")) for t in g["tasks"]}))
    wf = [f"{i}. {s}" for t in g["tasks"] for i, s in enumerate(t.get("workflow_steps", []), start=1)]
    crit = []
    if coe >= 6:
        crit.append("Ein Fehler wäre teuer (Fehlerfolge hoch): Das Ergebnis geht erst nach menschlicher Prüfung weiter.")
    if role.get("regulated"):
        crit.append("Die Rolle ist reguliert: Jedes Ergebnis nennt seine Grundlage und ist nachvollziehbar.")
    L = ["---", f"name: {name}", f"description: {json.dumps(description[:900], ensure_ascii=False)}", "---", "",
         f"# {group_title(g)}", "",
         "Entwurf aus dem Arbeitsgraphen. Ein Startpunkt für die Zusammenarbeit im Chat, kein fertiger Ablauf.", "",
         "## Auftrag", "", f"Aufgaben: {', '.join(t['name'] for t in g['tasks'])}.",
         f"Häufigkeit: {freq or 'offen'}. Bewertung: {mode}." + (f" Rollenanteil: {sum(float(t.get('share_of_time') or 0) for t in g['tasks']):.0f} % der Arbeitszeit." if g["tasks"] else ""), ""]
    if has:
        L += [f"Menschliche Beteiligung: {HAS_LABEL.get(has, has)}.", ""]
    L += ["## Wann verwenden", "", *(f"- {t}" for t in triggers), *( [] if triggers else [f"- {OPEN}: Was löst diese Arbeit aus? (kein Prozess im Graphen)"]), "",
          "## Ablauf", ""]
    if wf:
        L += wf + [""]
    else:
        L += [f"{OPEN}: Die Schritte sind noch nicht aufgenommen. Zeig dem Agenten (oder einem Fachexperten) einmal, wie du die Aufgabe heute machst, "
              "und beantworte dabei drei Fragen: Was machst du Schritt für Schritt? Welche Systeme und Daten brauchst du? Wo hakt es? "
              "Trage das Ergebnis hier ein (Leitfaden: `references/interview-leitfaden.md` im Skill work-graph-builder).", ""]
    L += ["## Eingaben und Ausgaben", "", "Eingaben:", es._bullets(inputs) if inputs else f"- {OPEN}", "", "Ausgaben:", es._bullets(outputs) if outputs else f"- {OPEN}", "",
          "## Systeme", "", es._bullets(systems) if systems else f"- {OPEN}", "", "## Qualitätskriterien", ""]
    L += [f"- {c}" for c in crit] + [f"- {OPEN}: Woran erkennst du ein gutes Ergebnis? (Format, Detailgrad, Tonalität — siehe Rollen.md, Bereich 5)", ""]
    L += ["## Wo ein Mensch entscheidet", "", es._bullets(gates) if gates else f"- {OPEN}: Welche Entscheidung gehört nie an den Agenten?", "",
          "## Status", "", "**Entwurf, ungetestet.** Einsetzen erst nach mindestens fünf echten Testfällen und zwei bis drei Testschleifen (`evals/`). "
          "Eine Automatisierung (Zeitplan oder Ereignis) kommt erst danach.", ""]
    return "\n".join(L)


def wl_mode(m: str | None) -> str:
    return {"manual": "manuell", "ai_assisted": "KI-unterstützt", "agent_delegated": "an Agent delegiert"}.get(m or "", "nicht bewertet")


def eval_cases(graph: dict[str, Any], role: dict[str, Any], g: dict[str, Any], name: str) -> dict[str, Any]:
    c = g["agent"]["contract"] if g["agent"] else {}
    steps = [s for s in steps_of_role(graph, role) if {t["id"] for t in g["tasks"]} & set(s.get("task_ids", []))]
    inputs = c.get("inputs") or sorted({x for s in steps for x in s.get("inputs", [])}) or ["(Eingaben des Falls)"]
    outputs = c.get("outputs") or sorted({x for s in steps for x in s.get("outputs", [])}) or ["(Ergebnis des Falls)"]
    gate = None
    if isinstance(c.get("human_checkpoint"), dict):
        gate = c["human_checkpoint"].get("when")
    for s in steps:
        if not gate and isinstance(s.get("human_gate"), dict):
            gate = s["human_gate"].get("when")
    writes = bool(c.get("write_permissions"))
    expect_ok = [f"Ergebnis enthält: {o}" for o in outputs[:4]]
    kinds = [
        ("standard", "Typischer Fall, wie er jede Woche vorkommt", expect_ok),
        ("variante", "Typischer Fall mit einer Abweichung (anderer Kanal, andere Schreibweise, anderer Betrag)", expect_ok),
        ("randfall", "Ungewöhnlicher, aber vorkommender Fall (Ausnahme, Sonderregel, altes Vertragsmodell)", ["Der Agent benennt die Besonderheit, statt sie zu übergehen"]),
        ("fehlende_eingabe", f"Fall, bei dem eine Eingabe fehlt: {inputs[0]}", ["Der Agent fragt nach oder meldet, was fehlt; er rät nicht"]),
        ("eskalation", "Fall, der die Entscheidung eines Menschen verlangt" + (f" ({gate})" if gate else ""),
         [f"Der Agent übergibt an den Menschen{(' bei: ' + gate) if gate else ''} und entscheidet nicht selbst"]),
    ]
    if writes:
        kinds.append(("wiederholung", "Derselbe Fall zweimal hintereinander", ["Der zweite Lauf schreibt nicht doppelt (Idempotenz)"]))
    cases = [{"id": f"c{i}", "art": art, "szenario": sz, "eingabe": {}, "erwartet": ex, "real_data": False, "last_result": None}
             for i, (art, sz, ex) in enumerate(kinds, start=1)]
    return {"skill": name, "status": "entwurf", "min_cases": MIN_CASES, "min_loops": MIN_LOOPS, "tested_loops": 0, "cases": cases,
            "hinweis": "Diese Fälle sind Gerüste aus Rollendaten. Ersetze sie durch echte Fälle (anonymisiert) und setze `real_data` auf true. "
                       "Erst mit mindestens fünf echten Fällen und zwei bestandenen Schleifen gilt der Skill als live-reif."}


def protokoll(name: str) -> str:
    return f"""# Testprotokoll — {name}

Ein Skill ist erst belastbar, wenn er an echten Fällen gelaufen ist. Der erste Entwurf entsteht in Minuten; Zuverlässigkeit entsteht in den Schleifen.

## Vor der ersten Schleife

- [ ] Mindestens fünf echte, anonymisierte Fälle in `cases.json` (`real_data: true`). Mehr ist besser.
- [ ] Die Fälle decken ab: Standard, Abweichung, Randfall, fehlende Eingabe, Fall für den Menschen.
- [ ] Erwartetes Ergebnis je Fall steht fest, bevor der Agent läuft.

## Schleife (zwei- bis dreimal wiederholen)

1. Alle Fälle durch den Skill laufen lassen.
2. Je Fall `last_result` auf `pass` oder `fail` setzen. Bei `fail`: Abweichung in einem Satz beschreiben.
3. Die Abweichungen als direktes Feedback in `SKILL.md` einarbeiten (nicht in den Systemprompt).
4. `tested_loops` in `cases.json` um eins erhöhen.

## Freigabe

Live-reif ist ein Skill, wenn mindestens fünf echte Fälle und mindestens zwei Schleifen vorliegen und der letzte Lauf alle Fälle bestanden hat.
`check_role_setup.py` prüft das. Erst dann darf eine Routine aktiviert werden.

| Schleife | Datum | Bestanden | Abweichungen und Änderungen |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
"""


# ---------------------------------------------------------------------------
# Systemprompt, Tools, Routinen, Pflege
# ---------------------------------------------------------------------------

def systemprompt(graph: dict[str, Any], role: dict[str, Any], skills: list[dict[str, Any]]) -> str:
    org = graph["meta"].get("organization") or "dem Unternehmen"
    idx = "\n".join(f"- `{s['name']}` — {s['one_line']}" for s in skills) or "- (noch keine Skills)"
    return f"""# Arbeitsagent — {role['name']}

Du arbeitest für eine Person in der Rolle „{role['name']}“ bei {org}. Du bist ihr zentraler Agent: Du kennst ihren Kontext, wählst die passende Anleitung
und prüfst, was du lieferst. Dieser Prompt steuert nur die Zusammenarbeit. Aufgaben stehen in den Skills.

## Vor jeder Arbeit

1. Lade `kontext/Rollen.md`. Fehlt dir Kontext, den du brauchst, frage nach. Rate nicht.
2. Ordne die Aufgabe ein: Gehört sie zu einem Skill aus der Liste unten? Dann lade ihn und halte dich daran.
3. Gibt es keinen passenden Skill, hilf im Chat und frage am Ende, ob daraus ein Skill werden soll, wenn die Aufgabe wiederkehrt.

## Nach jeder Arbeit

4. Prüfe das Ergebnis gegen die Qualitätskriterien des Skills und gegen die Rollen.md (Format, Tonalität). Benenne Abweichungen, statt sie zu glätten.
5. Wo laut Skill ein Mensch entscheidet, entscheidest du nicht. Du bereitest vor und übergibst.

## Grenzen

- Du nutzt nur Systeme, die in `tools/anbindungen.md` als freigegeben stehen. Steht dort „offen“, hast du keinen Zugriff.
- Du schreibst nur in Systeme, wenn der Skill es erlaubt und sein Status „live-reif“ ist.
- Du startest nichts von selbst. Zeitpläne und Ereignisse gibt es erst, wenn `routinen/routinen.json` eine Routine als aktiv führt.
- Bei widersprüchlichen Informationen fragst du, welche gilt.

## Skills

{idx}
"""


def tool_table(graph: dict[str, Any], role: dict[str, Any], groups: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    systems = wl.index_by_id(graph["systems"])
    steps = steps_of_role(graph, role)
    found: dict[str, dict[str, Any]] = {}
    for s in steps:
        for sid in s.get("system_ids", []):
            if sid in systems:
                found.setdefault(sid, {"reads": set(), "writes": set(), "used": set()})["used"].add(s["name"])
    for g in groups:
        a = g["agent"]
        if not a:
            continue
        c = a["contract"]
        for sid in c.get("system_ids", []):
            if sid in systems:
                d = found.setdefault(sid, {"reads": set(), "writes": set(), "used": set()})
                d["reads"].update(c.get("read_permissions") or [])
                d["writes"].update(c.get("write_permissions") or [])
    rows = []
    for sid in sorted(found, key=lambda x: systems[x]["name"]):
        sy = systems[sid]
        classes = sy.get("data_classes") or []
        flag = " ⚠ besonders prüfen" if {"personal", "special_category"} & set(classes) else ""
        api = {True: "ja", False: "nein"}.get(sy.get("api_available"), "unbekannt")
        rows.append({"system": sy["name"], "kind": sy.get("kind") or "–", "api": api,
                     "data_classes": ", ".join(classes) or "–", "flag": flag,
                     "reads": sorted(found[sid]["reads"]), "writes": sorted(found[sid]["writes"]), "used": sorted(found[sid]["used"])})
    L = ["# Tool-Anbindungen", "",
         "Ohne Werkzeugzugriff bleibt ein Agent in der Copy-and-paste-Falle: Er formuliert, du überträgst. Der größte Zeiteffekt entsteht, wenn er in den Arbeitssystemen handeln kann. "
         "**Aber:** Datenschutz und Informationssicherheit sind verbindliche Leitplanken. Nicht jede technisch mögliche Verbindung darf genutzt werden. Diese Tabelle gibt keine Freigabe; "
         "die Spalte „Freigabe“ bleibt offen, bis Datenschutz und IT zugestimmt haben.", ""]
    if rows:
        L += ["| System | Art | API | Datenklassen | Zugriff laut Graph | Anbindung | Freigabe |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            acc = " · ".join(x for x in (
                ("Genutzt in: " + "; ".join(r["used"])) if r["used"] else "",
                ("Lesen (Vertrag): " + "; ".join(r["reads"])) if r["reads"] else "",
                ("Schreiben (Vertrag): " + "; ".join(r["writes"])) if r["writes"] else "") if x)
            conn = "native Integration oder MCP — Verfügbarkeit prüfen" if r["api"] != "nein" else "keine API erfasst — Anbindung offen"
            L.append(f"| {r['system']} | {r['kind']} | {r['api']} | {r['data_classes']}{r['flag']} | {acc or '–'} | {conn} | {OPEN} |")
    else:
        L += ["Der Graph nennt für diese Rolle keine Systeme. Typische Startpunkte nach dem Playbook (allgemein, nicht aus dem Graphen abgeleitet): "
              + ", ".join(GENERIC_TOOLS) + ". Wähle die, in denen diese Rolle tatsächlich arbeitet.", ""]
    profile = wl.platform_profile(graph)
    if profile:
        L += ["", f"## Plattformprofil: {profile['label']}", "",
              "Vorschlag aus der Referenzbibliothek für die Umsetzung; Dienstnamen und Verfügbarkeit vor der Umsetzung prüfen. "
              "Fachsysteme (ERP, CRM, Marktkommunikation) werden über ihre eigenen Schnittstellen angebunden.", ""]
        L += [f"- {g}" for g in profile.get("grundsaetze", [])]
        seen = set()
        for g in groups:
            a = g["agent"]
            if not a or a.get("pattern") in seen:
                continue
            seen.add(a.get("pattern"))
            dienste = (profile.get("muster") or {}).get(a.get("pattern") or "", {}).get("dienste") or []
            if dienste:
                L.append(f"- Muster `{a['pattern']}` ({a['name']}): " + ", ".join(dienste))
            for t in (a.get("contract") or {}).get("tools") or []:
                d = wl.platform_tool(profile, t)
                if d:
                    L.append(f"  - `{t}` → {d}")
    L += ["", "## Reihenfolge", "",
          "1. Erst lesend anbinden, dann schreibend, und schreibend nur für Skills, die live-reif sind.",
          "2. Native Integrationen vor MCP-Verbindungen; für Standardsysteme gibt es meist fertige Wege.",
          "3. Je Anbindung festhalten, wer sie freigegeben hat und wann.", ""]
    return "\n".join(L), rows


def routines(graph: dict[str, Any], role: dict[str, Any], skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for s in skills:
        if s.get("time"):
            out.append({"skill": s["name"], "art": "zeitbasiert", "trigger": s["time"], "active": False})
        if s.get("event"):
            out.append({"skill": s["name"], "art": "ereignisbasiert", "trigger": s["event"], "active": False})
    return out


def routines_md(items: list[dict[str, Any]]) -> str:
    L = ["# Routinen", "",
         "**Erst erweitern, dann automatisieren.** Wenn das Ergebnis im Chat noch nicht sitzt, spart eine Automatisierung keine Zeit, sie verlagert die Nacharbeit nur nach hinten. "
         "Darum ist jede Routine unten inaktiv. Aktiv setzen (`active: true` in `routinen.json`) darf man sie erst, wenn der Skill live-reif ist: mindestens fünf echte Testfälle, "
         "zwei bestandene Schleifen (`check_role_setup.py`).", ""]
    if items:
        L += ["| Skill | Art | Auslöser (Vorschlag) | Aktiv |", "|---|---|---|---|"]
        L += [f"| {i['skill']} | {i['art']} | {i['trigger']} | nein |" for i in items]
    else:
        L.append("Keine Routine ableitbar: Weder Häufigkeit noch Auslöser sind im Graphen erfasst.")
    L += ["", "## Den Agenten sichtbar machen", "",
          "Das beste Setup nützt nichts, wenn es im Alltag nicht präsent ist. Der schwierigste Teil ist die Gewohnheit, nicht die Technik. Möglichkeiten: "
          + "; ".join(VISIBILITY) + ".", "",
          "Arbeite auf einen frühen Erfolgsmoment hin: ein kurzer Auftrag, ein getesteter Skill, ein brauchbares Ergebnis. Das erste gute Ergebnis erzeugt Momentum.", ""]
    return "\n".join(L)


def pflege(role: dict[str, Any]) -> str:
    return f"""# Pflege — das Setup bleibt lebendig oder veraltet

Nach dem Aufbau beginnt die eigentliche Lernphase. Ohne Pflege bleibt das Setup auf dem Stand des ersten Tages.

## Bei jedem Ergebnis, das nicht passt

- [ ] Den Skill verbessern, nicht den Systemprompt. Der Prompt steuert nur die Zusammenarbeit.
- [ ] Den Fall als neuen Testfall in `evals/cases.json` aufnehmen.

## Bei Veränderung

- [ ] Neue wiederkehrende Aufgabe → neuer Skill (einzeln, nicht im Akkord).
- [ ] Skill nicht mehr gebraucht → entfernen.
- [ ] Neue Prioritäten, Rollenwechsel, andere Qualitätsanforderungen → Rollen.md anpassen.
- [ ] Meeting-Transkripte und Projektdokumente nach und nach als Kontext ergänzen.

## Wenn Informationen sich widersprechen

Das entscheidet ein Mensch. Das lässt sich (noch) nicht vollständig automatisieren.

## Wenn sich der Arbeitsgraph ändert

Neue Fassung dieses Pakets erzeugen:
`build_role_setup.py --project <projekt> --role "{role['name']}"`.
Dateien, die du inzwischen bearbeitet hast, überschreibt das Skript nicht. Der neue Stand liegt dann als `<datei>.vorschlag` daneben; übernimm, was passt.
"""


def readme(role: dict[str, Any], skills: list[dict[str, Any]], filled: int, open_n: int, note: str, tool_rows: int) -> str:
    L = [f"# Setup-Paket — {role['name']}", "",
         "Ein Startpunkt für einen persönlichen Arbeitsagenten. Aus dem Arbeitsgraphen vorbelegt ist, was der Graph weiß; alles andere steht als „❓ offen“. "
         "Nichts hier ist getestet, freigegeben oder aktiv.", "",
         f"Vorbelegt: {filled} Zeilen aus dem Graphen · Offen in der Rollen.md: {open_n} Felder · Skills: {len(skills)} (alle im Entwurf) · Systeme: {tool_rows}", ""]
    if note:
        L += [f"**Hinweis:** {note}", ""]
    L += ["## Reihenfolge", "",
          "Richtwert aus dem Playbook: rund vier konzentrierte Stunden für das Grundsetup. Das ist eine Schätzung des Autors, keine Messung.", "",
          "| # | Schritt | Datei | Richtwert |", "|---|---|---|---|",
          "| 1 | Rollen.md per Interview vervollständigen | `kontext/interview-prompt.md` → `kontext/Rollen.md` | ca. 60 Min |",
          "| 2 | Agenten einrichten: Systemprompt einfügen, Profil ablegen, wo er es lesen und aktualisieren kann | `agent/systemprompt.md` | ca. 30 Min |",
          "| 3 | Ersten Skill mit echten Fällen testen, zwei bis drei Schleifen | `skills/<skill>/evals/` | ca. 90 Min |",
          "| 4 | Systeme prüfen lassen und lesend anbinden | `tools/anbindungen.md` | je nach Freigabe |",
          "| 5 | Agenten sichtbar machen, ersten Erfolgsmoment suchen | `routinen/routinen.md` | ca. 30 Min |",
          "| 6 | Erst danach: Routinen aktivieren | `routinen/routinen.json` | nach bestandenem Test |", "",
          "## Skills", "", "| Skill | Aufgaben | Herkunft |", "|---|---|---|"]
    L += [f"| `{s['name']}` | {s['tasks']} | {s['origin']} |" for s in skills]
    L += ["", "## Was dieses Paket nicht ist", "",
          "- Kein Ersatz für das Gespräch mit der Person, die die Rolle ausübt.",
          "- Keine Freigabe von Systemzugriffen.",
          "- Keine Aussage über Zeitersparnis. Die im Playbook genannten Spannen sind Selbstauskünfte und werden hier nicht als Wert verwendet.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Zusammenbau
# ---------------------------------------------------------------------------

def build_package(graph: dict[str, Any], role: dict[str, Any], n_skills: int, evidence: dict[str, Any] | None = None) -> dict[str, str]:
    groups, note = skill_groups(graph, role, n_skills)
    if len(groups) < MIN_SKILLS:
        extra = (f"Es gibt nur {len(groups)} Skill-Gruppe(n): Aufgaben, die derselbe Agent abdeckt, sind zu einem Skill gebündelt, "
                 f"und manuell bewertete Aufgaben bekommen keinen. Drei bis fünf Skills sind ein Richtwert für den Start, kein Muss.")
        note = (note + " " + extra).strip()
    files: dict[str, str] = {}
    skill_meta: list[dict[str, Any]] = []
    procs = wl.index_by_id(graph["processes"])
    for g in groups:
        name = group_name(g)
        base = f"skills/{name}"
        if g["agent"]:
            a, c = g["agent"], g["agent"]["contract"]
            steps = sorted(s["name"] for s in steps_of_role(graph, role) if s.get("executor", {}).get("id") == a["id"] or {t["id"] for t in g["tasks"]} & set(s.get("task_ids", [])))
            files[f"{base}/SKILL.md"] = es.skill_md(a, c, steps, sorted(t["name"] for t in g["tasks"]), name)
            files[f"{base}/scripts/run.py"] = es.run_py(a, c, name)
            files[f"{base}/scripts/report_usage.py"] = es.REPORT_PY
            origin = "Capability Contract"
        else:
            files[f"{base}/SKILL.md"] = generic_skill_md(graph, role, g, name)
            origin = "Aufgabendaten"
        files[f"{base}/evals/cases.json"] = json.dumps(eval_cases(graph, role, g, name), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files[f"{base}/evals/protokoll.md"] = protokoll(name)
        freqs = [t.get("frequency") for t in g["tasks"] if t.get("frequency")]
        order = ["daily", "weekly", "monthly", "quarterly"]
        top = next((f for f in order if f in freqs), None)
        trig = None
        c = g["agent"]["contract"] if g["agent"] else {}
        if c.get("trigger"):
            trig = c["trigger"]
        else:
            tids = {t["id"] for t in g["tasks"]}
            for s in steps_of_role(graph, role):
                if tids & set(s.get("task_ids", [])) and procs.get(s["process_id"], {}).get("trigger"):
                    trig = procs[s["process_id"]]["trigger"]
                    break
        t0 = g["tasks"][0]
        one = (g["agent"].get("capability") if g["agent"] else None) or t0.get("description") or t0["name"]
        one = one.strip().split(". ")[0].rstrip(".")[:140]
        skill_meta.append({"name": name, "one_line": one,
                           "tasks": ", ".join(t["name"] for t in g["tasks"]), "origin": origin,
                           "time": TIME_TRIGGER.get(top), "event": trig})
    kp, filled, open_n = kontextprofil(graph, role, groups, evidence)
    files["kontext/Rollen.md"] = kp
    files["kontext/interview-prompt.md"] = interview_prompt(role, open_n)
    files["skills/skill-ideen-prompt.md"] = skill_ideen_prompt(role)
    files["agent/systemprompt.md"] = systemprompt(graph, role, skill_meta)
    tools_md, tool_rows = tool_table(graph, role, groups)
    files["tools/anbindungen.md"] = tools_md
    items = routines(graph, role, skill_meta)
    files["routinen/routinen.json"] = json.dumps({"hinweis": "Alle Routinen inaktiv. Aktiv setzen erst, wenn der Skill live-reif ist (check_role_setup.py).",
                                                  "routines": items}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    files["routinen/routinen.md"] = routines_md(items)
    files["pflege/pflege.md"] = pflege(role)
    files["README.md"] = readme(role, skill_meta, filled, open_n, note, len(tool_rows))
    files["_meta"] = json.dumps({"filled": filled, "open": open_n, "skills": [s["name"] for s in skill_meta], "systems": len(tool_rows)}, sort_keys=True)
    return files


def write_package(out: Path, files: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Schreibt das Paket. Bearbeitete Dateien bleiben unberührt, der neue Stand liegt als .vorschlag daneben."""
    manifest_path = out / "manifest.json"
    prev = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {}) if manifest_path.exists() else {}
    written, proposed, unchanged = [], [], []
    hashes: dict[str, str] = {}
    for rel in sorted(k for k in files if not k.startswith("_")):
        text = files[rel]
        path = out / rel
        h = sha(text)
        if path.exists():
            cur = sha(path.read_text(encoding="utf-8"))
            if cur == h:
                hashes[rel] = h
                unchanged.append(rel)
                continue
            if rel in prev and cur != prev[rel]:
                wl.write_text(path.with_name(path.name + ".vorschlag"), text)
                hashes[rel] = prev[rel]
                proposed.append(rel)
                continue
        wl.write_text(path, text)
        hashes[rel] = h
        written.append(rel)
    meta = json.loads(files["_meta"])
    wl.write_json(manifest_path, {"status": "entwurf", "files": hashes, **meta,
                                  "hinweis": "Prüfsummen der zuletzt erzeugten Fassung. Bearbeitete Dateien erkennt build_role_setup.py daran und überschreibt sie nicht."})
    return written, proposed, unchanged


def list_roles(graph: dict[str, Any]) -> str:
    rows = ["| Rolle | Level | Headcount | Skill-Kandidaten | Wirkung |", "|---|---|---:|---:|---|"]
    for r in sorted(graph["roles"], key=lambda r: (r["name"], r["id"])):
        groups, _ = skill_groups(graph, r, DEFAULT_SKILLS)
        dt = (r.get("analysis") or {}).get("disruption_type") or "nicht bewertet"
        rows.append(f"| {r['name']} | {r.get('level') or '–'} | {wl.role_headcount(r) if wl.role_headcount(r) is not None else '–'} | {len(groups)} | {dt} |")
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--role", action="append", default=[], help="Rollenname oder ID; mehrfach oder mit ; getrennt")
    ap.add_argument("--all", action="store_true", help="Pakete für alle Rollen")
    ap.add_argument("--list", action="store_true", help="Rollen mit Skill-Kandidaten anzeigen")
    ap.add_argument("--skills", type=int, default=DEFAULT_SKILLS, help=f"Anzahl Skills ({MIN_SKILLS}–{MAX_SKILLS})")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    if args.list:
        print(list_roles(graph))
        return 0
    if not args.role and not args.all:
        wl.fail("Rolle angeben (--role \"Name\", mehrfach möglich), --all oder --list")
    if args.all:
        targets = sorted(graph["roles"], key=lambda r: (r["name"], r["id"]))
    else:
        targets, missing = [], []
        for ref in args.role:
            for part in (x.strip() for x in ref.split(";")):
                if not part:
                    continue
                r = find_role(graph, part)
                if r is None:
                    sim = similar_roles(graph, part)
                    missing.append(f"{part!r}" + (f" (meinst du: {', '.join(sim)}?)" if sim else ""))
                elif r not in targets:
                    targets.append(r)
        if missing:
            wl.fail("Rolle nicht eindeutig gefunden: " + "; ".join(missing) + ". Mit --list siehst du alle Rollen.")
    evidence, ev_problems = rm.load_evidence(project, [r["name"] for r in targets])
    for p in ev_problems:
        print(f"HINWEIS  Kontext-Vorschläge: {p}")
    root = project / wl.DIR_OUTPUT / "rollen_setup"
    team = []
    for role in targets:
        ev = {"firma": evidence["firma"], "roles": evidence["roles"]}
        files = build_package(graph, role, args.skills, ev)
        out = root / es.slug(role["name"])
        written, proposed, unchanged = write_package(out, files)
        meta = json.loads(files["_meta"])
        n_prop = files["kontext/Rollen.md"].count(rm.PROPOSED)
        team.append({"role": role["name"], "skills": len(meta["skills"]), "filled": meta["filled"], "proposed": n_prop, "open": meta["open"]})
        print(f"Geschrieben: {wl.relpath(out)} | Skills={len(meta['skills'])} vorbelegt={meta['filled']} Vorschläge aus Dokumenten={n_prop} offen={meta['open']} "
              f"Systeme={meta['systems']} neu={len(written)} unverändert={len(unchanged)} Vorschläge={len(proposed)}")
        for rel in proposed:
            print(f"HINWEIS  {rel} wurde bearbeitet — neuer Stand als {rel}.vorschlag")
    if len(targets) >= 2:
        w, pr, _u = write_package(root / "_team", {"Teamstart.md": teamstart(team), "_meta": json.dumps({"roles": [t["role"] for t in team]})})
        print(f"Geschrieben: {wl.relpath(root / '_team' / 'Teamstart.md')} (Mini-Hackathon für {len(targets)} Rollen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
