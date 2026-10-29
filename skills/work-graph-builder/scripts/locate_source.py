#!/usr/bin/env python3
"""
locate_source.py — zeigt die Fundstellen einer registrierten Quelle und findet Zitate.

Aufruf:
    python3 <skill>/scripts/locate_source.py --project ./mein-projekt                      alle Quellen
    python3 <skill>/scripts/locate_source.py --project ./mein-projekt --source src-…       Anker und Zeilen
    python3 <skill>/scripts/locate_source.py --project ./mein-projekt --source src-… --find "Zeitanteile"
    python3 <skill>/scripts/locate_source.py --project ./mein-projekt --check "src-…@#anker"

Ein Beleg hat die Form src-<hash>@<fundstelle>. Die Fundstelle ist ein Überschriftenanker (#…),
eine Zeile (L12), ein Bereich (L12-18) oder Freitext (Seite, Folie). Anker und Zeilen prüft
dieses Skript; Freitext nicht.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def source_body(project: Path, rec: dict) -> str:
    path = project / rec["file"]
    if not path.exists():
        wl.fail(f"Quelle {rec['source_id']} fehlt: {rec['file']}")
    _, body = wl.split_frontmatter(path.read_text(encoding="utf-8"))
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--source", default=None)
    ap.add_argument("--find", default=None, help="Textstück; gibt passende Zeilen als Beleg aus")
    ap.add_argument("--check", default=None, help="einen Beleg src-…@… prüfen")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    reg = wl.load_source_register(project)
    if not reg:
        print("Kein Quellenregister. Quellen mit register_source.py aufnehmen.")
        return 3
    if args.check:
        ev = wl.parse_evidence(args.check)
        if not ev:
            wl.fail(f"{args.check!r} hat nicht die Form src-<hash>@<fundstelle>")
        sid, loc = ev
        if sid not in reg:
            wl.fail(f"{sid} nicht im Register")
        ok, note = wl.resolve_locator(source_body(project, reg[sid]), loc)
        print(("OK       " if ok else "FEHLER   ") + args.check + (f"  ({note})" if note else ""))
        return 0 if ok else 2
    if not args.source:
        print(f"{len(reg)} Quelle(n):")
        for sid, rec in sorted(reg.items()):
            print(f"  {sid}  {rec.get('title')}  [{rec.get('kind')}, {rec.get('lines')} Zeilen, {rec.get('status')}]")
        return 0
    rec = reg.get(args.source)
    if not rec:
        wl.fail(f"{args.source} nicht im Register")
    body = source_body(project, rec)
    if args.find:
        needle = wl.normalize_name(args.find)
        hits = [(n, line) for n, line in enumerate(body.splitlines(), start=1) if needle and needle in wl.normalize_name(line)]
        if not hits:
            print(f"Nicht gefunden: {args.find!r} in {args.source}")
            return 1
        heads = wl.source_headings(body)
        for n, line in hits:
            section = max((h for h in heads if h[0] <= n), key=lambda h: h[0], default=None)
            anchor = f"  (Abschnitt {args.source}@#{section[3]})" if section else ""
            print(f"{args.source}@L{n}{anchor}\n    {line.strip()[:160]}")
        return 0
    print(f"{args.source}: {rec.get('title')} ({rec.get('lines')} Zeilen)")
    for n, level, text, anchor in wl.source_headings(body):
        print(f"  {'#' * level} {text}\n      {args.source}@#{anchor}   (Zeile {n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
