#!/usr/bin/env python3
"""
release_project.py — friert einen geprüften Stand als Freigabestand ein.

Aufruf:
    python3 <skill>/scripts/release_project.py --project ./mein-projekt --version 1.0.0 [--note "…"] [--date 2026-03-01]

Ein Freigabestand ist kein zweiter Ordner, sondern ein Manifest: 60_releases/<version>/manifest.json
hält den Hash jeder Datei des Stands fest (Eingaben, Extraktionen, Graph, Review, Ausgaben), und
60_releases/releases.jsonl bekommt eine unveränderliche Zeile mit Version, Datum, Graph-Version,
Manifest-Hash und dem Manifest-Hash des Vorgängers. So lässt sich später beweisen, dass ein
weitergegebener Ordner dem freigegebenen Stand entspricht, und ob er sich seitdem verändert hat
(verify_release.py).

Vorbedingungen, ohne die kein Stand entsteht:
- der Validator meldet keinen Fehler;
- bei Belegpflicht strict ist nichts unbelegt;
- niemand anderes hält einen gültigen Pflegeanspruch;
- die Version ist höher als die letzte;
- 40_output/ existiert (vorher run_pipeline.py).
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
import project_lock as pl  # noqa: E402

# validate_graph liegt im Builder; der Orchestrator kennt die Geschwister-Skills über --skills,
# hier reicht die Nachbarschaft im Repository oder im Installationsordner.
_builder = Path(__file__).resolve().parent.parent.parent / "work-graph-builder" / "scripts"
if _builder.is_dir():
    sys.path.insert(0, str(_builder))


def version_tuple(v: str) -> tuple[int, int, int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v or "")
    if not m:
        wl.fail(f"Version {v!r}: erwartet X.Y.Z")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def read_log(project: Path) -> list[dict]:
    p = project / wl.DIR_RELEASES / wl.RELEASE_LOG
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_hash(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def preflight(project: Path) -> list[str]:
    problems = []
    graph = wl.load_latest_graph(project)
    if not graph:
        return ["kein Graph"]
    try:
        import validate_graph  # noqa: WPS433
        strict = wl.evidence_policy(project) == "strict"
        errors, _ = validate_graph.validate(graph, strict_evidence=strict)
        problems += [f"Validator: {e}" for e in errors[:10]]
        if len(errors) > 10:
            problems.append(f"Validator: … {len(errors) - 10} weitere Fehler")
    except ImportError:
        problems.append("validate_graph.py nicht gefunden (Skill work-graph-builder neben diesem Skill?)")
    if not (project / wl.DIR_OUTPUT).is_dir():
        problems.append("40_output/ fehlt: erst run_pipeline.py")
    holders = pl.foreign_holders(project)
    for c in holders:
        problems.append(f"Pflegeanspruch: {pl.describe(c)}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    vt = version_tuple(args.version)
    when = args.date or date.today().isoformat()
    log = read_log(project)
    if log:
        last = log[-1]
        if version_tuple(last["version"]) >= vt:
            wl.fail(f"Version {args.version} ist nicht höher als die letzte ({last['version']})")
    problems = preflight(project)
    if problems:
        for p in problems:
            print(f"FEHLER   {p}")
        wl.fail("Kein Freigabestand: erst die Punkte oben klären")
    rel_dir = project / wl.DIR_RELEASES / args.version
    if rel_dir.exists():
        wl.fail(f"{wl.relpath(rel_dir)} existiert schon")
    # Die Versionsnummer gehört zum Stand und wird deshalb vor dem Hashen in project.json geschrieben;
    # sonst wäre der Stand im Moment seiner Freigabe schon „verändert“.
    meta = wl.load_project_meta(project)
    meta["release_version"] = args.version
    wl.save_project_meta(project, meta)
    files = wl.controlled_files(project, with_output=True)
    manifest = wl.manifest_of(project, files)
    mh = manifest_hash(manifest)
    wl.write_json(rel_dir / "manifest.json", {"version": args.version, "created": when, "note": args.note,
                                              "graph_version": meta.get("graph_version", 0),
                                              "schema_version": wl.SCHEMA_VERSION, "manifest_sha256": mh,
                                              "files": manifest})
    entry = {"version": args.version, "created": when, "note": args.note, "graph_version": meta.get("graph_version", 0),
             "file_count": len(files), "manifest_sha256": mh,
             "previous_manifest_sha256": log[-1]["manifest_sha256"] if log else None}
    with open(project / wl.DIR_RELEASES / wl.RELEASE_LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Freigabestand {args.version}: {len(files)} Dateien, Graph-Version {entry['graph_version']}, "
          f"Manifest {mh[:12]}… | {wl.relpath(rel_dir / 'manifest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
