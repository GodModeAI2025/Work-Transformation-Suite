#!/usr/bin/env python3
"""
export_skill.py — macht aus einem Capability Contract das Gerüst eines Skills, den ein
Team in sein Agenten-Harness legen kann.

Aufruf:
    python3 <skill>/scripts/export_skill.py --project ./mein-projekt [--status pilot,live] [--agent "Name"]

Ausgabe je Agent mit Vertrag (NNN = Graph-Version):
    40_output/skills_export/<name>/SKILL.md              Anweisung, aus dem Vertrag abgeleitet
    40_output/skills_export/<name>/scripts/run.py        deterministisches Gerüst
    40_output/skills_export/<name>/scripts/report_usage.py  aggregierte Nutzungsmeldung
    40_output/skills_export/<name>/evals/cases.json      Hülle für die Testmenge

Ehrlich gesagt, was das ist: ein **Gerüst**, kein fertiger Skill. Eine Skill-Anweisung allein
ist ein Prompt, und ein Prompt hält sich nicht zuverlässig an „alle Prüfungen ausführen“.
Das Gerüst legt deshalb das Deterministische in ein Skript — Eingabeprüfung,
Idempotenzschlüssel, Konfidenzschwelle, Kontrollpunkt, Rückfall, Audit-Zeilen — und lässt
nur die Systemaufrufe offen (`TODO`). Wer die ausfüllt und die Testmenge befüllt, hat einen
Skill, den man prüfen kann.

Die Nutzungsmeldung schickt nur Zählwerte (Skill, Version, Ausgang). Keine Person, keine
Fallinhalte. Ohne gesetzte Adresse tut sie nichts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

RESERVED = ("anthropic", "claude")


def slug(name: str) -> str:
    s = wl.normalize_name(name)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60].strip("-") or "agent"
    for word in RESERVED:
        s = s.replace(word, "x" + word[1:])
    return s


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (nicht festgelegt)"


def skill_md(a: dict[str, Any], c: dict[str, Any], steps: list[str], tasks: list[str], name: str) -> str:
    hcp = c.get("human_checkpoint")
    scope = {"recommend": "Du schlägst nur vor. Du schreibst nichts in ein System.",
             "execute_reversible": "Du darfst umkehrbare Änderungen ausführen. Jede Änderung wird protokolliert.",
             "execute_irreversible": "Du darfst nicht umkehrbare Änderungen nur nach menschlicher Freigabe ausführen."
             }.get(c.get("decision_scope"), "Reichweite nicht festgelegt — als Vorschlag behandeln.")
    desc = (a.get("capability") or a["name"]).strip().replace("\n", " ")
    trigger = (c.get("trigger") or "").strip().replace("\n", " ")
    description = f"{desc} Verwenden bei: {trigger}" if trigger else desc
    lines = ["---", f"name: {name}", f"description: {json.dumps(description[:900], ensure_ascii=False)}", "---", "",
             f"# {a['name']}", "",
             "Dieses Gerüst stammt aus einem Capability Contract der Work-Transformation-Suite. "
             "Der Vertrag beschreibt die Fähigkeit, nicht das Modell.", "",
             "## Auftrag", "", scope, ""]
    if tasks:
        lines += ["Abgedeckte Aufgaben:", _bullets(tasks), ""]
    if steps:
        lines += ["Prozessschritte, die du ausführst:", _bullets(steps), ""]
    lines += ["## Ablauf", "",
              "1. `scripts/run.py` mit der Eingabe aufrufen. Es prüft die Eingaben, bildet den "
              "Idempotenzschlüssel und stoppt bei Wiederholung.",
              "2. Die Systemaufrufe im Skript (`TODO`) liefern die Daten; die Bewertung des Falls "
              "übernimmst du.",
              "3. Liegt die Konfidenz unter der Schwelle oder greift die Kontrollpunkt-Bedingung, "
              "übergibst du an den Menschen. Du entscheidest dann nichts selbst.",
              "4. Scheitert ein Schritt, gilt die Rückfallebene unten. Kein Teilergebnis schreiben.",
              "", "## Eingaben und Ausgaben", "", "Eingaben:", _bullets(c.get("inputs")), "",
              "Ausgaben:", _bullets(c.get("outputs")), "", "## Rechte", "", "Lesen:",
              _bullets(c.get("read_permissions")), "", "Schreiben:", _bullets(c.get("write_permissions")), ""]
    if c.get("confidence_threshold") is not None:
        lines += [f"## Konfidenzschwelle\n\n{c['confidence_threshold']}. Darunter greift der Kontrollpunkt.\n"]
    if isinstance(hcp, dict):
        lines += ["## Menschlicher Kontrollpunkt", "", f"Wann: {hcp.get('when', '—')}"]
        if hcp.get("sla_minutes"):
            lines.append(f"Reaktionszeit: {hcp['sla_minutes']} Minuten")
        lines.append("")
    lines += ["## Rückfallebene", "", c.get("fallback") or "(nicht festgelegt)", "",
              "## Protokoll", "", "Schreibe diese Ereignisse (Skript `run.py` tut es für dich):",
              _bullets(c.get("audit_events")), "", "## Prüfung", "",
              "Die Testmenge steht in `evals/cases.json`. Vor jedem Einsatz laufen lassen; "
              "unter den dort genannten Schwellen wird der Skill nicht freigegeben.", ""]
    ev = c.get("evaluation_set")
    if isinstance(ev, dict):
        lines += [f"Schwellen: {ev.get('thresholds', '—')}", ""]
    lines += ["## Nutzungsmeldung", "",
              "`scripts/report_usage.py` meldet nach jedem Lauf nur: Skill, Version, Ausgang "
              "(`ok`, `escalated`, `failed`). Keine Person, keine Fallinhalte. Ohne gesetzte "
              "Umgebungsvariable `WTS_USAGE_URL` meldet es nichts.", ""]
    return "\n".join(lines)


def run_py(a: dict[str, Any], c: dict[str, Any], name: str) -> str:
    thr = c.get("confidence_threshold")
    required = [str(i).split("(")[0].strip() for i in (c.get("inputs") or [])]
    return f'''#!/usr/bin/env python3
"""Gerüst für „{a["name"]}“ — aus dem Capability Contract erzeugt.

Das Deterministische steht hier, die Systemaufrufe fehlen noch (TODO). Aufruf:
    python3 run.py eingabe.json
"""

import hashlib
import json
import sys
import time

REQUIRED_INPUTS = {json.dumps(required, ensure_ascii=False)}
CONFIDENCE_THRESHOLD = {thr if thr is not None else "None"}
IDEMPOTENCY_KEY_FIELDS = {json.dumps(c.get("idempotency_key") or "", ensure_ascii=False)}  # Hinweis aus dem Vertrag
SEEN = set()  # TODO: durch dauerhaften Speicher ersetzen, sonst gilt Idempotenz nur je Lauf


def audit(event, **fields):
    # TODO: in das Protokollsystem des Hauses schreiben; bis dahin Standardausgabe.
    print(json.dumps({{"event": event, "ts": time.time(), **fields}}, ensure_ascii=False), file=sys.stderr)


def idempotency_key(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def main():
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
    missing = [k for k in REQUIRED_INPUTS if k and k not in payload]
    if missing:
        audit("failed", reason="missing_inputs", fields=missing)
        print(json.dumps({{"status": "failed", "reason": "Eingaben fehlen", "fields": missing}}))
        return 2
    key = idempotency_key(payload)
    if key in SEEN:
        print(json.dumps({{"status": "skipped", "reason": "bereits verarbeitet"}}))
        return 0
    SEEN.add(key)

    # TODO: Daten aus den Systemen lesen (nur die Leserechte aus dem Vertrag).
    # TODO: Fall bewerten; Ergebnis und Konfidenz bestimmen.
    result, confidence = None, 0.0

    if CONFIDENCE_THRESHOLD is not None and confidence < CONFIDENCE_THRESHOLD:
        audit("escalated", key=key, confidence=confidence)
        print(json.dumps({{"status": "escalated", "reason": "Konfidenz unter Schwelle"}}))
        return 0
    # TODO: Schreibaktion nur hier, nur im Rahmen der Schreibrechte, mit key als Idempotenzschlüssel.
    audit("ok", key=key)
    print(json.dumps({{"status": "ok", "result": result}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


REPORT_PY = '''#!/usr/bin/env python3
"""Meldet nur den Ausgang eines Laufs, ohne Person und ohne Inhalt.

    python3 report_usage.py <skill> <version> ok|escalated|failed

Ohne WTS_USAGE_URL passiert nichts. Die Meldung ist eine Zählung, kein Protokoll.
"""
import json
import os
import sys
import urllib.request

OUTCOMES = {"ok", "escalated", "failed"}


def main():
    if len(sys.argv) != 4 or sys.argv[3] not in OUTCOMES:
        print("Aufruf: report_usage.py <skill> <version> ok|escalated|failed", file=sys.stderr)
        return 2
    url = os.environ.get("WTS_USAGE_URL")
    if not url:
        return 0
    body = json.dumps({"skill": sys.argv[1], "version": sys.argv[2], "outcome": sys.argv[3]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).close()
    except OSError:
        pass  # Eine fehlende Meldung darf nie den Lauf stören.
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def collect(graph, statuses, only):
    tasks = wl.index_by_id(graph["tasks"])
    steps_by_agent: dict[str, list[str]] = {}
    for st in graph["process_steps"]:
        ex = st.get("executor") or {}
        if ex.get("type") == "agent" and ex.get("id"):
            steps_by_agent.setdefault(ex["id"], []).append(st["name"])
    for a in sorted(graph["agents"], key=lambda x: x["id"]):
        c = a.get("contract")
        if not isinstance(c, dict):
            continue
        if statuses and a.get("status") not in statuses:
            continue
        if only and wl.normalize_name(a["name"]) != wl.normalize_name(only):
            continue
        yield a, c, sorted(steps_by_agent.get(a["id"], [])), sorted(tasks[t]["name"] for t in a.get("task_ids", []) if t in tasks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--status", default="")
    ap.add_argument("--agent", default="")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    statuses = {s.strip() for s in args.status.split(",") if s.strip()}
    root = project / wl.DIR_OUTPUT / "skills_export"
    n = 0
    for a, c, steps, tasks in collect(graph, statuses, args.agent):
        name = slug(a["name"])
        d = root / name
        wl.write_text(d / "SKILL.md", skill_md(a, c, steps, tasks, name))
        wl.write_text(d / "scripts" / "run.py", run_py(a, c, name))
        wl.write_text(d / "scripts" / "report_usage.py", REPORT_PY)
        ev = c.get("evaluation_set") if isinstance(c.get("evaluation_set"), dict) else {}
        wl.write_json(d / "evals" / "cases.json", {
            "name": ev.get("name") or f"{name}-eval", "planned_cases": ev.get("cases"),
            "source": ev.get("source"), "thresholds": ev.get("thresholds"), "cases": []})
        n += 1
    without = sum(1 for a in graph["agents"] if not isinstance(a.get("contract"), dict))
    print(f"Geschrieben: {wl.relpath(root)} | Skill-Gerüste={n} Agenten ohne Vertrag={without}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
