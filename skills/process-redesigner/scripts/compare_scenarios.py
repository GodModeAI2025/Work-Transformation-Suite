#!/usr/bin/env python3
"""
compare_scenarios.py — stellt Ist-Prozess und Soll-Szenarien nebeneinander und
schreibt den Vergleich als Markdown und CSV nach 40_output/.

Aufruf:
    python3 <skill>/scripts/compare_scenarios.py --project ./mein-projekt [--process pr_…]

Ausgaben (NNN = Graph-Version):
    40_output/scenarios_vNNN.md     Vergleich je Prozess, Schritt für Schritt
    40_output/scenarios_vNNN.csv    dieselben Kennzahlen maschinenlesbar

Jede Zahl im Vergleich stammt aus den Soll-Schritten des Blueprints, nicht aus einer
Zusage. Wo eine Zahl geschätzt ist, steht das dabei. Ein Delta ohne sichtbare
Belastbarkeit ist in einer Transformationsdiskussion gefährlicher als gar keins.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import redesign_lib as rl  # noqa: E402

BASIS_LABEL = {"observed": "gemessen", "expert_confirmed": "bestätigt", "estimated": "geschätzt"}
METRIC_LABEL = {
    "steps": "Schritte",
    "human_touches": "Human Touchpoints",
    "handovers": "Übergaben",
    "handling_time_min": "Bearbeitungszeit (min)",
    "wait_time_min": "Wartezeit (min)",
    "lead_time_hours": "Durchlaufzeit (h)",
    "rework_pct": "Nacharbeit (%)",
    "automated_steps": "automatisierte Schritte",
}
ROW_ORDER = ["steps", "human_touches", "handovers", "handling_time_min", "wait_time_min",
             "lead_time_hours", "rework_pct", "automated_steps"]


def _names(graph: dict[str, Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for c in wl.COLLECTIONS:
        for it in graph.get(c, []):
            out[it["id"]] = it
    return out


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x)


def _signed(x) -> str:
    if x is None:
        return "—"
    v = int(x) if isinstance(x, float) and x == int(x) else x
    return f"{v:+g}" if isinstance(v, (int, float)) else str(v)


def report(graph: dict[str, Any], only: str = "") -> tuple[str, list[dict]]:
    names = _names(graph)
    rows: list[dict] = []
    out = ["# Ist und Soll im Vergleich", "",
           "Je Prozess: der heutige Ablauf, die entworfenen Szenarien und was sich zwischen "
           "ihnen tatsächlich ändert. Alle Soll-Zahlen sind aus den Schritten des jeweiligen "
           "Blueprints gerechnet, nicht zugesagt.", ""]
    by_process: dict[str, list[dict]] = {}
    for bp in graph["blueprints"]:
        by_process.setdefault(bp["process_id"], []).append(bp)

    for pr in sorted(graph["processes"], key=lambda p: p["id"]):
        if only and pr["id"] != only and wl.normalize_name(pr["name"]) != wl.normalize_name(only):
            continue
        bps = sorted(by_process.get(pr["id"], []),
                     key=lambda b: rl.SCENARIO_ORDER.index(b["scenario"])
                     if b.get("scenario") in rl.SCENARIO_ORDER else 9)
        out.append(f"## {pr['name']}")
        out.append("")
        out.append(f"**Ergebnis:** {names.get(pr.get('outcome_id'), {}).get('name', '—')}  ")
        vol = pr.get("volume_per_year")
        out.append(f"**Menge:** {int(vol) if vol else 'unbekannt'} Fälle/Jahr")
        out.append("")
        if not bps:
            out.append("Noch kein Szenario entworfen.")
            out.append("")
            continue

        ist = wl.process_totals(graph, pr["id"])
        header = "| Kennzahl | Ist | " + " | ".join(rl.SCENARIO_LABEL[b["scenario"]] for b in bps) + " |"
        out.append(header)
        out.append("|" + "---|" * (2 + len(bps)))
        for key in ROW_ORDER:
            cells = []
            for b in bps:
                soll = b["soll_totals"].get(key)
                imp = (b["delta"].get(key) or {}).get("improvement")
                cells.append(f"{_fmt(soll)} ({_signed(imp)})")
            out.append(f"| {METRIC_LABEL[key]} | {_fmt(ist.get(key))} | " + " | ".join(cells) + " |")
        fte_cells = []
        for b in bps:
            f = b.get("fte_equivalent")
            fte_cells.append(_fmt(f) if f is not None else "—")
        ist_fte = rl.fte_equivalent(rl.human_minutes_per_case(graph, pr["id"]), vol)
        out.append(f"| Menschliche Arbeit (VZÄ) | {_fmt(ist_fte)} | " + " | ".join(fte_cells) + " |")
        out.append("")
        out.append("Der Wert in Klammern ist die Verbesserung gegenüber dem Ist "
                   "(positiv heißt immer besser, unabhängig von der Richtung der Kennzahl).")
        out.append("")

        for b in bps:
            out.append(f"### {rl.SCENARIO_LABEL[b['scenario']]}: {b['name']}")
            out.append("")
            if b.get("summary"):
                out.append(b["summary"])
                out.append("")
            ops = ", ".join(f"{rl.OPERATOR_LABEL[o]} {n}×"
                            for o, n in sorted((b.get("operator_counts") or {}).items()) if n)
            out.append(f"**Angewandte Operatoren:** {ops or '—'}  ")
            out.append(f"**Status:** {b.get('status', 'draft')}")
            out.append("")
            out.append("| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |")
            out.append("|---|---|---|---|---|---|")
            for i, st in enumerate(b.get("steps", []), start=1):
                ex = st.get("executor") or {}
                who = ex.get("type") or "—"
                label = ex.get("name") or names.get(ex.get("id"), {}).get("name")
                if label:
                    who += f" ({label})"
                froms = ", ".join(names.get(f, {}).get("name", f) for f in st.get("from_step_ids", []))
                gate = " · Human Gate: " + st["human_gate"]["when"] if st.get("human_gate") else ""
                out.append(f"| {i} | {st['name']} | {rl.OPERATOR_LABEL.get(st['operator'], st['operator'])} "
                           f"| {who} | {froms or 'neu'} | {st.get('rationale', '')}{gate} |")
            out.append("")
            if b.get("removed_steps"):
                out.append("**Gestrichene Schritte**")
                out.append("")
                out.append("| Ist-Schritt | Begründung | Ersatz |")
                out.append("|---|---|---|")
                for r in b["removed_steps"]:
                    out.append(f"| {names.get(r['step_id'], {}).get('name', r['step_id'])} "
                               f"| {r.get('rationale', '')} | {r.get('replacement') or '—'} |")
                out.append("")
            cov = b.get("control_coverage") or {}
            if cov.get("replaced") or cov.get("dropped_control_ids"):
                out.append("**Veränderte Kontrollen**")
                out.append("")
                out.append("| Kontrolle | Wie | Ersatz | Freigabe |")
                out.append("|---|---|---|---|")
                for r in cov.get("replaced", []):
                    out.append(f"| {names.get(r['control_id'], {}).get('name', r['control_id'])} "
                               f"| ersetzt | {r.get('replacement', '')} | {r.get('approved_by') or '—'} |")
                for c in cov.get("dropped_control_ids", []):
                    out.append(f"| {names.get(c, {}).get('name', c)} | gestrichen | — | — |")
                out.append("")
            pm = b.get("projected_metrics") or []
            if pm:
                out.append("**Zugesagte Kennzahlen**")
                out.append("")
                out.append("| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |")
                out.append("|---|---|---|---|")
                metrics = wl.index_by_id(graph["metrics"])
                for m in pm:
                    met = metrics.get(m["metric_id"], {})
                    base, base_basis = wl.metric_value(met, "baseline") if met else (None, None)
                    out.append(f"| {met.get('name', m['metric_id'])} "
                               f"| {_fmt(base)} ({BASIS_LABEL.get(base_basis, '—')}) "
                               f"| {_fmt(m.get('value'))} | {BASIS_LABEL.get(m.get('basis'), '—')} |")
                out.append("")
            if b.get("open_assumptions"):
                out.append("**Offene Annahmen**")
                out.append("")
                for a in b["open_assumptions"]:
                    out.append(f"- {a}")
                out.append("")
            if b.get("risks"):
                out.append("**Risiken**")
                out.append("")
                for r in b["risks"]:
                    out.append(f"- {r}")
                out.append("")
            if b.get("proposed_agents"):
                out.append("**Noch anzulegende Agenten:** " + ", ".join(b["proposed_agents"]))
                out.append("")

            row = {"process": pr["name"], "scenario": b["scenario"],
                   "scenario_label": rl.SCENARIO_LABEL[b["scenario"]], "blueprint": b["name"],
                   "status": b.get("status")}
            for key in ROW_ORDER:
                row[f"ist_{key}"] = ist.get(key)
                row[f"soll_{key}"] = b["soll_totals"].get(key)
                row[f"delta_{key}"] = (b["delta"].get(key) or {}).get("improvement")
            row["ist_fte"] = ist_fte
            row["soll_fte"] = b.get("fte_equivalent")
            rows.append(row)
    return "\n".join(out) + "\n", rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--process", default="")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph["blueprints"]:
        wl.fail("Keine Blueprints im Graphen (zuerst build_blueprints.py)")
    md, rows = report(graph, args.process)
    version = int(graph.get("meta", {}).get("version", 0))
    outdir = project / wl.DIR_OUTPUT
    md_path = outdir / f"scenarios_v{version:03d}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(md_path, md)
    csv_path = outdir / f"scenarios_v{version:03d}.csv"
    fields = list(rows[0].keys()) if rows else ["process"]
    wl.write_csv(csv_path, rows, fields)
    print(f"Geschrieben: {wl.relpath(md_path)}, {wl.relpath(csv_path)} | "
          f"Szenarien={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
