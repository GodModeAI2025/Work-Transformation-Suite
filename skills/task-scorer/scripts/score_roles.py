#!/usr/bin/env python3
"""
score_roles.py — übernimmt Aufgabenbewertungen aus 20_graph/scores.json, wendet
Score-Overrides aus 30_review/overrides.csv an, leitet daraus deterministisch
Ausführungsmodus, HAS-Level und Zeithorizont je Aufgabe ab und aggregiert je
Rolle Disruptionsscore, Disruptionstyp, Zeitanteile und Handlungsempfehlung.

Aufruf:
    python3 <skill>/scripts/score_roles.py --project ./mein-projekt [--force]

--force  überschreibt vorhandene Scores mit denen aus scores.json (sonst werden nur
         Aufgaben ohne Scores befüllt). Overrides gewinnen in beiden Fällen.

Alle Regeln sind in references/rubric.md dokumentiert und hier als Konstanten
sichtbar. Wer eine Schwelle ändert, ändert sie an genau einer Stelle.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from apply_overrides import apply as apply_overrides  # noqa: E402
from validate_graph import validate  # noqa: E402

NUMERIC = ["automation_ai", "automation_physical", "human_judgment", "productivity_boost",
           "data_readiness", "consequence_of_error"]

# --- Schwellen (siehe references/rubric.md) ---------------------------------
DELEGATE_AP_MIN = 7.0
DELEGATE_HJ_MAX = 3.0
DELEGATE_COE_MAX = 5.0
DELEGATE_COE_MAX_REGULATED = 3.0
ASSIST_AP_MIN = 4.0
ASSIST_PB_MIN = 5.0
HORIZON_NEAR_DR_MIN = 6.0
HORIZON_NEAR_COE_MAX = 5.0
HORIZON_MID_DR_MIN = 3.0
W_AP, W_PB, W_HJ = 0.5, 0.3, 0.2
ELIM_DELEGATED_MIN = 60.0
ELIM_HJ_MAX = 3.0
TRANS_DELEGATED_MIN = 30.0
TRANS_AP_MIN, TRANS_HJ_MAX = 6.0, 5.0
AUG_AUTOMATABLE_MIN = 40.0
AUG_PB_MIN = 5.0
ROLE_HORIZON_SHARE = 30.0

TRANSFORMATION_LOGIC = {
    "eliminated": ("Redesign-Potenzial → Eliminiert → Retire-Critical",
                   "Aufgaben strukturiert an Agenten und Nachbarrollen umverteilen; Abhängigkeiten in Prozessen und Freigaben prüfen, bevor Kapazität abgebaut wird."),
    "transformed": ("Redesign-Potenzial → Transformiert → Rolle neu schneiden",
                    "Rolle um den menschlichen Kern neu definieren: delegierbare Aufgaben an Agenten, verbleibende Aufgaben zu einem neuen Profil bündeln, Skillplan aufsetzen."),
    "augmented": ("Produktivitätshebel → Augmentiert → KI-Assistenz ausrollen",
                  "KI-Werkzeuge für die assistierbaren Aufgaben bereitstellen, Schulung und Qualitätssicherung einführen, Zeitgewinn in Kernaufgaben lenken."),
    "emerging": ("Neue Rolle → Entstehend → Profil und Besetzung planen",
                 "Rollenprofil finalisieren, Skills definieren, Besetzung aus transformierten Rollen prüfen."),
    "stable": ("Geringe Exposition → Stabil → Beobachten",
               "Keine strukturelle Änderung; punktuelle KI-Assistenz optional, Neubewertung in 12 Monaten."),
}

HORIZON_LABEL = {"near": "kurzfristig (0–2 Jahre)", "mid": "mittelfristig (2–5 Jahre)", "long": "langfristig (5+ Jahre)"}


def automation_potential(sc: dict[str, Any], nature: str) -> float:
    ai = float(sc["automation_ai"])
    ph = float(sc["automation_physical"])
    if nature == "physical":
        return wl.round1(ph)
    if nature == "mixed":
        return wl.round1((ai + ph) / 2.0)
    return wl.round1(ai)


def derive_mode(ap: float, hj: float, pb: float, coe: float, regulated: bool) -> str:
    coe_max = DELEGATE_COE_MAX_REGULATED if regulated else DELEGATE_COE_MAX
    if ap >= DELEGATE_AP_MIN and hj <= DELEGATE_HJ_MAX and coe <= coe_max:
        return "agent_delegated"
    if ap >= ASSIST_AP_MIN or pb >= ASSIST_PB_MIN:
        return "ai_assisted"
    return "manual"


def classify_role(role: dict[str, Any], ap: float, hj: float, pb: float, s_del: float, s_ass: float) -> str:
    if role.get("is_new"):
        return "emerging"
    if s_del >= ELIM_DELEGATED_MIN and hj <= ELIM_HJ_MAX:
        return "eliminated"
    if s_del >= TRANS_DELEGATED_MIN or (ap >= TRANS_AP_MIN and hj <= TRANS_HJ_MAX):
        return "transformed"
    if (s_del + s_ass) >= AUG_AUTOMATABLE_MIN or pb >= AUG_PB_MIN:
        return "augmented"
    return "stable"


def derive_task(t: dict[str, Any], role: dict[str, Any]) -> None:
    sc = t["scores"]
    ap = automation_potential(sc, t["nature"])
    hj = float(sc["human_judgment"])
    pb = float(sc["productivity_boost"])
    dr = float(sc["data_readiness"])
    coe = float(sc["consequence_of_error"])
    mode = derive_mode(ap, hj, pb, coe, bool(role.get("regulated")))

    if ap >= 8 and hj <= 2:
        has = 1
    elif ap >= 6 and hj <= 4:
        has = 2
    elif ap >= 4 and hj <= 6:
        has = 3
    elif ap >= 2:
        has = 4
    else:
        has = 5

    if mode == "manual":
        horizon = None
    elif dr >= HORIZON_NEAR_DR_MIN and coe <= HORIZON_NEAR_COE_MAX:
        horizon = "near"
    elif dr >= HORIZON_MID_DR_MIN:
        horizon = "mid"
    else:
        horizon = "long"

    t["automation_potential"] = ap
    t["mode"] = mode
    t["has_level"] = has
    t["horizon"] = horizon


def evidence_level(role: dict[str, Any], scored: list[dict[str, Any]], total: float) -> dict[str, Any]:
    """Belastbarkeit der Rollenbewertung: Woher stammen Zeitanteile, Aufgaben, Headcount, gab es Review?

    Punkte: Zeitanteile aus Quelle +2 · Rolle reviewed +2 / approved +3 · < 20 % der Zeit
    aus abgeleiteten Aufgaben +1 · Headcount bekannt +1. high ≥ 5, medium ≥ 2, sonst low.
    """
    points, reasons = 0, []
    if role.get("time_shares_source") == "source":
        points += 2
        reasons.append("Zeitanteile aus Quelle")
    else:
        reasons.append("Zeitanteile geschätzt")
    st = role.get("status")
    if st == "approved":
        points += 3
        reasons.append("von Experten freigegeben")
    elif st == "reviewed":
        points += 2
        reasons.append("von Experten geprüft")
    else:
        reasons.append("ungeprüft")
    inferred = sum(float(t["share_of_time"]) for t in scored if t.get("confidence") == "inferred") * 100.0 / total
    if inferred < 20:
        points += 1
    else:
        reasons.append(f"{inferred:.0f} % der Zeit aus abgeleiteten Aufgaben")
    if role.get("headcount") is not None:
        points += 1
    else:
        reasons.append("Headcount unbekannt")
    level = "high" if points >= 5 else "medium" if points >= 2 else "low"
    return {"level": level, "points": points, "reasons": reasons}


def tipping_analysis(role: dict[str, Any], scored: list[dict[str, Any]], total: float, base_type: str) -> dict[str, Any]:
    """Kipp-Analyse: Wie viele Einzeländerungen um ±1 an Maschinenanteil, Urteilsbedarf oder
    Fehlergewicht einer Aufgabe ändern die Rollenwirkung? Deterministisch, ohne Zufall."""
    regulated = bool(role.get("regulated"))
    fields = ["automation_ai", "human_judgment", "consequence_of_error"]
    flips, trials, examples = 0, 0, []
    for i, t in enumerate(scored):
        for f in fields:
            for delta in (-1, 1):
                v = float(t["scores"][f]) + delta
                if v < 0 or v > 10:
                    continue
                trials += 1
                # Rolle mit einer veränderten Aufgabe neu bewerten
                ap_sum = hj_sum = pb_sum = 0.0
                s_del = s_ass = 0.0
                for j, u in enumerate(scored):
                    sc = dict(u["scores"])
                    if j == i:
                        sc[f] = v
                    ap = automation_potential(sc, u["nature"])
                    hj = float(sc["human_judgment"])
                    pb = float(sc["productivity_boost"])
                    coe = float(sc["consequence_of_error"])
                    mode = derive_mode(ap, hj, pb, coe, regulated)
                    w = float(u["share_of_time"])
                    ap_sum += ap * w
                    hj_sum += hj * w
                    pb_sum += pb * w
                    if mode == "agent_delegated":
                        s_del += w
                    elif mode == "ai_assisted":
                        s_ass += w
                new_type = classify_role(role, wl.round1(ap_sum / total), wl.round1(hj_sum / total), wl.round1(pb_sum / total),
                                         wl.round1(s_del * 100.0 / total), wl.round1(s_ass * 100.0 / total))
                if new_type != base_type:
                    flips += 1
                    if len(examples) < 3:
                        examples.append({"task": t["name"], "field": f, "delta": delta, "new_type": new_type})
    share = wl.round1(100.0 * flips / trials) if trials else 0.0
    stability = "stable" if flips == 0 else "borderline" if share <= 10 else "fragile"
    return {"stability": stability, "flip_share": share, "examples": examples}


def aggregate_role(role: dict[str, Any], tasks: list[dict[str, Any]], skills: dict[str, dict]) -> dict[str, Any]:
    scored = [t for t in tasks if t.get("scores")]
    total = sum(float(t["share_of_time"]) for t in scored)
    if not scored or total <= 0:
        return {"scored": False, "tasks_total": len(tasks), "tasks_scored": len(scored)}

    def wmean(key_fn) -> float:
        return wl.round1(sum(key_fn(t) * float(t["share_of_time"]) for t in scored) / total)

    ap = wmean(lambda t: float(t["automation_potential"]))
    ai = wmean(lambda t: float(t["scores"]["automation_ai"]))
    ph = wmean(lambda t: float(t["scores"]["automation_physical"]))
    hj = wmean(lambda t: float(t["scores"]["human_judgment"]))
    pb = wmean(lambda t: float(t["scores"]["productivity_boost"]))
    dr = wmean(lambda t: float(t["scores"]["data_readiness"]))
    coe = wmean(lambda t: float(t["scores"]["consequence_of_error"]))

    def share(mode: str) -> float:
        return wl.round1(sum(float(t["share_of_time"]) for t in scored if t["mode"] == mode) * 100.0 / total)

    s_del, s_ass, s_man = share("agent_delegated"), share("ai_assisted"), share("manual")
    # Rundungsrest deterministisch auf den größten Anteil
    diff = wl.round1(100.0 - (s_del + s_ass + s_man))
    if abs(diff) >= 0.05:
        biggest = max([("agent_delegated", s_del), ("ai_assisted", s_ass), ("manual", s_man)], key=lambda x: (x[1], x[0]))[0]
        if biggest == "agent_delegated":
            s_del = wl.round1(s_del + diff)
        elif biggest == "ai_assisted":
            s_ass = wl.round1(s_ass + diff)
        else:
            s_man = wl.round1(s_man + diff)

    disruption = wl.round1(W_AP * ap + W_PB * pb + W_HJ * (10.0 - hj))

    dtype = classify_role(role, ap, hj, pb, s_del, s_ass)

    def hshare(h: str) -> float:
        return sum(float(t["share_of_time"]) for t in scored if t.get("horizon") == h) * 100.0 / total

    near, mid = hshare("near"), hshare("mid")
    if s_del + s_ass <= 0:
        rhorizon = None
    elif near >= ROLE_HORIZON_SHARE:
        rhorizon = "near"
    elif near + mid >= ROLE_HORIZON_SHARE:
        rhorizon = "mid"
    else:
        rhorizon = "long"

    # Bereitschaft: Datenlage der delegier-/assistierbaren Aufgaben
    auto_tasks = [t for t in scored if t["mode"] != "manual"]
    if auto_tasks:
        at = sum(float(t["share_of_time"]) for t in auto_tasks)
        readiness_val = wl.round1(sum(float(t["scores"]["data_readiness"]) * float(t["share_of_time"]) for t in auto_tasks) / at)
        readiness = "high" if readiness_val >= 7 else "medium" if readiness_val >= 4 else "low"
    else:
        readiness_val, readiness = None, "n/a"

    # Skills: welche hängen an bleibenden (manuell/assistiert), welche an delegierten Aufgaben.
    # retained = weiterhin gebraucht; declining = Bedarf sinkt, weil die Aufgaben an Agenten gehen.
    skill_share: dict[str, dict[str, float]] = {}
    for t in scored:
        for sid in t.get("skill_ids", []):
            d = skill_share.setdefault(sid, {"manual": 0.0, "ai_assisted": 0.0, "agent_delegated": 0.0})
            d[t["mode"]] += float(t["share_of_time"])
    retained_skills, declining_skills = [], []
    for sid, d in sorted(skill_share.items()):
        tot = sum(d.values())
        if tot <= 0:
            continue
        name = skills.get(sid, {}).get("name", sid)
        if d["agent_delegated"] / tot >= 0.6:
            declining_skills.append(name)
        elif (d["manual"] + d["ai_assisted"]) / tot >= 0.6:
            retained_skills.append(name)

    logic, action = TRANSFORMATION_LOGIC[dtype]
    evidence = evidence_level(role, scored, total)
    tipping = tipping_analysis(role, scored, total, dtype)
    return {
        "scored": True,
        "evidence": evidence["level"],
        "evidence_points": evidence["points"],
        "evidence_reasons": evidence["reasons"],
        "stability": tipping["stability"],
        "flip_share": tipping["flip_share"],
        "flip_examples": tipping["examples"],
        "tasks_total": len(tasks),
        "tasks_scored": len(scored),
        "automation_potential": ap,
        "automation_ai": ai,
        "automation_physical": ph,
        "human_judgment": hj,
        "productivity_boost": pb,
        "data_readiness": dr,
        "consequence_of_error": coe,
        "share_agent_delegated": s_del,
        "share_ai_assisted": s_ass,
        "share_human_core": s_man,
        "disruption_score": disruption,
        "disruption_type": dtype,
        "horizon": rhorizon,
        "horizon_label": HORIZON_LABEL.get(rhorizon, "nicht anwendbar"),
        "readiness": readiness,
        "readiness_value": readiness_val,
        "transformation_logic": logic,
        "next_action": action,
        "retained_skills": sorted(retained_skills),
        "declining_skills": sorted(declining_skills),
    }


def merge_scores(graph: dict[str, Any], scores: dict[str, Any], force: bool) -> tuple[int, list[str]]:
    tasks = wl.index_by_id(graph["tasks"])
    n, problems = 0, []
    for tid in sorted(scores):
        entry = scores[tid]
        t = tasks.get(tid)
        if not t:
            problems.append(f"scores.json: Task {tid} nicht im Graphen")
            continue
        if t.get("scores") and not force:
            continue
        sc = {}
        bad = False
        for f in NUMERIC:
            v = entry.get(f)
            if v is None:
                problems.append(f"{tid} ({t['name']}): {f} fehlt")
                bad = True
                continue
            try:
                sc[f] = float(wl.clamp(float(v), 0, 10))
            except (TypeError, ValueError):
                problems.append(f"{tid}: {f}={v!r} keine Zahl")
                bad = True
        if bad:
            continue
        sc["rationale"] = str(entry.get("rationale", "")).strip()
        t["scores"] = sc
        n += 1
    return n, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")

    scores_path = project / wl.DIR_GRAPH / "scores.json"
    merged, problems = 0, []
    if scores_path.exists():
        merged, problems = merge_scores(graph, wl.read_json(scores_path), args.force)
    else:
        print(f"HINWEIS  {wl.relpath(scores_path)} fehlt, verwende nur vorhandene Bewertungen")

    ov = project / wl.DIR_REVIEW / "overrides.csv"
    ov_applied = 0
    if ov.exists():
        ov_applied, ov_problems = apply_overrides(graph, wl.read_csv(ov))
        problems += ov_problems

    roles = wl.index_by_id(graph["roles"])
    skills = wl.index_by_id(graph["skills"])
    for t in graph["tasks"]:
        if t.get("scores"):
            derive_task(t, roles[t["role_id"]])
    tasks_by_role: dict[str, list] = {}
    for t in graph["tasks"]:
        tasks_by_role.setdefault(t["role_id"], []).append(t)
    unscored_roles = 0
    for r in graph["roles"]:
        r["analysis"] = aggregate_role(r, tasks_by_role.get(r["id"], []), skills)
        if not r["analysis"]["scored"]:
            unscored_roles += 1

    for p in problems:
        print(f"HINWEIS  {p}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "scorer")
    verb = "Geschrieben" if changed else "Unverändert"
    counts = {}
    for r in graph["roles"]:
        dt = r["analysis"].get("disruption_type", "unscored")
        counts[dt] = counts.get(dt, 0) + 1
    print(
        f"{verb}: {wl.relpath(path)} (Version {version}) | Scores übernommen={merged} Overrides={ov_applied} "
        f"Rollen ohne Bewertung={unscored_roles} | " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
