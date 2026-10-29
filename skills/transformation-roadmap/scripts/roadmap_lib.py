#!/usr/bin/env python3
"""
roadmap_lib.py — Kandidaten, Bewertung, Wellenbildung und Jobarchitektur für das Fahrplan-Raster.

Die Funktionen sind rein: gleicher Graph, gleiche Konfiguration, gleiche Entscheidungen ergeben
dasselbe Raster. Was ein Mensch entscheiden muss (Welle, Zeitraum, Beschluss), steht nie hier,
sondern kommt aus `30_review/wellen.csv` und aus der Konfiguration.

Grundsätze:
- Ein Vorschlag bleibt Vorschlag, bis eine benannte Person ihn bestätigt hat.
- „Nicht bewertet“ ist nicht null: fehlt eine Größe, fehlt sie in der Ausgabe, und der Score
  rechnet nur mit dem, was bekannt ist.
- Wert und Reichweite beschreiben die gebundene Arbeit, nicht die Ersparnis.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_DIR / "assets" / "wave-config.json"
DECISIONS_FILE = "wellen.csv"
DECISION_COLUMNS = ["eintrag", "welle", "begruendung", "entschieden_von", "datum"]
COMPONENTS = ["value", "reach", "ease", "readiness", "process"]
COMPONENT_LABEL = {"value": "Wert", "reach": "Reichweite", "ease": "Umsetzbarkeit",
                   "readiness": "Reifegrad", "process": "Prozessrang"}
ABSORPTION_LABEL = {"growth": "Wachstum", "attrition": "Fluktuation / Altersteilzeit",
                    "redeployment": "Umbesetzung", "none": "kein Auffangweg"}
PLACEMENT_LABEL = {"confirmed": "bestätigt", "running": "läuft bereits", "proposed": "Vorschlag"}


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(wl.read_json(DEFAULT_CONFIG))
    if path is not None:
        user = wl.read_json(Path(path))
        for key, val in user.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(val)
            else:
                cfg[key] = val
    problems = check_config(cfg)
    if problems:
        wl.fail("Konfiguration ungültig: " + "; ".join(problems))
    return cfg


def check_config(cfg: dict[str, Any]) -> list[str]:
    problems = []
    waves = cfg.get("waves") or []
    if not waves:
        problems.append("keine Wellen definiert")
    ids = [w.get("id") for w in waves]
    if len(set(ids)) != len(ids) or any(not isinstance(i, int) for i in ids):
        problems.append("Wellen-IDs müssen eindeutige ganze Zahlen sein")
    elif ids != sorted(ids):
        problems.append("Wellen müssen aufsteigend sortiert sein")
    for w in waves:
        cap = w.get("capacity")
        if cap is not None and (not isinstance(cap, int) or cap < 1):
            problems.append(f"Welle {w.get('id')}: capacity muss eine ganze Zahl ≥ 1 oder null sein")
    red = cfg.get("max_red_zone_share_first_wave", 50)
    if not isinstance(red, (int, float)) or not 0 <= red <= 100:
        problems.append("max_red_zone_share_first_wave muss zwischen 0 und 100 liegen")
    weights = cfg.get("weights") or {}
    if set(weights) != set(COMPONENTS):
        problems.append("weights braucht genau: " + ", ".join(COMPONENTS))
    elif any((not isinstance(v, (int, float))) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        problems.append("weights: Werte ≥ 0, Summe > 0")
    return problems


# ---------------------------------------------------------------------------
# Reichweite einer Aufgabenmenge (ohne Doppelzählung)
# ---------------------------------------------------------------------------

def reach_of_tasks(graph: dict[str, Any], task_ids) -> dict[str, Any]:
    """Betroffene Rollen, FTE und Wert für eine Menge von Aufgaben.

    Eine Aufgabe zählt einmal, auch wenn mehrere Vorhaben sie berühren. Der Wert entsteht nur
    bei gesetztem Tagessatz; Rollen ohne Headcount oder ohne Tagessatz werden gezählt und
    ausgewiesen, nicht mit null verrechnet.
    """
    tasks = wl.index_by_id(graph.get("tasks", []))
    roles = wl.index_by_id(graph.get("roles", []))
    per_role: dict[str, float] = {}
    for tid in sorted(set(task_ids)):
        t = tasks.get(tid)
        if t and t.get("role_id") in roles:
            per_role[t["role_id"]] = per_role.get(t["role_id"], 0.0) + float(t.get("share_of_time") or 0)
    rows, fte_total, value_total = [], 0.0, 0.0
    value_known = False
    no_headcount = no_rate = 0
    for rid in sorted(per_role, key=lambda r: (roles[r].get("name") or "", r)):
        r = roles[rid]
        hc = wl.role_headcount(r)
        share = min(100.0, per_role[rid])
        fte = wl.round1(float(hc) * share / 100.0) if hc is not None else None
        val = wl.day_value(r, fte)
        if fte is None:
            no_headcount += 1
        else:
            fte_total += fte
            if val is None:
                no_rate += 1
        if val is not None:
            value_total += val
            value_known = True
        rows.append({"role_id": rid, "name": r.get("name"), "headcount": hc,
                     "time_share_pct": wl.round1(share), "fte": fte, "value_eur": val})
    return {"roles": rows, "fte_total": wl.round1(fte_total),
            "value_eur": wl.round1(value_total) if value_known else None,
            "roles_without_headcount": no_headcount, "roles_without_rate": no_rate}


# ---------------------------------------------------------------------------
# Kandidaten
# ---------------------------------------------------------------------------

def zone_of_tasks(graph: dict[str, Any], task_ids) -> dict[str, Any] | None:
    """Beschäftigtensicht einer Aufgabenmenge: Anteil der Zonen an der befragten Zeit (Schema 1.4).

    Gewichtet wird mit dem Zeitanteil der Aufgabe in ihrer Rolle. Ohne befragte Aufgabe gibt es
    keine Aussage (None), nicht „alles in Ordnung“.
    """
    tasks = wl.index_by_id(graph.get("tasks", []))
    zones: dict[str, float] = {}
    rated = total = 0.0
    for tid in sorted(set(task_ids)):
        t = tasks.get(tid)
        if not t:
            continue
        w = float(t.get("share_of_time") or 0) or 1.0
        total += w
        z = (t.get("agency") or {}).get("zone")
        if z:
            zones[z] = zones.get(z, 0.0) + w
            rated += w
    if not rated:
        return None
    shares = {z: wl.round1(100.0 * v / rated) for z, v in sorted(zones.items())}
    main = sorted(shares.items(), key=lambda kv: (-kv[1], wl.ENUM_AGENCY_ZONE.index(kv[0])))[0][0]
    return {"shares": shares, "main": main, "rated_pct": wl.round1(100.0 * rated / total) if total else None}


def _task_bands(graph: dict[str, Any], cfg: dict[str, Any]) -> dict[str, tuple[str, float]]:
    """Beste Prioritätsstufe je Aufgabe aus den Prozessen, in denen sie vorkommt."""
    scores = cfg["band_score"]
    best: dict[str, tuple[str, float]] = {}
    for pr in graph.get("processes", []):
        band = (pr.get("value") or {}).get("band")
        if band not in scores:
            continue
        for s in wl.steps_of(graph, pr["id"]):
            for tid in s.get("task_ids", []):
                if tid not in best or scores[band] > best[tid][1]:
                    best[tid] = (band, float(scores[band]))
    return best


def build_candidates(graph: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Vorhaben, die das Raster verteilt: Agenten und Use Cases ohne Agent.

    Ein Use Case, der auf Agenten verweist, wird in deren Kandidat eingefaltet, damit dieselbe
    Arbeit nicht zweimal als Vorhaben erscheint.
    """
    agents = {a["id"]: a for a in graph.get("agents", [])}
    folded: dict[str, list[dict[str, Any]]] = {}
    standalone = []
    for u in graph.get("usecases", []):
        targets = [aid for aid in u.get("agent_ids", []) if aid in agents]
        if targets:
            for aid in targets:
                folded.setdefault(aid, []).append(u)
        else:
            standalone.append(u)
    bands = _task_bands(graph, cfg)
    out = []
    for a in sorted(agents.values(), key=lambda x: (x.get("name") or "", x["id"])):
        ucs = folded.get(a["id"], [])
        task_ids = sorted(set(a.get("task_ids", [])) | {t for u in ucs for t in u.get("task_ids", [])})
        declared = [u.get("value_eur_per_year") for u in ucs if u.get("value_eur_per_year") is not None]
        out.append({
            "key": a["id"], "kind": "agent", "name": a.get("name"), "status": a.get("status"),
            "complexity": a.get("complexity"), "evidence_grade": a.get("evidence_grade"),
            "orchestrates": [x for x in (a.get("orchestrates") or []) if x in agents],
            "prerequisites": list(a.get("prerequisites") or []),
            "capability": a.get("capability") or "",
            "usecases": [u.get("name") for u in ucs], "task_ids": task_ids,
            "value_declared_eur": wl.round1(sum(declared)) if declared else None,
        })
    for u in sorted(standalone, key=lambda x: (x.get("name") or "", x["id"])):
        out.append({
            "key": u["id"], "kind": "usecase", "name": u.get("name"),
            "status": (u.get("status") or "idea"), "complexity": None, "evidence_grade": None,
            "orchestrates": [], "prerequisites": [], "capability": u.get("description") or "",
            "usecases": [], "task_ids": sorted(set(u.get("task_ids", []))),
            "value_declared_eur": u.get("value_eur_per_year"),
        })
    for c in out:
        r = reach_of_tasks(graph, c["task_ids"])
        c["reach"] = r
        c["value_estimated_eur"] = r["value_eur"]
        c["fte"] = r["fte_total"] if r["roles"] and r["roles_without_headcount"] < len(r["roles"]) else None
        c["bands"] = sorted({bands[t][0] for t in c["task_ids"] if t in bands},
                            key=lambda b: -cfg["band_score"][b])
        c["band_score"] = max((bands[t][1] for t in c["task_ids"] if t in bands), default=None)
        c["zone"] = zone_of_tasks(graph, c["task_ids"])
    return out


def score_candidates(cands: list[dict[str, Any]], cfg: dict[str, Any]) -> None:
    """Hängt `components`, `score`, `score_basis` an; rechnet nur mit bekannten Größen."""
    weights = cfg["weights"]
    max_value = max((c["value_declared_eur"] if c["value_declared_eur"] is not None else (c["value_estimated_eur"] or 0)
                     for c in cands), default=0) or 0
    max_fte = max((c["fte"] or 0 for c in cands), default=0) or 0
    for c in cands:
        value = c["value_declared_eur"] if c["value_declared_eur"] is not None else c["value_estimated_eur"]
        c["value_eur"] = value
        c["value_source"] = ("Team-Angabe" if c["value_declared_eur"] is not None
                             else ("geschätzt (Tagessatz × Zeitanteil)" if value is not None else "nicht bewertet"))
        comp: dict[str, float | None] = {
            "value": wl.round1(10.0 * value / max_value) if value is not None and max_value > 0 else None,
            "reach": wl.round1(10.0 * c["fte"] / max_fte) if c["fte"] is not None and max_fte > 0 else None,
            "ease": (wl.round1(10.0 * (5 - min(5, max(1, int(c["complexity"])))) / 4.0)
                     if c["complexity"] is not None else None),
            "readiness": (float(cfg["status_readiness"][c["status"]])
                          if c["status"] in cfg["status_readiness"] else None),
            "process": c["band_score"],
        }
        known = {k: v for k, v in comp.items() if v is not None}
        c["components"] = comp
        if len(known) < int(cfg.get("min_components", 2)):
            c["score"], c["score_basis"] = None, "nicht bewertet (zu wenige Angaben)"
            continue
        wsum = sum(weights[k] for k in known)
        c["score"] = wl.round1(sum(weights[k] * v for k, v in known.items()) / wsum) if wsum > 0 else None
        missing = [COMPONENT_LABEL[k] for k in COMPONENTS if k not in known]
        c["score_basis"] = ("alle fünf Größen" if not missing
                            else f"{len(known)} von 5 Größen (es fehlt: {', '.join(missing)})")


# ---------------------------------------------------------------------------
# Entscheidungen
# ---------------------------------------------------------------------------

def read_decisions(project: Path, cands: list[dict[str, Any]], cfg: dict[str, Any]):
    """Wellenzuordnungen aus `30_review/wellen.csv`. Ohne Verantwortlichen zählt eine Zeile nicht."""
    path = project / wl.DIR_REVIEW / DECISIONS_FILE
    if not path.exists():
        return {}, []
    by_name = {wl.normalize_name(c["name"] or ""): c["key"] for c in cands}
    by_key = {c["key"]: c["key"] for c in cands}
    wave_ids = [w["id"] for w in cfg["waves"]]
    decisions, warnings = {}, []
    for n, row in enumerate(wl.read_csv(path), start=2):
        label = (row.get("eintrag") or "").strip()
        if not label:
            continue
        key = by_key.get(label) or by_name.get(wl.normalize_name(label))
        if key is None:
            warnings.append(f"{DECISIONS_FILE} Zeile {n}: Eintrag {label!r} nicht gefunden, ignoriert")
            continue
        try:
            wave = int(str(row.get("welle") or "").strip())
        except ValueError:
            wave = None
        if wave not in wave_ids:
            warnings.append(f"{DECISIONS_FILE} Zeile {n}: Welle {row.get('welle')!r} nicht definiert, ignoriert")
            continue
        who = (row.get("entschieden_von") or "").strip()
        if not who:
            warnings.append(f"{DECISIONS_FILE} Zeile {n}: {label!r} ohne Verantwortlichen nicht übernommen "
                            "(ein Vorschlag wird erst durch eine benannte Person zur Entscheidung)")
            continue
        if key in decisions:
            warnings.append(f"{DECISIONS_FILE} Zeile {n}: {label!r} steht mehrfach, die letzte Zeile gilt")
        decisions[key] = {"wave": wave, "reason": (row.get("begruendung") or "").strip(),
                          "decided_by": who, "date": (row.get("datum") or "").strip()}
    return decisions, warnings


# ---------------------------------------------------------------------------
# Wellenbildung
# ---------------------------------------------------------------------------

def assign_waves(cands, cfg, decisions):
    """Verteilt die Kandidaten auf Wellen. Gibt (Zuordnung, Hinweise) zurück.

    Reihenfolge: 1) bestätigte Entscheidungen, 2) laufende Vorhaben (Pilot/live) in die erste
    Welle, 3) der Rest nach Score, 4) Orchestratoren frühestens eine Welle nach den Agenten,
    die sie steuern. Schwere Vorhaben (Komplexität über der Grenze) beginnen nicht in Welle 1.
    """
    waves = cfg["waves"]
    ids = [w["id"] for w in waves]
    cap = {w["id"]: w.get("capacity") for w in waves}
    count = {i: 0 for i in ids}
    placement: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    by_key = {c["key"]: c for c in cands}
    running = set(cfg.get("running_statuses") or [])
    red_max = float(cfg.get("max_red_zone_share_first_wave", 50))

    def red_share(c) -> float:
        return float(((c.get("zone") or {}).get("shares") or {}).get("red", 0.0))

    for key, d in sorted(decisions.items()):
        placement[key] = {"wave": d["wave"], "state": "confirmed", "reason": d["reason"] or "Entscheidung",
                          "decided_by": d["decided_by"], "date": d["date"]}
        count[d["wave"]] += 1
    for c in cands:
        if c["key"] not in placement and c["status"] in running:
            placement[c["key"]] = {"wave": ids[0], "state": "running",
                                   "reason": f"Status „{c['status']}“: läuft schon und dient als Referenz",
                                   "decided_by": "", "date": ""}
            count[ids[0]] += 1

    def rank(c):
        return (c["score"] is None, -(c["score"] or 0.0), c["name"] or "", c["key"])

    def place(c, min_wave_index=0):
        for idx in range(min_wave_index, len(ids)):
            wid = ids[idx]
            if idx == 0 and c["complexity"] is not None and c["complexity"] > int(cfg.get("max_complexity_first_wave", 5)):
                continue
            if idx == 0 and red_share(c) > red_max:
                # Arbeit, die die Beschäftigten nicht abgeben wollen, beginnt nicht ohne Entscheidung.
                gated.add(c["key"])
                continue
            if cap[wid] is None or count[wid] < cap[wid]:
                if min_wave_index and idx == min_wave_index:
                    reason = "frühestens nach den gesteuerten Agenten"
                elif idx == 0:
                    reason = "Rang nach Score"
                elif c["key"] in gated:
                    reason = (f"Vorsichtszone überwiegt ({red_share(c):.0f} % der befragten Zeit): nicht in der ersten Welle "
                              "ohne Entscheidung")
                else:
                    reason = "Rang nach Score, frühere Wellen belegt oder zu schwer"
                placement[c["key"]] = {"wave": wid, "state": "proposed", "reason": reason,
                                       "decided_by": "", "date": ""}
                count[wid] += 1
                return
        wid = ids[-1]
        placement[c["key"]] = {"wave": wid, "state": "proposed",
                               "reason": "Kapazität aller Wellen belegt, in die letzte Welle gelegt",
                               "decided_by": "", "date": ""}
        count[wid] += 1
        notes.append(f"{c['name']}: Kapazität der Wellen überschritten, in {waves[-1]['label']} gelegt")

    gated: set[str] = set()
    rest = sorted((c for c in cands if c["key"] not in placement), key=rank)
    leaders = [c for c in rest if not c["orchestrates"]]
    orchestrators = [c for c in rest if c["orchestrates"]]
    for c in leaders:
        place(c)
    for c in sorted(orchestrators, key=rank):
        member_waves = [ids.index(placement[m]["wave"]) for m in c["orchestrates"] if m in placement]
        place(c, min(len(ids) - 1, max(member_waves) + 1) if member_waves else 0)

    for c in cands:
        if c["key"] in gated:
            notes.append(f"{c['name']}: überwiegend Vorsichtszone (machbar, von den Beschäftigten nicht gewünscht), "
                         "deshalb nicht in der ersten Welle; Gespräch vor dem Start")
        elif red_share(c) > red_max and placement.get(c["key"], {}).get("wave") == ids[0]:
            notes.append(f"{c['name']}: liegt in der ersten Welle, obwohl die Arbeit überwiegend in der Vorsichtszone liegt "
                         "(Entscheidung oder laufendes Vorhaben); Gespräch mit den Beschäftigten einplanen")
    # Abhängigkeitsverstöße durch bestätigte Entscheidungen melden, nicht stillschweigend ändern.
    for c in cands:
        if not c["orchestrates"] or c["key"] not in placement:
            continue
        mine = ids.index(placement[c["key"]]["wave"])
        for m in c["orchestrates"]:
            if m in placement and ids.index(placement[m]["wave"]) >= mine:
                notes.append(f"{c['name']} steuert {by_key[m]['name']}, liegt aber nicht nach ihm "
                             "(Abhängigkeit prüfen)")
    return placement, notes


def gaps(graph: dict[str, Any], cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prozesse in den Bändern „Jetzt“ und „Als Nächstes“, für die kein Vorhaben besteht."""
    return wl.blind_spots(graph)


# ---------------------------------------------------------------------------
# Raster
# ---------------------------------------------------------------------------

WAVE_STATE_LABEL = {"empty": "leer", "proposed": "Vorschlag", "partial": "teils entschieden",
                    "settled": "entschieden oder läuft bereits"}


def _wave_state(states: list[str]) -> str:
    if not states:
        return "empty"
    open_n = sum(1 for s in states if s == "proposed")
    return "proposed" if open_n == len(states) else ("partial" if open_n else "settled")


def plan(graph: dict[str, Any], cfg: dict[str, Any], decisions=None) -> dict[str, Any]:
    """Das vollständige Raster: Vorhaben je Welle, betroffene Rollen, Lücken, Jobarchitektur."""
    decisions = decisions or {}
    cands = build_candidates(graph, cfg)
    score_candidates(cands, cfg)
    placement, notes = assign_waves(cands, cfg, decisions)
    by_key = {c["key"]: c for c in cands}
    wave_rows, cumulative = [], set()
    for w in cfg["waves"]:
        items = sorted((c for c in cands if placement[c["key"]]["wave"] == w["id"]),
                       key=lambda c: (c["score"] is None, -(c["score"] or 0.0), c["name"] or "", c["key"]))
        tasks = sorted({t for c in items for t in c["task_ids"]})
        cumulative |= set(tasks)
        wave_rows.append({
            "id": w["id"], "label": w["label"], "period": w.get("period") or "", "capacity": w.get("capacity"),
            "items": [c["key"] for c in items],
            "reach": reach_of_tasks(graph, tasks),
            "cumulative_reach": reach_of_tasks(graph, sorted(cumulative)),
            "state": _wave_state([placement[c["key"]]["state"] for c in items]),
        })
    for w in wave_rows:
        cap_w = cap_of(cfg, w["id"])
        if cap_w is not None and len(w["items"]) > cap_w:
            notes.append(f"{w['label']}: {len(w['items'])} Vorhaben bei Kapazität {cap_w} "
                         "(laufende oder bestätigte Vorhaben zählen immer)")
    return {"candidates": cands, "placement": placement, "waves": wave_rows, "notes": notes,
            "gaps": gaps(graph, cands), "architecture": job_architecture(graph, wave_rows, cands, placement),
            "config": cfg, "by_key": by_key}


def job_architecture(graph, wave_rows, cands, placement) -> list[dict[str, Any]]:
    """Jobarchitektur heute und künftig je Rolle, mit der ersten Welle, die die Rolle berührt."""
    clusters = wl.index_by_id(graph.get("job_clusters", []))
    families = wl.index_by_id(graph.get("job_families", []))
    targets = {t["role_id"]: t for t in graph.get("target_roles", []) if t.get("role_id")}
    first_wave: dict[str, int] = {}
    for w in wave_rows:
        for r in w["reach"]["roles"]:
            first_wave.setdefault(r["role_id"], w["id"])
    rows = []
    for r in graph.get("roles", []):
        fam_id = (clusters.get(r.get("cluster_id")) or {}).get("family_id")
        t = targets.get(r["id"])
        an = r.get("analysis") or {}
        rows.append({
            "role_id": r["id"], "name": r.get("name"),
            "family": (families.get(fam_id) or {}).get("name", "ohne Jobfamilie"),
            "headcount": wl.role_headcount(r),
            "disruption_type": (t or {}).get("disruption_type") or an.get("disruption_type"),
            "retained_share_pct": (t or {}).get("retained_share_pct"),
            "fte_current": (t or {}).get("fte_current"),
            "fte_remaining": (t or {}).get("fte_remaining"),
            "fte_realisable": (t or {}).get("fte_realisable"),
            "absorption": (t or {}).get("absorption") or r.get("absorption"),
            "target_basis": (t or {}).get("basis"), "target_status": (t or {}).get("status"),
            "target_summary": (t or {}).get("summary") or "",
            "has_target": t is not None, "first_wave": first_wave.get(r["id"]),
        })
    rows.sort(key=lambda x: (x["family"], x["name"] or "", x["role_id"]))
    return rows


def cap_of(cfg: dict[str, Any], wave_id: int):
    return next((w.get("capacity") for w in cfg["waves"] if w["id"] == wave_id), None)


def plan_to_json(p: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    """Serialisierbare Form für 40_output/roadmap_vNNN.json."""
    meta = graph.get("meta", {})
    return {
        "graph_version": meta.get("version"), "schema_version": meta.get("schema_version"),
        "organization": meta.get("organization"), "scope": meta.get("scope"),
        "weights": p["config"]["weights"], "notes": p["notes"], "gaps": p["gaps"],
        "waves": [{**{k: v for k, v in w.items() if k not in ("reach", "cumulative_reach")},
                   "reach": w["reach"], "cumulative_reach": w["cumulative_reach"]} for w in p["waves"]],
        "items": [{**{k: v for k, v in c.items() if k not in ("reach",)},
                   "placement": p["placement"][c["key"]]} for c in p["candidates"]],
        "architecture": p["architecture"],
    }
