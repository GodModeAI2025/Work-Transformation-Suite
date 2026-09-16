#!/usr/bin/env python3
"""
check_suite.py — prüft die Installation der Suite: sind alle vier Skills da,
sind die gemeinsamen Bibliotheksdateien in allen Kopien identisch, läuft Python 3.9+,
ist der Frontmatter jeder SKILL.md gültig (name = Ordnername ohne „anthropic“/„claude“,
description höchstens 1024 Zeichen; so verlangt es die Skill-Spezifikation von Anthropic). Liegt neben dem Skill-Ordner ein
Ordner dist/ (so im Repository), wird zusätzlich geprüft, dass jedes .skill-Paket
denselben Inhalt hat wie der Skill-Ordner.

Aufruf:
    python3 <skill>/scripts/check_suite.py [--skills ../] [--dist ../../dist]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

SHARED = {
    "workgraph_lib.py": ["work-graph-builder", "task-scorer", "agent-mapper", "transformation-dashboard", "work-transformation"],
    "validate_graph.py": ["work-graph-builder", "task-scorer", "agent-mapper", "transformation-dashboard"],
    "apply_overrides.py": ["work-graph-builder", "task-scorer"],
}
REQUIRED = {
    "work-graph-builder": ["init_project.py", "build_graph.py", "make_review_list.py", "apply_overrides.py", "validate_graph.py", "import_positions.py"],
    "task-scorer": ["export_scoring_sheet.py", "score_roles.py", "calibrate.py"],
    "agent-mapper": ["export_agent_candidates.py", "compute_coverage.py"],
    "transformation-dashboard": ["build_dashboard.py"],
    "work-transformation": ["run_pipeline.py", "check_suite.py"],
}

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
RESERVED = ("anthropic", "claude")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def frontmatter(text: str) -> dict[str, str] | None:
    """Liest die flachen Schlüssel name/description aus dem YAML-Kopf, ohne PyYAML."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            value = m.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            meta[m.group(1)] = value
    return None


def check_frontmatter(skill_dir: Path) -> list[str]:
    name = skill_dir.name
    meta = frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    if meta is None:
        return [f"{name}/SKILL.md: kein gültiger Frontmatter-Block (--- … ---)"]
    errors = []
    if meta.get("name") != name:
        errors.append(f"{name}/SKILL.md: name '{meta.get('name')}' passt nicht zum Ordnernamen")
    elif len(name) > MAX_NAME or not NAME_RE.match(name):
        errors.append(f"{name}/SKILL.md: name nur Kleinbuchstaben, Ziffern, Bindestriche, höchstens {MAX_NAME} Zeichen")
    elif any(word in name for word in RESERVED):
        errors.append(f"{name}/SKILL.md: name darf 'anthropic' und 'claude' nicht enthalten")
    desc = meta.get("description", "")
    if not desc:
        errors.append(f"{name}/SKILL.md: description fehlt")
    elif len(desc) > MAX_DESCRIPTION:
        errors.append(f"{name}/SKILL.md: description hat {len(desc)} Zeichen, erlaubt sind {MAX_DESCRIPTION}")
    return errors


def check_package(package: Path, skill_dir: Path) -> list[str]:
    """Vergleicht Dateiliste und Inhalte eines .skill-Pakets (ZIP) mit dem Skill-Ordner."""
    name = skill_dir.name
    ignore = ("__pycache__", ".DS_Store")
    on_disk = {
        p.relative_to(skill_dir.parent).as_posix(): p.read_bytes()
        for p in sorted(skill_dir.rglob("*"))
        if p.is_file() and not any(part in ignore for part in p.parts)
    }
    try:
        with zipfile.ZipFile(package) as z:
            packed = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    except zipfile.BadZipFile:
        return [f"dist/{package.name}: kein gültiges ZIP"]
    errors = []
    for f in sorted(set(on_disk) - set(packed)):
        errors.append(f"dist/{package.name}: {f} fehlt im Paket")
    for f in sorted(set(packed) - set(on_disk)):
        errors.append(f"dist/{package.name}: {f} gibt es im Skill-Ordner nicht (mehr)")
    for f in sorted(set(on_disk) & set(packed)):
        if on_disk[f] != packed[f]:
            errors.append(f"dist/{package.name}: {f} ist veraltet")
    if errors:
        errors.append(f"dist/{package.name}: Paket neu bauen (Ordner {name}/ als ZIP)")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", default=None)
    ap.add_argument("--dist", default=None, help="Ordner mit .skill-Paketen (Standard: dist/ neben dem Skill-Ordner, falls vorhanden)")
    args = ap.parse_args()
    here = Path(__file__).resolve().parent.parent
    skills = Path(args.skills).resolve() if args.skills else here.parent
    dist = Path(args.dist).resolve() if args.dist else skills.parent / "dist"
    ok = True
    if sys.version_info < (3, 9):
        print(f"FEHLER   Python {sys.version.split()[0]} zu alt, mindestens 3.9")
        ok = False
    for skill, files in REQUIRED.items():
        d = skills / skill
        if not (d / "SKILL.md").exists():
            print(f"FEHLER   Skill fehlt: {skill} (erwartet unter {d})")
            ok = False
            continue
        for f in files:
            if not (d / "scripts" / f).exists():
                print(f"FEHLER   {skill}/scripts/{f} fehlt")
                ok = False
        for e in check_frontmatter(d):
            print(f"FEHLER   {e}")
            ok = False
    for f, owners in SHARED.items():
        hashes = {}
        for s in owners:
            p = skills / s / "scripts" / f
            if p.exists():
                hashes[s] = sha(p)
        if len(set(hashes.values())) > 1:
            print(f"FEHLER   {f} unterscheidet sich zwischen Skills: {hashes}")
            ok = False
    if args.dist and not dist.is_dir():
        print(f"FEHLER   dist-Ordner nicht gefunden: {dist}")
        ok = False
    elif dist.is_dir():
        for skill in REQUIRED:
            package = dist / f"{skill}.skill"
            if not package.exists():
                print(f"FEHLER   dist/{skill}.skill fehlt")
                ok = False
            elif (skills / skill).is_dir():
                for e in check_package(package, skills / skill):
                    print(f"FEHLER   {e}")
                    ok = False
    print("Suite OK" if ok else "Suite unvollständig")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
