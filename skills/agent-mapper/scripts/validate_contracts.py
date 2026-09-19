#!/usr/bin/env python3
"""
validate_contracts.py — prüft die Capability Contracts gegen den Prozess, in dem sie laufen.

Aufruf:
    python3 <skill>/scripts/validate_contracts.py --project ./mein-projekt [--quiet]

Exit-Code 0 = sauber, 1 = Warnungen, 2 = Fehler.

Abgrenzung zu validate_graph.py: Dort wird der Vertrag für sich geprüft (Pflichtfelder,
Schreibrechte mit Audit und Idempotenz, irreversible Entscheidungen mit Kontrollpunkt,
Modellagnostik). Hier wird er gegen seinen Einsatzort geprüft:

- Reicht die Entscheidungsreichweite des Vertrags für die Schritte, die der Agent ausführt?
- Kennt der Vertrag die Systeme, in die er schreiben soll — und haben die überhaupt eine
  Schnittstelle?
- Trägt der Agent Kontrollen, die sein Vertrag nicht abbildet?
- Passt die Testmenge zur Reichweite dessen, was der Agent tut?

Ein Vertrag, der für sich stimmig ist, aber nicht zu seinem Prozessschritt passt, ist die
teuerste Art von Fehler: Er fällt erst im Betrieb auf.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

SCOPE_RANK = {"recommend": 0, "execute_reversible": 1, "execute_irreversible": 2}
# Unter dieser Größe ist eine Testmenge eher ein Beispiel als eine Absicherung.
MIN_EVAL_CASES = 20


def _eval_size(ev: Any) -> int | None:
    if isinstance(ev, dict):
        n = ev.get("cases") if not isinstance(ev.get("cases"), list) else len(ev["cases"])
        try:
            return int(n) if n is not None else None
        except (TypeError, ValueError):
            return None
    if isinstance(ev, list):
        return len(ev)
    return None


def check(graph: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    systems = wl.index_by_id(graph["systems"])
    controls = wl.index_by_id(graph["controls"])
    agents = wl.index_by_id(graph["agents"])
    steps_by_agent: dict[str, list[dict]] = {}
    for st in graph["process_steps"]:
        ex = st.get("executor") or {}
        if ex.get("type") == "agent" and ex.get("id"):
            steps_by_agent.setdefault(ex["id"], []).append(st)
    for bp in graph["blueprints"]:
        for st in bp.get("steps", []):
            ex = st.get("executor") or {}
            if ex.get("type") == "agent" and ex.get("id"):
                steps_by_agent.setdefault(ex["id"], []).append(st)

    for aid in sorted(agents):
        a = agents[aid]
        c = a.get("contract")
        if not isinstance(c, dict):
            continue
        w = f"agent {a['name']}"
        steps = steps_by_agent.get(aid, [])

        # Entscheidungsreichweite gegen die Schritte, die der Agent tatsächlich ausführt.
        contract_scope = SCOPE_RANK.get(c.get("decision_scope"), 0)
        for st in steps:
            needed = SCOPE_RANK.get((st.get("decision") or {}).get("scope", "recommend"), 0)
            if needed > contract_scope:
                errors.append(f"{w}: führt Schritt '{st.get('name')}' aus, der "
                              f"'{(st.get('decision') or {}).get('scope')}' verlangt, der Vertrag "
                              f"erlaubt nur '{c.get('decision_scope')}'")

        # Schreibrechte gegen die Systeme des Schrittes.
        writes = {str(x) for x in (c.get("write_permissions") or [])}
        step_systems: set = set()
        for st in steps:
            step_systems.update(st.get("system_ids", []))
        for sid in sorted(step_systems):
            sysname = systems.get(sid, {}).get("name", sid)
            touches = any(wl.normalize_name(sysname) in wl.normalize_name(x) for x in writes)
            if touches and systems.get(sid, {}).get("api_available") is False:
                errors.append(f"{w}: soll in {sysname} schreiben, aber das System ist ohne "
                              "Schnittstelle erfasst (api_available=false). Entweder die "
                              "Schnittstelle schaffen oder den Schritt anders schneiden")
        if writes and not step_systems and steps:
            warnings.append(f"{w}: Vertrag hat Schreibrechte, aber keiner seiner Schritte "
                            "nennt ein System")

        # Kontrollen, die an den Schritten des Agenten hängen.
        step_controls: set = set()
        for st in steps:
            step_controls.update(st.get("control_ids", []))
        if step_controls and not (c.get("human_checkpoint") or c.get("controls")):
            names = ", ".join(sorted(controls.get(x, {}).get("name", x) for x in step_controls))
            warnings.append(f"{w}: seine Schritte tragen Kontrollen ({names}), der Vertrag "
                            "nennt weder human_checkpoint noch controls")

        # Testmenge im Verhältnis zur Reichweite.
        size = _eval_size(c.get("evaluation_set"))
        if size is not None and size < MIN_EVAL_CASES and a.get("status") in ("pilot", "live"):
            warnings.append(f"{w}: Testmenge mit {size} Fällen ist für den Status "
                            f"'{a['status']}' klein (Richtwert {MIN_EVAL_CASES})")

        # Schwelle und Kontrollpunkt gehören zusammen.
        hcp = c.get("human_checkpoint")
        if c.get("confidence_threshold") is not None and not hcp:
            warnings.append(f"{w}: confidence_threshold gesetzt, aber kein human_checkpoint — "
                            "was passiert unterhalb der Schwelle?")
        if isinstance(hcp, dict) and hcp.get("when") and "confidence" in str(hcp["when"]).lower() \
                and c.get("confidence_threshold") is None:
            errors.append(f"{w}: human_checkpoint verweist auf eine Konfidenz, der Vertrag "
                          "legt aber keine confidence_threshold fest")

        # Orchestrierung: wer koordiniert, braucht keine eigenen Schreibrechte.
        if a.get("orchestrates") and writes:
            warnings.append(f"{w}: koordiniert andere Agenten und hat zugleich eigene "
                            "Schreibrechte. Sauberer ist, das Schreiben den Spezialagenten "
                            "zu überlassen — sonst ist im Fehlerfall unklar, wer geschrieben hat")
        for target in a.get("orchestrates", []):
            t = agents.get(target)
            if t and not t.get("contract"):
                warnings.append(f"{w}: orchestriert {t['name']}, der keinen Vertrag hat")

        if not steps and a.get("status") in ("pilot", "live"):
            warnings.append(f"{w}: Status '{a['status']}', aber kein Prozessschritt und kein "
                            "Blueprint-Schritt weist ihm Arbeit zu")
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
    with_contract = [a for a in graph["agents"] if isinstance(a.get("contract"), dict)]
    if not with_contract:
        print(f"Keiner der {len(graph['agents'])} Agenten hat einen Capability Contract. "
              "Format: references/contract-format.md")
        return 0
    errors, warnings = check(graph)
    if not args.quiet:
        for e in errors:
            print(f"FEHLER   {e}")
        for w in warnings:
            print(f"WARNUNG  {w}")
    print(f"Geprüft: {len(with_contract)}/{len(graph['agents'])} Agenten mit Vertrag | "
          f"Fehler={len(errors)} Warnungen={len(warnings)}")
    if errors:
        return 2
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
