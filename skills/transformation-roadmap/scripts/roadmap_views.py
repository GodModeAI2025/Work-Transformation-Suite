#!/usr/bin/env python3
"""
roadmap_views.py — Markdown-Bausteine für Raster und Dokumente.

Jeder Baustein liefert Text, der Zahlen nur aus dem Plan nimmt und fehlende Angaben als
„nicht bewertet“ oder „❓ offen“ ausweist. Das Raster und die Dokumente setzen dieselben
Bausteine zusammen, damit Zahlen an keiner Stelle voneinander abweichen.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_lib as rl  # noqa: E402
import workgraph_lib as wl  # noqa: E402
from render_lib import OPEN, eur, md_table, num  # noqa: E402

STATUS_LABEL = {"live": "im Betrieb", "pilot": "Pilot", "building": "im Bau", "planned": "geplant",
                "proposed": "Vorschlag", "idea": "Idee"}
KIND_LABEL = {"agent": "Agent", "usecase": "Use Case"}
VALUE_NOTE = ("Wert ist die heute gebundene Arbeitszeit der betroffenen Aufgaben mal Tagessatz und damit eine "
              "Schätzung, was betroffen ist. Er sagt nicht, was eingespart wird.")


def period_of(w: dict) -> str:
    return w["period"] or OPEN


def state_of(p: dict, key: str) -> str:
    pl = p["placement"][key]
    base = rl.PLACEMENT_LABEL[pl["state"]]
    if pl["state"] == "confirmed" and pl["decided_by"]:
        return f"{base} ({pl['decided_by']})"
    return base


def wave_overview(p: dict) -> str:
    rows = []
    for w in p["waves"]:
        r = w["reach"]
        rows.append([w["label"], period_of(w), len(w["items"]), len(r["roles"]), num(r["fte_total"]) if r["roles"] else "–",
                     eur(r["value_eur"]), rl.WAVE_STATE_LABEL[w["state"]]])
    last = p["waves"][-1]["cumulative_reach"] if p["waves"] else None
    if last:
        rows.append(["**Alle Wellen zusammen**", "", sum(len(w["items"]) for w in p["waves"]), len(last["roles"]),
                     num(last["fte_total"]), eur(last["value_eur"]), ""])
    return md_table(["Welle", "Zeitraum", "Vorhaben", "Rollen", "FTE betroffen", "Wert/Jahr (geschätzt)", "Stand"],
                    rows, ["l", "l", "r", "r", "r", "r", "l"])


def wave_detail(p: dict, level: str = "###") -> str:
    out = []
    for w in p["waves"]:
        out += [f"{level} {w['label']}", ""]
        if not w["items"]:
            out += ["Keine Vorhaben in dieser Welle.", ""]
            continue
        rows = []
        surveyed = any(c.get("zone") for c in p["candidates"])
        for key in w["items"]:
            c = p["by_key"][key]
            row = [c["name"], KIND_LABEL[c["kind"]], STATUS_LABEL.get(c["status"], c["status"] or "–"),
                   num(c["score"]) if c["score"] is not None else "nicht bewertet",
                   eur(c["value_eur"]), num(c["fte"]), state_of(p, key)]
            if surveyed:
                row.append(zone_text(c))
            rows.append(row)
        heads = ["Vorhaben", "Art", "Status", "Score", "Wert/Jahr", "FTE", "Zuordnung"]
        align = ["l", "l", "l", "r", "r", "r", "l"]
        if surveyed:
            heads, align = heads + ["Sicht der Beschäftigten"], align + ["l"]
        out += [md_table(heads, rows, align), ""]
        prereq = [(p["by_key"][k]["name"], p["by_key"][k]["prerequisites"]) for k in w["items"]
                  if p["by_key"][k]["prerequisites"]]
        if prereq:
            out += ["Voraussetzungen laut Agentenbibliothek:", ""]
            out += [f"- {n}: {'; '.join(pr)}" for n, pr in prereq]
            out.append("")
        if w["reach"]["roles"]:
            rr = [[r["name"], num(r["headcount"], 0), f"{num(r['time_share_pct'])} %", num(r["fte"]), eur(r["value_eur"])]
                  for r in w["reach"]["roles"]]
            out += ["Betroffene Rollen:", "",
                    md_table(["Rolle", "Stellen", "Zeitanteil", "FTE", "Wert/Jahr"], rr, ["l", "r", "r", "r", "r"]), ""]
    return "\n".join(out)


def zone_text(c: dict) -> str:
    """„Freigabe 80 %“ aus der Zonenverteilung eines Vorhabens; „nicht befragt“ ohne Daten."""
    z = c.get("zone")
    if not z:
        return "nicht befragt"
    return f"{wl.AGENCY_ZONE_SHORT[z['main']]} {z['shares'][z['main']]:.0f} %"


def candidates_table(p: dict) -> str:
    rows = []
    for c in sorted(p["candidates"], key=lambda c: (c["score"] is None, -(c["score"] or 0), c["name"] or "")):
        comp = c["components"]
        rows.append([c["name"], KIND_LABEL[c["kind"]], num(c["score"]) if c["score"] is not None else "nicht bewertet"]
                    + [num(comp[k]) for k in rl.COMPONENTS]
                    + [c["value_source"], c["score_basis"], f"Welle {p['placement'][c['key']]['wave']}", state_of(p, c["key"])])
    heads = (["Vorhaben", "Art", "Score"] + [rl.COMPONENT_LABEL[k] for k in rl.COMPONENTS]
             + ["Wertquelle", "Basis des Scores", "Welle", "Zuordnung"])
    return md_table(heads, rows, ["l", "l", "r"] + ["r"] * 5 + ["l", "l", "l", "l"])


def architecture(p: dict) -> str:
    rows = []
    for a in p["architecture"]:
        if a["has_target"]:
            rows.append([a["family"], a["name"], num(a["headcount"], 0), num(a["fte_current"]), num(a["fte_remaining"]),
                         f"{num(a['retained_share_pct'], 0)} %" if a["retained_share_pct"] is not None else "–",
                         rl.ABSORPTION_LABEL.get(a["absorption"], "nicht festgelegt"),
                         f"Welle {a['first_wave']}" if a["first_wave"] else "keine",
                         "geschätzt" if a["target_basis"] == "estimated" else "von Fachleuten bestätigt"])
        else:
            rows.append([a["family"], a["name"], num(a["headcount"], 0), "nicht bewertet", "nicht bewertet", "–",
                         rl.ABSORPTION_LABEL.get(a["absorption"], "nicht festgelegt"),
                         f"Welle {a['first_wave']}" if a["first_wave"] else "keine", "kein Zielbild"])
    return md_table(["Jobfamilie", "Rolle", "Stellen heute", "FTE heute", "FTE künftig", "Bleibt", "Auffangweg",
                     "Erste Welle", "Basis"], rows, ["l", "l", "r", "r", "r", "r", "l", "l", "l"])


def gaps_block(p: dict) -> str:
    if not p["gaps"]:
        return "Keine: Jeder Prozess mit hohem Rang hat mindestens ein Vorhaben."
    rows = [[g["name"], "Jetzt" if g["band"] == "now" else "Als Nächstes", num(g["score"]), g["tasks"]] for g in p["gaps"]]
    return ("Prozesse mit hohem Rang, für die kein Vorhaben besteht. Das Raster verteilt nur, was es gibt.\n\n"
            + md_table(["Prozess", "Band", "Wert", "Aufgaben"], rows, ["l", "l", "r", "r"]))


def open_points(p: dict, graph: dict) -> list[str]:
    """Was vor einem Beschluss noch fehlt, aus den Daten abgeleitet."""
    pts = []
    pending = [w["label"] for w in p["waves"] if w["state"] in ("proposed", "partial")]
    if pending:
        pts.append("Wellenzuordnung bestätigen (bisher Vorschlag): " + "; ".join(pending))
    no_period = [w["label"] for w in p["waves"] if w["items"] and not w["period"]]
    if no_period:
        pts.append("Zeiträume festlegen: " + "; ".join(no_period))
    no_hc = [r["name"] for w in p["waves"][-1:] for r in w["cumulative_reach"]["roles"] if r["headcount"] is None]
    if no_hc:
        pts.append("Stellenzahl fehlt, FTE nicht berechenbar: " + ", ".join(sorted(no_hc)))
    no_rate = sorted({r["name"] for w in p["waves"][-1:] for r in w["cumulative_reach"]["roles"]
                      if r["headcount"] is not None and r["value_eur"] is None})
    if no_rate:
        pts.append("Tagessatz fehlt, Wert nicht berechenbar: " + ", ".join(no_rate))
    untargeted = [a["name"] for a in p["architecture"] if not a["has_target"] and a["first_wave"]]
    if untargeted:
        pts.append("Zielbild fehlt für betroffene Rollen: " + ", ".join(untargeted))
    unscored = [c["name"] for c in p["candidates"] if c["score"] is None]
    if unscored:
        pts.append("Vorhaben ohne ausreichende Angaben für einen Score: " + ", ".join(unscored))
    if p["gaps"]:
        pts.append("Prozesse mit hohem Rang ohne Vorhaben prüfen: " + ", ".join(g["name"] for g in p["gaps"]))
    if any(c.get("zone") for c in p["candidates"]):
        unsurveyed = sorted(c["name"] for c in p["candidates"] if not c.get("zone") and c["task_ids"])
        if unsurveyed:
            pts.append("Ohne Sicht der Beschäftigten (keine befragte Aufgabe): " + ", ".join(unsurveyed))
    pts += p["notes"]
    return pts
