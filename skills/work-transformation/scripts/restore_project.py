#!/usr/bin/env python3
"""
restore_project.py — stellt einen Snapshot wieder her.

Aufruf:
    python3 <skill>/scripts/restore_project.py --project ./mein-projekt --snapshot <ordnername> [--dry-run]

Bevor etwas überschrieben wird, entsteht ein Snapshot des jetzigen Stands („vor-restore“). Dann
werden die Dateien des gewählten Snapshots zurückkopiert; Dateien, die es heute gibt, im Snapshot
aber nicht, werden entfernt, sofern sie zum Stand gehören (00_input, 10_extraction, 20_graph ohne
alte Versionen, 30_review). Alte Graph-Versionen und 40_output bleiben unberührt; danach einmal
run_pipeline.py, damit die Ausgaben wieder zum Stand passen.

--dry-run zeigt nur, was sich ändern würde.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import snapshot_project as sp  # noqa: E402


def plan(project: Path, snap: Path) -> tuple[list[str], list[str], list[str]]:
    """(zu schreiben, zu entfernen, unverändert)."""
    manifest = wl.read_json(snap / "manifest.json")["files"]
    current = wl.manifest_of(project, wl.controlled_files(project))
    write = [rel for rel, h in manifest.items() if current.get(rel) != h]
    remove = [rel for rel in current if rel not in manifest]
    same = [rel for rel in manifest if current.get(rel) == manifest[rel]]
    return sorted(write), sorted(remove), sorted(same)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--snapshot", required=True, help="Ordnername unter 50_snapshots/")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    snap = sp.snapshot_dir(project) / args.snapshot
    if not (snap / "manifest.json").exists():
        wl.fail(f"Snapshot nicht gefunden: {args.snapshot} (snapshot_project.py --list)")
    for rel, h in wl.read_json(snap / "manifest.json")["files"].items():
        if not (snap / rel).exists() or wl.sha256_file(snap / rel) != h:
            wl.fail(f"Snapshot beschädigt: {rel} fehlt oder passt nicht zum Manifest")
    write, remove, same = plan(project, snap)
    print(f"Wiederherstellen aus {args.snapshot}: {len(write)} schreiben, {len(remove)} entfernen, {len(same)} unverändert")
    for rel in write:
        print(f"  schreiben  {rel}")
    for rel in remove:
        print(f"  entfernen  {rel}")
    if args.dry_run:
        return 0
    if not write and not remove:
        print("Nichts zu tun.")
        return 0
    safety, _ = sp.create(project, "vor-restore")
    print(f"Sicherung des jetzigen Stands: {wl.relpath(safety)}")
    for rel in write:
        dst = project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snap / rel, dst)
    for rel in remove:
        (project / rel).unlink()
    print("Wiederhergestellt. Jetzt run_pipeline.py, damit 40_output/ wieder zum Stand passt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
