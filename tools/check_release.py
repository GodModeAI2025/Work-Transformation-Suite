#!/usr/bin/env python3
"""
check_release.py — prüft, ob ein Stand als Release taugt.

Aufruf (aus dem Repository-Wurzelverzeichnis):
    python3 tools/check_release.py [--tag v0.2.0] [--checksums dist/SHA256SUMS]

Ohne --tag wird die Version aus .claude-plugin/plugin.json genommen.

Geprüft wird dreierlei, weil genau das erfahrungsgemäß auseinanderläuft:
1. Die Version im Plugin-Manifest passt zum Tag (semantische Version, ohne führendes v).
2. Die CHANGELOG.md hat einen Abschnitt für diese Version.
3. Die .skill-Pakete in dist/ entsprechen dem Stand der Skill-Ordner.

Mit --checksums wird zusätzlich eine SHA256SUMS-Datei über die Pakete geschrieben. Sie
macht nachprüfbar, dass ein heruntergeladenes Paket dem Stand des Tags entspricht — bei
Dateien, die Menschen per Drag-and-drop in einen Chat ziehen, ist das der einzige Beleg.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
CHANGELOG = ROOT / "CHANGELOG.md"
DIST = ROOT / "dist"
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None, help="Git-Tag, z. B. v0.2.0")
    ap.add_argument("--checksums", default=None, help="Pfad für die SHA256SUMS-Datei")
    args = ap.parse_args()

    problems: list = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()

    if not version:
        problems.append(".claude-plugin/plugin.json: Feld 'version' fehlt")
    elif not SEMVER.match(version):
        problems.append(f".claude-plugin/plugin.json: version {version!r} ist keine "
                        "semantische Version (MAJOR.MINOR.PATCH)")

    if args.tag:
        expected = args.tag[1:] if args.tag.startswith("v") else args.tag
        if expected != version:
            problems.append(f"Tag {args.tag} und plugin.json version {version!r} passen nicht "
                            "zusammen")

    if not CHANGELOG.exists():
        problems.append("CHANGELOG.md fehlt")
    else:
        text = CHANGELOG.read_text(encoding="utf-8")
        if f"[{version}]" not in text:
            problems.append(f"CHANGELOG.md hat keinen Abschnitt '[{version}]' — ein Release "
                            "ohne Eintrag ist für niemanden nachvollziehbar")

    packages = sorted(DIST.glob("*.skill"))
    skills = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())
    packaged = sorted(p.stem for p in packages)
    if packaged != skills:
        problems.append(f"dist/ passt nicht zu skills/: Pakete {packaged}, Skills {skills}")

    for line in problems:
        print(f"FEHLER   {line}")
    if problems:
        print("Nicht releasefähig")
        return 2

    digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in packages}
    if args.checksums:
        out = Path(args.checksums)
        out.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f"{d}  {name}\n" for name, d in sorted(digests.items()))
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(f"Geschrieben: {out.relative_to(ROOT)} ({len(digests)} Pakete)")
    print(f"Releasefähig: Version {version}, {len(digests)} Pakete, CHANGELOG-Eintrag vorhanden")
    for name, d in sorted(digests.items()):
        print(f"  {d[:16]}…  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
