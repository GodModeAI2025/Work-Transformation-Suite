#!/usr/bin/env python3
"""
build_documents.py — erzeugt die Unterlagen für eine Entscheidungsrunde aus dem Arbeitsgraphen.

Aufruf:
    python3 <skill>/scripts/build_documents.py --project ./mein-projekt [--config wave-config.json] [--strict]

Ausgaben in 40_output/dokumente/ (jeweils .md und .html):
    entscheidungsvorlage   Anlass, Ausgangslage, Jobarchitektur, Potenziale, Fahrplan, Pilot, Beschluss
    hr-einseiter           eine Seite für HR: was sich für Rollen ändert und was zu entscheiden ist
    anhang-potenziale      alle Vorhaben mit Score, Wertquelle und Zuordnung
    methodik               wie die Zahlen entstehen und was sie nicht sagen

Zahlen und Tabellen kommen aus dem Graphen, Erzählendes aus `30_review/dokumente/texte.json`.
Die Texte schreibt Claude oder ein Mensch, jeder mit Quelle:

    {"entscheidungsvorlage": {"anlass": {"text": "...", "quelle": "...", "verfasst_von": "..."}},
     "hr_einseiter": {"botschaft": {"text": "...", "quelle": "..."}}}

Ein Textfeld ohne Text oder ohne Quelle bleibt als „❓ offen“ stehen. Der Kopf jedes Dokuments
nennt den Stand: Entwurf, solange Textfelder offen sind oder Wellen nur Vorschlag sind.
Mit --strict endet der Lauf mit Code 1, wenn ein Dokument nicht versandfertig ist oder ein Textfeld ein Wort
aus `flag_words` (Konfiguration) enthält.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_lib as rl  # noqa: E402
import roadmap_views as rv  # noqa: E402
import workgraph_lib as wl  # noqa: E402
from render_lib import OPEN, eur, html_page, md_table, md_to_html, num  # noqa: E402

TEXT_FILE = Path("dokumente") / "texte.json"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Textfelder: Dokument -> (Schlüssel, Überschrift, Auftrag an den Verfasser)
SLOTS = {
    "entscheidungsvorlage": [
        ("anlass", "Anlass und Ziel",
         "Warum jetzt, und was soll erreicht werden? Ein bis drei Sätze, mit Verweis auf das Material."),
        ("pilot", "Pilot und Referenz",
         "Was aus dem laufenden Pilot gelernt wurde und was davon gezeigt werden darf. Namen Dritter nur mit Einverständnis."),
        ("vorgehen", "Vorgehen",
         "Wer verantwortet was, in welchen Schritten, mit welchen Zwischenentscheidungen."),
        ("beschluss", "Gewünschter Beschluss",
         "Was soll die Runde beschließen? Ein bis drei konkrete Sätze."),
    ],
    "hr_einseiter": [
        ("botschaft", "Kernbotschaft",
         "Was bedeutet das für die Rollen im Bereich? Eine Aussage ohne Fachbegriffe, belegbar mit der Tabelle darunter."),
        ("mitbestimmung", "Beteiligung und Rahmen",
         "Welche Gremien, Vereinbarungen und Qualifizierungen sind beteiligt? Nur Belegtes."),
    ],
}
DISRUPTION_PLAIN = {"eliminated": "Aufgaben entfallen weitgehend", "transformed": "Rolle wird neu zugeschnitten",
                    "augmented": "Rolle bleibt, KI unterstützt", "emerging": "neue Rolle entsteht",
                    "stable": "kaum Änderung"}


# ---------------------------------------------------------------------------
# Textfelder
# ---------------------------------------------------------------------------

def load_texts(project: Path, cfg: dict) -> tuple[dict, list[str], list[str]]:
    """Gibt (Texte, Hinweise, Tonfunde) zurück. Nur Felder mit Text und Quelle gelten als gefüllt."""
    path = project / wl.DIR_REVIEW / TEXT_FILE
    if not path.exists():
        return {}, [], []
    try:
        raw = wl.read_json(path)
    except ValueError as e:
        return {}, [f"{TEXT_FILE.as_posix()} nicht lesbar: {e}"], []
    texts, notes, tone = {}, [], []
    flags = [f.lower() for f in cfg.get("flag_words", [])]
    for doc, slots in SLOTS.items():
        for key, title, _ in slots:
            entry = (raw.get(doc) or {}).get(key)
            if not entry:
                continue
            text = (entry.get("text") or "").strip()
            source = (entry.get("quelle") or "").strip()
            if not text:
                continue
            if not source:
                notes.append(f"{doc}/{key}: Text ohne Quelle nicht übernommen")
                continue
            if EMAIL_RE.search(text):
                notes.append(f"{doc}/{key}: enthält eine E-Mail-Adresse, nicht übernommen (Personendaten gehören nicht in die Unterlage)")
                continue
            for f in flags:
                if f in text.lower():
                    tone.append(f"{doc}/{key}: enthält „{f}“ (laut flag_words der Konfiguration zu vermeiden)")
            texts[(doc, key)] = {"text": text, "quelle": source, "von": (entry.get("verfasst_von") or "").strip()}
    return texts, notes, tone


def slot_block(doc: str, key: str, title: str, hint: str, texts: dict, level: str = "##") -> tuple[str, bool]:
    """Überschrift plus Text oder offener Platzhalter; zweiter Wert: gefüllt?"""
    entry = texts.get((doc, key))
    if entry:
        who = f", verfasst von {entry['von']}" if entry["von"] else ""
        return f"{level} {title}\n\n{entry['text']}\n\n*Quelle: {entry['quelle']}{who}*\n", True
    return f"{level} {title}\n\n> {OPEN}: {hint}\n", False


# ---------------------------------------------------------------------------
# Bausteine aus dem Graphen
# ---------------------------------------------------------------------------

def baseline(graph: dict) -> list[str]:
    roles = graph.get("roles", [])
    tasks = graph.get("tasks", [])
    hcs = [wl.role_headcount(r) for r in roles]
    known = [h for h in hcs if h is not None]
    scored = sum(1 for t in tasks if t.get("scores"))
    lines = [f"- {len(roles)} Rollen"
             + (f" mit {num(sum(known), 0)} Stellen" if known else "")
             + (f" (bei {len(hcs) - len(known)} Rollen ist die Stellenzahl unbekannt)" if len(known) != len(hcs) else ""),
             f"- {len(tasks)} Aufgaben, davon {scored} bewertet",
             f"- {len(graph.get('processes', []))} End-to-End-Prozesse, {len(graph.get('agents', []))} Agenten, "
             f"{len(graph.get('usecases', []))} Use Cases"]
    return lines


def target_totals(p: dict) -> str:
    rows = [a for a in p["architecture"] if a["has_target"] and a["fte_current"] is not None]
    if not rows:
        return "Für die Rollen liegt noch kein Zielbild vor."
    cur = sum(a["fte_current"] for a in rows)
    rem = sum(a["fte_remaining"] for a in rows if a["fte_remaining"] is not None)
    missing = [a["name"] for a in p["architecture"] if not a["has_target"]]
    s = (f"Für {len(rows)} von {len(p['architecture'])} Rollen liegt ein Zielbild vor (Entwurf, geschätzt): "
         f"zusammen {num(cur)} FTE heute, {num(rem)} FTE künftig.")
    if missing:
        s += " Ohne Zielbild: " + ", ".join(missing) + "."
    return s


def pilot_facts(graph: dict) -> str:
    exps = graph.get("experiments", [])
    metrics = wl.index_by_id(graph.get("metrics", []))
    if not exps:
        return "Es liegen noch keine geplanten oder ausgewerteten Piloten im Graphen."
    rows = []
    for x in sorted(exps, key=lambda e: (e.get("name") or "", e["id"])):
        m = metrics.get(x.get("primary_metric_id")) or {}
        res = [r for r in x.get("results", []) if r.get("metric_id") == x.get("primary_metric_id")]
        unit = m.get("unit") or ""
        if res:
            r = res[-1]
            base = wl.metric_value(m, "baseline")[0] if m else None
            result = f"{num(r.get('value'))} {unit} (beobachtet"
            result += f", Ausgangswert {num(base)} {unit}" if base is not None else ""
            result += f", Ziel {num(x.get('target_value'))} {unit})" if x.get("target_value") is not None else ")"
        else:
            result = f"noch keine Messung (Ziel {num(x.get('target_value'))} {unit})" if x.get("target_value") is not None \
                else "noch keine Messung"
        rows.append([x.get("name"), {"ab_test": "A/B-Test", "shadow": "Schattenbetrieb", "stepped_rollout": "gestufter Rollout",
                                     "pre_post": "Vorher/Nachher"}.get(x.get("design"), x.get("design") or "–"),
                     {"draft": "Entwurf", "ready": "bereit", "running": "läuft", "stopped": "abgebrochen",
                      "completed": "abgeschlossen"}.get(x.get("status"), x.get("status") or "–"),
                     num(x.get("sample_size"), 0), m.get("name") or "–", result,
                     "ja" if x.get("frame_confirmed") else "nein"])
    return md_table(["Pilot", "Aufbau", "Stand", "Fälle", "Hauptkennzahl", "Ergebnis", "Rahmen bestätigt"], rows,
                    ["l", "l", "l", "r", "l", "l", "l"])


def status_line(doc_label: str, open_slots: list[str], p: dict, extra: list[str]) -> tuple[str, bool]:
    reasons = []
    if open_slots:
        reasons.append(f"Textfelder offen: {', '.join(open_slots)}")
    pending = [w["label"] for w in p["waves"] if w["state"] in ("proposed", "partial")]
    if pending:
        reasons.append(f"Wellen nur als Vorschlag: {len(pending)}")
    reasons += extra
    ready = not reasons
    return (f"**Stand: {'versandfertig' if ready else 'Entwurf'}**" + ("" if ready else " (" + "; ".join(reasons) + ")")), ready


# ---------------------------------------------------------------------------
# Dokumente
# ---------------------------------------------------------------------------

def doc_entscheidungsvorlage(graph, p, texts, version, tone):
    meta = graph.get("meta", {})
    scope = meta.get("scope") or meta.get("project") or "Projekt"
    blocks, open_slots = {}, []
    for key, title, hint in SLOTS["entscheidungsvorlage"]:
        blocks[key], ok = slot_block("entscheidungsvorlage", key, title, hint, texts)
        if not ok:
            open_slots.append(key)
    top = sorted((c for c in p["candidates"] if c["score"] is not None), key=lambda c: (-c["score"], c["name"] or ""))[:5]
    top_rows = [[c["name"], rv.KIND_LABEL[c["kind"]], num(c["score"]), eur(c["value_eur"]), num(c["fte"]),
                 f"Welle {p['placement'][c['key']]['wave']}"] for c in top]
    status, ready = status_line("Entscheidungsvorlage", open_slots, p, tone)
    pts = rv.open_points(p, graph)
    md = [f"# Entscheidungsvorlage: {scope}", "",
          f"{meta.get('organization') or ''} | Graph-Version {version}".strip(" |"), "", status, "",
          blocks["anlass"],
          "## Ausgangslage", "", *baseline(graph), "",
          "## Jobarchitektur heute und künftig", "", target_totals(p), "", rv.architecture(p), "",
          "Das Zielbild ist ein Entwurf: Zeitanteile stammen aus der Aufgabenanalyse, die Bewertung der Automatisierbarkeit "
          "ist geschätzt, bis Fachleute sie bestätigen. „Auffangweg“ nennt, wie frei werdende Kapazität aufgefangen werden "
          "soll; er ist eine Annahme der Rolle, keine Zusage.", "",
          "## Potenziale und Reihenfolge", "",
          "Die fünf Vorhaben mit dem höchsten Score:", "",
          md_table(["Vorhaben", "Art", "Score", "Wert/Jahr", "FTE", "Welle"], top_rows, ["l", "l", "r", "r", "r", "l"]) if top_rows
          else "Kein Vorhaben hat genug Angaben für einen Score.", "",
          "Alle Vorhaben mit Zuordnung stehen im Anhang.", "",
          "## Fahrplan in Wellen", "", rv.wave_overview(p), "", rv.VALUE_NOTE, "",
          "## Stand der Piloten", "", pilot_facts(graph), "",
          blocks["pilot"], blocks["vorgehen"], blocks["beschluss"],
          "## Was vor dem Beschluss noch offen ist", ""]
    md += [f"- {x}" for x in pts] if pts else ["Nichts."]
    md += ["", "## Grenzen der Zahlen", "",
           "- Wert und FTE beschreiben gebundene Arbeit, nicht Einsparung.",
           "- Geschätzte Werte stehen als geschätzt da; beobachtete Werte stammen aus Piloten und sind als beobachtet ausgewiesen.",
           "- Das Raster ist ein Vorschlag, bis benannte Personen die Zuordnung bestätigt haben.",
           "- Die Unterlage sagt nichts über einzelne Personen.", ""]
    return "\n".join(md), ready, open_slots


def doc_hr(graph, p, texts, version, tone):
    meta = graph.get("meta", {})
    scope = meta.get("scope") or meta.get("project") or "Projekt"
    blocks, open_slots = {}, []
    for key, title, hint in SLOTS["hr_einseiter"]:
        blocks[key], ok = slot_block("hr_einseiter", key, title, hint, texts)
        if not ok:
            open_slots.append(key)
    rows = []
    for a in p["architecture"]:
        change = DISRUPTION_PLAIN.get(a["disruption_type"], "nicht bewertet")
        rows.append([a["name"], num(a["headcount"], 0), change,
                     f"{num(a['retained_share_pct'], 0)} %" if a["retained_share_pct"] is not None else "nicht bewertet",
                     rl.ABSORPTION_LABEL.get(a["absorption"], "nicht festgelegt"),
                     f"Welle {a['first_wave']}" if a["first_wave"] else "bisher keine"])
    asks = []
    if any(w["state"] in ("proposed", "partial") for w in p["waves"]):
        asks.append("Die Reihenfolge der Wellen bestätigen oder ändern.")
    if any(not w["period"] for w in p["waves"] if w["items"]):
        asks.append("Zeiträume für die Wellen festlegen.")
    open_abs = [a["name"] for a in p["architecture"] if a["first_wave"] and not a["absorption"]]
    if open_abs:
        asks.append("Den Auffangweg festlegen für: " + ", ".join(open_abs) + ".")
    no_target = [a["name"] for a in p["architecture"] if a["first_wave"] and not a["has_target"]]
    if no_target:
        asks.append("Zielbild klären für: " + ", ".join(no_target) + ".")
    status, ready = status_line("HR-Einseiter", open_slots, p, tone)
    md = [f"# {scope}: was sich für Rollen ändert", "", status, "", blocks["botschaft"],
          "## Rollen im Überblick", "",
          md_table(["Rolle", "Stellen", "Was sich ändert", "Arbeit, die bleibt", "Auffangweg", "Betroffen ab"], rows,
                   ["l", "r", "l", "r", "l", "l"]), "",
          "Die Angaben sind Schätzungen aus der Aufgabenanalyse. Sie betreffen Rollen, nicht einzelne Personen.", "",
          "## Was HR entscheiden kann", ""]
    md += [f"- {x}" for x in asks] if asks else ["Aktuell ist nichts offen."]
    md += ["", blocks["mitbestimmung"]]
    return "\n".join(md), ready, open_slots


def doc_annex(graph, p, version):
    md = ["# Anhang: Vorhaben, Score und Zuordnung", "",
          f"Graph-Version {version}. Alle Vorhaben mit den fünf Größen des Scores (0 bis 10). „–“ heißt: nicht bekannt, "
          "nicht null.", "", rv.candidates_table(p), "",
          "## Basis des Scores je Vorhaben", ""]
    md += [f"- {c['name']}: {c['score_basis']}" for c in sorted(p["candidates"], key=lambda c: c["name"] or "")]
    md += ["", "## Vorhaben und betroffene Rollen je Welle", "", rv.wave_detail(p), "",
           "## Jobarchitektur im Detail", "", rv.architecture(p), "",
           "## Ohne Vorhaben", "", rv.gaps_block(p), ""]
    return "\n".join(md)


def doc_method(p):
    cfg = p["config"]
    w = cfg["weights"]
    rows = [[rl.COMPONENT_LABEL[k], f"{w[k]:.2f}", d] for k, d in [
        ("value", "Jahreswert des Vorhabens; Team-Angabe, sonst gebundene Arbeit mal Tagessatz. Relativ zum höchsten Wert."),
        ("reach", "Betroffene FTE, relativ zum höchsten Wert."),
        ("ease", "Aus der Komplexität des Agenten (1 leicht bis 5 schwer). Für Use Cases ohne Agent nicht bekannt."),
        ("readiness", "Aus dem Status: " + ", ".join(f"{k} {v}" for k, v in cfg["status_readiness"].items()) + "."),
        ("process", "Höchster Rang eines Prozesses, dem die Aufgaben angehören: "
                    + ", ".join(f"{k} {v}" for k, v in cfg["band_score"].items()) + ".")]]
    cap = "; ".join(f"{x['label']}: {x['capacity'] if x.get('capacity') else 'offen'}" for x in cfg["waves"])
    md = ["# Methodik: wie die Zahlen entstehen", "",
          "## Drei Arten von Zahlen", "",
          "- **Geschätzt:** aus Aufgabenanalyse, Zeitanteilen und Tagessätzen. Nachvollziehbar, aber nicht gemessen.",
          "- **Von Fachleuten bestätigt:** jemand mit Verantwortung hat den Wert geprüft und freigegeben.",
          "- **Beobachtet:** gemessen in einem Pilot, mit Zeitraum und Stichprobe.", "",
          "Jede Tabelle sagt, welche Art sie zeigt. Eine fehlende Angabe steht als „nicht bewertet“ da und fließt nicht als null ein.", "",
          "## Wert und Reichweite", "",
          "Die gebundene Arbeitszeit der betroffenen Aufgaben, je Rolle mal Stellenzahl und mal Tagessatz, ergibt den Wert. "
          "Das ist die Größe der Arbeit, die ein Vorhaben berührt. Wie viel davon frei wird, hängt von Gestaltung, Akzeptanz "
          "und Aufsicht ab und ist hier nicht berechnet. Berührt dieselbe Aufgabe mehrere Vorhaben, zählt sie in der Summe einmal.", "",
          "## Score", "", md_table(["Größe", "Gewicht", "Herkunft"], rows, ["l", "r", "l"]), "",
          "Fehlt eine Größe, rechnet der Score mit den übrigen und nennt im Anhang, was fehlt. "
          f"Mit weniger als {cfg.get('min_components', 2)} bekannten Größen bleibt der Score leer.", "",
          "## Wellen", "",
          "Bestätigte Entscheidungen (mit benannter Person) stehen fest. Laufende Vorhaben liegen in der ersten Welle. "
          "Der Rest folgt dem Score. Vorhaben mit Komplexität über "
          f"{cfg.get('max_complexity_first_wave', 5)} beginnen nicht in der ersten Welle. Orchestratoren kommen frühestens "
          f"eine Welle nach den Agenten, die sie steuern. Kapazität je Welle: {cap}. "
          "Zeiträume setzt das Raster nicht selbst.", "",
          "## Was die Unterlagen nicht sagen", "",
          "- Nichts über einzelne Personen.",
          "- Keine Zusage zu Stellen. Der Auffangweg ist eine Annahme je Rolle.",
          "- Keine Garantie für Einsparungen.", ""]
    return "\n".join(md)


# ---------------------------------------------------------------------------

def write_doc(out: Path, name: str, md: str, title: str) -> None:
    wl.write_text(out / f"{name}.md", md)
    wl.write_text(out / f"{name}.html", html_page(title, md_to_html(md)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--strict", action="store_true", help="Exit-Code 1, wenn ein Dokument nicht versandfertig ist")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph.get("agents") and not graph.get("usecases"):
        print("Hinweis: keine Agenten und keine Use Cases im Graphen; die Unterlagen hätten keinen Inhalt. "
              "Nächster Schritt: Skill agent-mapper.")
        return 3
    cfg = rl.load_config(Path(args.config) if args.config else None)
    probe = rl.build_candidates(graph, cfg)
    decisions, warnings = rl.read_decisions(project, probe, cfg)
    p = rl.plan(graph, cfg, decisions)
    texts, text_notes, tone = load_texts(project, cfg)
    version = int(graph.get("meta", {}).get("version", 0))
    out = project / wl.DIR_OUTPUT / "dokumente"
    out.mkdir(parents=True, exist_ok=True)
    scope = graph.get("meta", {}).get("scope") or "Projekt"

    ev, ev_ready, ev_open = doc_entscheidungsvorlage(graph, p, texts, version, tone)
    hr, hr_ready, hr_open = doc_hr(graph, p, texts, version, tone)
    write_doc(out, "entscheidungsvorlage", ev, f"Entscheidungsvorlage {scope}")
    write_doc(out, "hr-einseiter", hr, f"Einseiter für HR {scope}")
    write_doc(out, "anhang-potenziale", doc_annex(graph, p, version), f"Anhang {scope}")
    write_doc(out, "methodik", doc_method(p), f"Methodik {scope}")

    for n in warnings + text_notes + tone:
        print(f"HINWEIS  {n}")
    state = lambda ok: "versandfertig" if ok else "Entwurf"  # noqa: E731
    print(f"Geschrieben: {wl.relpath(out)}/ (entscheidungsvorlage, hr-einseiter, anhang-potenziale, methodik; .md und .html)")
    print(f"Stand: Entscheidungsvorlage {state(ev_ready)} (offene Textfelder: {len(ev_open)}), "
          f"HR-Einseiter {state(hr_ready)} (offene Textfelder: {len(hr_open)})")
    if (ev_open or hr_open) and not texts:
        print("Nächster Schritt für Claude: Textfelder in 30_review/dokumente/texte.json aus Quellen füllen "
              "(Format im Kopf von build_documents.py und in references/dokumente.md).")
    if args.strict and (not ev_ready or not hr_ready or tone):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
