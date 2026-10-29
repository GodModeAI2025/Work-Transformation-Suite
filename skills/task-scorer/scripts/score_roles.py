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
# Realisierbarkeit (Schema 1.2): Delegierte Arbeit wird voll als frei werdende Zeit gezählt,
# assistierte nur zu einem Fünftel — KI-Unterstützung verkürzt eine Aufgabe, ersetzt sie nicht.
ASSIST_FREED_FACTOR = wl.ASSIST_FREED_FACTOR
# Schema 1.4: zwei Merkmale der Aufgabe, die die Stanford-Befragung als Kennzeichen hoher Human Agency
# zeigt. Zwischenmenschliche Arbeit (Beziehung, Einfühlung, Verhandlung) landet nicht unter H4;
# Arbeit, die an nirgends aufgeschriebener Erfahrung hängt, nicht unter H3. Beide sind optional.
HAS_FLOOR_INTERPERSONAL = 4
HAS_FLOOR_TACIT = 3
FLAGS = ["interpersonal", "tacit_expertise"]
# Plausibilität: Mehr als dieser Anteil der Rollen mit überwiegend H1 ist ungewöhnlich (in der
# Stanford-Erhebung 16 von 104 Berufen) und spricht eher für zu optimistische Bewertungen.
H1_DOMINANT_MAX_SHARE = 25.0

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


def derive_has(ap: float, hj: float, sc: dict[str, Any]) -> int:
    """HAS-Stufe aus Potenzial und Urteilsbedarf, angehoben durch die Merkmale der Aufgabe."""
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
    if sc.get("interpersonal") is True:
        has = max(has, HAS_FLOOR_INTERPERSONAL)
    if sc.get("tacit_expertise") is True:
        has = max(has, HAS_FLOOR_TACIT)
    return has


def derive_task(t: dict[str, Any], role: dict[str, Any]) -> None:
    sc = t["scores"]
    ap = automation_potential(sc, t["nature"])
    hj = float(sc["human_judgment"])
    pb = float(sc["productivity_boost"])
    dr = float(sc["data_readiness"])
    coe = float(sc["consequence_of_error"])
    mode = derive_mode(ap, hj, pb, coe, bool(role.get("regulated")))
    has = derive_has(ap, hj, sc)

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


def capacity(role: dict[str, Any], s_del: float, s_ass: float) -> dict[str, Any]:
    """Frei werdende Kapazität: technisch möglich gegenüber tatsächlich auffangbar.

    Technisch ist, was die Aufgabenbewertung hergibt. Realisierbar ist davon nur der Teil,
    den die Organisation auffängt — durch Wachstum, Fluktuation und Altersteilzeit oder
    durch Umbesetzung. Fehlt die Angabe, bleibt `fte_realisable` leer: „nicht bewertet“
    ist eine andere Aussage als „null“.
    """
    hc = role.get("headcount_from_positions")
    if hc is None:
        hc = role.get("headcount")
    if hc is None:
        return {"headcount_basis": None, "fte_released_technical": None,
                "fte_realisable": None, "absorption": role.get("absorption")}
    hc = float(hc)
    technical = wl.round1(hc * (s_del + ASSIST_FREED_FACTOR * s_ass) / 100.0)
    absorption = role.get("absorption")
    realisable = None
    if absorption in wl.ENUM_ABSORPTION:
        default_pct = 0.0 if absorption == "none" else 100.0
        pct = float(role["absorption_pct"]) if role.get("absorption_pct") is not None else default_pct
        realisable = wl.round1(technical * pct / 100.0)
    return {"headcount_basis": hc, "fte_released_technical": technical,
            "fte_realisable": realisable, "absorption": absorption}


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

    has_weight: dict[int, float] = {}
    for t in scored:
        has_weight[int(t["has_level"])] = has_weight.get(int(t["has_level"]), 0.0) + float(t["share_of_time"])
    best = max(has_weight.values())
    has_dominant = max(k for k, v in has_weight.items() if v == best)

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
        "has_dominant": has_dominant,
        "horizon": rhorizon,
        "horizon_label": HORIZON_LABEL.get(rhorizon, "nicht anwendbar"),
        "readiness": readiness,
        "readiness_value": readiness_val,
        "transformation_logic": logic,
        "next_action": action,
        **capacity(role, s_del, s_ass),
        "retained_skills": sorted(retained_skills),
        "declining_skills": sorted(declining_skills),
    }


def skill_shift(graph: dict[str, Any]) -> None:
    """Kompetenzverschiebung je Skill (Schema 1.4): mittlere nötige Human Agency der Aufgaben, an denen
    der Skill hängt, und die Arbeit, die heute an ihm gebunden ist.

    Gebundene Arbeit ist FTE (Zeitanteil × Stellen), wo alle beteiligten Rollen einen Headcount haben,
    sonst die Summe der Zeitanteile in Prozent. Die Stanford-Auswertung stellt Lohn gegen Human Agency;
    ein Haus hat Löhne selten freigegeben, gebundene Arbeit ist hier das Wertmaß.
    """
    roles = wl.index_by_id(graph["roles"])
    use: dict[str, list[tuple[float, float, Any]]] = {}
    for t in graph["tasks"]:
        if t.get("has_level") is None:
            continue
        r = roles.get(t["role_id"]) or {}
        for sid in t.get("skill_ids", []):
            use.setdefault(sid, []).append((float(t["has_level"]), float(t.get("share_of_time") or 0), wl.role_headcount(r)))
    for sk in graph["skills"]:
        sk.pop("analysis", None)
        rows = use.get(sk["id"])
        if not rows:
            continue
        weight = sum(w for _, w, _ in rows) or 1.0
        fte_known = all(hc is not None for _, _, hc in rows)
        bound = (wl.round1(sum(w * float(hc) / 100.0 for _, w, hc in rows)) if fte_known
                 else wl.round1(sum(w for _, w, _ in rows)))
        sk["analysis"] = {"human_agency": wl.round1(sum(h * w for h, w, _ in rows) / weight),
                          "bound_work": bound, "bound_basis": "fte" if fte_known else "share_pct", "tasks": len(rows)}


def plausibility(graph: dict[str, Any]) -> list[str]:
    """Hinweise auf auffällige Bewertungsmuster; keine Fehler, nur Anlass zum Gegenlesen."""
    scored = [r for r in graph["roles"] if (r.get("analysis") or {}).get("scored")]
    notes = []
    if len(scored) >= 4:
        h1 = [r for r in scored if r["analysis"].get("has_dominant") == 1]
        share = 100.0 * len(h1) / len(scored)
        if share > H1_DOMINANT_MAX_SHARE:
            notes.append(f"{len(h1)} von {len(scored)} Rollen ({share:.0f} %) überwiegend H1 (Agent allein). In der Stanford-Erhebung "
                         f"sind es 16 von 104 Berufen; Bewertungen von Urteilsbedarf und Fehlerfolge gegenlesen: "
                         + ", ".join(sorted(r["name"] for r in h1)))
    flagged = [t for t in graph["tasks"] if (t.get("scores") or {}).get("interpersonal") or (t.get("scores") or {}).get("tacit_expertise")]
    delegated = [t["name"] for t in flagged if t.get("mode") == "agent_delegated"]
    if delegated:
        notes.append("An Agenten delegiert, obwohl als zwischenmenschlich oder erfahrungsgebunden markiert: "
                      + ", ".join(sorted(delegated)) + ". Delegation und Merkmal widersprechen sich; eins von beiden prüfen.")
    return notes


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
        for f in FLAGS:
            if isinstance(entry.get(f), bool):
                sc[f] = entry[f]
            elif entry.get(f) is not None:
                problems.append(f"{tid} ({t['name']}): {f}={entry[f]!r} ist kein true/false, ignoriert")
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

    skill_shift(graph)
    for p in problems:
        print(f"HINWEIS  {p}")
    for n in plausibility(graph):
        print(f"PLAUSIBILITÄT  {n}")
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
