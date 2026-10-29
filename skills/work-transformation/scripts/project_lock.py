#!/usr/bin/env python3
"""
project_lock.py — Pflege-Lock: wer arbeitet gerade an diesem Projekt?

Aufruf:
    python3 <skill>/scripts/project_lock.py acquire   --project P --owner <name> --operation "<was>" --token-file <datei außerhalb des Projekts>
    python3 <skill>/scripts/project_lock.py verify    --project P --token-file <datei>
    python3 <skill>/scripts/project_lock.py heartbeat --project P --token-file <datei>
    python3 <skill>/scripts/project_lock.py release   --project P --token-file <datei> [--remove-token-file]
    python3 <skill>/scripts/project_lock.py withdraw  --project P --owner <name> --reason "<warum>"
    python3 <skill>/scripts/project_lock.py status    --project P

Ein Projektordner kann auf einem geteilten Laufwerk liegen und von mehreren Personen oder Agenten
gepflegt werden. Das Lock ist eine Anspruchsdatei in <projekt>/.wts-lock/: wer sie hält, darf
schreiben. run_pipeline.py hält an, wenn ein anderer einen gültigen Anspruch hat.

Regeln:
- Ein Anspruch läuft ab (Standard zwei Stunden ohne heartbeat). Ein abgelaufener Anspruch eines
  anderen wird nie still übernommen: `acquire --take-over --reason …` hält die Übernahme in
  .wts-lock/handovers.jsonl fest. `--force --reason …` verdrängt auch gültige Ansprüche und ist
  für den Notfall, nach Rücksprache.
- Der Token steht nie in der Anspruchsdatei (nur sein Hash) und nie auf der Konsole. Die Tokendatei
  liegt außerhalb des Projekts mit Rechten 0600.
- Ohne irgendeinen Anspruch läuft alles wie bisher: Das Lock ist für Teams, nicht für den Einzelnen.

Exit-Codes: 0 ok, 2 Bedienfehler, 3 gehalten oder nicht verifizierbar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

DEFAULT_TTL = 7200


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def lock_dir(project: Path) -> Path:
    return project / wl.LOCK_DIR


def claim_path(project: Path, owner: str) -> Path:
    return lock_dir(project) / f"claim-{wl.normalize_name(owner).replace(' ', '-') or 'anonym'}.json"


def read_claims(project: Path) -> list[dict]:
    d = lock_dir(project)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("claim-*.json")):
        try:
            rec = wl.read_json(p)
        except (OSError, ValueError):
            rec = {"owner": p.stem, "unreadable": True}
        rec["_path"] = p
        hb = parse(rec.get("heartbeat") or rec.get("acquired") or "")
        rec["_expired"] = hb is None or (now() - hb) > timedelta(seconds=int(rec.get("ttl_seconds") or DEFAULT_TTL))
        out.append(rec)
    return out


def describe(c: dict) -> str:
    state = "abgelaufen" if c.get("_expired") else "gültig"
    return (f"{c.get('owner')} ({c.get('operation') or 'ohne Angabe'}), seit {c.get('acquired')}, "
            f"letztes Lebenszeichen {c.get('heartbeat')}, {state}")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def write_token(path: Path, project: Path, token: str) -> None:
    try:
        path.resolve().relative_to(project.resolve())
        wl.fail("Die Tokendatei darf nicht im Projekt liegen (sie würde mit dem Projekt kopiert und geteilt)")
    except ValueError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"project": project.name, "token": token}) + "\n")


def read_token(path: Path) -> str:
    if not path.exists():
        wl.fail(f"Tokendatei fehlt: {wl.relpath(path)}", code=3)
    try:
        return str(wl.read_json(path)["token"])
    except (ValueError, KeyError, TypeError):
        wl.fail(f"Tokendatei unlesbar: {wl.relpath(path)}", code=3)
    return ""


def own_claim(project: Path, token: str) -> dict | None:
    th = token_hash(token)
    for c in read_claims(project):
        if c.get("token_sha256") == th:
            return c
    return None


def foreign_holders(project: Path, owner: str | None = None, token: str | None = None) -> list[dict]:
    """Gültige Ansprüche, die nicht meine sind."""
    th = token_hash(token) if token else None
    return [c for c in read_claims(project)
            if not c.get("_expired") and c.get("token_sha256") != th
            and (owner is None or c["_path"] != claim_path(project, owner))]


def log_handover(project: Path, entry: dict) -> None:
    p = lock_dir(project) / "handovers.jsonl"
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_acquire(a) -> int:
    project = wl.resolve_project(a.project)
    if not (project / wl.PROJECT_FILE).exists():
        wl.fail(f"Kein Projekt unter {wl.relpath(project)}")
    token_file = Path(a.token_file)
    claims = read_claims(project)
    mine = claim_path(project, a.owner)
    others = [c for c in claims if c["_path"] != mine]
    live = [c for c in others if not c.get("_expired")]
    expired = [c for c in others if c.get("_expired")]
    if live and not a.force:
        print("GEHALTEN: Das Projekt wird gerade gepflegt von:")
        for c in live:
            print(f"  {describe(c)}")
        print("Warten, oder nach Rücksprache: acquire --force --reason \"…\"")
        return 3
    if expired and not (a.take_over or a.force):
        print("ABGELAUFEN: Ein fremder Anspruch ist abgelaufen und wird nicht still übernommen:")
        for c in expired:
            print(f"  {describe(c)}")
        print("Übernahme festhalten mit: acquire --take-over --reason \"…\"")
        return 3
    if (a.take_over or a.force) and not a.reason:
        wl.fail("--take-over und --force brauchen --reason")
    lock_dir(project).mkdir(exist_ok=True)
    for c in others:
        if c.get("_expired") or a.force:
            log_handover(project, {"at": iso(now()), "by": a.owner, "from": c.get("owner"),
                                   "kind": "force" if (a.force and not c.get("_expired")) else "take_over",
                                   "reason": a.reason, "their_claim": {k: v for k, v in c.items() if not k.startswith("_")}})
            try:
                c["_path"].unlink()
            except OSError:
                pass
    token = secrets.token_hex(32)
    t = now()
    rec = {"owner": a.owner, "operation": a.operation, "acquired": iso(t), "heartbeat": iso(t),
           "ttl_seconds": int(a.ttl), "token_sha256": token_hash(token), "host": socket.gethostname(),
           "claim_id": secrets.token_hex(8)}
    write_token(token_file, project, token)
    wl.write_json(mine, rec)
    print(f"Anspruch gesetzt: {a.owner} ({a.operation}), gültig {a.ttl} s ohne Lebenszeichen. "
          f"Token in {wl.relpath(token_file)} (nicht teilen).")
    return 0


def cmd_verify(a) -> int:
    project = wl.resolve_project(a.project)
    token = read_token(Path(a.token_file))
    c = own_claim(project, token)
    if c is None:
        print("NICHT GEHALTEN: Kein Anspruch zu diesem Token (verdrängt, zurückgezogen oder nie gesetzt).")
        return 3
    if c.get("_expired"):
        print(f"ABGELAUFEN: eigener Anspruch seit {c.get('heartbeat')} ohne Lebenszeichen. Neu setzen mit acquire.")
        return 3
    print(f"Gehalten: {describe(c)}")
    return 0


def cmd_heartbeat(a) -> int:
    project = wl.resolve_project(a.project)
    token = read_token(Path(a.token_file))
    c = own_claim(project, token)
    if c is None:
        print("NICHT GEHALTEN: kein Anspruch zu diesem Token.")
        return 3
    path = c.pop("_path")
    c.pop("_expired", None)
    c["heartbeat"] = iso(now())
    wl.write_json(path, c)
    print(f"Lebenszeichen: {c['owner']} {c['heartbeat']}")
    return 0


def cmd_release(a) -> int:
    project = wl.resolve_project(a.project)
    token_file = Path(a.token_file)
    token = read_token(token_file)
    c = own_claim(project, token)
    if c is None:
        print("Kein Anspruch zu diesem Token; nichts freizugeben.")
        return 3
    c["_path"].unlink()
    if a.remove_token_file:
        token_file.unlink()
    print(f"Freigegeben: {c.get('owner')}")
    return 0


def cmd_withdraw(a) -> int:
    project = wl.resolve_project(a.project)
    p = claim_path(project, a.owner)
    if not p.exists():
        print(f"Kein Anspruch von {a.owner}.")
        return 0
    rec = wl.read_json(p)
    log_handover(project, {"at": iso(now()), "by": a.owner, "from": rec.get("owner"), "kind": "withdraw",
                           "reason": a.reason, "their_claim": rec})
    p.unlink()
    print(f"Zurückgezogen: Anspruch von {a.owner} ({a.reason})")
    return 0


def cmd_status(a) -> int:
    project = wl.resolve_project(a.project)
    claims = read_claims(project)
    if not claims:
        print("Kein Anspruch. Das Projekt ist frei.")
        return 0
    for c in claims:
        print(("GÜLTIG     " if not c.get("_expired") else "ABGELAUFEN ") + describe(c))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("acquire", "verify", "heartbeat", "release", "withdraw", "status"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        if name == "acquire":
            p.add_argument("--owner", required=True)
            p.add_argument("--operation", default="Pflege")
            p.add_argument("--token-file", required=True)
            p.add_argument("--ttl", type=int, default=DEFAULT_TTL)
            p.add_argument("--take-over", action="store_true")
            p.add_argument("--force", action="store_true")
            p.add_argument("--reason", default="")
        elif name in ("verify", "heartbeat", "release"):
            p.add_argument("--token-file", required=True)
            if name == "release":
                p.add_argument("--remove-token-file", action="store_true")
        elif name == "withdraw":
            p.add_argument("--owner", required=True)
            p.add_argument("--reason", required=True)
    a = ap.parse_args()
    return {"acquire": cmd_acquire, "verify": cmd_verify, "heartbeat": cmd_heartbeat, "release": cmd_release,
            "withdraw": cmd_withdraw, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
