#!/usr/bin/env python3
"""
redesign_lib.py — gemeinsame Rechenregeln des Skills process-redesigner.

Liegt nur in diesem Skill (anders als workgraph_lib.py, das alle Skills teilen).
Hier stehen die Regeln, die aus einem Ist-Prozess und einem Blueprint deterministisch
Kennzahlen, Deltas und Redesign-Signale machen. Kein Urteil, nur Arithmetik:
Was ein Schritt kostet, wie viele Übergaben wegfallen, welcher Operator wo zulässig ist.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

# Arbeitsstunden je Vollzeitäquivalent und Jahr. Konservativ gerechnet (1600 statt 1720),
# damit eingesparte Minuten nicht zu optimistisch in Stellen umgerechnet werden.
FTE_HOURS_PER_YEAR = 1600.0

SCENARIO_ORDER = ["conservative", "balanced", "agent_native"]
SCENARIO_LABEL = {
    "conservative": "Konservativ",
    "balanced": "Ausgewogen",
    "agent_native": "Agent-nativ",
}
OPERATOR_LABEL = {
    "eliminate": "Eliminieren",
    "simplify": "Vereinfachen",
    "merge": "Zusammenführen",
    "parallelize": "Parallelisieren",
    "automate": "Automatisieren",
    "human_gate": "Human Gate",
}
VALUE_TYPE_LABEL = {
    "customer_value": "Kundenwert",
    "business_required": "Betrieblich nötig",
    "waste": "Ohne Wertbeitrag",
}


def blueprint_totals(bp: dict[str, Any]) -> dict[str, Any]:
    """Soll-Kennzahlen eines Blueprints aus seinen Schritten.

    Parallelisierung ist der einzige Fall, in dem nicht summiert wird: Schritte mit
    derselben `parallel_group` laufen gleichzeitig, deshalb zählt für die Durchlaufzeit
    nur der längste von ihnen. Die Bearbeitungszeit (Arbeit) bleibt die Summe —
    Parallelisierung spart Wartezeit, keine Arbeitsminuten.
    """
    steps = bp.get("steps") or []
    handling = sum(float(s.get("handling_time_min") or 0) for s in steps)

    groups: dict[str, float] = {}
    serial = 0.0
    for s in steps:
        span = float(s.get("handling_time_min") or 0) + float(s.get("wait_time_min") or 0)
        grp = s.get("parallel_group")
        if grp:
            groups[grp] = max(groups.get(grp, 0.0), span)
        else:
            serial += span
    elapsed = serial + sum(groups.values())

    rework = [float(s.get("rework_pct")) for s in steps if s.get("rework_pct") is not None]
    human_touches = sum(1 for s in steps if _step_has_human(s))
    # Übergaben: jeder Wechsel des Ausführenden zwischen aufeinanderfolgenden Schritten.
    # Parallele Schritte derselben Gruppe zählen nicht als Kette.
    handovers = 0
    previous = None
    for s in steps:
        cur = _executor_key(s)
        if previous is not None and cur != previous:
            handovers += 1
        previous = cur
    return {
        "steps": len(steps),
        "handling_time_min": wl.round1(handling),
        "wait_time_min": wl.round1(sum(float(s.get("wait_time_min") or 0) for s in steps)),
        "lead_time_hours": wl.round1(elapsed / 60.0),
        "human_touches": human_touches,
        "automated_steps": sum(1 for s in steps if (s.get("executor") or {}).get("type") in ("agent", "system", "rule")),
        "handovers": handovers,
        "rework_pct": wl.round1(sum(rework) / len(rework)) if rework else 0.0,
        "waste_steps": 0,
    }


def _executor_key(step: dict[str, Any]) -> str:
    ex = step.get("executor") or {}
    return f"{ex.get('type')}:{ex.get('id') or ex.get('name') or ''}"


def _step_has_human(step: dict[str, Any]) -> bool:
    """Gleiche Regel wie wl.step_has_human, hier für Blueprint-Schritte wiederverwendet:
    Blueprint- und Ist-Schritte tragen executor und human_gate in derselben Form."""
    return wl.step_has_human(step)


# Kennzahlen, bei denen weniger besser ist. Für sie wird das Delta so gedreht,
# dass ein positiver Wert immer eine Verbesserung bedeutet.
LOWER_IS_BETTER = {"steps", "handling_time_min", "wait_time_min", "lead_time_hours",
                   "human_touches", "handovers", "rework_pct", "waste_steps"}


def delta(ist: dict[str, Any], soll: dict[str, Any]) -> dict[str, Any]:
    """Absolute und relative Veränderung je Kennzahl, Vorzeichen als Verbesserung gelesen."""
    out: dict[str, Any] = {}
    for key in sorted(set(ist) | set(soll)):
        a, b = ist.get(key), soll.get(key)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            continue
        raw = b - a
        improvement = -raw if key in LOWER_IS_BETTER else raw
        out[key] = {
            "ist": a,
            "soll": b,
            "change": wl.round1(raw),
            "improvement": wl.round1(improvement),
            "improvement_pct": wl.round1(100.0 * improvement / abs(a)) if a else None,
        }
    return out


def human_minutes_per_case(graph: dict[str, Any], process_id: str) -> float:
    """Menschliche Bearbeitungsminuten je Fall im Ist-Prozess."""
    return wl.round1(sum(float(s.get("handling_time_min") or 0)
                         for s in wl.steps_of(graph, process_id) if wl.step_has_human(s)))


def fte_equivalent(minutes_per_case: float, volume_per_year) -> float | None:
    """Menschliche Arbeitszeit eines Prozesses in Vollzeitäquivalenten.

    Bewusst aus Zeit und Menge gerechnet, nicht aus Headcount: So lässt sich ein Prozess
    auch dann bewerten, wenn für die beteiligten Rollen keine Stellenzahlen vorliegen.
    """
    if volume_per_year is None:
        return None
    try:
        vol = float(volume_per_year)
    except (TypeError, ValueError):
        return None
    return wl.round1(minutes_per_case * vol / 60.0 / FTE_HOURS_PER_YEAR)


def redesign_signals(graph: dict[str, Any], process_id: str) -> list[dict[str, Any]]:
    """Maschinell erkennbare Ansatzpunkte für ein Redesign.

    Das sind ausdrücklich Hinweise, keine Entscheidungen: Sie zeigen, wo im Ist-Prozess
    Struktur verschwendet wird, und benennen den Operator, der dort typischerweise greift.
    Ob er fachlich zulässig ist, entscheidet der Mensch beziehungsweise Claude im Blueprint.
    """
    steps = wl.steps_of(graph, process_id)
    edges = wl.edges_of(graph, process_id)
    by_id = {s["id"]: s for s in steps}
    signals: list[dict[str, Any]] = []

    for s in steps:
        if s.get("value_type") == "waste":
            signals.append({"operator": "eliminate", "step_ids": [s["id"]],
                            "finding": f"{s['name']}: als Schritt ohne Wertbeitrag erfasst"})
        wait = float(s.get("wait_time_min") or 0)
        handling = float(s.get("handling_time_min") or 0)
        if wait >= 4 * max(handling, 1.0) and wait >= 60:
            signals.append({"operator": "parallelize", "step_ids": [s["id"]],
                            "finding": f"{s['name']}: {wl.round1(wait)} min Liegezeit gegenüber "
                                       f"{wl.round1(handling)} min Arbeit"})
        if float(s.get("rework_pct") or 0) >= 15:
            signals.append({"operator": "simplify", "step_ids": [s["id"]],
                            "finding": f"{s['name']}: {wl.round1(float(s['rework_pct']))} % Nacharbeit"})

    # Gleiche Ein- und Ausgaben bei aufeinanderfolgenden Schritten: Kandidat zum Zusammenführen.
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        shared = set(a.get("outputs", [])) & set(b.get("inputs", []))
        if shared and _executor_key(a) == _executor_key(b):
            signals.append({"operator": "merge", "step_ids": [a["id"], b["id"]],
                            "finding": f"{a['name']} und {b['name']}: gleicher Ausführender, "
                                       f"direkte Übergabe von {sorted(shared)[0]!r}"})

    # Medienbrüche: Übergaben per E-Mail, Telefon oder Meeting sind Wartezeitquellen.
    for e in edges:
        if e.get("handover") in ("email", "call", "meeting", "document"):
            a, b = by_id.get(e["from_step_id"]), by_id.get(e["to_step_id"])
            if a and b:
                signals.append({"operator": "automate", "step_ids": [a["id"], b["id"]],
                                "finding": f"Übergabe {a['name']} → {b['name']} per "
                                           f"{e['handover']} statt über ein System"})

    # Mehrfachprüfungen derselben Daten: der klassische Fall aus der Vorlage.
    seen_inputs: dict[tuple, list[str]] = {}
    for s in steps:
        key = tuple(sorted(s.get("inputs", [])))
        if key:
            seen_inputs.setdefault(key, []).append(s["id"])
    for key, sids in sorted(seen_inputs.items()):
        if len(sids) >= 3:
            names = ", ".join(by_id[x]["name"] for x in sids)
            signals.append({"operator": "merge", "step_ids": sorted(sids),
                            "finding": f"{len(sids)} Schritte arbeiten auf denselben Eingaben "
                                       f"{list(key)}: {names}"})

    # Entscheidungen ohne Kontrolle sind Kandidaten für ein bewusstes Human Gate.
    for s in steps:
        dec = s.get("decision") or {}
        if dec.get("scope") in ("execute_reversible", "execute_irreversible") \
                and not s.get("human_gate") and not s.get("control_ids"):
            signals.append({"operator": "human_gate", "step_ids": [s["id"]],
                            "finding": f"{s['name']}: Entscheidung mit Reichweite "
                                       f"'{dec['scope']}' ohne Gate und ohne Kontrolle"})

    signals.sort(key=lambda x: (x["operator"], x["step_ids"], x["finding"]))
    return signals
