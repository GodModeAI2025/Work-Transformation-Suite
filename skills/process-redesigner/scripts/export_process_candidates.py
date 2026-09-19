#!/usr/bin/env python3
"""
export_process_candidates.py — bereitet je Prozess alles auf, was für einen
Redesign-Entwurf gebraucht wird, und schreibt es als Arbeitsvorlage heraus.

Aufruf:
    python3 <skill>/scripts/export_process_candidates.py --project ./mein-projekt [--process pr_…]

Ausgaben:
    20_graph/redesign_todo.json        Arbeitsvorlage für Claude (je Prozess: Ist-Fluss,
                                       Kennzahlen, Kontrollen, maschinell erkannte Signale)
    30_review/redesign_briefing_vNNN.md  dieselbe Sache als Lesefassung für Fachexperten

Das Skript urteilt nicht. Es zeigt, wo im Ist-Prozess Struktur verschwendet wird
(Liegezeiten, Nacharbeit, Medienbrüche, Mehrfachprüfungen auf denselben Daten) und
welcher Operator dort typischerweise greift. Welche dieser Hinweise fachlich zulässig
sind, entscheidet der Blueprint — und dafür braucht es Menschen beziehungsweise Claude.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import redesign_lib as rl  # noqa: E402


def step_view(graph: dict[str, Any], st: dict[str, Any], names: dict[str, dict]) -> dict[str, Any]:
    ex = st.get("executor") or {}
    return {
        "step_id": st["id"],
        "name": st["name"],
        "executor": {"type": ex.get("type"), "name": names.get(ex.get("id"), {}).get("name")},
        "tasks": [names.get(t, {}).get("name") for t in st.get("task_ids", [])],
        "inputs": st.get("inputs", []),
        "outputs": st.get("outputs", []),
        "systems": [names.get(s, {}).get("name") for s in st.get("system_ids", [])],
        "controls": [names.get(c, {}).get("name") for c in st.get("control_ids", [])],
        "handling_time_min": st.get("handling_time_min"),
        "wait_time_min": st.get("wait_time_min"),
        "rework_pct": st.get("rework_pct"),
        "value_type": st.get("value_type"),
        "human_gate": bool(st.get("human_gate")),
        "decision_scope": (st.get("decision") or {}).get("scope"),
        "data_classes": st.get("data_classes", []),
    }


def build_todo(graph: dict[str, Any], only: str = "") -> list[dict[str, Any]]:
    names: dict[str, dict] = {}
    for c in wl.COLLECTIONS:
        for it in graph.get(c, []):
            names[it["id"]] = it
    metrics = wl.index_by_id(graph["metrics"])
    todo = []
    for pr in sorted(graph["processes"], key=lambda p: p["id"]):
        if only and pr["id"] != only and wl.normalize_name(pr["name"]) != wl.normalize_name(only):
            continue
        steps = wl.steps_of(graph, pr["id"])
        totals = wl.process_totals(graph, pr["id"])
        hmin = rl.human_minutes_per_case(graph, pr["id"])
        entry = {
            "process_id": pr["id"],
            "process": pr["name"],
            "trigger": pr.get("trigger"),
            "outcome": names.get(pr.get("outcome_id"), {}).get("name"),
            "beneficiary": pr.get("beneficiary"),
            "owner_role": names.get(pr.get("owner_role_id"), {}).get("name"),
            "volume_per_year": pr.get("volume_per_year"),
            "regulated": pr.get("regulated", False),
            "data_classes": pr.get("data_classes", []),
            "ist_totals": totals,
            "human_minutes_per_case": hmin,
            "fte_equivalent": rl.fte_equivalent(hmin, pr.get("volume_per_year")),
            "baseline_metrics": [
                {
                    "metric": metrics[m]["name"], "kind": metrics[m]["kind"],
                    "unit": metrics[m].get("unit"), "direction": metrics[m].get("direction"),
                    "baseline": wl.metric_value(metrics[m], "baseline")[0],
                    "basis": wl.metric_value(metrics[m], "baseline")[1],
                    "target": (metrics[m].get("target") or {}).get("value"),
                }
                for m in pr.get("baseline_metric_ids", []) if m in metrics
            ],
            "mandatory_controls": sorted({
                names[c]["name"] for st in steps for c in st.get("control_ids", [])
                if c in names and names[c].get("mandatory", True)
            }),
            "ist_steps": [step_view(graph, st, names) for st in steps],
            "signals": rl.redesign_signals(graph, pr["id"]),
            "scenarios_todo": [
                {"scenario": s, "label": rl.SCENARIO_LABEL[s], "status": "offen"}
                for s in rl.SCENARIO_ORDER
                if not any(b.get("process_id") == pr["id"] and b.get("scenario") == s
                           for b in graph["blueprints"])
            ],
        }
        todo.append(entry)
    return todo


def briefing(todo: list[dict[str, Any]]) -> str:
    out = ["# Redesign-Briefing", "",
           "Je Prozess: Ist-Fluss, Ausgangswerte und die maschinell erkannten Ansatzpunkte.",
           "Die Spalte „Operator\" ist ein Vorschlag, keine Entscheidung.", ""]
    for e in todo:
        out.append(f"## {e['process']}")
        out.append("")
        out.append(f"**Auslöser:** {e['trigger']}  ")
        out.append(f"**Ergebnis:** {e['outcome']} (für: {e['beneficiary'] or 'nicht benannt'})  ")
        out.append(f"**Owner:** {e['owner_role'] or 'nicht benannt'}  ")
        vol = e["volume_per_year"]
        out.append(f"**Menge:** {int(vol) if vol else 'unbekannt'} Fälle/Jahr  ")
        t = e["ist_totals"]
        fte = e["fte_equivalent"]
        out.append(f"**Ist:** {t['steps']} Schritte, {t['human_touches']} Human Touchpoints, "
                   f"{t['handovers']} Übergaben, {t['lead_time_hours']} h Durchlaufzeit "
                   f"({t['handling_time_min']} min Arbeit, {t['wait_time_min']} min Warten), "
                   f"{t['rework_pct']} % Nacharbeit"
                   + (f", rund {fte} VZÄ menschliche Arbeit" if fte is not None else ""))
        out.append("")
        if e["baseline_metrics"]:
            out.append("| Kennzahl | Art | Ausgangswert | Belastbarkeit | Ziel |")
            out.append("|---|---|---|---|---|")
            for m in e["baseline_metrics"]:
                basis = {"observed": "gemessen", "expert_confirmed": "bestätigt",
                         "estimated": "geschätzt"}.get(m["basis"], "—")
                out.append(f"| {m['metric']} | {m['kind']} | {m['baseline']} {m['unit'] or ''} "
                           f"| {basis} | {m['target'] if m['target'] is not None else '—'} |")
            out.append("")
        out.append("### Ist-Fluss")
        out.append("")
        out.append("| # | Schritt | Wer | Arbeit | Warten | Nacharbeit | Wertbeitrag | Kontrollen |")
        out.append("|---|---|---|---|---|---|---|---|")
        for i, s in enumerate(e["ist_steps"], start=1):
            who = f"{s['executor']['type']}" + (f" ({s['executor']['name']})" if s["executor"]["name"] else "")
            out.append(f"| {i} | {s['name']} | {who} | {s['handling_time_min']} min "
                       f"| {s['wait_time_min']} min | {s['rework_pct']} % "
                       f"| {rl.VALUE_TYPE_LABEL.get(s['value_type'], '—')} "
                       f"| {', '.join(c for c in s['controls'] if c) or '—'} |")
        out.append("")
        if e["mandatory_controls"]:
            out.append("**Pflichtkontrollen, die jeder Blueprint adressieren muss:** "
                       + ", ".join(e["mandatory_controls"]))
            out.append("")
        out.append("### Erkannte Ansatzpunkte")
        out.append("")
        if not e["signals"]:
            out.append("Keine — der Ist-Prozess zeigt keine strukturellen Auffälligkeiten. "
                       "Das heißt nicht, dass es kein Redesign gibt; es heißt, dass die Daten "
                       "keines nahelegen.")
        else:
            out.append("| Operator | Befund |")
            out.append("|---|---|")
            for s in e["signals"]:
                out.append(f"| {rl.OPERATOR_LABEL.get(s['operator'], s['operator'])} | {s['finding']} |")
        out.append("")
        offen = ", ".join(s["label"] for s in e["scenarios_todo"])
        out.append(f"**Noch zu entwerfen:** {offen or 'nichts, alle drei Szenarien liegen vor'}")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--process", default="", help="nur diesen Prozess (ID oder Name)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph["processes"]:
        wl.fail("Keine Prozesse im Graphen. Zuerst Prozesse extrahieren und "
                "work-graph-builder/scripts/build_processes.py laufen lassen "
                "(Format: references/process-format.md)")
    todo = build_todo(graph, args.process)
    if not todo:
        wl.fail(f"Kein Prozess passt auf --process {args.process!r}")
    version = int(graph.get("meta", {}).get("version", 0))
    out_todo = project / wl.DIR_GRAPH / "redesign_todo.json"
    wl.write_json(out_todo, todo)
    out_md = project / wl.DIR_REVIEW / f"redesign_briefing_v{version:03d}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(out_md, briefing(todo))
    offen = sum(len(e["scenarios_todo"]) for e in todo)
    print(f"Geschrieben: {wl.relpath(out_todo)}, {wl.relpath(out_md)} | "
          f"Prozesse={len(todo)} offene Szenarien={offen} "
          f"Signale={sum(len(e['signals']) for e in todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
