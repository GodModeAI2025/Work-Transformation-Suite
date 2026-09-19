#!/usr/bin/env python3
"""
make_experiments.py — macht aus einem Blueprint einen messbaren Pilot.

Aufruf:
    python3 <skill>/scripts/make_experiments.py --project ./mein-projekt [--force]

Fehlt 20_graph/experiments.json, schreibt das Skript eine vorbefüllte Vorlage nach
20_graph/experiments_todo.json (je freigegebenem oder geprüftem Blueprint eine Karte mit
vorgeschlagenem Design, Laufzeit, Guardrails und Stoppregeln) und hält mit Exit-Code 3 an.

Warum nicht überall A/B: Ein A/B-Test braucht gleichartige Fälle, ausreichend Menge und
die Freiheit, einen Teil der Fälle anders zu behandeln. Bei Personal- und Finanzprozessen
ist mindestens eine dieser Bedingungen oft nicht erfüllt. Deshalb kennt die Suite vier
Designs — A/B, Schattenbetrieb, gestaffelter Rollout und Vorher-Nachher — und schlägt
deterministisch das vor, das zur Menge und zur Reichweite der Entscheidungen passt.

Ergebnisse: Trägt eine Karte `results`, schreibt das Skript die gemessenen Werte als
`observed` auf die betroffenen Kennzahlen zurück — samt Provenienz-Eintrag. Erst damit
wird aus einer Schätzung eine Messung, und der Unterschied bleibt im Graphen sichtbar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import redesign_lib as rl  # noqa: E402
from validate_graph import validate  # noqa: E402

# Anteil der Fälle, die ein Design tatsächlich berührt. Grundlage der Mengenabschätzung.
EXPOSURE = {"ab_test": 0.5, "shadow": 1.0, "stepped_rollout": 0.2, "pre_post": 1.0}
DEFAULT_DURATION_DAYS = 42  # sechs Wochen: lang genug für Wocheneffekte, kurz genug für eine Entscheidung
AB_MIN_VOLUME = 2000
STEPPED_MIN_VOLUME = 200
DESIGN_LABEL = {
    "ab_test": "A/B-Test",
    "shadow": "Schattenbetrieb",
    "stepped_rollout": "gestaffelter Rollout",
    "pre_post": "Vorher-Nachher",
}


def _str(x, default=""):
    return str(x).strip() if x is not None else default


def _num(x, default=None):
    if x is None or x == "" or isinstance(x, bool):
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def suggest_design(graph: dict[str, Any], proc: dict[str, Any], bp: dict[str, Any]) -> str:
    """Deterministischer Designvorschlag aus Menge, Regulierung und Entscheidungsreichweite."""
    irreversible = any((s.get("decision") or {}).get("scope") == "execute_irreversible"
                       for s in wl.steps_of(graph, proc["id"]))
    if irreversible or proc.get("regulated") or bp.get("scenario") == "agent_native":
        return "shadow"
    vol = _num(proc.get("volume_per_year"), 0.0) or 0.0
    if vol >= AB_MIN_VOLUME:
        return "ab_test"
    if vol >= STEPPED_MIN_VOLUME:
        return "stepped_rollout"
    return "pre_post"


def exposure_estimate(proc: dict[str, Any], design: str, days: int) -> int | None:
    """Wie viele Fälle das Design in der Laufzeit berührt.

    Ausdrücklich eine Mengenabschätzung, keine Fallzahlplanung. Eine echte Power-Rechnung
    bräuchte die Streuung der Ausgangskennzahl; die liegt in der Suite nicht vor. Diese
    Zahl sagt nur, ob überhaupt genug Fälle zusammenkommen, um etwas zu sehen.
    """
    vol = _num(proc.get("volume_per_year"))
    if vol is None or vol <= 0:
        return None
    return max(1, int(round(vol * days / 365.0 * EXPOSURE.get(design, 1.0))))


def template(graph: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = wl.index_by_id(graph["metrics"])
    processes = wl.index_by_id(graph["processes"])
    roles = wl.index_by_id(graph["roles"])
    rows = []
    for bp in sorted(graph["blueprints"], key=lambda b: b["id"]):
        if bp.get("status") not in ("reviewed", "approved"):
            continue
        proc = processes.get(bp["process_id"])
        if proc is None:
            continue
        design = suggest_design(graph, proc, bp)
        own = [metrics[m] for m in proc.get("baseline_metric_ids", []) if m in metrics]
        primary = next((m for m in own if m["kind"] in ("outcome", "time", "cost")), own[0] if own else None)
        guardrails = [m for m in own if m["kind"] in ("quality", "risk") and (not primary or m["id"] != primary["id"])]
        target = None
        for pm in bp.get("projected_metrics", []):
            if primary and pm["metric_id"] == primary["id"]:
                target = pm.get("value")
        rows.append({
            "process": proc["name"],
            "blueprint_scenario": bp["scenario"],
            "name": f"Pilot {proc['name']} — {rl.SCENARIO_LABEL[bp['scenario']]}",
            "hypothesis": "",
            "design": design,
            "_design_begruendung": _design_reason(graph, proc, bp, design),
            "population": "",
            "control_group": "" if design != "ab_test" else "zufällige Hälfte der eingehenden Fälle",
            "comparison_period": "" if design != "pre_post" else "gleicher Zeitraum des Vorjahres",
            "duration_days": DEFAULT_DURATION_DAYS,
            "sample_size": exposure_estimate(proc, design, DEFAULT_DURATION_DAYS),
            "primary_metric": primary["name"] if primary else "",
            "target_value": target,
            "guardrail_metrics": [
                {"metric": m["name"],
                 "limit": (m.get("baseline") or {}).get("value"),
                 "direction": "max" if m.get("direction") == "lower_is_better" else "min"}
                for m in guardrails
            ],
            "stop_rules": [
                "Guardrail verletzt: Pilot sofort anhalten und auf den Ist-Prozess zurückschalten",
                "Ein Vorfall mit Kundenschaden: anhalten, Ursache klären, erst danach weiterlaufen",
            ],
            "rollback": "Fälle wieder vollständig über den Ist-Prozess führen; "
                        "im Pilot begonnene Fälle manuell nachbearbeiten",
            "owner_role": roles.get(proc.get("owner_role_id"), {}).get("name", ""),
            "status": "draft",
            "results": [],
        })
    return rows


def _design_reason(graph, proc, bp, design) -> str:
    vol = _num(proc.get("volume_per_year"))
    if design == "shadow":
        why = []
        if proc.get("regulated"):
            why.append("der Prozess steht unter Aufsicht")
        if any((s.get("decision") or {}).get("scope") == "execute_irreversible"
               for s in wl.steps_of(graph, proc["id"])):
            why.append("er enthält irreversible Entscheidungen")
        if bp.get("scenario") == "agent_native":
            why.append("das Szenario ist agent-nativ")
        return ("Schattenbetrieb vorgeschlagen, weil " + " und ".join(why)
                + ". Der Agent rechnet mit, entscheidet aber nichts.")
    if design == "ab_test":
        return (f"A/B-Test möglich: rund {int(vol)} Fälle im Jahr, keine Aufsicht, "
                "keine irreversiblen Entscheidungen.")
    if design == "stepped_rollout":
        return (f"Für einen A/B-Test zu wenig Menge ({int(vol) if vol else 'unbekannt'} Fälle/Jahr). "
                "Gestaffelt ausrollen, Team für Team, und nach jeder Stufe messen.")
    return ("Zu wenig Fälle für Gruppenvergleiche. Vorher-Nachher, mit ausdrücklichem "
            "Vergleichszeitraum und dem Hinweis, dass saisonale Effekte nicht ausgeschlossen sind.")


def build(graph: dict[str, Any], raw: list) -> tuple[list, list, list]:
    problems: list[str] = []
    observed_notes: list[str] = []
    processes = {wl.normalize_name(p["name"]): p for p in graph["processes"]}
    processes.update({p["id"]: p for p in graph["processes"]})
    roles_by_name = {wl.normalize_name(r["name"]): r["id"] for r in graph["roles"]}
    metrics = wl.index_by_id(graph["metrics"])
    metrics_by_name: dict[tuple, str] = {}
    for m in graph["metrics"]:
        metrics_by_name[(m.get("process_id"), wl.normalize_name(m["name"]))] = m["id"]

    experiments = []
    for entry in sorted(raw, key=lambda e: (_str(e.get("process")), _str(e.get("name")))):
        pname = _str(entry.get("process")) or _str(entry.get("process_id"))
        proc = processes.get(wl.normalize_name(pname)) or processes.get(pname)
        if proc is None:
            problems.append(f"Experiment für unbekannten Prozess {pname!r} übersprungen")
            continue
        scenario = _str(entry.get("blueprint_scenario"))
        bp = next((b for b in graph["blueprints"]
                   if b["process_id"] == proc["id"] and b["scenario"] == scenario), None)
        if scenario and bp is None:
            problems.append(f"{proc['name']}: kein Blueprint zum Szenario {scenario!r}")
        name = _str(entry.get("name")) or f"Pilot {proc['name']}"
        xid = wl.make_id("experiment", proc["name"], name)

        def mid_of(mname, where):
            m = metrics_by_name.get((proc["id"], wl.normalize_name(_str(mname))))
            if m is None and _str(mname):
                problems.append(f"{where}: Kennzahl {mname!r} gibt es im Prozess nicht")
            return m

        primary = mid_of(entry.get("primary_metric"), name)
        guardrails = []
        for g in entry.get("guardrail_metrics", []) or []:
            if isinstance(g, str):
                g = {"metric": g}
            m = mid_of(g.get("metric"), name)
            if m is None:
                continue
            guardrails.append({
                "metric_id": m,
                "limit": _num(g.get("limit")),
                "direction": "max" if _str(g.get("direction")) != "min" else "min",
            })
        guardrails.sort(key=lambda g: g["metric_id"])

        design = _str(entry.get("design"))
        if design not in wl.ENUM_EXPERIMENT_DESIGN:
            design = suggest_design(graph, proc, bp or {})
            problems.append(f"{name}: design {entry.get('design')!r} ungültig, auf "
                            f"'{design}' gesetzt")
        status = _str(entry.get("status")) or "draft"
        if status not in wl.ENUM_EXPERIMENT_STATUS:
            status = "draft"

        results = []
        for r in entry.get("results", []) or []:
            if not isinstance(r, dict):
                continue
            m = mid_of(r.get("metric"), f"{name} / results")
            if m is None:
                continue
            results.append({
                "metric_id": m,
                "value": _num(r.get("value")),
                "as_of": _str(r.get("as_of")),
                "note": _str(r.get("note")),
            })
        results.sort(key=lambda r: r["metric_id"])

        experiments.append({
            "id": xid,
            "process_id": proc["id"],
            "blueprint_id": bp["id"] if bp else None,
            "name": name,
            "hypothesis": _str(entry.get("hypothesis")),
            "design": design,
            "design_rationale": _str(entry.get("design_rationale")) or _design_reason(graph, proc, bp or {}, design),
            "population": _str(entry.get("population")),
            "control_group": _str(entry.get("control_group")),
            "comparison_period": _str(entry.get("comparison_period")),
            "duration_days": int(_num(entry.get("duration_days"), DEFAULT_DURATION_DAYS)),
            "sample_size": int(_num(entry.get("sample_size"),
                                    exposure_estimate(proc, design, int(_num(entry.get("duration_days"),
                                                                             DEFAULT_DURATION_DAYS))) or 1)),
            "primary_metric_id": primary,
            "target_value": _num(entry.get("target_value")),
            "guardrail_metric_ids": sorted({g["metric_id"] for g in guardrails}),
            "guardrails": guardrails,
            "stop_rules": [_str(x) for x in entry.get("stop_rules", []) if _str(x)],
            "rollback": _str(entry.get("rollback")),
            "owner_role_id": roles_by_name.get(wl.normalize_name(_str(entry.get("owner_role")))) or
                             _str(entry.get("owner_role_id")) or proc.get("owner_role_id"),
            "status": status,
            "results": results,
        })

        # Gemessene Werte zurück in den Graphen — mit Provenienz, sonst lehnt der Validator ab.
        if status in ("running", "stopped", "completed"):
            for r in results:
                if r["value"] is None:
                    continue
                m = metrics.get(r["metric_id"])
                if m is None:
                    continue
                m["observed"] = {"value": r["value"], "basis": "observed",
                                 "as_of": r["as_of"], "source": name}
                pvid = wl.make_id("provenance", "metrics", m["id"], "observed")
                graph["provenance"] = [p for p in graph["provenance"] if p["id"] != pvid] + [{
                    "id": pvid, "entity_type": "metrics", "entity_id": m["id"], "field": "observed",
                    "source_kind": "observation", "source_ref": name,
                    "locator": f"experiment {xid}", "author": name,
                    "reviewer": _str(entry.get("owner_role")), "confidence": 0.95,
                    "status": "verified" if _str(entry.get("owner_role")) else "asserted",
                    "as_of": r["as_of"],
                }]
                observed_notes.append(f"{m['name']}: {r['value']} {m.get('unit', '')} "
                                      f"als gemessen übernommen (aus {name})")
    experiments.sort(key=lambda x: x["id"])
    return experiments, problems, observed_notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / wl.DIR_GRAPH / "experiments.json"
    if not src.exists():
        rows = template(graph)
        if not rows:
            wl.fail("Kein Blueprint im Status 'reviewed' oder 'approved'. Ein Pilot wird für "
                    "einen entschiedenen Entwurf geplant, nicht für einen Entwurf im Entwurf.")
        todo = project / wl.DIR_GRAPH / "experiments_todo.json"
        wl.write_json(todo, rows)
        print(f"Geschrieben: {wl.relpath(todo)} | Vorschläge={len(rows)}")
        print(f"STOPP: {wl.relpath(src)} fehlt. Nächster Schritt: Hypothese, Zielgruppe und "
              "Stoppregeln in der Vorlage schärfen und als experiments.json speichern "
              "(Format: references/experiment-format.md).")
        return 3
    raw = wl.read_json(src)
    if not isinstance(raw, list):
        wl.fail("experiments.json muss eine Liste sein")
    experiments, problems, observed = build(graph, raw)
    graph["experiments"] = experiments
    for p in problems:
        print(f"HINWEIS  {p}")
    for o in observed:
        print(f"MESSUNG  {o}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "experiments")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Experimente={len(experiments)} "
          f"gemessene Werte übernommen={len(observed)}")
    for x in experiments:
        print(f"  {x['name']}: {DESIGN_LABEL.get(x['design'], x['design'])}, "
              f"{x['duration_days']} Tage, rund {x['sample_size']} Fälle, "
              f"{len(x['guardrails'])} Guardrails, Status {x['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
