#!/usr/bin/env python3
"""
validate_blueprints.py — prüft die Soll-Entwürfe gegen die Redesign-Regeln.

Aufruf:
    python3 <skill>/scripts/validate_blueprints.py --project ./mein-projekt [--quiet]

Exit-Code 0 = sauber, 1 = Warnungen, 2 = Fehler.

Abgrenzung zu validate_graph.py: Dort geht es um Struktur (existieren die Referenzen,
stimmen die Aufzählungswerte, ist jede Pflichtkontrolle adressiert). Hier geht es um die
fachliche Qualität des Redesigns — die Regeln aus references/redesign-rules.md:

- Passt der angewandte Operator zu dem, was der Schritt tatsächlich tut?
- Wird jede Änderung begründet, an einer Kennzahl festgemacht und mit ihrer Annahme benannt?
- Unterscheiden sich die drei Szenarien wirklich, oder ist es dreimal derselbe Entwurf?
- Bleibt „konservativ" wirklich konservativ (alle heutigen Kontrollen erhalten)?
- Sind die versprochenen Deltas mit den eigenen Soll-Schritten überhaupt erreichbar?

Diese Prüfung existiert, weil ein Redesign auf dem Papier immer gut aussieht. Sie soll
nicht klug sein, sondern unbequem an den Stellen, an denen Entwürfe erfahrungsgemäß
schönrechnen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import redesign_lib as rl  # noqa: E402

# Operatoren, bei denen eine betroffene Kennzahl zwingend ist: Sie versprechen eine
# messbare Wirkung. Ein Human Gate verspricht Kontrolle, keine Zahl.
METRIC_REQUIRED = {"simplify", "merge", "parallelize", "automate"}


def _name(graph: dict[str, Any], sid: str, default: str = "?") -> str:
    for c in wl.COLLECTIONS:
        for it in graph.get(c, []):
            if it.get("id") == sid:
                return it.get("name", default)
    return default


def check(graph: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    processes = wl.index_by_id(graph["processes"])
    metrics = wl.index_by_id(graph["metrics"])
    steps_ist = wl.index_by_id(graph["process_steps"])
    by_process: dict[str, list[dict]] = {}
    for bp in graph["blueprints"]:
        by_process.setdefault(bp.get("process_id", ""), []).append(bp)

    for bp in sorted(graph["blueprints"], key=lambda b: b["id"]):
        proc = processes.get(bp.get("process_id"))
        if proc is None:
            continue
        w = f"{proc['name']} / {rl.SCENARIO_LABEL.get(bp.get('scenario'), bp.get('scenario'))}"
        steps = bp.get("steps") or []

        # --- R1 Operator passt zum Schritt ---------------------------------
        groups: dict[str, list[str]] = {}
        for st in steps:
            sw = f"{w} / {st.get('name')}"
            op = st.get("operator")
            froms = st.get("from_step_ids") or []
            ex_type = (st.get("executor") or {}).get("type")

            if op == "simplify":
                if len(froms) != 1:
                    errors.append(f"{sw}: Operator 'simplify' braucht genau einen Vorläufer "
                                  f"(from_steps), hat {len(froms)}")
                elif froms[0] in steps_ist:
                    ist_h = float(steps_ist[froms[0]].get("handling_time_min") or 0)
                    soll_h = float(st.get("handling_time_min") or 0)
                    if soll_h >= ist_h and ist_h > 0:
                        errors.append(f"{sw}: 'simplify' ohne Wirkung — Bearbeitungszeit "
                                      f"{soll_h} min gegenüber {ist_h} min im Ist")
            elif op == "merge":
                if len(froms) < 2:
                    errors.append(f"{sw}: Operator 'merge' braucht mindestens zwei Vorläufer, "
                                  f"hat {len(froms)}")
                else:
                    ist_sum = sum(float(steps_ist[f].get("handling_time_min") or 0)
                                  for f in froms if f in steps_ist)
                    if float(st.get("handling_time_min") or 0) > ist_sum and ist_sum > 0:
                        errors.append(f"{sw}: 'merge' kostet mehr Arbeit als die zusammengelegten "
                                      f"Schritte ({st.get('handling_time_min')} > {wl.round1(ist_sum)} min)")
            elif op == "parallelize":
                if not st.get("parallel_group"):
                    errors.append(f"{sw}: Operator 'parallelize' ohne 'parallel_group' — ohne "
                                  "Gruppe lässt sich nicht ausrechnen, was gleichzeitig läuft")
            elif op == "automate":
                if ex_type == "human":
                    errors.append(f"{sw}: Operator 'automate', aber executor.type='human'")
                if not froms:
                    warnings.append(f"{sw}: 'automate' ohne Vorläufer — das ist ein neuer Schritt, "
                                    "kein automatisierter Ist-Schritt")
            elif op == "human_gate":
                if not st.get("human_gate") and ex_type != "human":
                    errors.append(f"{sw}: Operator 'human_gate' ohne human_gate und ohne "
                                  "menschlichen Ausführenden")

            if st.get("parallel_group"):
                groups.setdefault(st["parallel_group"], []).append(st.get("name", "?"))

            # --- R7 Begründung, Kennzahl, Annahme --------------------------
            if op in METRIC_REQUIRED and not st.get("metric_id"):
                errors.append(f"{sw}: Operator '{op}' ohne betroffene Kennzahl. Eine Änderung, "
                              "deren Wirkung an keiner Zahl hängt, lässt sich später nicht prüfen")
            if not st.get("assumption") and op in METRIC_REQUIRED:
                warnings.append(f"{sw}: keine Annahme benannt — woran scheitert diese Änderung?")
            if st.get("is_new") and not st.get("rationale"):
                errors.append(f"{sw}: neuer Schritt ohne Begründung")

        for grp, members in sorted(groups.items()):
            if len(members) < 2:
                errors.append(f"{w}: parallel_group {grp!r} hat nur einen Schritt "
                              f"({members[0]}) — das ist keine Parallelisierung")

        # --- R1b Streichungen ----------------------------------------------
        for r in bp.get("removed_steps") or []:
            sid = r.get("step_id")
            sname = _name(graph, sid)
            sw = f"{w} / gestrichen: {sname}"
            if not r.get("rationale"):
                errors.append(f"{sw}: Streichung ohne Begründung")
            ist = steps_ist.get(sid, {})
            if ist.get("value_type") == "customer_value":
                if not r.get("replacement"):
                    errors.append(f"{sw}: Schritt mit Kundenwert gestrichen, ohne zu sagen, "
                                  "wodurch der Kundennutzen künftig entsteht ('replacement')")
                if not r.get("assumption"):
                    warnings.append(f"{sw}: Schritt mit Kundenwert gestrichen, ohne Annahme")
            if ist.get("control_ids"):
                cov = bp.get("control_coverage") or {}
                handled = set(cov.get("retained_control_ids", [])) \
                    | {x.get("control_id") for x in cov.get("replaced", [])} \
                    | set(cov.get("dropped_control_ids", []))
                missing = [c for c in ist["control_ids"] if c not in handled]
                if missing:
                    errors.append(f"{sw}: trägt Kontrolle(n) "
                                  f"{', '.join(_name(graph, c) for c in missing)}, die im "
                                  "control_coverage nicht auftauchen")

        # --- R4 Szenarioprofil ---------------------------------------------
        cov = bp.get("control_coverage") or {}
        if bp.get("scenario") == "conservative":
            touched = set(cov.get("dropped_control_ids", [])) \
                | {x.get("control_id") for x in cov.get("replaced", [])}
            if touched:
                errors.append(f"{w}: Szenario 'konservativ' verändert Kontrollen "
                              f"({', '.join(sorted(_name(graph, c) for c in touched))}). "
                              "Konservativ heißt: heutige Kontrollen bleiben, KI assistiert nur")
        if bp.get("scenario") == "agent_native":
            irreversible = [s for s in wl.steps_of(graph, proc["id"])
                            if (s.get("decision") or {}).get("scope") == "execute_irreversible"]
            if irreversible and bp["soll_totals"]["human_touches"] == 0:
                errors.append(f"{w}: kein einziger Human Touchpoint, obwohl der Prozess "
                              "irreversible Entscheidungen enthält")

        # --- R5 Plausibilität der versprochenen Werte ------------------------
        soll = bp.get("soll_totals") or {}
        for pm in bp.get("projected_metrics") or []:
            m = metrics.get(pm.get("metric_id"))
            if not m or m.get("kind") != "time":
                continue
            unit = wl.normalize_name(m.get("unit", ""))
            factor = {"stunden": 1.0, "stunde": 1.0, "h": 1.0, "hours": 1.0, "hour": 1.0}.get(unit)
            if factor is None:
                continue
            claimed = float(pm.get("value") or 0) * factor
            computed = float(soll.get("lead_time_hours") or 0)
            if computed > 0 and claimed < computed * 0.7:
                errors.append(f"{w}: versprochene {m['name']} von {claimed} h ist kleiner als die "
                              f"Summe der eigenen Soll-Schritte ({computed} h). Entweder fehlen "
                              "Schritte im Blueprint oder die Zusage ist nicht gedeckt")
        d = bp.get("delta") or {}
        lead = d.get("lead_time_hours") or {}
        if (lead.get("improvement_pct") or 0) >= 90:
            bases = {pm.get("basis") for pm in bp.get("projected_metrics") or []}
            if bases <= {"estimated"} or not bases:
                warnings.append(f"{w}: über 90 % Durchlaufzeitgewinn, ausschließlich geschätzt. "
                                "Vor dem Rollout mit einem Pilot belegen, sonst ist die Zahl "
                                "Scheingenauigkeit")

    # --- R4b Szenarien müssen unterscheidbar sein --------------------------
    for pid, bps in sorted(by_process.items()):
        proc = processes.get(pid)
        if proc is None or len(bps) < 2:
            continue
        seen: dict[tuple, str] = {}
        for bp in sorted(bps, key=lambda b: rl.SCENARIO_ORDER.index(b["scenario"])
                         if b.get("scenario") in rl.SCENARIO_ORDER else 9):
            fingerprint = (
                tuple(sorted((bp.get("operator_counts") or {}).items())),
                bp["soll_totals"]["steps"], bp["soll_totals"]["human_touches"],
                bp["soll_totals"]["automated_steps"], bp["soll_totals"]["lead_time_hours"],
            )
            if fingerprint in seen:
                errors.append(f"{proc['name']}: Szenarien '{seen[fingerprint]}' und "
                              f"'{bp['scenario']}' sind in Operatoren und Kennzahlen identisch — "
                              "dann gibt es nichts zu entscheiden")
            seen[fingerprint] = bp["scenario"]
        ladder = {bp["scenario"]: bp for bp in bps}
        order = [s for s in rl.SCENARIO_ORDER if s in ladder]

        def auto_share(b):
            """Anteil automatisierter Schritte, nicht ihre Zahl.

            Ein ambitionierteres Szenario hat oft weniger Schritte insgesamt — die absolute
            Zahl automatisierter Schritte kann dabei sinken, obwohl mehr automatisiert ist.
            Der Anteil bildet die Ambition richtig ab."""
            total = b["soll_totals"]["steps"]
            return b["soll_totals"]["automated_steps"] / total if total else 0.0

        for a, b in zip(order, order[1:]):
            if auto_share(ladder[a]) > auto_share(ladder[b]) + 1e-9:
                warnings.append(f"{proc['name']}: '{rl.SCENARIO_LABEL[a]}' automatisiert anteilig "
                                f"mehr als '{rl.SCENARIO_LABEL[b]}' "
                                f"({auto_share(ladder[a]):.0%} gegenüber {auto_share(ladder[b]):.0%}). "
                                "Die Szenarien sollten eine Leiter steigender Ambition bilden")
            if ladder[a]["soll_totals"]["human_touches"] < ladder[b]["soll_totals"]["human_touches"]:
                warnings.append(f"{proc['name']}: '{rl.SCENARIO_LABEL[b]}' bindet mehr Human "
                                f"Touchpoints als '{rl.SCENARIO_LABEL[a]}' — das ist möglich, "
                                "sollte aber begründet sein")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph["blueprints"]:
        print("Keine Blueprints im Graphen — nichts zu prüfen. "
              "Zuerst export_process_candidates.py, dann Szenarien entwerfen, "
              "dann build_blueprints.py.")
        return 0
    errors, warnings = check(graph)
    if not args.quiet:
        for e in errors:
            print(f"FEHLER   {e}")
        for w in warnings:
            print(f"WARNUNG  {w}")
    print(f"Geprüft: {len(graph['blueprints'])} Blueprints zu "
          f"{len({b['process_id'] for b in graph['blueprints']})} Prozess(en) | "
          f"Fehler={len(errors)} Warnungen={len(warnings)}")
    if errors:
        return 2
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
