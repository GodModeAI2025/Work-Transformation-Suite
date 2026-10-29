#!/usr/bin/env python3
"""
verify_release.py — prüft, ob der Projektordner noch dem Freigabestand entspricht.

Aufruf:
    python3 <skill>/scripts/verify_release.py --project ./mein-projekt [--version 1.0.0]

Ohne --version gilt der letzte Freigabestand. Geprüft wird jede Datei des Manifests (verändert,
fehlt) und ob Dateien hinzugekommen sind, die zum Stand gehören würden. Außerdem muss die Kette in
releases.jsonl geschlossen sein: jeder Eintrag nennt den Manifest-Hash seines Vorgängers, und das
Manifest jedes Eintrags ergibt den eingetragenen Hash.

Exit-Code 0: entspricht dem Stand. 1: Abweichungen (werden einzeln genannt). 2: kein Stand oder Kette gebrochen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import release_project as rp  # noqa: E402


def check_chain(project: Path, log: list[dict]) -> list[str]:
    problems = []
    prev = None
    for e in log:
        m = project / wl.DIR_RELEASES / e["version"] / "manifest.json"
        if not m.exists():
            problems.append(f"{e['version']}: manifest.json fehlt")
        else:
            data = wl.read_json(m)
            if rp.manifest_hash(data.get("files", {})) != e.get("manifest_sha256"):
                problems.append(f"{e['version']}: Manifest passt nicht zum Hash in releases.jsonl")
        if e.get("previous_manifest_sha256") != prev:
            problems.append(f"{e['version']}: Vorgänger-Hash passt nicht zur Kette")
        prev = e.get("manifest_sha256")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    log = rp.read_log(project)
    if not log:
        print("Kein Freigabestand (release_project.py).")
        return 2
    chain = check_chain(project, log)
    for p in chain:
        print(f"FEHLER   Kette: {p}")
    if chain:
        return 2
    entry = next((e for e in log if e["version"] == args.version), log[-1]) if args.version else log[-1]
    if args.version and entry["version"] != args.version:
        wl.fail(f"Version {args.version} nicht in releases.jsonl")
    manifest = wl.read_json(project / wl.DIR_RELEASES / entry["version"] / "manifest.json")["files"]
    current_files = wl.controlled_files(project, with_output=True)
    changed, missing = [], []
    for rel, h in manifest.items():
        p = project / rel
        if not p.exists():
            missing.append(rel)
        elif wl.sha256_file(p) != h:
            changed.append(rel)
    added = [rel for rel in current_files if rel not in manifest]
    for rel in changed:
        print(f"VERÄNDERT {rel}")
    for rel in missing:
        print(f"FEHLT     {rel}")
    for rel in added:
        print(f"NEU       {rel}")
    drift = len(changed) + len(missing) + len(added)
    print(f"Freigabestand {entry['version']} ({entry['created']}): {len(manifest)} Dateien geprüft, "
          f"verändert={len(changed)} fehlt={len(missing)} neu={len(added)}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
