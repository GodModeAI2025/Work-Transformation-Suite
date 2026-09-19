#!/usr/bin/env python3
"""
compute_coverage.py — übernimmt die Agentenbibliothek aus 20_graph/agents.json,
vergibt deterministische IDs, verknüpft Aufgaben, berechnet je Agent die
Rollenabdeckung, Sourcing, Horizont und Priorität, und schreibt eine neue
Graph-Version (Stage "mapper").

Aufruf:
    python3 <skill>/scripts/compute_coverage.py --project ./mein-projekt [--shared-tasks]

--shared-tasks  erlaubt, dass mehrere Agenten dieselbe Aufgabe abdecken. Standard ist
                weiterhin genau ein Agent je nicht-manueller Aufgabe: für eine Opportunity
                Map ist das die ehrlichere Darstellung, weil sich Abdeckung dann addieren
                lässt. Im Redesignmodus stimmt die Annahme nicht mehr — ein Prozessschritt
                kann menschliche, regelbasierte, systemische und agentische Fähigkeiten
                kombinieren, und ein Orchestrator koordiniert mehrere Spezialagenten.
                Mit --shared-tasks werden Überschneidungen zugelassen, je Agent ausgewiesen
                (overlap_task_ids) und am Ende als bereinigte Gesamtabdeckung gemeldet,
                damit niemand FTE doppelt zählt.

Eingabe 20_graph/agents.json:
[
  {
    "name": "Marktkommunikations-Agent Lieferantenwechsel",
    "pattern": "market-communication",
    "capability": "Wickelt An-/Abmeldungen und Stammdatenänderungen über EDIFACT ab ...",
    "specificity": "proprietary",
    "status": "proposed",
    "complexity": 4,
    "existing_system": null,
    "oversight": "Stichprobe 5 % durch Sachbearbeitung, Vier-Augen bei Ablehnungen",
    "prerequisites": ["Schreibzugriff SAP IS-U über Schnittstelle", "Freigabe Betriebsrat"],
    "task_ids": ["ta_...", "ta_..."]
  }
]

Rechenregeln (siehe SKILL.md):
- Abdeckung je Rolle = Σ share_of_time(task) × automation_potential(task)/10 über die
  Aufgaben des Agenten in dieser Rolle. Einheit: Prozent der Rollenarbeitszeit.
- fte_equivalent = Σ_Rollen Abdeckung/100 × headcount (nur Rollen mit Headcount).
- sourcing: generic→buy, domain→hybrid, proprietary→build.
- horizon: frühester Horizont der zugeordneten Aufgaben (near < mid < long).
- priority_rank (Wert): fte_equivalent absteigend, dann coverage_points absteigend, dann complexity aufsteigend, dann Name.
- sequence_rank (Bau-Reihenfolge, Quick Wins zuerst): Horizont near<mid<long, dann complexity aufsteigend, dann Wert.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

SOURCING = {"generic": "buy", "domain": "hybrid", "proprietary": "build"}
HORIZON_RANK = {"near": 0, "mid": 1, "long": 2}
ALLOWED_PATTERNS = {
    "document-extraction", "classification-routing", "data-reconciliation", "master-data-maintenance",
    "standard-correspondence", "report-generation", "anomaly-detection", "forecasting", "regulatory-monitor",
    "knowledge-qa", "scheduling-coordination", "ticket-resolution", "conversational-assistant", "contract-change-handling",
    "market-communication", "meter-data-processing", "invoice-verification", "compliance-check",
    "quality-review", "drafting-assistant", "analysis-copilot", "meeting-assistant", "onboarding-guide",
    "workflow-orchestration", "inspection-support", "dispatch-optimization",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--shared-tasks", action="store_true",
                    help="mehrere Agenten dürfen dieselbe Aufgabe abdecken (Redesignmodus)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / wl.DIR_GRAPH / "agents.json"
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt (zuerst export_agent_candidates.py, dann Agenten definieren)")
    raw = wl.read_json(src)
    if not isinstance(raw, list):
        wl.fail("agents.json muss eine Liste sein")

    tasks = wl.index_by_id(graph["tasks"])
    roles = wl.index_by_id(graph["roles"])
    problems: list[str] = []

    # Alte Zuordnungen löschen, neu aufbauen (agents.json ist die Wahrheit)
    for t in graph["tasks"]:
        t["agent_ids"] = []
    agents: dict[str, dict[str, Any]] = {}
    assigned: dict[str, str] = {}
    shared: dict[str, list[str]] = {}
    for a in sorted(raw, key=lambda a: str(a.get("name", ""))):
        name = str(a.get("name", "")).strip()
        if not name:
            problems.append("Agent ohne Namen übersprungen")
            continue
        aid = wl.make_id("agent", name)
        pattern = str(a.get("pattern", "")).strip()
        if pattern not in ALLOWED_PATTERNS:
            problems.append(f"{name}: pattern '{pattern}' nicht im Katalog, auf workflow-orchestration gesetzt")
            pattern = "workflow-orchestration"
        spec = str(a.get("specificity", "")).strip()
        if spec not in wl.ENUM_SPECIFICITY:
            problems.append(f"{name}: specificity '{spec}' ungültig, auf domain gesetzt")
            spec = "domain"
        status = str(a.get("status", "proposed")).strip()
        if status not in wl.ENUM_AGENT_STATUS:
            status = "proposed"
        try:
            complexity = int(wl.clamp(int(a.get("complexity", 3)), 1, 5))
        except (TypeError, ValueError):
            complexity = 3
        tids = []
        for tid in a.get("task_ids", []):
            if tid not in tasks:
                problems.append(f"{name}: Task {tid} unbekannt")
                continue
            if tasks[tid].get("mode") == "manual":
                problems.append(f"{name}: Task {tid} ({tasks[tid]['name']}) ist manuell, nicht zugeordnet")
                continue
            if tid in assigned:
                if not args.shared_tasks:
                    problems.append(f"{name}: Task {tid} schon bei {assigned[tid]} zugeordnet, "
                                    "ignoriert (mit --shared-tasks erlaubt)")
                    continue
                shared.setdefault(tid, [assigned[tid]]).append(name)
            assigned.setdefault(tid, name)
            tids.append(tid)
            tasks[tid]["agent_ids"] = sorted(set(tasks[tid].get("agent_ids", []) + [aid]))
        agents[aid] = {
            "id": aid,
            "name": name,
            "pattern": pattern,
            "capability": str(a.get("capability", "")).strip(),
            "specificity": spec,
            "sourcing": SOURCING[spec],
            "status": status,
            "complexity": complexity,
            "existing_system": a.get("existing_system") or None,
            "oversight": str(a.get("oversight", "")).strip(),
            "prerequisites": sorted({str(p).strip() for p in a.get("prerequisites", []) if str(p).strip()}),
            "task_ids": sorted(tids),
        }
        # Der Capability Contract wird unverändert übernommen; geprüft wird er im Validator
        # (validate_graph.validate_contract) und tiefer in validate_contracts.py.
        if isinstance(a.get("contract"), dict):
            agents[aid]["contract"] = a["contract"]
        if a.get("capability_profile"):
            agents[aid]["capability_profile"] = a["capability_profile"]
        if a.get("orchestrates"):
            agents[aid]["orchestrates"] = sorted({str(x).strip() for x in a["orchestrates"] if str(x).strip()})

    # Nicht zugeordnete automatisierbare Aufgaben melden
    unassigned = [t for t in graph["tasks"] if t.get("mode") in ("ai_assisted", "agent_delegated") and not t["agent_ids"]]
    for t in sorted(unassigned, key=lambda t: t["id"]):
        problems.append(f"nicht zugeordnet: {t['id']} ({roles[t['role_id']]['name']}: {t['name']})")

    # Abdeckung berechnen
    for aid, ag in agents.items():
        per_role: dict[str, dict[str, Any]] = {}
        horizons = []
        for tid in ag["task_ids"]:
            t = tasks[tid]
            r = roles[t["role_id"]]
            d = per_role.setdefault(r["id"], {"role_id": r["id"], "role": r["name"], "coverage_pct": 0.0,
                                             "task_ids": [], "headcount": r.get("headcount")})
            d["coverage_pct"] += float(t["share_of_time"]) * float(t.get("automation_potential", 0)) / 10.0
            d["task_ids"].append(tid)
            if t.get("horizon"):
                horizons.append(t["horizon"])
        rows = []
        cov_points = 0.0
        fte = 0.0
        fte_known = False
        for rid in sorted(per_role):
            d = per_role[rid]
            d["coverage_pct"] = wl.round1(d["coverage_pct"])
            d["task_ids"].sort()
            cov_points += d["coverage_pct"]
            if d["headcount"] is not None:
                fte += d["coverage_pct"] / 100.0 * float(d["headcount"])
                fte_known = True
            rows.append(d)
        rows.sort(key=lambda d: (-d["coverage_pct"], d["role_id"]))
        ag["roles_covered"] = rows
        ag["roles_covered_count"] = len(rows)
        ag["coverage_points"] = wl.round1(cov_points)
        ag["avg_coverage_pct"] = wl.round1(cov_points / len(rows)) if rows else 0.0
        ag["fte_equivalent"] = wl.round1(fte) if fte_known else None
        ag["horizon"] = min(horizons, key=lambda h: HORIZON_RANK[h]) if horizons else None
        ag["share_delegated_tasks"] = wl.round1(
            100.0 * sum(1 for tid in ag["task_ids"] if tasks[tid]["mode"] == "agent_delegated") / len(ag["task_ids"])
        ) if ag["task_ids"] else 0.0

    ranked = sorted(
        agents.values(),
        key=lambda a: (-(a["fte_equivalent"] if a["fte_equivalent"] is not None else -1.0), -a["coverage_points"], a["complexity"], a["name"]),
    )
    for i, a in enumerate(ranked, start=1):
        a["priority_rank"] = i
    # Zweite Rangfolge: Bau-Reihenfolge (Quick Wins zuerst): Horizont, dann Komplexität, dann Wert.
    sequence = sorted(
        agents.values(),
        key=lambda a: (HORIZON_RANK.get(a["horizon"], 3), a["complexity"],
                       -(a["fte_equivalent"] if a["fte_equivalent"] is not None else -1.0), -a["coverage_points"], a["name"]),
    )
    for i, a in enumerate(sequence, start=1):
        a["sequence_rank"] = i

    # Orchestrator-Verweise von Namen auf IDs heben, jetzt wo alle Agenten IDs haben.
    by_name = {wl.normalize_name(a["name"]): a["id"] for a in agents.values()}
    for ag in agents.values():
        if ag.get("orchestrates"):
            resolved = []
            for nm in ag["orchestrates"]:
                target = by_name.get(wl.normalize_name(nm))
                if target is None:
                    problems.append(f"{ag['name']}: orchestriert unbekannten Agenten {nm!r}")
                elif target == ag["id"]:
                    problems.append(f"{ag['name']}: orchestriert sich selbst, ignoriert")
                else:
                    resolved.append(target)
            ag["orchestrates"] = sorted(set(resolved))

    for tid, names in sorted(shared.items()):
        for ag in agents.values():
            if tid in ag["task_ids"]:
                ag.setdefault("overlap_task_ids", []).append(tid)
        problems.append(f"Aufgabe {tid} ({tasks[tid]['name']}) wird von mehreren Agenten "
                        f"abgedeckt: {', '.join(sorted(set(names)))}. Abdeckungen dieser "
                        "Agenten überschneiden sich, ihre FTE-Werte dürfen nicht addiert werden")
    for ag in agents.values():
        if ag.get("overlap_task_ids"):
            ag["overlap_task_ids"] = sorted(set(ag["overlap_task_ids"]))

    graph["agents"] = list(agents.values())
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "mapper")
    verb = "Geschrieben" if changed else "Unverändert"
    # Bereinigte Gesamtabdeckung: jede Aufgabe genau einmal, egal wie viele Agenten sie
    # anfassen. Das ist die Zahl, die in eine Portfoliodiskussion gehört.
    net_fte = 0.0
    net_known = False
    for tid in sorted(assigned):
        t = tasks[tid]
        r = roles[t["role_id"]]
        if r.get("headcount") is None:
            continue
        net_known = True
        net_fte += float(t["share_of_time"]) * float(t.get("automation_potential", 0)) / 10.0 / 100.0 \
            * float(r["headcount"])
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Agenten={len(agents)} "
          f"zugeordnete Aufgaben={len(assigned)} offen={len(unassigned)} Hinweise={len(problems)}")
    if net_known:
        print(f"Bereinigte Gesamtabdeckung: {wl.round1(net_fte)} VZÄ über {len(assigned)} Aufgaben "
              f"(überschneidungsfrei gerechnet, nicht die Summe der Einzelagenten)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
