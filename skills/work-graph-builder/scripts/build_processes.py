#!/usr/bin/env python3
"""
build_processes.py — liest die Prozessextraktionen aus 10_extraction/process_*.json
und schreibt daraus die Prozessebene des Arbeitsgraphen (Schema 1.1): outcomes,
systems, controls, metrics, processes, process_steps, process_edges, provenance.

Aufruf:
    python3 <skill>/scripts/build_processes.py --project ./mein-projekt

Eingabeformat: siehe references/process-format.md.

Warum ein eigenes Skript und nicht ein Teil von build_graph.py:
Der Arbeitsgraph beantwortet „wer macht was", die Prozessebene „in welcher Reihenfolge,
mit welchen Übergaben und welchem Ergebnis". Beides entsteht aus unterschiedlichen
Quellen (Stellenbeschreibungen gegenüber Prozessbeobachtung, Systemexporten, Interviews)
und in unterschiedlichem Takt. Getrennt gehalten kann die Prozessarbeit laufen, ohne bei
jeder neuen Stellenbeschreibung neu gemacht zu werden — build_graph.py übernimmt die
Prozessebene unverändert aus der Vorversion.

Determinismus:
- Dateien in alphabetischer Reihenfolge; IDs sind Hashes der normalisierten Namen.
- Rollen, Aufgaben und Agenten werden über ihren Namen im bestehenden Graphen aufgelöst.
  Ist ein Name nicht eindeutig oder unbekannt, bricht das Skript ab, statt zu raten.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

VALUE_STAGES = ("baseline", "target", "observed")


def _str(x: Any, default: str = "") -> str:
    return str(x).strip() if x is not None else default


def _num(x, default=None):
    if x is None or x == "" or isinstance(x, bool):
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


class NameIndex:
    """Löst Klartextnamen aus der Prozessextraktion auf IDs im Graphen auf.

    Prozesse werden von Fachleuten beschrieben, nicht von IDs. Damit die Extraktion
    lesbar bleibt, stehen dort Namen („Servicemitarbeiter", „Reklamation aufnehmen").
    Diese Klasse macht daraus IDs — und meldet jede Mehrdeutigkeit, statt die erste
    Treffer zu nehmen. Ein still falsch aufgelöster Rollenname würde sonst eine
    komplette Prozessanalyse auf die falsche Rolle buchen.
    """

    def __init__(self, graph: dict[str, Any]):
        self.problems: list[str] = []
        self._roles: dict[str, list[str]] = {}
        for r in graph["roles"]:
            self._roles.setdefault(wl.normalize_name(r["name"]), []).append(r["id"])
        self._agents: dict[str, list[str]] = {}
        for a in graph["agents"]:
            self._agents.setdefault(wl.normalize_name(a["name"]), []).append(a["id"])
        self._tasks: dict[tuple, list[str]] = {}
        for t in graph["tasks"]:
            self._tasks.setdefault((t["role_id"], wl.normalize_name(t["name"])), []).append(t["id"])

    def _one(self, table: dict, key, what: str, where: str):
        hits = table.get(key, [])
        if not hits:
            self.problems.append(f"{where}: {what} nicht im Graphen gefunden")
            return None
        if len(hits) > 1:
            self.problems.append(f"{where}: {what} ist mehrdeutig ({', '.join(sorted(hits))}), "
                                 "bitte im Extraktionsformat die ID angeben")
            return None
        return hits[0]

    def role(self, name: str, where: str):
        if not name:
            return None
        if name.startswith("ro_"):
            return name
        return self._one(self._roles, wl.normalize_name(name), f"Rolle {name!r}", where)

    def agent(self, name: str, where: str):
        if not name:
            return None
        if name.startswith("ag_"):
            return name
        return self._one(self._agents, wl.normalize_name(name), f"Agent {name!r}", where)

    def task(self, role_id: str, name: str, where: str):
        if not name:
            return None
        if name.startswith("ta_"):
            return name
        if not role_id:
            self.problems.append(f"{where}: Aufgabe {name!r} ohne auflösbare Rolle")
            return None
        return self._one(self._tasks, (role_id, wl.normalize_name(name)), f"Aufgabe {name!r}", where)


def _value_block(raw: Any, default_basis: str = "estimated"):
    """Normalisiert {value, basis, as_of, source} und akzeptiert auch eine blanke Zahl."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return {"value": float(raw), "basis": default_basis, "as_of": "", "source": ""}
    if not isinstance(raw, dict):
        return None
    basis = _str(raw.get("basis")) or default_basis
    return {
        "value": _num(raw.get("value")),
        "basis": basis if basis in wl.ENUM_VALUE_BASIS else default_basis,
        "as_of": _str(raw.get("as_of")),
        "source": _str(raw.get("source")),
    }


def _enum(value: Any, allowed: list, default):
    v = _str(value)
    return v if v in allowed else default


def load_files(project: Path) -> list:
    exdir = project / wl.DIR_EXTRACTION
    files = sorted(exdir.glob("process_*.json"))
    out = []
    for f in files:
        try:
            out.append((f.name, wl.read_json(f)))
        except Exception as e:  # noqa: BLE001
            wl.fail(f"{f.name}: kein gültiges JSON ({e})")
    return out


def build(project: Path) -> tuple:
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden — zuerst build_graph.py laufen lassen")
    files = load_files(project)
    if not files:
        wl.fail(f"Keine Prozessextraktionen in {wl.relpath(project / wl.DIR_EXTRACTION)} "
                "(erwartet process_*.json, Format: references/process-format.md)")

    # Was aus der Extraktion kommt, wird neu gebaut. Was NICHT aus ihr kommt, muss
    # den Neubau überleben: im Pilot gemessene Werte (make_experiments.py) und
    # Freigabestände aus dem Entscheidungslog (apply_governance.py). Ohne diese
    # Übernahme würde jeder Lauf eine Messung verwerfen und eine neue Version schreiben.
    prev_metrics = wl.index_by_id(graph.get("metrics", []))
    prev_processes = wl.index_by_id(graph.get("processes", []))
    decided = {d.get("subject_id") for d in graph.get("decisions", [])}

    idx = NameIndex(graph)
    outcomes: dict[str, dict] = {}
    systems: dict[str, dict] = {}
    controls: dict[str, dict] = {}
    metrics: dict[str, dict] = {}
    processes: dict[str, dict] = {}
    steps: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    provenance: dict[str, dict] = {}
    stats = {"files": 0, "processes": 0, "steps": 0, "edges": 0, "metrics": 0,
             "provenance_dropped": 0}

    def system_id(name: str) -> str:
        sid = wl.make_id("system", name)
        systems.setdefault(sid, {"id": sid, "name": _str(name), "kind": "application",
                                 "system_of_record": False, "api_available": None, "data_classes": []})
        return sid

    def control_id(name: str) -> str:
        cid = wl.make_id("control", name)
        controls.setdefault(cid, {"id": cid, "name": _str(name), "kind": "quality",
                                  "mode": "detective", "mandatory": True, "legal_basis": "",
                                  "evidence": ""})
        return cid

    for fname, ex in files:
        stats["files"] += 1
        source = _str(ex.get("source")) or fname

        for o in ex.get("outcomes", []):
            name = _str(o.get("name"))
            if not name:
                continue
            oid = wl.make_id("outcome", name)
            # Zusammenführen, nicht ersetzen: Dateien werden alphabetisch verarbeitet, und
            # die Kennzahlen eines Ergebnisses entstehen erst beim Prozess in derselben oder
            # einer früheren Datei. Ein Ersetzen würde sie stillschweigend wieder abräumen.
            entry = outcomes.setdefault(oid, {
                "id": oid, "name": name, "description": "", "beneficiary": "",
                "metric_ids": [], "source_refs": [],
            })
            # Beschreibende Felder: die erste Datei gewinnt (wie in build_graph.py).
            if not entry["description"]:
                entry["description"] = _str(o.get("description"))
            if not entry["beneficiary"]:
                entry["beneficiary"] = _str(o.get("beneficiary"))
            entry["source_refs"] = sorted(set(entry["source_refs"] + [source]))

        for sy in ex.get("systems", []):
            name = _str(sy.get("name")) if isinstance(sy, dict) else _str(sy)
            if not name:
                continue
            sid = system_id(name)
            if isinstance(sy, dict):
                systems[sid].update({
                    "kind": _str(sy.get("kind")) or "application",
                    "system_of_record": bool(sy.get("system_of_record", False)),
                    "api_available": sy.get("api_available"),
                    "data_classes": [d for d in sy.get("data_classes", []) if d in wl.ENUM_DATA_CLASS],
                })

        for c in ex.get("controls", []):
            name = _str(c.get("name")) if isinstance(c, dict) else _str(c)
            if not name:
                continue
            cid = control_id(name)
            if isinstance(c, dict):
                controls[cid].update({
                    "kind": _enum(c.get("kind"), wl.ENUM_CONTROL_KIND, "quality"),
                    "mode": _enum(c.get("mode"), wl.ENUM_CONTROL_MODE, "detective"),
                    "mandatory": bool(c.get("mandatory", True)),
                    "legal_basis": _str(c.get("legal_basis")),
                    "evidence": _str(c.get("evidence")),
                })

        for pr in ex.get("processes", []):
            pname = _str(pr.get("name"))
            if not pname:
                continue
            where = f"{fname}: Prozess {pname!r}"
            pid = wl.make_id("process", pname)
            stats["processes"] += 1

            oc_name = _str(pr.get("outcome"))
            oid = wl.make_id("outcome", oc_name) if oc_name else None
            if oid:
                entry = outcomes.setdefault(oid, {
                    "id": oid, "name": oc_name, "description": "",
                    "beneficiary": "", "metric_ids": [], "source_refs": [],
                })
                if not entry["beneficiary"]:
                    entry["beneficiary"] = _str(pr.get("beneficiary"))
                entry["source_refs"] = sorted(set(entry["source_refs"] + [source]))

            baseline_ids = []
            for m in pr.get("baseline_metrics", []):
                mname = _str(m.get("name"))
                if not mname:
                    continue
                mid = wl.make_id("metric", pname, mname)
                entry = {
                    "id": mid, "name": mname, "process_id": pid,
                    "kind": _enum(m.get("kind"), wl.ENUM_METRIC_KIND, "outcome"),
                    "unit": _str(m.get("unit")),
                    "direction": _enum(m.get("direction"), wl.ENUM_METRIC_DIRECTION, "lower_is_better"),
                }
                for stage in VALUE_STAGES:
                    block = _value_block(m.get(stage))
                    if block is not None:
                        entry[stage] = block
                previous = prev_metrics.get(mid)
                if previous:
                    # Ein Messwert beschreibt den veränderten Prozess und steht nicht
                    # in der Ist-Extraktion. Er bleibt erhalten.
                    if previous.get("observed") is not None and "observed" not in entry:
                        entry["observed"] = previous["observed"]
                    if previous.get("target") is not None and "target" not in entry:
                        entry["target"] = previous["target"]
                metrics[mid] = entry
                baseline_ids.append(mid)
                stats["metrics"] += 1
                if oid:
                    outcomes[oid]["metric_ids"] = sorted(set(outcomes[oid]["metric_ids"] + [mid]))
                for pv in m.get("provenance", []) or []:
                    _add_provenance(provenance, "metrics", mid, pv, source, default_field="baseline")

            step_ids = []
            step_name_to_id = {}
            # Nur benannte Schritte bilden den Prozess. Ein namenloser Schritt wird gemeldet,
            # statt still zu verschwinden — sonst fehlt er im Modell und niemand weiß warum.
            named_steps = []
            for pos, st in enumerate(pr.get("steps", []), start=1):
                if _str(st.get("name")):
                    named_steps.append(st)
                else:
                    idx.problems.append(f"{where}: Schritt an Position {pos} hat keinen Namen "
                                        "und wurde nicht übernommen")
            for st in named_steps:
                sname = _str(st.get("name"))
                sid = wl.make_id("process_step", pname, sname)
                step_name_to_id[wl.normalize_name(sname)] = sid
                sw = f"{where}, Schritt {sname!r}"
                ex_raw = st.get("executor")
                if isinstance(ex_raw, str):
                    ex_raw = {"type": ex_raw}
                ex_raw = ex_raw or {}
                etype = _enum(ex_raw.get("type"), wl.ENUM_EXECUTOR, "human")
                role_id = idx.role(_str(st.get("role")), sw)
                if etype == "human":
                    eid = role_id or idx.role(_str(ex_raw.get("id")), sw)
                elif etype == "agent":
                    eid = idx.agent(_str(ex_raw.get("id")) or _str(ex_raw.get("name")), sw)
                elif etype == "system":
                    eid = system_id(_str(ex_raw.get("id")) or _str(ex_raw.get("name"))) \
                        if (_str(ex_raw.get("id")) or _str(ex_raw.get("name"))) else None
                else:
                    eid = None
                task_ids = [t for t in (idx.task(role_id, _str(x), sw) for x in st.get("tasks", [])) if t]

                hg = st.get("human_gate")
                human_gate = None
                if isinstance(hg, dict) and (hg.get("when") or hg.get("role")):
                    human_gate = {"when": _str(hg.get("when")),
                                  "role_id": idx.role(_str(hg.get("role")) or _str(hg.get("role_id")), sw)}
                dec = st.get("decision")
                decision = None
                if isinstance(dec, dict) and dec.get("scope"):
                    decision = {
                        "scope": _enum(dec.get("scope"), wl.ENUM_DECISION_SCOPE, "recommend"),
                        "accountable_role_id": idx.role(
                            _str(dec.get("accountable_role")) or _str(dec.get("accountable_role_id")), sw),
                        "escalation": _str(dec.get("escalation")),
                    }

                steps[sid] = {
                    "id": sid, "process_id": pid, "name": sname,
                    "description": _str(st.get("description")),
                    "task_ids": sorted(set(task_ids)),
                    "executor": {"type": etype, "id": eid},
                    "role_id": role_id,
                    "inputs": sorted({_str(x) for x in st.get("inputs", []) if _str(x)}),
                    "outputs": sorted({_str(x) for x in st.get("outputs", []) if _str(x)}),
                    "system_ids": sorted({system_id(_str(x)) for x in st.get("systems", []) if _str(x)}),
                    "control_ids": sorted({control_id(_str(x)) for x in st.get("controls", []) if _str(x)}),
                    "data_classes": sorted({d for d in st.get("data_classes", []) if d in wl.ENUM_DATA_CLASS}),
                    "handling_time_min": _num(st.get("handling_time_min"), 0.0),
                    "wait_time_min": _num(st.get("wait_time_min"), 0.0),
                    "rework_pct": _num(st.get("rework_pct"), 0.0),
                    "value_type": _enum(st.get("value_type"), wl.ENUM_VALUE_TYPE, "business_required"),
                    "human_gate": human_gate,
                    "decision": decision,
                    "source_refs": [source],
                }
                step_ids.append(sid)
                stats["steps"] += 1
                for pv in st.get("provenance", []) or []:
                    _add_provenance(provenance, "process_steps", sid, pv, source, default_field="handling_time_min")

            # Kanten: entweder ausdrücklich über "next" je Schritt, sonst linear in Reihenfolge.
            # Die implizite Kette läuft über named_steps, nicht über die Rohliste — sonst
            # zeigte sie bei einem namenlosen Schritt ins Leere und die Kette bräche ab.
            explicit = any(st.get("next") for st in named_steps)
            for i, st in enumerate(named_steps):
                sname = _str(st.get("name"))
                from_id = step_name_to_id[wl.normalize_name(sname)]
                targets = st.get("next") or []
                if not targets and not explicit and i + 1 < len(named_steps):
                    targets = [{"to": named_steps[i + 1].get("name"), "handover": "system"}]
                for nx in targets:
                    if isinstance(nx, str):
                        nx = {"to": nx}
                    to_name = wl.normalize_name(_str(nx.get("to")))
                    to_id = step_name_to_id.get(to_name)
                    if not to_id:
                        idx.problems.append(f"{where}: Kante von {sname!r} nach "
                                            f"{_str(nx.get('to'))!r} — Zielschritt unbekannt")
                        continue
                    cond = _str(nx.get("condition"))
                    eid = wl.make_id("process_edge", pname, sname, _str(nx.get("to")), cond)
                    edges[eid] = {
                        "id": eid, "process_id": pid,
                        "from_step_id": from_id, "to_step_id": to_id,
                        "condition": cond,
                        "handover": _enum(nx.get("handover"), wl.ENUM_HANDOVER, "system"),
                        "share_pct": _num(nx.get("share_pct")),
                    }
                    stats["edges"] += 1

            previous = prev_processes.get(pid)
            # Der Status kommt aus dem Entscheidungslog, nicht aus der Extraktion.
            status = "generated"
            if previous and pid in decided:
                status = previous.get("status", "generated")
            processes[pid] = {
                "id": pid, "name": pname,
                "trigger": _str(pr.get("trigger")),
                "outcome_id": oid,
                "beneficiary": _str(pr.get("beneficiary")),
                "owner_role_id": idx.role(_str(pr.get("owner_role")) or _str(pr.get("owner_role_id")), where),
                "volume_per_year": _num(pr.get("volume_per_year")),
                "variants": [_str(v) for v in pr.get("variants", []) if _str(v)],
                "regulated": bool(pr.get("regulated", False)),
                "data_classes": sorted({d for d in pr.get("data_classes", []) if d in wl.ENUM_DATA_CLASS}),
                "baseline_metric_ids": sorted(set(baseline_ids)),
                "step_ids": step_ids,
                "status": status,
                "source_refs": [source],
            }
            if previous and previous.get("value") is not None:
                # Die Prozessbewertung entsteht in score_processes.py und wird hier
                # unverändert mitgenommen; sonst müsste sie nach jedem Lauf neu entstehen.
                processes[pid]["value"] = previous["value"]
            for pv in pr.get("provenance", []) or []:
                _add_provenance(provenance, "processes", pid, pv, source, default_field="volume_per_year")

    # Bestehende Governance- und Redesign-Artefakte bleiben erhalten.
    keep_prov = {p["id"]: p for p in graph.get("provenance", [])}
    keep_prov.update(provenance)
    graph["outcomes"] = list(outcomes.values())
    graph["systems"] = list(systems.values())
    graph["controls"] = list(controls.values())
    graph["metrics"] = list(metrics.values())
    graph["processes"] = list(processes.values())
    graph["process_steps"] = list(steps.values())
    graph["process_edges"] = list(edges.values())

    # Verwaiste Provenienz aussortieren. IDs sind Hashes der Namen: Wer eine Kennzahl oder
    # einen Schritt umbenennt, erzeugt eine neue ID — der alte Provenienzeintrag zeigt dann
    # ins Leere und der Validator lehnt den Graphen ab. Ohne diese Bereinigung bliebe ein
    # Projekt nach einer Umbenennung dauerhaft blockiert, bis jemand den Graphen von Hand
    # repariert. Geprüft wird nur, was dieses Skript selbst neu aufbaut; Provenienz zu
    # Rollen, Aufgaben oder Agenten bleibt unangetastet.
    rebuilt = {"outcomes": outcomes, "systems": systems, "controls": controls,
               "metrics": metrics, "processes": processes, "process_steps": steps,
               "process_edges": edges}
    live_prov = {}
    for pid, entry in keep_prov.items():
        table = rebuilt.get(entry.get("entity_type"))
        if table is not None and entry.get("entity_id") not in table:
            idx.problems.append(
                f"Provenienz zu {entry.get('entity_type')}/{entry.get('entity_id')} "
                f"(Feld '{entry.get('field')}') entfernt — der Eintrag existiert nicht mehr, "
                "vermutlich nach einer Umbenennung")
            stats["provenance_dropped"] += 1
            continue
        live_prov[pid] = entry
    graph["provenance"] = list(live_prov.values())
    wl.sort_graph(graph)
    return graph, stats, idx.problems


def _add_provenance(store: dict, entity_type: str, entity_id: str, pv: Any, source: str,
                    default_field: str) -> None:
    if not isinstance(pv, dict):
        return
    field = _str(pv.get("field")) or default_field
    pid = wl.make_id("provenance", entity_type, entity_id, field)
    store[pid] = {
        "id": pid,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "field": field,
        "source_kind": _enum(pv.get("source_kind"), wl.ENUM_SOURCE_KIND, "estimate"),
        "source_ref": _str(pv.get("source_ref")) or source,
        "locator": _str(pv.get("locator")),
        "author": _str(pv.get("author")),
        "reviewer": _str(pv.get("reviewer")),
        "confidence": _num(pv.get("confidence"), 0.5),
        "status": _enum(pv.get("status"), wl.ENUM_PROVENANCE_STATUS, "asserted"),
        "as_of": _str(pv.get("as_of")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph, stats, problems = build(project)
    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    for w in warnings:
        print(f"WARNUNG  {w}")
    if errors:
        wl.fail("Prozessebene nicht geschrieben, bitte Prozessextraktionen korrigieren")
    path, version, changed = wl.save_graph_version(project, graph, "processes")
    verb = "Geschrieben" if changed else "Unverändert"
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | Dateien={stats['files']} "
          f"Prozesse={stats['processes']} Schritte={stats['steps']} Kanten={stats['edges']} "
          f"Kennzahlen={stats['metrics']}")
    for pr in sorted(graph["processes"], key=lambda p: p["id"]):
        t = wl.process_totals(graph, pr["id"])
        print(f"  {pr['name']}: {t['steps']} Schritte, {t['human_touches']} Human Touchpoints, "
              f"{t['handovers']} Übergaben, Durchlaufzeit {t['lead_time_hours']} h, "
              f"{t['waste_steps']} Schritte ohne Wertbeitrag")
        gap = wl.lead_time_gap(graph, pr["id"])
        if gap:
            print(f"HINWEIS  {pr['name']}: modelliert {gap['modelled_hours']} h, gemessen "
                  f"{gap['measured_hours']} h ({gap['deviation_pct']:+} %). Das Modell erklärt die "
                  "gemessene Durchlaufzeit nicht — es fehlen vermutlich Schritte oder Liegezeiten. "
                  "Jedes Redesign-Delta rechnet sonst auf einer zu kleinen Grundmenge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
