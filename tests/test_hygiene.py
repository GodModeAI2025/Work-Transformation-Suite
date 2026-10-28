"""Was nirgends im Repository stehen darf.

Die Namen unten werden aus Teilen zusammengesetzt, damit diese Datei sich nicht selbst findet.
Geprüft werden alle versionierten Textdateien und der Inhalt der .skill-Pakete.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import ROOT  # noqa: E402

FORBIDDEN = [re.compile(p, re.IGNORECASE) for p in (
    "co" + r"[\s\-_]?" + "brain", "con" + "brain", "ko" + r"[\s\-_]?" + "brain",
    # Quelle des Rollen-Setups: weder Sendung noch Person noch Dateiname der Vorlage werden genannt.
    "ai" + r"[\s\-_]?" + "first" + r"\b", "pod" + "cast", "schlen" + "ther", "fel" + "ix" + r"\s+schl", "inst" + "inct")]


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True)
    if out.returncode != 0:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [ROOT / line for line in out.stdout.splitlines() if (ROOT / line).is_file()]


class TestNothingForbidden(unittest.TestCase):
    def test_no_forbidden_name_in_text_files(self):
        hits = []
        for p in tracked_files():
            if p.suffix in (".skill", ".png", ".jpg", ".ico", ".zip"):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pat in FORBIDDEN:
                if pat.search(text) or pat.search(p.name):
                    hits.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(hits, [])

    def test_no_forbidden_name_inside_skill_packages(self):
        hits = []
        for pkg in sorted((ROOT / "dist").glob("*.skill")):
            with zipfile.ZipFile(pkg) as z:
                for info in z.infolist():
                    data = z.read(info).decode("utf-8", errors="ignore") + info.filename
                    if any(pat.search(data) for pat in FORBIDDEN):
                        hits.append(f"{pkg.name}:{info.filename}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
