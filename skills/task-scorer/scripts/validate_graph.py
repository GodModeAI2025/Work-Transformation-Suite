#!/usr/bin/env python3
"""
validate_graph.py — prüft eine work-graph.json gegen das Schema (Version 1.1).

Aufruf (relativ zum Projektordner):
    python3 <skill>/scripts/validate_graph.py --project ./mein-projekt
    python3 <skill>/scripts/validate_graph.py --file ./mein-projekt/20_graph/work-graph_latest.json

Exit-Code 0 = gültig, 1 = Warnungen, 2 = Fehler.
Die Prüfung ist bewusst streng bei Referenzen und Aufzählungswerten, damit
nachgelagerte Skripte (Scorer, Mapper, Redesigner, Dashboard) nie mit halben Daten laufen.

Ab Schema 1.1 prüft der Validator zusätzlich die Prozessebene (Prozesse, Schritte,
Kanten, Systeme, Kontrollen, Kennzahlen), die Redesign-Artefakte (Blueprints,
Experimente) und die Governance-Regeln (Provenienz, Entscheidungsrechte,
Kontrollpunkte). Die Governance-Regeln sind der Grund, warum ein Blueprint nicht
still auf `approved` springen kann: Wer eine Pflichtkontrolle streicht oder einen
irreversiblen Schritt automatisiert, muss den Ersatz beziehungsweise den
verantwortlichen Menschen im Graphen benennen.

Ein Graph nach Schema 1.0 wird vor der Prüfung im Speicher migriert (additiv,
verlustfrei); die neuen Sammlungen sind dann leer und lösen keine Fehler aus.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402


def check_enum(errors: list[str], where: str, field: str, value, allowed: list[str], required=True):
    if value is None or value == "":
        if required:
            errors.append(f"{where}: Feld '{field}' fehlt")
        return
    if value not in allowed:
        errors.append(f"{where}: '{field}'='{value}' nicht erlaubt (erlaubt: {', '.join(allowed)})")


def check_range(errors: list[str], where: str, field: str, value, lo, hi, required=False):
    if value is None:
        if required:
            errors.append(f"{where}: Feld '{field}' fehlt")
        return
    if not isinstance(value, (int, float)) or value < lo or value > hi:
        errors.append(f"{where}: '{field}'={value!r} außerhalb {lo}..{hi}")


def _num(value, default=None):
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def validate(graph: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    sv = graph.get("meta", {}).get("schema_version")
    if sv not in wl.SCHEMA_VERSIONS_SUPPORTED:
        warnings.append(
            f"meta.schema_version={sv!r} unbekannt, unterstützt: {', '.join(wl.SCHEMA_VERSIONS_SUPPORTED)}"
        )
    elif sv != wl.SCHEMA_VERSION:
        warnings.append(f"meta.schema_version={sv!r}: Projekt läuft noch auf altem Schema, "
                        f"migrate_graph.py hebt es auf {wl.SCHEMA_VERSION}")
    # Arbeitskopie statt Mutation des übergebenen Graphen. Ein Eintrag ohne id wird hier
    # gemeldet und dann aussortiert: Die Detailprüfungen unten greifen auf it["id"] zu und
    # würden sonst mit einem KeyError abbrechen — ausgerechnet an dem Eintrag, dessen
    # eigentlichen Fehler sie gerade melden wollten.
    data = dict(graph)
    for c in wl.COLLECTIONS:
        if c not in graph or not isinstance(graph[c], list):
            errors.append(f"Sammlung '{c}' fehlt oder ist keine Liste")
            data[c] = []

    ids: dict[str, set[str]] = {}
    for c in wl.COLLECTIONS:
        seen: set[str] = set()
        kept: list = []
        for it in data[c]:
            if not isinstance(it, dict):
                errors.append(f"{c}: Eintrag ist kein Objekt: {it!r}")
                continue
            iid = it.get("id")
            if not iid:
                errors.append(f"{c}: Eintrag ohne id: {it.get('name')!r}")
                continue
            if iid in seen:
                errors.append(f"{c}: doppelte id {iid}")
            seen.add(iid)
            kept.append(it)
        ids[c] = seen
        data[c] = kept
    graph = data

    fam = ids["job_families"]
    clu = ids["job_clusters"]
    rol = ids["roles"]
    tas = ids["tasks"]
    ski = ids["skills"]
    age = ids["agents"]

    for jc in graph["job_clusters"]:
        if jc.get("family_id") not in fam:
            errors.append(f"job_cluster {jc['id']} ({jc.get('name')}): family_id unbekannt")

    for sk in graph["skills"]:
        check_enum(errors, f"skill {sk['id']} ({sk.get('name')})", "kind", sk.get("kind"), wl.ENUM_SKILL_KIND)
        if not sk.get("name"):
            errors.append(f"skill {sk['id']}: name fehlt")

    task_by_role: dict[str, list[dict]] = {}
    for t in graph["tasks"]:
        task_by_role.setdefault(t.get("role_id", ""), []).append(t)

    for r in graph["roles"]:
        w = f"role {r['id']} ({r.get('name')})"
        if not r.get("name"):
            errors.append(f"{w}: name fehlt")
        if r.get("cluster_id") not in clu:
            errors.append(f"{w}: cluster_id unbekannt")
        check_enum(errors, w, "status", r.get("status"), wl.ENUM_STATUS)
        check_enum(errors, w, "archetype", r.get("archetype"), wl.ENUM_ARCHETYPE, required=False)
        for s in r.get("skills", []):
            if s.get("skill_id") not in ski:
                errors.append(f"{w}: skill_id {s.get('skill_id')} unbekannt")
            check_range(errors, w, "skills[].level", s.get("level"), 1, 5, required=True)
            check_enum(errors, w, "skills[].importance", s.get("importance"), wl.ENUM_SKILL_IMPORTANCE)
        for tid in r.get("task_ids", []):
            if tid not in tas:
                errors.append(f"{w}: task_id {tid} unbekannt")
        rtasks = task_by_role.get(r["id"], [])
        if not rtasks:
            warnings.append(f"{w}: keine Aufgaben")
        else:
            total = sum(float(t.get("share_of_time") or 0) for t in rtasks)
            if abs(total - 100.0) > 0.51:
                warnings.append(f"{w}: Zeitanteile summieren auf {total:.1f} statt 100")
        if r.get("headcount") is not None:
            check_range(errors, w, "headcount", r.get("headcount"), 0, 1_000_000)
        an = r.get("analysis")
        if an and an.get("scored"):
            check_enum(errors, w, "analysis.disruption_type", an.get("disruption_type"), wl.ENUM_DISRUPTION)
            check_range(errors, w, "analysis.disruption_score", an.get("disruption_score"), 0, 10)

    for t in graph["tasks"]:
        w = f"task {t['id']} ({t.get('name')})"
        if not t.get("name"):
            errors.append(f"{w}: name fehlt")
        if t.get("role_id") not in rol:
            errors.append(f"{w}: role_id unbekannt")
        check_enum(errors, w, "frequency", t.get("frequency"), wl.ENUM_FREQUENCY)
        check_enum(errors, w, "nature", t.get("nature"), wl.ENUM_NATURE)
        check_enum(errors, w, "status", t.get("status"), wl.ENUM_STATUS)
        check_range(errors, w, "share_of_time", t.get("share_of_time"), 0, 100, required=True)
        for sid in t.get("skill_ids", []):
            if sid not in ski:
                errors.append(f"{w}: skill_id {sid} unbekannt")
        for aid in t.get("agent_ids", []):
            if aid not in age:
                errors.append(f"{w}: agent_id {aid} unbekannt")
        sc = t.get("scores")
        if sc:
            for f in ["automation_ai", "automation_physical", "human_judgment", "productivity_boost",
                      "data_readiness", "consequence_of_error"]:
                check_range(errors, w, f"scores.{f}", sc.get(f), 0, 10, required=True)
            if not sc.get("rationale"):
                warnings.append(f"{w}: scores.rationale fehlt")
        check_enum(errors, w, "mode", t.get("mode"), wl.ENUM_MODE, required=False)
        check_enum(errors, w, "horizon", t.get("horizon"), wl.ENUM_HORIZON, required=False)
        if t.get("has_level") is not None:
            check_range(errors, w, "has_level", t.get("has_level"), 1, 5)

    for a in graph["agents"]:
        w = f"agent {a['id']} ({a.get('name')})"
        if not a.get("name"):
            errors.append(f"{w}: name fehlt")
        check_enum(errors, w, "status", a.get("status"), wl.ENUM_AGENT_STATUS)
        check_enum(errors, w, "specificity", a.get("specificity"), wl.ENUM_SPECIFICITY)
        check_enum(errors, w, "sourcing", a.get("sourcing"), wl.ENUM_SOURCING, required=False)
        check_enum(errors, w, "horizon", a.get("horizon"), wl.ENUM_HORIZON, required=False)
        for tid in a.get("task_ids", []):
            if tid not in tas:
                errors.append(f"{w}: task_id {tid} unbekannt")
        if not a.get("task_ids") and not a.get("orchestrates"):
            # Ein Orchestrator deckt bewusst keine eigene Aufgabe ab; er koordiniert andere.
            warnings.append(f"{w}: deckt keine Aufgabe ab")
        validate_contract(a, w, ids, errors, warnings)

    for p in graph["positions"]:
        if p.get("role_id") not in rol:
            errors.append(f"position {p.get('id')}: role_id unbekannt")

    validate_process_layer(graph, ids, errors, warnings)
    return errors, warnings


# Konkrete Modellnamen gehören nicht in einen Capability Contract. Ein Vertrag beschreibt
# eine Fähigkeit und ihre Betriebsbedingungen; welches Modell sie erfüllt, ist eine
# Beschaffungsfrage und ändert sich schneller als der Prozess. Die Liste ist bewusst
# knapp: sie soll die häufigsten Versehen abfangen, nicht Anbieter zensieren.
MODEL_NAME_HINTS = (
    "gpt-", "gpt4", "gpt5", "gpt6", "claude-", "gemini-", "llama-", "mistral-",
    "o1-preview", "o3-", "deepseek-", "qwen-", "grok-",
)
CONTRACT_REQUIRED = ["trigger", "inputs", "outputs", "decision_scope", "fallback"]


def validate_contract(agent: dict, w: str, ids: dict, errors: list, warnings: list) -> None:
    """Prüft den Capability Contract eines Agenten (Schema 1.1).

    Der Vertrag ist der Übergang von „wir hätten gern einen Agenten dafür" zu etwas,
    das eine Plattform betreiben kann. Die Regeln hier sind bewusst Betriebsregeln und
    keine Stilfragen: Schreibrechte ohne Rückfallebene, irreversible Entscheidungen ohne
    Kontrollpunkt und Produktivbetrieb ohne Testmenge sind die drei Arten, wie
    Agentenprojekte in der Praxis scheitern.
    """
    c = agent.get("contract")
    if not c:
        if agent.get("status") in ("pilot", "live"):
            errors.append(f"{w}: Status '{agent.get('status')}' ohne Capability Contract — "
                          "was in Betrieb geht, braucht Auslöser, Rechte, Rückfallebene und Audit")
        else:
            warnings.append(f"{w}: kein Capability Contract (contract) hinterlegt")
        return
    if not isinstance(c, dict):
        errors.append(f"{w}: contract muss ein Objekt sein")
        return

    for f in CONTRACT_REQUIRED:
        if not c.get(f):
            errors.append(f"{w}: contract.{f} fehlt")
    check_enum(errors, w, "contract.decision_scope", c.get("decision_scope"),
               wl.ENUM_DECISION_SCOPE)
    check_range(errors, w, "contract.confidence_threshold", c.get("confidence_threshold"), 0, 1)
    check_range(errors, w, "contract.timeout_seconds", c.get("timeout_seconds"), 1, 86400)

    writes = c.get("write_permissions") or []
    if writes:
        if not c.get("audit_events"):
            errors.append(f"{w}: contract mit Schreibrechten ({', '.join(sorted(writes))}) "
                          "ohne audit_events — eine Schreibaktion ohne Spur ist nicht prüfbar")
        if not c.get("idempotency_key"):
            errors.append(f"{w}: contract mit Schreibrechten ohne idempotency_key — "
                          "ein Wiederholungslauf würde doppelt schreiben")
        if not c.get("retry_policy"):
            warnings.append(f"{w}: contract mit Schreibrechten ohne retry_policy")
    if c.get("decision_scope") == "execute_irreversible" and not c.get("human_checkpoint"):
        errors.append(f"{w}: contract.decision_scope='execute_irreversible' ohne human_checkpoint")
    if agent.get("status") in ("pilot", "live") and not c.get("evaluation_set"):
        errors.append(f"{w}: Status '{agent.get('status')}' ohne contract.evaluation_set — "
                      "ohne Testmenge lässt sich eine Verschlechterung nicht bemerken")
    if agent.get("status") in ("pilot", "live") and not c.get("service_level"):
        warnings.append(f"{w}: Status '{agent.get('status')}' ohne contract.service_level")

    cost = c.get("cost_ceiling")
    if cost is not None:
        if not isinstance(cost, dict) or _num(cost.get("amount")) is None or not cost.get("period"):
            errors.append(f"{w}: contract.cost_ceiling braucht amount, currency und period")
    elif agent.get("status") in ("pilot", "live"):
        warnings.append(f"{w}: Status '{agent.get('status')}' ohne contract.cost_ceiling")

    for sid in c.get("system_ids", []):
        if sid not in ids.get("systems", set()):
            errors.append(f"{w}: contract.system_ids {sid} unbekannt")
    if c.get("human_checkpoint"):
        rid = (c["human_checkpoint"] or {}).get("role_id") if isinstance(c["human_checkpoint"], dict) else None
        if rid and rid not in ids["roles"]:
            errors.append(f"{w}: contract.human_checkpoint.role_id unbekannt")

    # Modellagnostisch bleiben.
    blob = " ".join(str(v).lower() for v in (
        [c.get("model_requirements"), c.get("capability_profile"), c.get("notes")]
        + list(c.get("tools") or [])
    ) if v)
    for hint in MODEL_NAME_HINTS:
        if hint in blob:
            errors.append(f"{w}: contract nennt ein konkretes Modell ({hint!r}). Ein Contract "
                          "beschreibt die gebrauchte Fähigkeit, nicht das Produkt, das sie "
                          "heute erfüllt — sonst veraltet der Prozess mit dem Modell")
            break


# ---------------------------------------------------------------------------
# Schema 1.1: Prozessebene, Redesign, Governance
# ---------------------------------------------------------------------------

def _check_value_block(errors, warnings, where, label, block, required_basis=True):
    """Prüft einen Kennzahlenblock {value, basis, as_of, source}."""
    if not isinstance(block, dict):
        errors.append(f"{where}: '{label}' muss ein Objekt {{value, basis, ...}} sein")
        return
    if _num(block.get("value")) is None:
        errors.append(f"{where}: '{label}.value' fehlt oder ist keine Zahl")
    if required_basis:
        check_enum(errors, where, f"{label}.basis", block.get("basis"), wl.ENUM_VALUE_BASIS)
    if not block.get("as_of"):
        warnings.append(f"{where}: '{label}.as_of' fehlt (Stand der Zahl unklar)")


def validate_process_layer(graph: dict, ids: dict, errors: list, warnings: list) -> None:
    """Alle Prüfungen, die erst mit Schema 1.1 dazugekommen sind.

    Die Reihenfolge ist Absicht: erst Stammdaten (Systeme, Kontrollen, Kennzahlen),
    dann der Prozessfluss, dann Redesign und Governance. So zeigt die erste Fehlermeldung
    immer die Ursache und nicht die Folge.
    """
    rol = ids["roles"]
    tas = ids["tasks"]
    age = ids["agents"]
    out = ids["outcomes"]
    sysm = ids["systems"]
    ctl = ids["controls"]
    met = ids["metrics"]
    prc = ids["processes"]
    stp = ids["process_steps"]

    controls = wl.index_by_id(graph["controls"])
    steps_by_id = wl.index_by_id(graph["process_steps"])
    processes = wl.index_by_id(graph["processes"])

    # Provenienz vorab indizieren: (entity_type, entity_id, field)
    prov_index = set()
    for pv in graph["provenance"]:
        prov_index.add((pv.get("entity_type"), pv.get("entity_id"), pv.get("field")))

    # --- Ergebnisse ---------------------------------------------------------
    for o in graph["outcomes"]:
        w = f"outcome {o['id']} ({o.get('name')})"
        if not o.get("name"):
            errors.append(f"{w}: name fehlt")
        if not o.get("beneficiary"):
            warnings.append(f"{w}: beneficiary fehlt (für wen ist das Ergebnis gut?)")
        for mid in o.get("metric_ids", []):
            if mid not in met:
                errors.append(f"{w}: metric_id {mid} unbekannt")

    # --- Systeme ------------------------------------------------------------
    for sy in graph["systems"]:
        w = f"system {sy['id']} ({sy.get('name')})"
        if not sy.get("name"):
            errors.append(f"{w}: name fehlt")
        for dc in sy.get("data_classes", []):
            check_enum(errors, w, "data_classes[]", dc, wl.ENUM_DATA_CLASS)

    # --- Kontrollen ---------------------------------------------------------
    for c in graph["controls"]:
        w = f"control {c['id']} ({c.get('name')})"
        if not c.get("name"):
            errors.append(f"{w}: name fehlt")
        check_enum(errors, w, "kind", c.get("kind"), wl.ENUM_CONTROL_KIND)
        check_enum(errors, w, "mode", c.get("mode"), wl.ENUM_CONTROL_MODE)
        if c.get("kind") == "regulatory" and not c.get("legal_basis"):
            errors.append(f"{w}: kind='regulatory' ohne legal_basis — ohne Rechtsgrundlage "
                          "lässt sich der Wegfall der Kontrolle später nicht bewerten")
        if c.get("mandatory") is None:
            warnings.append(f"{w}: 'mandatory' nicht gesetzt, wird als Pflichtkontrolle behandelt")

    # --- Kennzahlen ---------------------------------------------------------
    for m in graph["metrics"]:
        w = f"metric {m['id']} ({m.get('name')})"
        if not m.get("name"):
            errors.append(f"{w}: name fehlt")
        check_enum(errors, w, "kind", m.get("kind"), wl.ENUM_METRIC_KIND)
        check_enum(errors, w, "direction", m.get("direction"), wl.ENUM_METRIC_DIRECTION)
        if not m.get("unit"):
            warnings.append(f"{w}: unit fehlt")
        if m.get("process_id") and m["process_id"] not in prc:
            errors.append(f"{w}: process_id unbekannt")
        if m.get("baseline") is not None:
            _check_value_block(errors, warnings, w, "baseline", m["baseline"])
        else:
            warnings.append(f"{w}: keine baseline — ohne Ausgangswert ist kein Delta belegbar")
        for stage in ("target", "observed"):
            if m.get(stage) is not None:
                _check_value_block(errors, warnings, w, stage, m[stage],
                                   required_basis=(stage != "observed"))
        # Governance: wer Evidenz behauptet, muss sie belegen können. Baseline und
        # Messwert werden getrennt geprüft — sie beschreiben verschiedene Prozesszustände.
        base = m.get("baseline") or {}
        base_prov = ("metrics", m["id"], "baseline") in prov_index
        if base.get("basis") in ("expert_confirmed", "observed") and not base_prov:
            errors.append(f"{w}: baseline.basis behauptet Evidenz ({base.get('basis')}), aber es "
                          "gibt keinen provenance-Eintrag für 'baseline'")
        elif base.get("value") is not None and not base_prov:
            warnings.append(f"{w}: Baseline ohne Provenienz — als Schätzung gekennzeichnet")
        if (m.get("observed") or {}).get("value") is not None \
                and ("metrics", m["id"], "observed") not in prov_index:
            errors.append(f"{w}: observed-Wert ohne provenance-Eintrag für 'observed' — eine "
                          "Messung ohne Fundstelle ist schlechter als eine ehrliche Schätzung")

    # --- Prozesse -----------------------------------------------------------
    steps_by_process: dict[str, list[dict]] = {}
    for st in graph["process_steps"]:
        steps_by_process.setdefault(st.get("process_id", ""), []).append(st)

    for pr in graph["processes"]:
        w = f"process {pr['id']} ({pr.get('name')})"
        if not pr.get("name"):
            errors.append(f"{w}: name fehlt")
        if not pr.get("trigger"):
            errors.append(f"{w}: trigger fehlt (womit beginnt der Prozess?)")
        if pr.get("outcome_id") not in out:
            errors.append(f"{w}: outcome_id unbekannt — ein Prozess ohne Ergebnis lässt sich nicht redesignen")
        if pr.get("owner_role_id") and pr["owner_role_id"] not in rol:
            errors.append(f"{w}: owner_role_id unbekannt")
        elif not pr.get("owner_role_id"):
            warnings.append(f"{w}: owner_role_id fehlt (niemand verantwortet den Prozess)")
        check_enum(errors, w, "status", pr.get("status"), wl.ENUM_STATUS)
        for dc in pr.get("data_classes", []):
            check_enum(errors, w, "data_classes[]", dc, wl.ENUM_DATA_CLASS)
        for mid in pr.get("baseline_metric_ids", []):
            if mid not in met:
                errors.append(f"{w}: baseline_metric_id {mid} unbekannt")
        own = {s["id"] for s in steps_by_process.get(pr["id"], [])}
        listed = list(pr.get("step_ids", []))
        for sid in listed:
            if sid not in stp:
                errors.append(f"{w}: step_id {sid} unbekannt")
            elif sid not in own:
                errors.append(f"{w}: step_id {sid} gehört zu Prozess "
                              f"{steps_by_id[sid].get('process_id')}")
        if len(set(listed)) != len(listed):
            errors.append(f"{w}: step_ids enthält Dubletten")
        missing = sorted(own - set(listed))
        if missing:
            errors.append(f"{w}: Schritte nicht in step_ids gelistet: {', '.join(missing)}")
        if not own:
            warnings.append(f"{w}: keine Schritte")
        if _num(pr.get("volume_per_year")) is None:
            warnings.append(f"{w}: volume_per_year fehlt — ohne Menge keine Wertschätzung")
        # Governance: Ein Prozess mit hoher Fehlerfolge darf nicht ohne Kontrollpunkt
        # freigegeben werden. „Hohe Fehlerfolge" heißt hier: unter Aufsicht, oder mit einer
        # nicht umkehrbaren Entscheidung, oder mit personenbezogenen Daten. Die Freigabe ist
        # der Moment, in dem jemand die Verantwortung übernimmt — ohne eine Kontrolle oder
        # ein Human Gate im Ablauf gibt es dafür nichts, woran man sich halten könnte.
        own_steps = steps_by_process.get(pr["id"], [])
        sensitive_data = {"personal", "special_category"} & set(pr.get("data_classes", []))
        irreversible = any((st.get("decision") or {}).get("scope") == "execute_irreversible"
                           for st in own_steps)
        high_consequence = bool(pr.get("regulated")) or irreversible or bool(sensitive_data)
        has_checkpoint = any(st.get("control_ids") or st.get("human_gate") for st in own_steps)
        if high_consequence and pr.get("status") == "approved" and not has_checkpoint:
            grund = []
            if pr.get("regulated"):
                grund.append("steht unter Aufsicht")
            if irreversible:
                grund.append("enthält eine nicht umkehrbare Entscheidung")
            if sensitive_data:
                grund.append(f"verarbeitet {sorted(sensitive_data)}")
            errors.append(f"{w}: Status 'approved', aber kein einziger Schritt trägt eine "
                          f"Kontrolle oder ein Human Gate — der Prozess {' und '.join(grund)}")

        v = pr.get("value")
        if v:
            check_enum(errors, w, "value.band", v.get("band"), wl.ENUM_PRIORITY_BAND)
            check_range(errors, w, "value.score", v.get("score"), 0, 10, required=True)
            if not v.get("weights_version"):
                warnings.append(f"{w}: value ohne weights_version — die Rangfolge ist dann "
                                "nicht reproduzierbar")

    # --- Prozessschritte ----------------------------------------------------
    for st in graph["process_steps"]:
        w = f"process_step {st['id']} ({st.get('name')})"
        if not st.get("name"):
            errors.append(f"{w}: name fehlt")
        if st.get("process_id") not in prc:
            errors.append(f"{w}: process_id unbekannt")
        for tid in st.get("task_ids", []):
            if tid not in tas:
                errors.append(f"{w}: task_id {tid} unbekannt")
        ex = st.get("executor") or {}
        check_enum(errors, w, "executor.type", ex.get("type"), wl.ENUM_EXECUTOR)
        etype, eid = ex.get("type"), ex.get("id")
        if etype == "human" and eid not in rol:
            errors.append(f"{w}: executor.type='human' braucht eine bekannte role_id")
        if etype == "agent" and eid not in age:
            errors.append(f"{w}: executor.type='agent' braucht eine bekannte agent_id")
        if etype == "system" and eid not in sysm:
            errors.append(f"{w}: executor.type='system' braucht eine bekannte system_id")
        check_enum(errors, w, "value_type", st.get("value_type"), wl.ENUM_VALUE_TYPE)
        check_range(errors, w, "handling_time_min", st.get("handling_time_min"), 0, 100_000)
        check_range(errors, w, "wait_time_min", st.get("wait_time_min"), 0, 10_000_000)
        check_range(errors, w, "rework_pct", st.get("rework_pct"), 0, 100)
        for sid in st.get("system_ids", []):
            if sid not in sysm:
                errors.append(f"{w}: system_id {sid} unbekannt")
        for cid in st.get("control_ids", []):
            if cid not in ctl:
                errors.append(f"{w}: control_id {cid} unbekannt")
        for dc in st.get("data_classes", []):
            check_enum(errors, w, "data_classes[]", dc, wl.ENUM_DATA_CLASS)
        hg = st.get("human_gate")
        if hg:
            if not hg.get("when"):
                errors.append(f"{w}: human_gate ohne 'when' — eine Bedingung, die immer gilt, "
                              "ist kein Gate, sondern ein manueller Schritt")
            if hg.get("role_id") not in rol:
                errors.append(f"{w}: human_gate.role_id unbekannt")
        dec = st.get("decision")
        if dec:
            check_enum(errors, w, "decision.scope", dec.get("scope"), wl.ENUM_DECISION_SCOPE)
            # Governance: automatisierte Entscheidungen brauchen einen Menschen, der sie verantwortet.
            if wl.step_is_automated(st) and dec.get("scope") in ("execute_reversible", "execute_irreversible"):
                if dec.get("accountable_role_id") not in rol:
                    errors.append(f"{w}: automatisierter Entscheidungsschritt ohne bekannte "
                                  "decision.accountable_role_id")
                if not dec.get("escalation"):
                    errors.append(f"{w}: automatisierter Entscheidungsschritt ohne decision.escalation")
                if dec.get("scope") == "execute_irreversible" and not (hg or st.get("control_ids")):
                    errors.append(f"{w}: irreversible Entscheidung ohne human_gate und ohne Kontrolle")
        sensitive = {"personal", "special_category"} & set(st.get("data_classes", []))
        if sensitive and wl.step_is_automated(st):
            kinds = {controls[c]["kind"] for c in st.get("control_ids", []) if c in controls}
            if "privacy" not in kinds:
                warnings.append(f"{w}: verarbeitet {sorted(sensitive)} automatisiert, "
                                "aber ohne Kontrolle der Art 'privacy'")

    # --- Kanten -------------------------------------------------------------
    edges_out: dict[str, list[dict]] = {}
    edges_in: dict[str, list[dict]] = {}
    for e in graph["process_edges"]:
        w = f"process_edge {e.get('id')}"
        if e.get("process_id") not in prc:
            errors.append(f"{w}: process_id unbekannt")
        ok = True
        for side in ("from_step_id", "to_step_id"):
            sid = e.get(side)
            if sid not in stp:
                errors.append(f"{w}: {side} {sid} unbekannt")
                ok = False
            elif steps_by_id[sid].get("process_id") != e.get("process_id"):
                errors.append(f"{w}: {side} {sid} gehört zu einem anderen Prozess")
                ok = False
        check_enum(errors, w, "handover", e.get("handover"), wl.ENUM_HANDOVER, required=False)
        check_range(errors, w, "share_pct", e.get("share_pct"), 0, 100)
        if ok:
            edges_out.setdefault(e["from_step_id"], []).append(e)
            edges_in.setdefault(e["to_step_id"], []).append(e)

    # Erreichbarkeit und Sackgassen je Prozess. Schleifen sind ausdrücklich erlaubt
    # (Nacharbeit ist ein Fakt, kein Modellfehler), unerreichbare Schritte nicht.
    for pr in graph["processes"]:
        own_steps = [s["id"] for s in steps_by_process.get(pr["id"], [])]
        if len(own_steps) < 2:
            continue
        start = pr.get("step_ids", [None])[0] if pr.get("step_ids") else None
        if start is None:
            continue
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for e in edges_out.get(cur, []):
                if e["to_step_id"] not in seen:
                    seen.add(e["to_step_id"])
                    stack.append(e["to_step_id"])
        unreachable = sorted(set(own_steps) - seen)
        if unreachable:
            warnings.append(f"process {pr['id']} ({pr.get('name')}): vom Startschritt nicht "
                            f"erreichbar: {', '.join(unreachable)}")
        ends = [s for s in own_steps if not edges_out.get(s)]
        if not ends:
            warnings.append(f"process {pr['id']} ({pr.get('name')}): kein Endschritt, "
                            "jede Kante führt weiter")

    _validate_blueprints(graph, ids, errors, warnings, controls, steps_by_id, processes)
    _validate_experiments(graph, ids, errors, warnings)
    _validate_governance(graph, ids, errors, warnings, prov_index)


def _validate_blueprints(graph, ids, errors, warnings, controls, steps_by_id, processes) -> None:
    prc, age, met, rol = ids["processes"], ids["agents"], ids["metrics"], ids["roles"]
    seen_scenarios: dict[tuple, str] = {}
    for bp in graph["blueprints"]:
        w = f"blueprint {bp['id']} ({bp.get('name')})"
        if bp.get("process_id") not in prc:
            errors.append(f"{w}: process_id unbekannt")
            continue
        proc = processes[bp["process_id"]]
        check_enum(errors, w, "scenario", bp.get("scenario"), wl.ENUM_SCENARIO)
        check_enum(errors, w, "status", bp.get("status"), wl.ENUM_BLUEPRINT_STATUS)
        key = (bp["process_id"], bp.get("scenario"))
        if key in seen_scenarios:
            errors.append(f"{w}: Szenario '{bp.get('scenario')}' gibt es für diesen Prozess schon "
                          f"({seen_scenarios[key]})")
        seen_scenarios[key] = bp["id"]

        # Das Ergebnis muss erhalten bleiben — sonst ist es kein Redesign, sondern ein anderer Prozess.
        if bp.get("outcome_id") and bp["outcome_id"] != proc.get("outcome_id"):
            if not bp.get("outcome_change_rationale"):
                errors.append(f"{w}: anderes outcome_id als der Ist-Prozess, ohne "
                              "outcome_change_rationale")

        own_steps = {s["id"] for s in graph["process_steps"] if s.get("process_id") == bp["process_id"]}
        target = bp.get("steps") or []
        if not target:
            errors.append(f"{w}: keine Soll-Schritte")
        for i, st in enumerate(target):
            sw = f"{w} steps[{i}] ({st.get('name')})"
            if not st.get("name"):
                errors.append(f"{sw}: name fehlt")
            check_enum(errors, sw, "operator", st.get("operator"), wl.ENUM_OPERATOR)
            ex = st.get("executor") or {}
            check_enum(errors, sw, "executor.type", ex.get("type"), wl.ENUM_EXECUTOR)
            if ex.get("type") == "agent" and ex.get("id") and ex["id"] not in age:
                errors.append(f"{sw}: executor.id {ex['id']} ist kein bekannter Agent")
            for sid in st.get("from_step_ids", []):
                if sid not in own_steps:
                    errors.append(f"{sw}: from_step_ids {sid} gehört nicht zum Ist-Prozess")
            if not st.get("rationale"):
                errors.append(f"{sw}: rationale fehlt — jede Änderung braucht eine Begründung")
            if st.get("metric_id") and st["metric_id"] not in met:
                errors.append(f"{sw}: metric_id unbekannt")
            elif not st.get("metric_id"):
                warnings.append(f"{sw}: keine betroffene Kennzahl benannt")
            hg = st.get("human_gate")
            if hg and hg.get("role_id") and hg["role_id"] not in rol:
                errors.append(f"{sw}: human_gate.role_id unbekannt")

        for sid in bp.get("removed_step_ids", []):
            if sid not in own_steps:
                errors.append(f"{w}: removed_step_ids {sid} gehört nicht zum Ist-Prozess")
        for aid in bp.get("agent_ids", []):
            if aid not in age:
                errors.append(f"{w}: agent_id {aid} unbekannt")

        # Kernregel des Redesigns: nicht einfach alles an Agenten hängen.
        ops = [st.get("operator") for st in target]
        if target and all(o == "automate" for o in ops):
            errors.append(f"{w}: alle Schritte nur 'automate' — das ist KI auf dem Altprozess, "
                          "kein Redesign. Mindestens ein weiterer Operator (eliminate, simplify, "
                          "merge, parallelize, human_gate) muss begründet angewendet sein")
        if bp.get("scenario") == "agent_native" and not any(
                st.get("human_gate") or st.get("operator") == "human_gate" for st in target):
            errors.append(f"{w}: Szenario 'agent_native' ohne einen einzigen Human Gate — "
                          "Verantwortungsgrenzen müssen benannt sein")

        # Pflichtkontrollen: entweder behalten oder dokumentiert ersetzt.
        cov = bp.get("control_coverage") or {}
        retained = set(cov.get("retained_control_ids", []))
        replaced = {r.get("control_id"): r for r in cov.get("replaced", []) if isinstance(r, dict)}
        dropped = set(cov.get("dropped_control_ids", []))
        ist_controls = set()
        for s in graph["process_steps"]:
            if s.get("process_id") == bp["process_id"]:
                ist_controls.update(s.get("control_ids", []))
        for cid in sorted(ist_controls):
            c = controls.get(cid)
            if c is None:
                continue
            mandatory = c.get("mandatory", True)
            if cid in retained:
                continue
            if cid in replaced:
                r = replaced[cid]
                if not r.get("replacement") or not r.get("rationale"):
                    errors.append(f"{w}: Kontrolle {cid} ({c.get('name')}) ersetzt, aber ohne "
                                  "'replacement' und 'rationale'")
                if mandatory and not r.get("approved_by"):
                    errors.append(f"{w}: Pflichtkontrolle {cid} ({c.get('name')}) ersetzt, aber "
                                  "ohne 'approved_by' — ein Mensch muss den Ersatz freigeben")
                continue
            if cid in dropped:
                if mandatory:
                    errors.append(f"{w}: Pflichtkontrolle {cid} ({c.get('name')}) entfällt ersatzlos. "
                                  "Zulässig nur über control_coverage.replaced mit Ersatz und Freigabe")
                continue
            errors.append(f"{w}: Kontrolle {cid} ({c.get('name')}) aus dem Ist-Prozess wird in "
                          "control_coverage weder behalten, ersetzt noch bewusst gestrichen")

        for pm in bp.get("projected_metrics", []) or []:
            if pm.get("metric_id") not in met:
                errors.append(f"{w}: projected_metrics.metric_id {pm.get('metric_id')} unbekannt")
            check_enum(errors, w, "projected_metrics[].basis", pm.get("basis"), wl.ENUM_VALUE_BASIS)
        if bp.get("status") == "approved":
            if bp.get("open_assumptions"):
                warnings.append(f"{w}: Status 'approved' trotz {len(bp['open_assumptions'])} "
                                "offener Annahmen")
            if not any(d.get("subject_id") == bp["id"] for d in graph["decisions"]):
                errors.append(f"{w}: Status 'approved' ohne Eintrag im Entscheidungslog (decisions)")


def _validate_experiments(graph, ids, errors, warnings) -> None:
    prc, blp, met, rol = ids["processes"], ids["blueprints"], ids["metrics"], ids["roles"]
    metrics = wl.index_by_id(graph["metrics"])
    for x in graph["experiments"]:
        w = f"experiment {x['id']} ({x.get('name')})"
        if x.get("process_id") not in prc:
            errors.append(f"{w}: process_id unbekannt")
        if x.get("blueprint_id") and x["blueprint_id"] not in blp:
            errors.append(f"{w}: blueprint_id unbekannt")
        check_enum(errors, w, "design", x.get("design"), wl.ENUM_EXPERIMENT_DESIGN)
        check_enum(errors, w, "status", x.get("status"), wl.ENUM_EXPERIMENT_STATUS)
        if not x.get("hypothesis"):
            errors.append(f"{w}: hypothesis fehlt")
        if x.get("primary_metric_id") not in met:
            errors.append(f"{w}: primary_metric_id unbekannt")
        guard = x.get("guardrail_metric_ids", [])
        for mid in guard:
            if mid not in met:
                errors.append(f"{w}: guardrail_metric_id {mid} unbekannt")
        kinds = {metrics[m]["kind"] for m in guard if m in metrics}
        primary_kind = metrics.get(x.get("primary_metric_id"), {}).get("kind")
        have = kinds | ({primary_kind} if primary_kind else set())
        # Jeder Pilot braucht Ergebnis, Qualität und Risiko — sonst optimiert er eine Zahl kaputt.
        for needed in ("quality", "risk"):
            if needed not in have:
                errors.append(f"{w}: keine Kennzahl der Art '{needed}' unter Primär- und "
                              "Guardrail-Metriken")
        if not ({"outcome", "cost", "time", "adoption"} & have):
            errors.append(f"{w}: keine Ergebniskennzahl (outcome/cost/time/adoption)")
        if not x.get("stop_rules"):
            errors.append(f"{w}: stop_rules fehlen — ohne Abbruchkriterium kein verantworteter Pilot")
        if not x.get("rollback"):
            errors.append(f"{w}: rollback fehlt")
        if x.get("owner_role_id") not in rol:
            errors.append(f"{w}: owner_role_id unbekannt")
        if x.get("design") == "ab_test" and not x.get("control_group"):
            errors.append(f"{w}: design='ab_test' ohne control_group")
        if x.get("design") == "pre_post" and not x.get("comparison_period"):
            errors.append(f"{w}: design='pre_post' ohne comparison_period")
        check_range(errors, w, "duration_days", x.get("duration_days"), 1, 3650)
        check_range(errors, w, "sample_size", x.get("sample_size"), 1, 10_000_000)
        if x.get("status") in ("running", "stopped", "completed") and not x.get("results"):
            warnings.append(f"{w}: Status '{x.get('status')}' ohne results")


def _validate_governance(graph, ids, errors, warnings, prov_index) -> None:
    for pv in graph["provenance"]:
        w = f"provenance {pv['id']}"
        et = pv.get("entity_type")
        if et not in wl.COLLECTIONS:
            errors.append(f"{w}: entity_type '{et}' ist keine bekannte Sammlung")
        elif pv.get("entity_id") not in ids.get(et, set()):
            errors.append(f"{w}: entity_id {pv.get('entity_id')} in '{et}' unbekannt")
        if not pv.get("field"):
            errors.append(f"{w}: field fehlt")
        check_enum(errors, w, "source_kind", pv.get("source_kind"), wl.ENUM_SOURCE_KIND)
        check_enum(errors, w, "status", pv.get("status"), wl.ENUM_PROVENANCE_STATUS)
        check_range(errors, w, "confidence", pv.get("confidence"), 0, 1)
        if pv.get("source_kind") in ("document", "system_export") and not pv.get("locator"):
            warnings.append(f"{w}: source_kind '{pv.get('source_kind')}' ohne locator (Fundstelle)")
        if pv.get("status") in ("reviewed", "verified") and not pv.get("reviewer"):
            errors.append(f"{w}: Status '{pv.get('status')}' ohne reviewer")

    for d in graph["decisions"]:
        w = f"decision {d['id']}"
        st = d.get("subject_type")
        if st not in wl.COLLECTIONS:
            errors.append(f"{w}: subject_type '{st}' ist keine bekannte Sammlung")
        elif d.get("subject_id") not in ids.get(st, set()):
            errors.append(f"{w}: subject_id {d.get('subject_id')} in '{st}' unbekannt")
        check_enum(errors, w, "decision", d.get("decision"), wl.ENUM_DECISION_TYPE)
        if not d.get("decided_by"):
            errors.append(f"{w}: decided_by fehlt — eine Freigabe ohne Namen ist keine Freigabe")
        if not d.get("date"):
            errors.append(f"{w}: date fehlt")
        if not d.get("rationale"):
            warnings.append(f"{w}: rationale fehlt")


def main() -> int:
    ap = argparse.ArgumentParser(description="work-graph.json validieren")
    ap.add_argument("--project", help="Projektordner (relativ)")
    ap.add_argument("--file", help="Alternativ: konkrete Graph-Datei")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = Path.cwd() / path
    elif args.project:
        path = wl.latest_graph_path(wl.resolve_project(args.project))
    else:
        ap.error("--project oder --file angeben")
        return 2
    if not path.exists():
        wl.fail(f"Datei nicht gefunden: {wl.relpath(path)}")
    graph = wl.read_json(path)
    for note in wl.migrate_graph(graph):
        if not args.quiet:
            print(f"MIGRATION {note}")
    errors, warnings = validate(graph)
    if not args.quiet:
        for e in errors:
            print(f"FEHLER   {e}")
        for w in warnings:
            print(f"WARNUNG  {w}")
    counts = {c: len(graph.get(c, [])) for c in wl.COLLECTIONS}
    print(
        f"Geprüft: {wl.relpath(path)} | "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        + f" | Fehler={len(errors)} Warnungen={len(warnings)}"
    )
    if errors:
        return 2
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
