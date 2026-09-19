#!/usr/bin/env python3
"""
pack_skills.py — baut die .skill-Pakete in dist/ aus den Skill-Ordnern.

check_suite.py vergleicht jedes Paket Datei für Datei mit dem Skill-Ordner. Damit
ein Paket nach einer Codeänderung nicht veraltet, wird es hier neu gebaut — und
zwar deterministisch: feste Dateireihenfolge, fester Zeitstempel, feste Rechte.
Zweimal packen ergibt byteidentische Dateien, sodass dist/ nur dann im Diff
auftaucht, wenn sich der Inhalt eines Skills wirklich geändert hat.

Aufruf (aus dem Repository-Wurzelverzeichnis):
    python3 tools/pack_skills.py [--check]
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
DIST = ROOT / "dist"
IGNORE_PARTS = ("__pycache__", ".DS_Store", ".pytest_cache")
# Fester Zeitstempel (1980-01-01), der kleinste, den das ZIP-Format kennt.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def files_of(skill_dir: Path) -> list[Path]:
    return sorted(
        (p for p in skill_dir.rglob("*")
         if p.is_file() and not any(part in IGNORE_PARTS for part in p.parts)),
        key=lambda p: p.relative_to(skill_dir).as_posix(),
    )


def build(skill_dir: Path) -> bytes:
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files_of(skill_dir):
            arcname = f"{skill_dir.name}/{f.relative_to(skill_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="nur melden, nichts schreiben")
    args = ap.parse_args()
    DIST.mkdir(exist_ok=True)
    stale = 0
    for skill_dir in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").exists()):
        package = DIST / f"{skill_dir.name}.skill"
        data = build(skill_dir)
        if package.exists() and package.read_bytes() == data:
            continue
        stale += 1
        if args.check:
            print(f"VERALTET dist/{package.name}")
        else:
            package.write_bytes(data)
            print(f"gebaut   dist/{package.name} ({len(data)} Bytes)")
    known = {f"{p.name}.skill" for p in SKILLS.iterdir() if (p / "SKILL.md").exists()}
    for old in sorted(DIST.glob("*.skill")):
        if old.name not in known:
            stale += 1
            if args.check:
                print(f"ÜBERZÄHLIG dist/{old.name}")
            else:
                old.unlink()
                print(f"entfernt dist/{old.name}")
    if args.check:
        print("Pakete aktuell" if not stale else f"{stale} Paket(e) veraltet")
        return 1 if stale else 0
    print("Pakete aktuell" if not stale else f"{stale} Paket(e) neu gebaut")
    return 0


if __name__ == "__main__":
    sys.exit(main())
