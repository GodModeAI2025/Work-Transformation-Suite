#!/usr/bin/env python3
"""
extract_context_evidence.py — holt aus vorhandenem Material Vorschläge für die Felder der Rollen.md, die der Arbeitsgraph
nicht kennt und die man sonst per Frage und Antwort erfragen müsste.

Aufruf:
    python3 <skill>/scripts/extract_context_evidence.py --project ./mein-projekt [--role "Forderungsmanager"] [--keep-names]

Wo das Material liegt (`00_input/kontext/`):
    firma/                  Texte über das Unternehmen: Über-uns, Geschäftsbericht (als Text), Leitbild, Produktseiten
    <rolle>/                Material der Person in dieser Rolle (Ordnername = Rollenname in Kleinbuchstaben, Umlaute aufgelöst)
      texte/                eigene Texte: Mails, Beiträge, Notizen — daraus wird der Stil gemessen
      transkripte/          Meeting-Transkripte
      projekte/             Projektdokumente, Protokolle, Statusberichte
    Ohne Unterordner ordnet das Skript nach Dateiname und Inhalt zu.
    Gelesen werden nur Textdateien (.md, .txt, .csv, .json, .srt, .vtt). PDF, Word und Mail liest Claude und trägt die Funde im
    selben Format ein (siehe `references/kontext-aus-dokumenten.md`).

Ausgabe: `30_review/kontext_evidenz/firma.json` und `<rolle>.json` plus eine lesbare Fassung `kontext_evidenz.md`.

Was gilt:
- Jeder Vorschlag trägt Quelle, Fundstelle und ein kurzes Zitat. Ohne Zitat und Quelle gibt es keinen Eintrag.
- Vorschläge sind **Vorschläge**. In der Rollen.md stehen sie mit „✎ Vorschlag aus Dokument — bitte bestätigen“, nicht als Tatsache.
- Stil wird **gemessen**, nicht geraten: Anrede, Satzlänge, Listenanteil, Grußformeln, wiederkehrende Wendungen. Mit weniger als drei Texten oder
  600 Wörtern entsteht kein Stilprofil („zu wenig Material“).
- „Don'ts“ entstehen nur aus einem Befund: Typische KI-Floskeln, die in den eigenen Texten nie vorkommen.
- Personendaten: E-Mail-Adressen, Telefonnummern und Anreden mit Namen („Hallo Anna“) werden maskiert; Personennamen werden **nicht** automatisch
  extrahiert. Die Maskierung ist eine Heuristik und kein Anonymisierungsverfahren — Transkripte enthalten Daten Dritter und gehören nur mit Einverständnis in
  das Projekt. Mit --keep-names bleiben Anreden unmaskiert.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import export_skill as es  # noqa: E402

SCHEMA = "kontext-evidenz-1"
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".srt", ".vtt"}
MAX_PER_FIELD = 5
QUOTE_MAX = 220
MIN_STYLE_TEXTS, MIN_STYLE_WORDS = 3, 600

# Feldschlüssel -> Beschriftung in der Rollen.md
FIELD_KEYS = {
    "firma.geschaeftsmodell": "Was das Unternehmen tut (Geschäftsmodell)",
    "firma.kunden": "Für wen (Kunden und Empfänger der Ergebnisse)",
    "firma.markt": "Markt und Branche",
    "firma.produkte": "Produkte und Leistungen",
    "firma.sprachgebrauch": "Sprachgebrauch im Haus (Fachbegriffe, Anrede)",
    "rolle.zeitfresser": "Zeitfresser aus deiner Sicht",
    "team.kanaele": "Bevorzugter Kanal je Anlass (dringend, Abstimmung, Dokumentation)",
    "prio.aktuell": "Woran du gerade arbeitest",
    "prio.ziele": "Ziele dieses Quartals",
    "stil.ton": "Tonalität (wie du klingst, Anrede, Förmlichkeit)",
    "stil.format": "Bevorzugte Formate (Tabelle, Stichpunkte, Fließtext, Länge)",
    "stil.dos": "Do's für KI-Texte",
    "stil.donts": "Don'ts für KI-Texte (Floskeln, Formulierungen, die du nie schreiben würdest)",
}

BRANCHEN = {
    "Energiewirtschaft": ["energie", "strom", "netzbetrieb", "stadtwerke", "erneuerbar", "gasnetz", "versorger"],
    "Finanzdienstleistung": ["bank", "versicherung", "kreditinstitut", "zahlungsverkehr", "vermögen"],
    "Industrie und Fertigung": ["fertigung", "maschinenbau", "produktion", "förderanlage", "zulieferer", "hersteller"],
    "Handel": ["handel", "filiale", "sortiment", "onlineshop"],
    "Gesundheit": ["klinik", "patient", "pflege", "medizin", "krankenhaus"],
    "Öffentliche Verwaltung": ["verwaltung", "behörde", "kommune", "bürger"],
    "IT und Software": ["software", "plattform", "cloud", "saas", "entwicklung"],
    "Logistik": ["logistik", "spedition", "lieferkette", "transport"],
}
FRICTION = re.compile(r"\b(dauert|aufwand|manuell|händisch|haendisch|jedes mal|nervt|medienbruch|doppelt|warten|wartezeit|rückfrage|rueckfrage|"
                      r"abtippen|copy.?paste|excel|hin und her|zeitfresser|fehleranfällig|fehleranfaellig|suchen)\b", re.I)
GOALS = re.compile(r"\b(ziel|ziele|okr|kpi|zielwert|soll bis|meilenstein|ambition)\b", re.I)
PRIOS = re.compile(r"\b(priorität|prioritaet|prio\b|fokus|dringend|deadline|bis (ende )?(q[1-4]|\d{1,2}\.\d{1,2}\.)|action item|to-?do)\b", re.I)
CHANNELS = re.compile(r"\b(e-?mail|mail|messenger|telefon|anruf|ticket|meeting|chat|sms|portal|serviceportal)\b", re.I)
COMPANY = {
    "firma.geschaeftsmodell": re.compile(r"\b(wir sind|wir betreiben|wir entwickeln|wir bieten|unser geschäft|unser geschaeft|geschäftsmodell|geschaeftsmodell|"
                                         r"unsere mission|unser auftrag|wir stehen für)\b", re.I),
    "firma.kunden": re.compile(r"\b(unsere kunden|kunden sind|privatkunden|geschäftskunden|geschaeftskunden|für unsere kunden|zielgruppe)\b", re.I),
    "firma.produkte": re.compile(r"\b(unsere produkte|unsere leistungen|portfolio|angebot|dienstleistungen|lösungen)\b", re.I),
}
# Typische KI-Floskeln (deutsch). Stehen sie in den eigenen Texten nie, ist das ein Befund — und ein Don't-Kandidat.
AI_CLICHES = ["in der heutigen schnelllebigen welt", "tauchen wir ein", "es ist wichtig zu beachten", "zusammenfassend lässt sich sagen",
              "ich hoffe, diese nachricht erreicht sie gut", "gerne unterstütze ich sie", "nahtlos", "ganzheitlich", "game-changer",
              "in der heutigen digitalen welt", "lassen sie mich", "ein wahrer", "maßgeschneidert", "hebeln", "synergien",
              "im folgenden möchte ich", "abschließend lässt sich festhalten", "von entscheidender bedeutung"]
MASKED = {"name", "email", "mail", "nummer"}
STOP = set("""der die das und oder aber nicht ist sind war waren wird werden wurde wurden ein eine einen einem einer eines mit von für auf aus bei nach
zum zur den dem des im in an am es sie wir ich du er ihr uns euch auch noch nur schon sehr dass wie was wer wo wenn dann als so zu über unter
bis durch gegen ohne um mehr viel habe haben hat hatte kann können muss müssen soll sollen""".split())


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def slug_of_role(name: str) -> str:
    return es.slug(name)


def mask(text: str, keep_names: bool) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[E-Mail]", text)
    text = re.sub(r"(?<!\w)(\+?\d[\d /().-]{7,}\d)(?!\w)", "[Nummer]", text)
    if not keep_names:
        text = re.sub(r"\b(Hallo|Hi|Hey|Moin|Danke|Dank|Liebe|Lieber|Guten Tag|Grüße an)\s+(Herr\s+|Frau\s+)?[A-ZÄÖÜ][\wäöüß-]+", r"\1 [Name]", text)
        text = re.sub(r"\b(Herr|Frau)\s+[A-ZÄÖÜ][\wäöüß-]+", r"\1 [Name]", text)
        text = re.sub(r"@[A-Za-z0-9_.-]+", "@[Name]", text)
    return text


def quote(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= QUOTE_MAX else s[:QUOTE_MAX - 1].rstrip() + "…"


def classify(path: Path, text: str, hint: str | None) -> str:
    if hint:
        return hint
    name = wl.normalize_name(path.name)
    if any(k in name for k in ("transkript", "protokoll meeting", "meeting", "gespraech", "interview")) or _looks_like_transcript(text):
        return "transkript"
    if any(k in name for k in ("beispiel", "mail", "beitrag", "artikel", "notiz", "text")):
        return "text"
    return "projekt"


def _looks_like_transcript(text: str) -> bool:
    lines = text.splitlines()[:200]
    stamps = sum(1 for ln in lines if re.match(r"^\s*(\d{1,2}:\d{2}(:\d{2})?)\s+\S", ln))
    speakers = sum(1 for ln in lines if re.match(r"^\s*(Sprecher|Speaker|Teilnehmer)\s*\d+", ln, re.I))
    return stamps >= 5 or speakers >= 5


def entry(field: str, text: str, q: str, source: str, line_no: int | None, conf: str = "low") -> dict[str, Any]:
    return {"field": field, "text": text, "quote": quote(q), "source": source,
            "locator": f"Zeile {line_no}" if line_no else "Dokument", "by": "script", "confidence": conf}


def add_capped(out: list[dict[str, Any]], e: dict[str, Any]) -> None:
    if sum(1 for x in out if x["field"] == e["field"]) < MAX_PER_FIELD and not any(x["field"] == e["field"] and x["quote"] == e["quote"] for x in out):
        out.append(e)


# ---------------------------------------------------------------------------
# Firmentexte
# ---------------------------------------------------------------------------

def company_entries(files: list[tuple[Path, str]], project: Path, keep_names: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    branch_hits: Counter[str] = Counter()
    terms: Counter[str] = Counter()
    for p, raw in files:
        text = mask(raw, keep_names)
        src = p.relative_to(project).as_posix() if project in p.parents else p.name
        low = text.lower()
        for b, kws in BRANCHEN.items():
            branch_hits[b] += sum(len(re.findall(r"\b" + re.escape(k), low)) for k in kws)
        for m in re.finditer(r"\b[A-ZÄÖÜ][a-zäöüß]{5,}\b", text):
            terms[m.group(0)] += 1
        # Absätze zusammenziehen und satzweise prüfen: Umbrüche mitten im Satz würden sonst Zitate zerreißen.
        n = 1
        for para in re.split(r"\n\s*\n", text):
            first = n
            n += para.count("\n") + 2
            for sent in re.split(r"(?<=[.!?])\s+", re.sub(r"\s*\n\s*", " ", para.strip())):
                if len(sent) < 25 or sent.startswith("#"):
                    continue
                for fld, rx in COMPANY.items():
                    if rx.search(sent):
                        add_capped(out, entry(fld, quote(sent), sent, src, first))
    top = [b for b, c in branch_hits.most_common(2) if c >= 3]
    if top:
        n = sum(branch_hits[b] for b in top)
        out.append({"field": "firma.markt", "text": " / ".join(top), "quote": f"{n} Treffer auf Branchenbegriffe in {len(files)} Dokument(en)",
                    "source": "mehrere", "locator": "Zählung", "by": "script", "confidence": "low"})
    common = [t for t, c in terms.most_common(40) if c >= 3 and t.lower() not in STOP][:8]
    if common:
        out.append({"field": "firma.sprachgebrauch", "text": "Häufige Fachbegriffe: " + ", ".join(common),
                    "quote": "; ".join(f"{t} ({terms[t]}×)" for t in common[:5]), "source": "mehrere", "locator": "Zählung", "by": "script", "confidence": "low"})
    return out


# ---------------------------------------------------------------------------
# Transkripte und Projektdokumente
# ---------------------------------------------------------------------------

def talk_entries(p: Path, raw: str, src: str, kind: str, keep_names: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    text = mask(raw, keep_names)
    for n, ln in enumerate(text.splitlines(), start=1):
        s = ln.strip()
        if len(s) < 25:
            continue
        s = re.sub(r"^\s*(\d{1,2}:\d{2}(:\d{2})?\s+)?(Sprecher|Speaker|Teilnehmer)\s*\d+\s*[:\-]?\s*", "", s, flags=re.I)
        s = re.sub(r"^\d{1,2}:\d{2}(:\d{2})?\s+", "", s)
        if len(s) < 25:
            continue
        if GOALS.search(s):
            add_capped(out, entry("prio.ziele", quote(s), s, src, n))
        elif PRIOS.search(s):
            add_capped(out, entry("prio.aktuell", quote(s), s, src, n))
        if FRICTION.search(s):
            add_capped(out, entry("rolle.zeitfresser", quote(s), s, src, n))
        if CHANNELS.search(s) and re.search(r"\b(über|per|via|schicke|schicken|schick|melde|melden|abstimmen|rufe|rufen|läuft|laeuft|geht)\b", s, re.I):
            add_capped(out, entry("team.kanaele", quote(s), s, src, n))
    return out


# ---------------------------------------------------------------------------
# Stil aus eigenen Texten
# ---------------------------------------------------------------------------

def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)) if len(s.split()) >= 2]


def style_entries(samples: list[tuple[str, str]], keep_names: bool) -> list[dict[str, Any]]:
    """samples: (Quelle, Text). Misst; schätzt nicht."""
    texts = [(src, mask(t, keep_names)) for src, t in samples]
    words = sum(len(t.split()) for _s, t in texts)
    if len(texts) < MIN_STYLE_TEXTS or words < MIN_STYLE_WORDS:
        return [{"field": "stil.ton", "text": f"Zu wenig Material für ein Stilprofil ({len(texts)} Texte, {words} Wörter; nötig sind mindestens "
                                               f"{MIN_STYLE_TEXTS} Texte und {MIN_STYLE_WORDS} Wörter).",
                 "quote": f"{len(texts)} Texte, {words} Wörter", "source": "texte/", "locator": "Zählung", "by": "script", "confidence": "none"}]
    joined = "\n\n".join(t for _s, t in texts)
    low = joined.lower()
    out: list[dict[str, Any]] = []
    informal_rx = re.compile(r"\b(du|dein|deine|deinen|deinem|deiner|dir|dich|ihr|euch|euer|eure|euren|eurem|eurer)\b")
    formal_rx = re.compile(r"(?<![.!?]\s)(?<!^)\b(Sie|Ihre|Ihren|Ihrem|Ihrer|Ihnen|Ihr)\b")
    informal_texts = formal_texts = 0
    for _s, t in texts:
        a, b = len(informal_rx.findall(t.lower())), len(formal_rx.findall(t))
        if a > b:
            informal_texts += 1
        elif b > a:
            formal_texts += 1
    if informal_texts + formal_texts == 0:
        anrede = "nicht erkennbar (kaum direkte Anrede)"
    elif formal_texts == 0:
        anrede = f"durchgehend informell (du/ihr) in {informal_texts} von {len(texts)} Texten"
    elif informal_texts == 0:
        anrede = f"durchgehend formell (Sie) in {formal_texts} von {len(texts)} Texten"
    else:
        anrede = (f"je nach Adressat: {informal_texts} Texte informell (du/ihr), {formal_texts} formell (Sie) — "
                  "Intern und Kunden unterscheiden sich vermutlich")
    sents = sentences(joined)
    avg = sum(len(s.split()) for s in sents) / len(sents) if sents else 0
    length = "kurze Sätze" if avg < 14 else "mittellange Sätze" if avg < 22 else "lange Sätze"
    excl = joined.count("!") / max(1, len(sents))
    emoji = len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", joined))
    lines = [ln for ln in joined.splitlines() if ln.strip()]
    bullets = sum(1 for ln in lines if re.match(r"^\s*([-*•]|\d+[.)])\s+", ln))
    paras = [p for p in re.split(r"\n\s*\n", joined) if p.strip()]
    pavg = sum(len(p.split()) for p in paras) / len(paras) if paras else 0
    ton = (f"Anrede: {anrede}; {length} (Ø {avg:.0f} Wörter); Ausrufezeichen in {100 * excl:.0f} % der Sätze"
           + ("; Emojis kommen vor" if emoji else "; keine Emojis"))
    out.append({"field": "stil.ton", "text": ton, "quote": f"{len(texts)} Texte, {words} Wörter gemessen", "source": "texte/", "locator": "Messung",
                "by": "script", "confidence": "medium"})
    fmt = f"Listen: {100 * bullets / max(1, len(lines)):.0f} % der Zeilen; Absätze Ø {pavg:.0f} Wörter ({'kompakt' if pavg < 45 else 'ausführlich'})"
    out.append({"field": "stil.format", "text": fmt, "quote": f"{len(paras)} Absätze, {len(lines)} Zeilen", "source": "texte/", "locator": "Messung",
                "by": "script", "confidence": "medium"})
    # Wiederkehrende Wendungen (Zweiwortfolgen ohne Füllwörter) und Grußformeln
    toks = [[w for w in re.findall(r"[a-zäöüß]{3,}", t.lower())] for _s, t in texts]
    grams: Counter[str] = Counter()
    per_text: dict[str, set[int]] = {}
    for i, ws in enumerate(toks):
        for a, b in zip(ws, ws[1:]):
            if a in STOP or b in STOP or a in MASKED or b in MASKED:
                continue
            g = f"{a} {b}"
            grams[g] += 1
            per_text.setdefault(g, set()).add(i)
    recurring = [g for g, c in grams.most_common(60) if c >= 3 and len(per_text[g]) >= 2 and g not in ("viele grüße", "viele gruesse")][:5]
    closers = Counter()
    for _s, t in texts:
        ls = [ln.strip() for ln in t.splitlines() if ln.strip()]
        if len(ls) >= 3 and len(ls[-1].split()) <= 4:
            closers[ls[-1]] += 1
        elif len(ls) >= 4 and len(ls[-2].split()) <= 4:
            closers[ls[-2]] += 1
    closer = next(((c, n) for c, n in closers.most_common(1) if n >= 2), None)
    dos = []
    if recurring:
        dos.append("wiederkehrende Wendungen: " + "; ".join(f"„{g}“" for g in recurring))
    if closer:
        dos.append(f"Schlussformel „{closer[0]}“ ({closer[1]} von {len(texts)} Texten)")
    if dos:
        out.append({"field": "stil.dos", "text": " · ".join(dos), "quote": f"aus {len(texts)} eigenen Texten gezählt", "source": "texte/", "locator": "Zählung",
                    "by": "script", "confidence": "low"})
    absent = [c for c in AI_CLICHES if c not in low]
    present = [c for c in AI_CLICHES if c in low]
    if len(absent) >= 10:
        out.append({"field": "stil.donts", "text": "In den eigenen Texten kommen typische KI-Floskeln nicht vor, zum Beispiel: "
                    + "; ".join(f"„{c}“" for c in absent[:6]) + (f". Kommen vor: {', '.join(present)}." if present else "."),
                    "quote": f"{len(absent)} von {len(AI_CLICHES)} Floskeln in {words} Wörtern nie gefunden", "source": "texte/", "locator": "Zählung",
                    "by": "script", "confidence": "low"})
    return out


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------

def collect(folder: Path) -> list[tuple[Path, str, str | None]]:
    files = []
    if not folder.is_dir():
        return files
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and not p.name.startswith(".") and p.name.lower() != "readme.md":
            hint = {"texte": "text", "transkripte": "transkript", "projekte": "projekt"}.get(p.relative_to(folder).parts[0] if len(p.relative_to(folder).parts) > 1 else "")
            files.append((p, read_text(p), hint))
    return files


def role_entries(folder: Path, project: Path, keep_names: bool) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out: list[dict[str, Any]] = []
    counts = {"text": 0, "transkript": 0, "projekt": 0}
    samples: list[tuple[str, str]] = []
    for p, raw, hint in collect(folder):
        kind = classify(p, raw, hint)
        counts[kind] += 1
        src = p.relative_to(project).as_posix() if project in p.parents else p.name
        if kind == "text":
            samples.append((src, raw))
        else:
            for e in talk_entries(p, raw, src, kind, keep_names):
                add_capped(out, e)
    if samples:
        out.extend(style_entries(samples, keep_names))
    return out, counts


def validate_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    ok, problems = [], []
    for i, e in enumerate(entries):
        if e.get("field") not in FIELD_KEYS:
            problems.append(f"Eintrag {i}: Feld {e.get('field')!r} unbekannt")
        elif not (e.get("quote") or "").strip() or not (e.get("source") or "").strip() or not (e.get("text") or "").strip():
            problems.append(f"Eintrag {i} ({e.get('field')}): ohne Zitat, Quelle oder Text — nicht übernommen")
        else:
            ok.append(e)
    return ok, problems


def write_doc(path: Path, scope: str, role: str | None, entries: list[dict[str, Any]], counts: dict[str, int] | None) -> None:
    wl.write_json(path, {"schema": SCHEMA, "scope": scope, "role": role, "sources": counts or {}, "entries": entries})


def render_md(docs: list[tuple[str, list[dict[str, Any]]]]) -> str:
    L = ["# Kontext-Vorschläge aus Dokumenten", "",
         "Vorschläge für Felder der Rollen.md, die der Arbeitsgraph nicht kennt. **Vorschläge, keine Tatsachen:** Jeder Eintrag nennt Quelle, Fundstelle und Zitat. "
         "In der Rollen.md stehen sie als „✎ Vorschlag aus Dokument — bitte bestätigen“, bis jemand die Datei bearbeitet.", ""]
    for title, entries in docs:
        L += [f"## {title}", ""]
        if not entries:
            L += ["Nichts gefunden.", ""]
            continue
        for key in FIELD_KEYS:
            es_ = [e for e in entries if e["field"] == key]
            if not es_:
                continue
            L += [f"### {FIELD_KEYS[key]}", ""]
            for e in es_:
                L.append(f"- {e['text']}  \n  _{e['source']}, {e['locator']}: „{e['quote']}“ ({e['by']}, Sicherheit {e.get('confidence', 'low')})_")
            L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--role", action="append", default=[], help="nur diese Rolle(n); sonst alle mit Ordner")
    ap.add_argument("--keep-names", action="store_true", help="Anreden mit Namen nicht maskieren")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    root = project / wl.DIR_INPUT / "kontext"
    if not root.is_dir():
        wl.fail(f"{wl.relpath(root)} fehlt. Lege Material dort ab (firma/, <rolle>/texte, <rolle>/transkripte, <rolle>/projekte); Details im Kopf dieses Skripts.")
    out_dir = project / wl.DIR_REVIEW / "kontext_evidenz"
    docs: list[tuple[str, list[dict[str, Any]]]] = []
    firma_files = [(p, t) for p, t, _h in collect(root / "firma")]
    if firma_files:
        fe = company_entries(firma_files, project, args.keep_names)
        write_doc(out_dir / "firma.json", "firma", None, fe, {"dokumente": len(firma_files)})
        docs.append(("Firmenprofil", fe))
    graph = wl.load_latest_graph(project)
    role_names = {es.slug(r["name"]): r["name"] for r in graph["roles"]} if graph else {}
    wanted = {es.slug(x) for x in args.role}
    for sub in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "firma"):
        if wanted and sub.name not in wanted:
            continue
        name = role_names.get(sub.name)
        if graph and name is None:
            print(f"HINWEIS  Ordner {sub.name!r} passt zu keiner Rolle des Graphen — übersprungen (Rollennamen: {', '.join(sorted(role_names))})")
            continue
        entries, counts = role_entries(sub, project, args.keep_names)
        write_doc(out_dir / f"{sub.name}.json", "rolle", name, entries, counts)
        docs.append((f"Rolle: {name or sub.name}", entries))
        print(f"Rolle {name or sub.name}: Texte={counts['text']} Transkripte={counts['transkript']} Projektdokumente={counts['projekt']} Vorschläge={len(entries)}")
    wl.write_text(out_dir / "kontext_evidenz.md", render_md(docs))
    print(f"Geschrieben: {wl.relpath(out_dir)} | Abschnitte={len(docs)} Vorschläge={sum(len(e) for _t, e in docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
