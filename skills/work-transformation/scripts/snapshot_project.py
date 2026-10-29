#!/usr/bin/env python3
"""
snapshot_project.py — legt einen Wiederherstellungspunkt des Projekts an.

Aufruf:
    python3 <skill>/scripts/snapshot_project.py --project ./mein-projekt [--label "vor Review"] [--id 20260301-120000]
    python3 <skill>/scripts/snapshot_project.py --project ./mein-projekt --list

Ein Snapshot kopiert alles, was Menschen oder Claude geschrieben haben, plus den aktuellen Graphen
nach 50_snapshots/<id>[-<label>]/ und schreibt ein manifest.json mit dem Hash jeder Datei.
Erzeugte Ausgaben (40_output) gehören nicht hinein: Sie entstehen aus dem Snapshot neu.
Ältere Graph-Versionen (work-graph_vNNN_*.json) ebenfalls nicht; sie sind Geschichte, nicht Stand.

restore_project.py stellt einen Snapshot wieder her und legt davor selbst einen an.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def snapshot_dir(project: Path) -> Path:
    return project / wl.DIR_SNAPSHOTS


def list_snapshots(project: Path) -> list[dict]:
    out = []
    base = snapshot_dir(project)
    if not base.is_dir():
        return out
    for d in sorted(base.iterdir()):
        m = d / "manifest.json"
        if d.is_dir() and m.exists():
            rec = wl.read_json(m)
            rec["dir"] = d.name
            out.append(rec)
    return out


def create(project: Path, label: str = "", snap_id: str | None = None) -> tuple[Path, dict]:
    files = wl.controlled_files(project)
    if not files:
        wl.fail(f"Nichts zu sichern unter {wl.relpath(project)}")
    snap_id = snap_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if not re.match(r"^\d{8}-\d{6}$", snap_id):
        wl.fail("--id im Format JJJJMMTT-HHMMSS")
    slug = wl.normalize_name(label).replace(" ", "-")[:40]
    name = f"{snap_id}-{slug}" if slug else snap_id
    target = snapshot_dir(project) / name
    if target.exists():
        wl.fail(f"Snapshot {name} existiert schon")
    manifest = wl.manifest_of(project, files)
    for rel in files:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / rel, dst)
    meta = wl.load_project_meta(project)
    rec = {"id": snap_id, "label": label, "created": snap_id, "graph_version": meta.get("graph_version", 0),
           "files": manifest, "file_count": len(files)}
    wl.write_json(target / "manifest.json", rec)
    return target, rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--id", default=None, help="feste Kennung (Standard: UTC-Zeitstempel)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    if args.list:
        snaps = list_snapshots(project)
        if not snaps:
            print("Keine Snapshots.")
            return 0
        for s in snaps:
            print(f"  {s['dir']}  Graph-Version {s.get('graph_version')}, {s.get('file_count')} Dateien"
                  + (f", {s['label']}" if s.get("label") else ""))
        return 0
    target, rec = create(project, args.label, args.id)
    print(f"Snapshot: {wl.relpath(target)} | {rec['file_count']} Dateien, Graph-Version {rec['graph_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
