#!/usr/bin/env python3
"""
build_blueprints.py — übernimmt die Soll-Entwürfe aus 20_graph/blueprints.json,
vergibt deterministische IDs, löst Namen auf IDs auf, rechnet die Soll-Kennzahlen
und das Delta gegen den Ist-Prozess aus und schreibt eine neue Graph-Version
(Stage "redesign").

Aufruf:
    python3 <skill>/scripts/build_blueprints.py --project ./mein-projekt

Eingabeformat 20_graph/blueprints.json: siehe references/blueprint-format.md.

Arbeitsteilung wie überall in der Suite: Der Entwurf ist ein Urteil und kommt von
Claude beziehungsweise von Fachleuten. Alles, was sich daraus ausrechnen lässt —
Durchlaufzeit, Human Touchpoints, Übergaben, Deltas, Vollständigkeit gegenüber dem
Ist-Prozess — rechnet dieses Skript, damit niemand ein Delta von Hand schönschreibt.

Vollständigkeitsregel: Jeder Ist-Schritt muss im Blueprint vorkommen — entweder als
Vorläufer eines Soll-Schrittes (`from_steps`) oder ausdrücklich unter `removed_steps`.
Ein Schritt, der einfach verschwindet, ist der häufigste Weg, ein Redesign schönzurechnen.
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


def _str(x: Any, default: str = "") -> str:
    return str(x).strip() if x is not None else default


def _num(x, default=None):
    if x is None or x == "" or isinstance(x, bool):
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _enum(value, allowed, default):
    v = _str(value)
    return v if v in allowed else default


def _signed(value, suffix: str = "") -> str:
    """Vorzeichenbehaftete Zahl für die Zusammenfassung, oder ein Strich.

    delta() liefert keinen Prozentwert, wenn der Ist-Wert 0 ist — durch 0 lässt sich keine
    Veränderung ausdrücken. Das ist ein gültiger Fall (ein Prozess ohne erfasste Zeiten),
    und er darf die Ausgabe nicht sprengen: Der Graph ist an dieser Stelle längst
    geschrieben, ein Absturz hier würde nur den Eindruck erwecken, der Lauf sei gescheitert.
    """
    if value is None:
        return "–"
    return f"{value:+g}{suffix}"


def build(graph: dict[str, Any], raw: list) -> tuple[list, list, list]:
    problems: list[str] = []
    proposed_agents: list[str] = []
    processes = {wl.normalize_name(p["name"]): p for p in graph["processes"]}
    processes.update({p["id"]: p for p in graph["processes"]})
    agents_by_name = {wl.normalize_name(a["name"]): a["id"] for a in graph["agents"]}
    roles_by_name = {wl.normalize_name(r["name"]): r["id"] for r in graph["roles"]}
    systems_by_name = {wl.normalize_name(s["name"]): s["id"] for s in graph["systems"]}
    controls_by_name = {wl.normalize_name(c["name"]): c["id"] for c in graph["controls"]}
    metrics_by_name: dict[tuple, str] = {}
    for m in graph["metrics"]:
        metrics_by_name[(m.get("process_id"), wl.normalize_name(m["name"]))] = m["id"]

    # Über den Status eines Blueprints entscheidet das Entscheidungslog
    # (30_review/decisions.csv), nicht die Entwurfsdatei. Für jeden Blueprint, zu dem
    # eine Entscheidung vorliegt, gilt deshalb der Stand aus dem Graphen — sonst würde
    # dieser Lauf jede Freigabe still auf "draft" oder "reviewed" zurückdrehen.
    prev_blueprints = wl.index_by_id(graph.get("blueprints", []))
    decided = {d.get("subject_id") for d in graph.get("decisions", [])
               if d.get("subject_type") == "blueprints"}

    blueprints: list[dict[str, Any]] = []
    for entry in sorted(raw, key=lambda e: (_str(e.get("process")), _str(e.get("scenario")))):
        pname = _str(entry.get("process")) or _str(entry.get("process_id"))
        proc = processes.get(wl.normalize_name(pname)) or processes.get(pname)
        if proc is None:
            problems.append(f"Blueprint für unbekannten Prozess {pname!r} übersprungen")
            continue
        scenario = _enum(entry.get("scenario"), wl.ENUM_SCENARIO, "")
        if not scenario:
            problems.append(f"{pname}: scenario {entry.get('scenario')!r} ungültig "
                            f"(erlaubt: {', '.join(wl.ENUM_SCENARIO)}), übersprungen")
            continue
        where = f"{proc['name']} / {rl.SCENARIO_LABEL[scenario]}"
        bid = wl.make_id("blueprint", proc["name"], scenario)
        ist_steps = wl.steps_of(graph, proc["id"])
        ist_by_name = {wl.normalize_name(s["name"]): s["id"] for s in ist_steps}
        ist_ids = {s["id"] for s in ist_steps}

        def ist_step(name: str) -> str | None:
            n = _str(name)
            if n in ist_ids:
                return n
            sid = ist_by_name.get(wl.normalize_name(n))
            if sid is None:
                problems.append(f"{where}: Ist-Schritt {n!r} gibt es im Prozess nicht")
            return sid

        steps_out = []
        used_from: set = set()
        agent_ids: set = set()
        bp_proposed: list = []
        for i, st in enumerate(entry.get("steps", [])):
            sname = _str(st.get("name"))
            if not sname:
                problems.append(f"{where}: Schritt {i + 1} ohne Namen übersprungen")
                continue
            sw = f"{where} / {sname}"
            ex_raw = st.get("executor")
            if isinstance(ex_raw, str):
                ex_raw = {"type": ex_raw}
            ex_raw = ex_raw or {}
            etype = _enum(ex_raw.get("type"), wl.ENUM_EXECUTOR, "human")
            ename = _str(ex_raw.get("name")) or _str(ex_raw.get("id"))
            eid = None
            if etype == "agent" and ename:
                eid = agents_by_name.get(wl.normalize_name(ename))
                if eid is None:
                    # Ein Redesign darf Agenten vorschlagen, die es noch nicht gibt.
                    # Sie bleiben ohne ID, bis sie über agents.json angelegt sind.
                    bp_proposed.append(ename)
                    proposed_agents.append(ename)
                else:
                    agent_ids.add(eid)
            elif etype == "human" and ename:
                eid = roles_by_name.get(wl.normalize_name(ename))
                if eid is None:
                    problems.append(f"{sw}: Rolle {ename!r} unbekannt")
            elif etype == "system" and ename:
                eid = systems_by_name.get(wl.normalize_name(ename))
                if eid is None:
                    problems.append(f"{sw}: System {ename!r} unbekannt")

            from_ids = sorted({x for x in (ist_step(n) for n in st.get("from_steps", [])) if x})
            used_from.update(from_ids)
            hg = st.get("human_gate")
            human_gate = None
            if isinstance(hg, dict) and (hg.get("when") or hg.get("role")):
                rid = roles_by_name.get(wl.normalize_name(_str(hg.get("role"))))
                if rid is None and _str(hg.get("role")):
                    problems.append(f"{sw}: human_gate.role {hg.get('role')!r} unbekannt")
                human_gate = {"when": _str(hg.get("when")), "role_id": rid}

            mid = None
            if _str(st.get("metric")):
                mid = metrics_by_name.get((proc["id"], wl.normalize_name(_str(st.get("metric")))))
                if mid is None:
                    problems.append(f"{sw}: Kennzahl {st.get('metric')!r} gibt es im Prozess nicht")

            steps_out.append({
                "step_id": wl.make_id("process_step", proc["name"] + "|" + scenario, sname),
                "name": sname,
                "operator": _enum(st.get("operator"), wl.ENUM_OPERATOR, "simplify"),
                "from_step_ids": from_ids,
                "is_new": not from_ids,
                "executor": {"type": etype, "id": eid, "name": ename or None},
                "system_ids": sorted({systems_by_name[wl.normalize_name(_str(x))]
                                      for x in st.get("systems", [])
                                      if wl.normalize_name(_str(x)) in systems_by_name}),
                "control_ids": sorted({controls_by_name[wl.normalize_name(_str(x))]
                                       for x in st.get("controls", [])
                                       if wl.normalize_name(_str(x)) in controls_by_name}),
                "handling_time_min": _num(st.get("handling_time_min"), 0.0),
                "wait_time_min": _num(st.get("wait_time_min"), 0.0),
                "rework_pct": _num(st.get("rework_pct")),
                "parallel_group": _str(st.get("parallel_group")) or None,
                "human_gate": human_gate,
                "rationale": _str(st.get("rationale")),
                "metric_id": mid,
                "assumption": _str(st.get("assumption")),
            })

        # Gestrichene Schritte tragen ihre eigene Begründung. Kurzform (nur der Name)
        # wird akzeptiert, bleibt aber ohne Begründung — validate_blueprints.py meldet das.
        removals = []
        for r in entry.get("removed_steps", []) or []:
            if isinstance(r, str):
                r = {"step": r}
            if not isinstance(r, dict):
                continue
            sid = ist_step(r.get("step") or r.get("step_id"))
            if sid is None:
                continue
            mid = None
            if _str(r.get("metric")):
                mid = metrics_by_name.get((proc["id"], wl.normalize_name(_str(r.get("metric")))))
                if mid is None:
                    problems.append(f"{where}: gestrichener Schritt — Kennzahl "
                                    f"{r.get('metric')!r} gibt es im Prozess nicht")
            removals.append({
                "step_id": sid,
                "operator": "eliminate",
                "rationale": _str(r.get("rationale")),
                "metric_id": mid,
                "assumption": _str(r.get("assumption")),
                "replacement": _str(r.get("replacement")),
            })
        removals.sort(key=lambda r: r["step_id"])
        removed = sorted({r["step_id"] for r in removals})

        # Vollständigkeit: Jeder Ist-Schritt ist entweder übernommen oder gestrichen.
        unaccounted = sorted(ist_ids - used_from - set(removed))
        if unaccounted:
            names = ", ".join(next(s["name"] for s in ist_steps if s["id"] == x) for x in unaccounted)
            problems.append(f"{where}: Ist-Schritte weder übernommen noch gestrichen: {names}. "
                            "Jeder Ist-Schritt gehört in from_steps eines Soll-Schrittes oder "
                            "in removed_steps")

        cov_raw = entry.get("control_coverage") or {}

        def cid(name):
            c = controls_by_name.get(wl.normalize_name(_str(name)))
            if c is None and _str(name):
                problems.append(f"{where}: Kontrolle {name!r} unbekannt")
            return c

        coverage = {
            "retained_control_ids": sorted({c for c in (cid(x) for x in cov_raw.get("retained", [])) if c}),
            "dropped_control_ids": sorted({c for c in (cid(x) for x in cov_raw.get("dropped", [])) if c}),
            "replaced": [],
        }
        for r in cov_raw.get("replaced", []) or []:
            if not isinstance(r, dict):
                continue
            c = cid(r.get("control"))
            if c is None:
                continue
            coverage["replaced"].append({
                "control_id": c,
                "replacement": _str(r.get("replacement")),
                "rationale": _str(r.get("rationale")),
                "approved_by": _str(r.get("approved_by")),
            })
        coverage["replaced"].sort(key=lambda r: r["control_id"])

        projected_metrics = []
        for pm in entry.get("projected_metrics", []) or []:
            mid = metrics_by_name.get((proc["id"], wl.normalize_name(_str(pm.get("metric")))))
            if mid is None:
                problems.append(f"{where}: projected_metrics — Kennzahl {pm.get('metric')!r} unbekannt")
                continue
            projected_metrics.append({
                "metric_id": mid,
                "value": _num(pm.get("value")),
                "basis": _enum(pm.get("basis"), wl.ENUM_VALUE_BASIS, "estimated"),
            })
        projected_metrics.sort(key=lambda m: m["metric_id"])

        bp = {
            "id": bid,
            "process_id": proc["id"],
            "scenario": scenario,
            "name": _str(entry.get("name")) or f"{proc['name']} — {rl.SCENARIO_LABEL[scenario]}",
            "summary": _str(entry.get("summary")),
            "outcome_id": proc.get("outcome_id"),
            "steps": steps_out,
            "removed_step_ids": removed,
            "removed_steps": removals,
            "agent_ids": sorted(agent_ids),
            "proposed_agents": sorted(set(bp_proposed)),
            "control_coverage": coverage,
            "projected_metrics": projected_metrics,
            "open_assumptions": [_str(a) for a in entry.get("open_assumptions", []) if _str(a)],
            "risks": [_str(r) for r in entry.get("risks", []) if _str(r)],
            "status": (prev_blueprints[bid].get("status")
                       if bid in decided and bid in prev_blueprints
                       else _enum(entry.get("status"), wl.ENUM_BLUEPRINT_STATUS, "draft")),
        }
        if _str(entry.get("outcome_change_rationale")):
            bp["outcome_change_rationale"] = _str(entry["outcome_change_rationale"])

        ist_totals = wl.process_totals(graph, proc["id"])
        soll_totals = rl.blueprint_totals(bp)
        bp["ist_totals"] = ist_totals
        bp["soll_totals"] = soll_totals
        bp["delta"] = rl.delta(ist_totals, soll_totals)
        counts = {op: sum(1 for s in steps_out if s["operator"] == op) for op in wl.ENUM_OPERATOR}
        counts["eliminate"] = len(removals)
        bp["operator_counts"] = counts
        hmin = wl.round1(sum(float(s.get("handling_time_min") or 0) for s in steps_out
                             if wl.step_has_human(s)))
        bp["human_minutes_per_case"] = hmin
        bp["fte_equivalent"] = rl.fte_equivalent(hmin, proc.get("volume_per_year"))
        blueprints.append(bp)

    # Blueprints, deren Prozess nicht mehr existiert, verschwinden mit ihm.
    blueprints.sort(key=lambda b: b["id"])
    return blueprints, problems, sorted(set(proposed_agents))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    src = project / wl.DIR_GRAPH / "blueprints.json"
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt (zuerst export_process_candidates.py, dann Szenarien "
                "entwerfen — Format: references/blueprint-format.md)")
    raw = wl.read_json(src)
    if not isinstance(raw, list):
        wl.fail("blueprints.json muss eine Liste sein")

    blueprints, problems, proposed = build(graph, raw)
    graph["blueprints"] = blueprints
    for p in problems:
        print(f"HINWEIS  {p}")
    if proposed:
        print(f"HINWEIS  Vorgeschlagene, noch nicht angelegte Agenten: {', '.join(proposed)}. "
              "In 20_graph/agents.json ergänzen und agent-mapper/scripts/compute_coverage.py "
              "laufen lassen, dann wird der Blueprint mit Agenten-IDs verknüpft.")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "redesign")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Blueprints={len(blueprints)}")
    for bp in blueprints:
        d = bp["delta"]
        print(f"  {bp['name']}: {bp['soll_totals']['steps']} Schritte "
              f"({_signed(d.get('steps', {}).get('improvement'))}), "
              f"{bp['soll_totals']['human_touches']} Human Touchpoints "
              f"({_signed(d.get('human_touches', {}).get('improvement'))}), Durchlaufzeit "
              f"{bp['soll_totals']['lead_time_hours']} h "
              f"({_signed(d.get('lead_time_hours', {}).get('improvement_pct'), suffix=' %')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
