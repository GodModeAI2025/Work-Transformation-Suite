#!/usr/bin/env python3
"""
export_agent_candidates.py — listet alle delegier- oder assistierbaren Aufgaben
mit Kontext und einem deterministischen Mustervorschlag (Keyword-Treffer aus
references/agent-patterns.md) nach 20_graph/agents_todo.json.

Aufruf:
    python3 <skill>/scripts/export_agent_candidates.py --project ./mein-projekt

Claude bündelt die Aufgaben zu Agenten und schreibt 20_graph/agents.json
(Format siehe SKILL.md). Danach: compute_coverage.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

# Muster -> Stichwörter (Stämme, kleingeschrieben). Erster Treffer in Listenreihenfolge gewinnt.
PATTERN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("market-communication", ["marktkommunikation", "edifact", "gpke", "geli", "anmeld", "abmeld", "lieferantenwechsel"]),
    ("meter-data-processing", ["zählerst", "zaehlerst", "messwert", "ablesung", "ersatzwert", "smart meter"]),
    ("contract-change-handling", ["vertrag", "tarif", "kündig", "kuendig", "verlänger", "verlaenger", "einzug", "auszug"]),
    ("invoice-verification", ["rechnung", "kontier", "faktur", "gutschrift"]),
    ("regulatory-monitor", ["gesetz", "regulier", "verordnung", "bnetza", "novelle", "rechtsänderung"]),
    ("compliance-check", ["compliance", "konform", "freigabe", "checkliste", "revision", "kontrollsystem"]),
    ("forecasting", ["prognos", "vorhersag", "forecast", "absatzplan", "lastgang"]),
    ("anomaly-detection", ["überwach", "ueberwach", "monitor", "auffällig", "auffaellig", "abweichung", "alarm"]),
    ("data-reconciliation", ["abgleich", "plausib", "konsolid", "differenz"]),
    ("master-data-maintenance", ["stammdat", "anlegen", "pflegen", "aktualisier"]),
    ("document-extraction", ["erfass", "auslesen", "übernehmen", "uebernehmen", "digitalisier", "formular", "dokument"]),
    ("classification-routing", ["sichten", "zuordn", "weiterleit", "triag", "klassifiz", "eingang"]),
    ("standard-correspondence", ["beantwort", "bestätig", "bestaetig", "versend", "schreiben", "antwort", "informier"]),
    ("report-generation", ["bericht", "report", "auswert", "kennzahl", "dashboard"]),
    ("scheduling-coordination", ["termin", "koordin", "abstimm", "einsatzplan"]),
    ("dispatch-optimization", ["dispon", "route", "einplan", "zuweis"]),
    ("inspection-support", ["inspek", "begeh", "zustand", "wartung", "instandhalt"]),
    ("conversational-assistant", ["chat", "telefon", "anruf", "hotline", "voice", "auskunft"]),
    ("ticket-resolution", ["ticket", "anliegen", "störung", "stoerung", "anfrage", "bearbeit"]),
    ("knowledge-qa", ["recherch", "nachschlag", "erklär", "erklaer", "wissen", "faq"]),
    ("meeting-assistant", ["protokoll", "meeting", "besprechung", "sitzung"]),
    ("drafting-assistant", ["entwurf", "entwerf", "formulier", "konzept", "präsentation", "praesentation", "texten"]),
    ("analysis-copilot", ["analys", "modell", "szenario", "vergleich", "bewert"]),
    ("quality-review", ["review", "qualität", "qualitaet", "prüf", "pruef", "kontroll"]),
    ("workflow-orchestration", ["auslös", "ausloes", "prozess", "abschließ", "abschliess", "nachhalt"]),
    ("onboarding-guide", ["einarbeit", "onboard", "einführ", "einfuehr", "begleit"]),
]


def suggest_pattern(text: str) -> str:
    t = wl.normalize_name(text)
    t_raw = text.lower()
    for pattern, kws in PATTERN_KEYWORDS:
        for kw in kws:
            if kw in t or kw in t_raw:
                return pattern
    return "workflow-orchestration"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    roles = wl.index_by_id(graph["roles"])
    clusters = wl.index_by_id(graph["job_clusters"])
    agents = wl.index_by_id(graph.get("agents", []))

    cands = []
    for t in graph["tasks"]:
        if t.get("mode") in ("ai_assisted", "agent_delegated"):
            r = roles[t["role_id"]]
            cands.append({
                "task_id": t["id"],
                "task": t["name"],
                "description": t.get("description", ""),
                "role": r["name"],
                "role_id": r["id"],
                "cluster": clusters[r["cluster_id"]]["name"],
                "regulated": r.get("regulated", False),
                "mode": t["mode"],
                "horizon": t.get("horizon"),
                "automation_potential": t.get("automation_potential"),
                "share_of_time": t["share_of_time"],
                "suggested_pattern": suggest_pattern(t["name"] + " " + t.get("description", "")),
                "current_agent": (t.get("agent_ids") or [None])[0],
            })
    if not cands:
        wl.fail("Keine bewerteten, nicht-manuellen Aufgaben; zuerst task-scorer ausführen")
    cands.sort(key=lambda c: (c["suggested_pattern"], c["cluster"], c["role"], -c["share_of_time"], c["task"]))
    by_pattern: dict[str, list] = {}
    for c in cands:
        by_pattern.setdefault(c["suggested_pattern"], []).append(c)

    out = {
        "_hint": "Aufgaben nach Mustervorschlag gruppiert. Bündle sie zu Agenten und schreibe 20_graph/agents.json. "
                 "Vorschlag ist nur Startpunkt; fachlich sinnvolle Umgruppierung ist erwünscht.",
        "existing_agents": [{"id": a["id"], "name": a["name"], "status": a.get("status")} for a in sorted(agents.values(), key=lambda a: a["id"])],
        "candidates_by_pattern": by_pattern,
    }
    path = project / wl.DIR_GRAPH / "agents_todo.json"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    modes = {}
    for c in cands:
        modes[c["mode"]] = modes.get(c["mode"], 0) + 1
    print(f"Geschrieben: {wl.relpath(path)} ({len(cands)} Aufgaben in {len(by_pattern)} Mustergruppen; "
          + ", ".join(f"{k}={v}" for k, v in sorted(modes.items())) + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
