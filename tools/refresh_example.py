#!/usr/bin/env python3
"""
refresh_example.py — erzeugt den erwarteten Stand des Referenzbeispiels neu.

Aufruf (aus dem Repository-Wurzelverzeichnis):
    python3 tools/refresh_example.py [--example examples/order-to-cash] [--check]

Der End-to-End-Test vergleicht einen frischen Lauf des Beispielprojekts mit
`expected/`. Wenn sich das Ergebnis absichtlich ändert — neue Regel, korrigierte
Rechnung, erweitertes Schema —, schreibt dieses Werkzeug den Vergleichsstand neu.

Der Lauf findet in einem temporären Ordner statt, damit das eingecheckte Beispiel
sauber bleibt (es enthält nur Eingabedateien, keine erzeugten Stände).

Mit --check wird nur geprüft, ob der hinterlegte Stand noch stimmt; geschrieben wird
nichts. Exit-Code 1 bedeutet: er stimmt nicht mehr.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "work-transformation" / "scripts"))
import workgraph_lib as wl  # noqa: E402

PIPELINE = ROOT / "skills" / "work-transformation" / "scripts" / "run_pipeline.py"
READABLE_PREFIXES = ("report_v", "scenarios_v", "contracts_v")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_example(example: Path, workdir: Path) -> Path:
    project = workdir / example.name
    shutil.copytree(example, project)
    shutil.rmtree(project / "expected", ignore_errors=True)
    result = subprocess.run([sys.executable, str(PIPELINE), "--project", str(project)],
                            cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        wl.fail(f"Pipeline beendet mit Code {result.returncode}")
    return project


def build_manifest(project: Path, graph: dict) -> dict:
    manifest = {
        "description": "Erwartete Ausgaben eines vollständigen Laufs dieses Beispielprojekts. "
                       "Die Prüfsummen belegen, dass die Pipeline deterministisch ist: gleiche "
                       "Eingaben, gleiche Bytes. Ein Unterschied hier ist entweder ein Fehler "
                       "oder eine bewusste Änderung, die mit aktualisierten Prüfsummen "
                       "festgehalten wird.",
        "graph_version": graph["meta"]["version"],
        "schema_version": graph["meta"]["schema_version"],
        "counts": {c: len(graph.get(c, [])) for c in wl.COLLECTIONS if graph.get(c)},
        "files": {},
    }
    for path in sorted((project / wl.DIR_OUTPUT).rglob("*")):
        if path.is_file():
            manifest["files"][path.relative_to(project).as_posix()] = sha(path)
    latest = project / wl.DIR_GRAPH / wl.LATEST_GRAPH
    manifest["files"][latest.relative_to(project).as_posix()] = sha(latest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--example", default="examples/order-to-cash")
    ap.add_argument("--check", action="store_true", help="nur vergleichen, nichts schreiben")
    args = ap.parse_args()
    example = (ROOT / args.example).resolve()
    if not (example / "project.json").exists():
        wl.fail(f"Kein Projekt unter {args.example}")
    expected = example / "expected"

    tmp = Path(tempfile.mkdtemp(prefix="wts-refresh-"))
    try:
        project = run_example(example, tmp)
        graph = wl.read_json(project / wl.DIR_GRAPH / wl.LATEST_GRAPH)
        manifest = build_manifest(project, graph)

        if args.check:
            if not (expected / "manifest.json").exists():
                print("Kein hinterlegter Stand vorhanden")
                return 1
            old = wl.read_json(expected / "manifest.json")
            drift = [k for k in sorted(set(old["files"]) | set(manifest["files"]))
                     if old["files"].get(k) != manifest["files"].get(k)]
            if drift or old.get("counts") != manifest["counts"]:
                for k in drift:
                    print(f"ABWEICHUNG {k}")
                if old.get("counts") != manifest["counts"]:
                    print(f"ABWEICHUNG counts: {old.get('counts')} -> {manifest['counts']}")
                return 1
            print(f"Hinterlegter Stand stimmt ({len(manifest['files'])} Dateien, "
                  f"Graph-Version {manifest['graph_version']})")
            return 0

        expected.mkdir(parents=True, exist_ok=True)
        for old in expected.glob("*"):
            if old.is_file():
                old.unlink()
        wl.write_json(expected / "work-graph_final.json", graph)
        wl.write_json(expected / "manifest.json", manifest)
        for path in sorted((project / wl.DIR_OUTPUT).glob("*.md")):
            if path.name.startswith(READABLE_PREFIXES):
                shutil.copy(path, expected / path.name)
        print(f"Geschrieben: {expected.relative_to(ROOT)} | Graph-Version "
              f"{manifest['graph_version']}, {len(manifest['files'])} Prüfsummen")
        print("Bitte im Commit begründen, warum sich das Ergebnis ändert.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
