#!/usr/bin/env python3
"""
register_source.py — nimmt eine Quelle treu als Markdown in das Quellenregister des Projekts auf.

Aufruf:
    python3 <skill>/scripts/register_source.py --project ./mein-projekt --file 00_input/stellenbeschreibungen.md \
        --title "Stellenbeschreibungen Bereich X" [--origin "HR-Ablage/Stellen_2026.pdf"] [--original <pfad>] \
        [--kind document|interview|system_export|observation] [--language de] [--extractor human|claude|script] \
        [--status active|partial] [--date 2026-01-15] [--supersedes src-…]

Ergebnis:
    00_input/sources/src-<hash>-<slug>.md     Kopf mit Metadaten, darunter der Inhalt unverändert
    00_input/sources/register.jsonl           eine Zeile je Quelle (source_id, Titel, Herkunft, Hash, Datei)

Was das Register verspricht:
- Der Inhalt wird nicht verändert, nicht zusammengefasst, nicht übersetzt. Was nicht lesbar ist,
  bleibt weg und wird als `status: partial` kenntlich gemacht.
- Die source_id ist der Hash des Inhalts. Dieselben Bytes ergeben dieselbe ID; eine zweite
  Registrierung derselben Datei ist kein Fehler und erzeugt keinen zweiten Eintrag.
- Lesbar sind .md und .txt (verbatim) sowie .csv, .tsv und .json (als Codeblock). PDF, Word und
  Excel liest Claude und legt die treue Markdown-Fassung ab; die Originaldatei wird mit --original
  gehasht, aber nicht ins Projekt kopiert.
- Zugangsdaten stoppen die Aufnahme. Ein absoluter Pfad als Herkunft wird abgelehnt: Das Projekt
  muss auf jedem Rechner dasselbe bedeuten.

Belege im Graphen verweisen dann als "src-<hash>@<fundstelle>" auf diese Quelle; die Fundstelle ist
ein Überschriftenanker (#auftragssachbearbeiter-9-stellen), eine Zeile (L12) oder ein Bereich (L12-18).
locate_source.py zeigt die Anker und findet Zitate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

VERBATIM = {".md", ".markdown", ".txt"}
FENCED = {".csv": "csv", ".tsv": "tsv", ".json": "json"}
KINDS = ["document", "interview", "system_export", "observation", "reference"]
EXTRACTORS = ["human", "claude", "script"]


def slug(text: str) -> str:
    return (wl.normalize_name(text).replace(" ", "-")[:48].strip("-")) or "quelle"


def to_markdown(path: Path) -> tuple[str, str]:
    """(Markdown-Rumpf, Format). Verbatim oder als Codeblock; alles andere wird abgelehnt."""
    suffix = path.suffix.lower()
    if suffix in VERBATIM:
        return path.read_text(encoding="utf-8"), "markdown" if suffix != ".txt" else "text"
    if suffix in FENCED:
        raw = path.read_text(encoding="utf-8")
        fence = "```" if "```" not in raw else "````"
        return f"{fence}{FENCED[suffix]}\n{raw.rstrip(chr(10))}\n{fence}\n", FENCED[suffix]
    wl.fail(f"{path.name}: {suffix or 'ohne Endung'} kann dieses Skript nicht treu lesen. "
            "PDF, Word, Excel und Bilder liest Claude und legt die treue Markdown-Fassung als .md ab; "
            "dann diese Datei registrieren und mit --original auf die Ausgangsdatei zeigen.")
    return "", ""


def frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{k}: [" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]")
        elif v is None:
            lines.append(f"{k}: null")
        else:
            lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def register(project: Path, file: Path, title: str, origin: str | None, kind: str, language: str,
             extractor: str, status: str, when: str, original: Path | None, supersedes: str | None) -> dict:
    if not file.exists():
        wl.fail(f"Datei nicht gefunden: {wl.relpath(file)}")
    body, fmt = to_markdown(file)
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        wl.fail(f"{file.name}: leer, nichts zu registrieren")
    hits = wl.credential_findings(body)
    if hits:
        for n, k in hits:
            print(f"FEHLER   {file.name} Zeile {n}: sieht aus wie ein Zugangsdatum ({k})")
        wl.fail("Nicht registriert: Zugangsdaten gehören in keine Quelle. Entfernen, Schlüssel tauschen, erneut registrieren.")
    try:
        rel = file.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        rel = file.name
    origin = (origin or rel).strip()
    if not wl.portable_reference(origin):
        wl.fail(f"Herkunft {origin!r} ist kein portabler Verweis (kein absoluter Pfad, kein ~, kein ..). "
                "Einen relativen Namen, eine URL oder eine logische Bezeichnung angeben.")
    if supersedes and not wl.SOURCE_ID_RE.match(supersedes):
        wl.fail(f"--supersedes {supersedes!r} ist keine source_id")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    source_id = f"src-{sha[:12]}"
    register_path = wl.sources_dir(project) / wl.SOURCE_REGISTER
    existing = wl.load_source_register(project)
    if source_id in existing:
        rec = existing[source_id]
        print(f"Bereits registriert: {source_id} ({rec.get('title')}), Datei {rec.get('file')}. Nichts geändert.")
        return rec
    if supersedes and supersedes not in existing:
        wl.fail(f"--supersedes {supersedes}: nicht im Register")
    headings = wl.source_headings(body)
    meta = {
        "source_id": source_id, "title": title.strip(), "origin": origin, "kind": kind, "format": fmt,
        "language": language, "extractor": extractor, "status": status, "registered": when,
        "content_sha256": sha, "lines": len(body.splitlines()), "headings": len(headings),
    }
    if original is not None:
        if not original.exists():
            wl.fail(f"--original nicht gefunden: {wl.relpath(original)}")
        meta["original_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        meta["original_name"] = original.name
    if supersedes:
        meta["supersedes"] = supersedes
    out = wl.sources_dir(project) / f"{source_id}-{slug(title)}.md"
    wl.write_text(out, frontmatter(meta) + "\n" + body.rstrip("\n") + "\n")
    rec = dict(meta)
    rec["file"] = out.relative_to(project).as_posix()
    with open(register_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Registriert: {source_id} → {wl.relpath(out)} | {meta['lines']} Zeilen, {len(headings)} Überschriften")
    for n, _, text, anchor in headings[:12]:
        print(f"  {source_id}@#{anchor}   (Zeile {n}: {text})")
    if len(headings) > 12:
        print(f"  … {len(headings) - 12} weitere, siehe locate_source.py --source {source_id}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", required=True, help="zu registrierende Datei (.md, .txt, .csv, .tsv, .json)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--origin", default=None, help="portabler Verweis auf das Original (Standard: Pfad relativ zum Projekt)")
    ap.add_argument("--original", default=None, help="Ausgangsdatei, deren Hash festgehalten wird (nicht kopiert)")
    ap.add_argument("--kind", choices=KINDS, default="document")
    ap.add_argument("--language", default="de")
    ap.add_argument("--extractor", choices=EXTRACTORS, default="human")
    ap.add_argument("--status", choices=["active", "partial"], default="active")
    ap.add_argument("--date", default=None, help="Registrierungsdatum (Standard: heute)")
    ap.add_argument("--supersedes", default=None, help="source_id einer älteren Fassung")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    file = Path(args.file)
    if not file.is_absolute():
        file = Path.cwd() / file
    when = args.date or date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", when):
        wl.fail("--date im Format JJJJ-MM-TT")
    register(project, file, args.title, args.origin, args.kind, args.language, args.extractor, args.status, when,
             Path(args.original) if args.original else None, args.supersedes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
