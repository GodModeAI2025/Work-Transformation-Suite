#!/usr/bin/env python3
"""
export_contracts.py — schreibt die Capability Contracts als JSON und als Markdown heraus.

Aufruf:
    python3 <skill>/scripts/export_contracts.py --project ./mein-projekt [--status pilot,live]

Ausgaben (NNN = Graph-Version):
    40_output/contracts_vNNN.json   maschinenlesbar, für Plattform- und Architekturteams
    40_output/contracts_vNNN.md     lesbar, für Freigabe, Betriebsrat, Revision

Das JSON ist bewusst flach und anbieterneutral. Es benennt, welche Fähigkeit gebraucht
wird, unter welchen Bedingungen sie laufen darf und woran man merkt, dass sie nicht mehr
gut genug ist — nicht, mit welchem Modell sie umgesetzt wird. Genau diese Trennung macht
den Vertrag über einen Modellwechsel hinaus haltbar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

SCOPE_LABEL = {
    "recommend": "schlägt vor, entscheidet nicht",
    "execute_reversible": "führt aus, umkehrbar",
    "execute_irreversible": "führt aus, nicht umkehrbar",
}
FIELD_ORDER = [
    ("trigger", "Auslöser"),
    ("inputs", "Eingaben"),
    ("outputs", "Ausgaben"),
    ("tools", "Werkzeuge"),
    ("read_permissions", "Leserechte"),
    ("write_permissions", "Schreibrechte"),
    ("decision_scope", "Entscheidungsreichweite"),
    ("confidence_threshold", "Konfidenzschwelle"),
    ("human_checkpoint", "Menschlicher Kontrollpunkt"),
    ("fallback", "Rückfallebene"),
    ("timeout_seconds", "Zeitgrenze (s)"),
    ("retry_policy", "Wiederholung"),
    ("idempotency_key", "Idempotenzschlüssel"),
    ("audit_events", "Audit-Ereignisse"),
    ("service_level", "Servicezusage"),
    ("evaluation_set", "Testmenge"),
    ("cost_ceiling", "Kostendeckel"),
    ("capability_profile", "Gebrauchte Fähigkeiten"),
]


def _fmt(value: Any) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "—"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_fmt(v)}" for k, v in sorted(value.items()))
    return str(value)


def collect(graph: dict[str, Any], statuses: set) -> list[dict[str, Any]]:
    systems = wl.index_by_id(graph["systems"])
    roles = wl.index_by_id(graph["roles"])
    tasks = wl.index_by_id(graph["tasks"])
    agents = wl.index_by_id(graph["agents"])
    steps_by_agent: dict[str, list[str]] = {}
    for st in graph["process_steps"]:
        ex = st.get("executor") or {}
        if ex.get("type") == "agent" and ex.get("id"):
            steps_by_agent.setdefault(ex["id"], []).append(st["name"])

    out = []
    for a in sorted(graph["agents"], key=lambda x: x["id"]):
        c = a.get("contract")
        if not isinstance(c, dict):
            continue
        if statuses and a.get("status") not in statuses:
            continue
        entry = {
            "agent_id": a["id"],
            "name": a["name"],
            "pattern": a.get("pattern"),
            "capability": a.get("capability"),
            "status": a.get("status"),
            "sourcing": a.get("sourcing"),
            "specificity": a.get("specificity"),
            "oversight": a.get("oversight"),
            "prerequisites": a.get("prerequisites", []),
            "orchestrates": [agents[t]["name"] for t in a.get("orchestrates", []) if t in agents],
            "covers_tasks": [tasks[t]["name"] for t in a.get("task_ids", []) if t in tasks],
            "process_steps": sorted(steps_by_agent.get(a["id"], [])),
            "contract": {k: c.get(k) for k, _ in FIELD_ORDER if c.get(k) is not None},
        }
        hcp = c.get("human_checkpoint")
        if isinstance(hcp, dict) and hcp.get("role_id") in roles:
            entry["contract"]["human_checkpoint"] = dict(hcp, role=roles[hcp["role_id"]]["name"])
        if c.get("system_ids"):
            entry["contract"]["systems"] = [systems[s]["name"] for s in c["system_ids"] if s in systems]
        out.append(entry)
    return out


def to_markdown(entries: list[dict[str, Any]]) -> str:
    out = ["# Capability Contracts", "",
           "Je Agent: was ihn auslöst, worauf er zugreifen darf, wo ein Mensch entscheidet, "
           "was passiert, wenn er scheitert, und woran man merkt, dass er schlechter wird.",
           "",
           "Die Verträge nennen keine Modellnamen. Sie beschreiben die gebrauchte Fähigkeit, "
           "damit ein Modellwechsel eine Beschaffungsentscheidung bleibt und keine "
           "Prozessänderung erzwingt.", ""]
    if not entries:
        out.append("Noch kein Agent hat einen Vertrag.")
        return "\n".join(out) + "\n"
    out.append("| Agent | Status | Reichweite | Schreibrechte | Kontrollpunkt |")
    out.append("|---|---|---|---|---|")
    for e in entries:
        c = e["contract"]
        out.append(f"| {e['name']} | {e['status']} "
                   f"| {SCOPE_LABEL.get(c.get('decision_scope'), '—')} "
                   f"| {_fmt(c.get('write_permissions'))} | {_fmt(c.get('human_checkpoint'))} |")
    out.append("")
    for e in entries:
        out.append(f"## {e['name']}")
        out.append("")
        if e.get("capability"):
            out.append(e["capability"])
            out.append("")
        meta = [f"**Muster:** {e.get('pattern')}", f"**Status:** {e.get('status')}",
                f"**Bezug:** {e.get('sourcing')}"]
        out.append("  \n".join(meta))
        out.append("")
        if e["process_steps"]:
            out.append("**Führt aus:** " + ", ".join(e["process_steps"]))
            out.append("")
        if e["orchestrates"]:
            out.append("**Koordiniert:** " + ", ".join(e["orchestrates"]))
            out.append("")
        out.append("| Feld | Wert |")
        out.append("|---|---|")
        for key, label in FIELD_ORDER:
            if key in e["contract"]:
                out.append(f"| {label} | {_fmt(e['contract'][key])} |")
        out.append("")
        if e["prerequisites"]:
            out.append("**Voraussetzungen vor dem Bau**")
            out.append("")
            for p in e["prerequisites"]:
                out.append(f"- {p}")
            out.append("")
        if e.get("oversight"):
            out.append(f"**Aufsicht im Betrieb:** {e['oversight']}")
            out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--status", default="", help="nur diese Status, kommagetrennt (z. B. pilot,live)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    statuses = {s.strip() for s in args.status.split(",") if s.strip()}
    entries = collect(graph, statuses)
    version = int(graph.get("meta", {}).get("version", 0))
    outdir = project / wl.DIR_OUTPUT
    json_path = outdir / f"contracts_v{version:03d}.json"
    wl.write_json(json_path, entries)
    md_path = outdir / f"contracts_v{version:03d}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(md_path, to_markdown(entries))
    without = sum(1 for a in graph["agents"] if not isinstance(a.get("contract"), dict))
    print(f"Geschrieben: {wl.relpath(json_path)}, {wl.relpath(md_path)} | "
          f"Verträge={len(entries)} ohne Vertrag={without}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
