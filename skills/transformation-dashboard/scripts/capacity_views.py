"""
capacity_views.py — Ansichten und Berichte zu Schema 1.2: Kapazität, Zielbild, Nutzungsstand,
Reichweite — und die beiden Berichtsvarianten (HR und IT).

Zwei Spuren, ein Graph:

- Spur A, Rollenaggregation: Je Jobfamilie technisches und realisierbares Potenzial, dazu das
  Zielbild je Rolle. Schnell, grob, für HR. Das ist der zweitbeste Weg.
- Spur B, Prozessredesign: Ketten, Übergaben, Wert je Prozess. Belastbarer, für IT und
  Fachbereiche. Das ist der beste Weg, weil Einzelrollen nur Teile eines Ablaufs sehen.

Alle Zahlen hier sind Schätzungen aus der Aufgabenbewertung. Wo etwas nicht bewertet ist,
steht „nicht bewertet“, nie null.
"""

from __future__ import annotations

import html
from typing import Any

import agency_views as av
import workgraph_lib as wl

# Sprache für HR-Leser: Eine Rolle „verändert sich“, sie „entfällt“ nicht. Die Typen sind
# Aussagen über Aufgabenanteile, nicht über Menschen.
HR_TYPE_LABEL = {
    "eliminated": "Aufgaben gehen überwiegend an Agenten — Rolle verändert sich grundlegend",
    "transformed": "Rolle wird um ihren menschlichen Kern neu geschnitten",
    "augmented": "Rolle bleibt, KI unterstützt",
    "emerging": "Neue Rolle",
    "stable": "Rolle bleibt im Kern",
    "unscored": "nicht bewertet",
}
ABSORPTION_LABEL = {"growth": "Wachstum", "attrition": "Fluktuation / Altersteilzeit",
                    "redeployment": "Umbesetzung", "none": "nicht auffangbar", None: "nicht bewertet"}
ADOPTION_LABEL = {"prioritized": "priorisiert", "building": "im Bau", "in_use": "in Nutzung"}
GRADE_LABEL = {"heuristic": "Heuristik", "expert_confirmed": "fachlich bestätigt", "proven": "erprobt"}
BAND_LABEL = {"now": "Jetzt", "next": "Als Nächstes", "later": "Später", "hold": "Zurückstellen"}


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def f1(x: Any, nd: int = 1) -> str:
    return "nicht bewertet" if x is None else f"{x:.{nd}f}"


def has_capacity_data(graph: dict[str, Any]) -> bool:
    return any((r.get("analysis") or {}).get("fte_released_technical") is not None for r in graph["roles"])


def has_any(graph: dict[str, Any]) -> bool:
    return bool(has_capacity_data(graph) or graph.get("target_roles") or graph.get("adoption")
                or graph.get("usecases") or av.has_agency(graph))


# ---------------------------------------------------------------------------
# HTML-Abschnitte
# ---------------------------------------------------------------------------

def capacity_html(graph: dict[str, Any]) -> str:
    fams = wl.family_capacity(graph)
    if not fams:
        return ""
    rows = "".join(
        f'<tr><td>{esc(f["name"])}</td><td class="n">{f["roles"]}</td><td class="n">{f1(f["headcount"], 0)}</td>'
        f'<td class="n">{f1(f["fte_technical"])}</td><td class="n">{f1(f["fte_realisable"]) if not f["roles_unassessed"] else f1(f["fte_realisable"]) + " + offen"}</td>'
        f'<td class="n">{f["roles_unassessed"]}</td></tr>' for f in fams)
    return f"""<section id="kapazitaet"><h2>Kapazität: technisch möglich, tatsächlich auffangbar</h2>
<p>Spur A: je Jobfamilie, wie viel Arbeit die Bewertung frei setzt und wie viel davon die Organisation auffangen kann (Wachstum, Fluktuation, Altersteilzeit, Umbesetzung). Der Unterschied ist die Mahnung: Automatisierung, die keine Kapazität freisetzt, bringt keine Produktivität.</p>
<table><thead><tr><th>Jobfamilie</th><th class="n">Rollen</th><th class="n">Headcount</th><th class="n">FTE technisch</th><th class="n">FTE auffangbar</th><th class="n">Rollen ohne Bewertung</th></tr></thead><tbody>{rows}</tbody></table>
<p class="meta" style="margin-top:8px">Technisch = Headcount × (delegierter Zeitanteil + {int(wl.ASSIST_FREED_FACTOR * 100)} % des assistierten). „Nicht bewertet“ heißt: für die Rolle fehlt die Angabe <code>absorption</code>; das ist nicht dasselbe wie null.</p></section>"""


def target_html(graph: dict[str, Any]) -> str:
    trs = graph.get("target_roles") or []
    if not trs:
        return ""
    roles = wl.index_by_id(graph["roles"])
    rows = []
    for t in sorted(trs, key=lambda x: (roles.get(x["role_id"], {}).get("name", ""), x["id"])):
        merge = ", ".join(roles[r]["name"] for r in t.get("merge_with_role_ids", []) if r in roles) or "–"
        rows.append(f'<tr><td>{esc(roles[t["role_id"]]["name"])}</td><td>{esc(HR_TYPE_LABEL.get(t.get("disruption_type"), "–"))}</td>'
                    f'<td class="n">{f1(t["retained_share_pct"], 0)} %</td><td class="n">{f1(t.get("fte_current"))}</td>'
                    f'<td class="n">{f1(t.get("fte_remaining"))}</td><td class="n">{f1(t.get("fte_realisable"))}</td>'
                    f'<td>{esc(ABSORPTION_LABEL.get(t.get("absorption")))}</td><td>{esc(merge)}</td></tr>')
    return f"""<section id="zielbild"><h2>Zielbild je Rolle (Entwurf)</h2>
<p>Was bleibt, wenn alle delegierbaren Aufgaben übernommen würden, und wie viel davon auffangbar ist. Ein Entwurf aus der Aufgabenbewertung, keine Prognose und keine Entscheidung: Welche Rollen künftig gebraucht werden, ist eine Unternehmensfrage.</p>
<table><thead><tr><th>Rolle</th><th>Wirkung</th><th class="n">Bleibt</th><th class="n">FTE heute</th><th class="n">FTE danach (technisch)</th><th class="n">FTE auffangbar</th><th>Auffangweg</th><th>Zusammenlegung prüfen</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>"""


def adoption_html(graph: dict[str, Any]) -> str:
    ad = graph.get("adoption") or []
    if not ad:
        return ""
    roles = wl.index_by_id(graph["roles"])
    names = {**{a["id"]: a["name"] for a in graph["agents"]}, **{u["id"]: u["name"] for u in graph["usecases"]}}
    rows, supp = [], 0
    for a in sorted(ad, key=lambda x: (names.get(x.get("agent_id") or x.get("usecase_id"), ""),
                                       roles.get(x["role_id"], {}).get("name", ""))):
        who = names.get(a.get("agent_id") or a.get("usecase_id"), "–")
        rn = roles.get(a["role_id"], {}).get("name", "–")
        if a.get("suppressed"):
            supp += 1
            rows.append(f'<tr><td>{esc(who)}</td><td>{esc(rn)}</td><td colspan="4" class="meta">unterdrückt — weniger als {wl.ADOPTION_MIN_GROUP} Stellen</td></tr>')
            continue
        n = a["group_size"]
        done, bld, prio = a["in_use"], a["building"], a["prioritized"]
        rest = max(0, n - done - bld - prio)
        rows.append(f'<tr><td>{esc(who)}</td><td>{esc(rn)}</td><td class="n">{n}</td><td class="n">{prio}</td><td class="n">{bld}</td><td class="n">{done}</td>'
                    f'<td class="n">{rest}</td></tr>')
    return f"""<section id="nutzung"><h2>Nutzungsstand je Rolle</h2>
<p>Wie weit ist eine Automatisierung in einer Rolle? Nur Rolle × Agent, nie Person × Agent. Sätze unter {wl.ADOPTION_MIN_GROUP} Stellen werden nicht gezeigt; eine Quote für drei Menschen wäre Leistungskontrolle.</p>
<table><thead><tr><th>Agent / Use Case</th><th>Rolle</th><th class="n">Stellen</th><th class="n">priorisiert</th><th class="n">im Bau</th><th class="n">in Nutzung</th><th class="n">noch nichts</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<p class="meta" style="margin-top:8px">{supp} Sätze unterdrückt. Wo einige Stellen schon nutzen und andere nicht, können die einen den anderen zeigen, was sie gebaut haben.</p></section>"""


def reach_html(graph: dict[str, Any]) -> str:
    reach = wl.agent_reach(graph)
    spots = wl.blind_spots(graph)
    if not reach and not spots:
        return ""
    rows = "".join(
        f'<tr><td>{"Agent" if r["kind"] == "agent" else "Use Case"}</td><td>{esc(r["name"])}</td><td class="n">{len(r["roles"])}</td>'
        f'<td class="n">{f1(r["fte_total"])}</td><td class="n">{f1(r["value_eur_estimated"], 0)}</td><td class="n">{f1(r["value_eur_declared"], 0)}</td></tr>'
        for r in reach)
    spot_html = ("".join(f'<li><b>{esc(s["name"])}</b> ({BAND_LABEL[s["band"]]}, Wert {f1(s["score"])}, {s["tasks"]} Aufgaben)</li>' for s in spots)
                 or "<li>Keine</li>")
    return f"""<section id="reichweite"><h2>Reichweite und Blindflecken</h2>
<p>Für wie viele Rollen und FTE gilt ein Agent oder Use Case? Und welche hochwertigen Prozesse hat bisher niemand angefragt?</p>
<table><thead><tr><th>Typ</th><th>Name</th><th class="n">Rollen</th><th class="n">FTE betroffen</th><th class="n">Wert/Jahr (Suite)</th><th class="n">Wert/Jahr (Team)</th></tr></thead><tbody>{rows}</tbody></table>
<div class="k meta" style="margin-top:10px">Blindflecken</div><ul>{spot_html}</ul></section>"""


def sections(graph: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    """Alle Abschnitte plus Navigationseinträge. Leer, solange keine Schema-1.2-Daten da sind."""
    parts = [("#kapazitaet", "Kapazität", capacity_html(graph)), ("#zielbild", "Zielbild", target_html(graph)),
             ("#nutzung", "Nutzung", adoption_html(graph)), ("#reichweite", "Reichweite", reach_html(graph))]
    shown = [p for p in parts if p[2]]
    return "\n".join(p[2] for p in shown), [(p[0], p[1]) for p in shown]


# ---------------------------------------------------------------------------
# Berichte: HR und IT
# ---------------------------------------------------------------------------

def hr_report(graph: dict[str, Any], title: str) -> str:
    meta = graph["meta"]
    roles = wl.index_by_id(graph["roles"])
    lines = [f"# {title} — Bericht für HR", "",
             f"{meta.get('organization', '')} · {meta.get('scope', '')} · Work-Graph Version {meta.get('version')}", "",
             "Dieser Bericht beschreibt, wie sich Arbeit verändern kann und was davon die Organisation "
             "auffangen könnte. Er ist ein **Entwurf aus Schätzungen**, keine Prognose und kein Plan. "
             "Ob und wie Rollen künftig geschnitten werden, ist eine Entscheidung des Unternehmens — "
             "die Zahlen hier sind die Grundlage für diese Entscheidung, nicht ihr Ersatz.", ""]
    fams = wl.family_capacity(graph)
    lines += ["## Kapazität je Jobfamilie", ""]
    if fams:
        lines += ["| Jobfamilie | Rollen | Headcount | FTE technisch | FTE auffangbar | Rollen ohne Bewertung |",
                  "|---|---:|---:|---:|---:|---:|"]
        for f in fams:
            lines.append(f"| {f['name']} | {f['roles']} | {f1(f['headcount'], 0)} | {f1(f['fte_technical'])} "
                         f"| {f1(f['fte_realisable'])}{' + offen' if f['roles_unassessed'] else ''} | {f['roles_unassessed']} |")
        unassessed = sum(f["roles_unassessed"] for f in fams)
        if unassessed:
            lines += ["", f"Für {unassessed} Rollen fehlt die Angabe, wie frei werdende Kapazität aufgefangen wird "
                          "(Wachstum, Fluktuation, Altersteilzeit, Umbesetzung). Ohne sie bleibt die Spalte „auffangbar“ unvollständig — "
                          "das ist nicht dasselbe wie null."]
    else:
        lines.append("Noch keine Kapazitätsrechnung: Rollen brauchen Bewertung und Headcount.")
    lines += ["", "## Zielbild je Rolle (Entwurf)", ""]
    trs = graph.get("target_roles") or []
    if trs:
        lines += ["| Rolle | Wirkung | Bleibt | FTE heute | FTE danach | FTE auffangbar | Zusammenlegung prüfen |",
                  "|---|---|---:|---:|---:|---:|---|"]
        for t in sorted(trs, key=lambda x: (roles.get(x["role_id"], {}).get("name", ""), x["id"])):
            merge = ", ".join(roles[r]["name"] for r in t.get("merge_with_role_ids", []) if r in roles) or "–"
            lines.append(f"| {roles[t['role_id']]['name']} | {HR_TYPE_LABEL.get(t.get('disruption_type'), '–')} "
                         f"| {f1(t['retained_share_pct'], 0)} % | {f1(t.get('fte_current'))} | {f1(t.get('fte_remaining'))} "
                         f"| {f1(t.get('fte_realisable'))} | {merge} |")
    else:
        lines.append("Zielbild noch nicht erzeugt (`build_target_roles.py`).")
    lines += ["", "## Voraussetzung vor jedem Gespräch mit Beschäftigten", "",
              "Bevor jemand bestätigen soll, welcher Teil seiner Arbeit automatisierbar ist, muss der Rahmen "
              "feststehen: Beschäftigtenvertretung beteiligt, Zusagen zur Beschäftigung benannt, Zweck der Erhebung klar. "
              "Ohne diesen Rahmen bestätigt niemand ehrlich — und die Datenlage wird schlechter, nicht besser.", ""]
    exps = graph.get("experiments") or []
    if exps:
        lines += ["| Pilot | Status | Rahmen bestätigt | Vermerk |", "|---|---|---|---|"]
        for x in sorted(exps, key=lambda e: e["id"]):
            lines.append(f"| {x.get('name')} | {x.get('status')} | {'ja' if x.get('frame_confirmed') else 'nein'} | {x.get('frame_note') or '–'} |")
        lines.append("")
    extra = av.hr_lines(graph)
    if extra:
        lines += extra[1:] + [""]
    lines += skill_shift_lines(graph)
    return "\n".join(lines) + "\n"


SHIFT_RANK_GAP = 3


def skill_shift_lines(graph: dict[str, Any]) -> list[str]:
    """Kompetenzverschiebung: Skills nach nötiger Human Agency gegen Skills nach gebundener Arbeit."""
    sk = [s for s in graph.get("skills", []) if s.get("analysis") and s.get("kind") != "tool"]
    if len(sk) < 4:
        return []
    by_agency = sorted(sk, key=lambda s: (-s["analysis"]["human_agency"], s["name"]))
    by_work = sorted(sk, key=lambda s: (-s["analysis"]["bound_work"], s["name"]))
    ra = {s["id"]: i + 1 for i, s in enumerate(by_agency)}
    rw = {s["id"]: i + 1 for i, s in enumerate(by_work)}
    unit = "FTE" if all(s["analysis"]["bound_basis"] == "fte" for s in sk) else "% Zeitanteil"
    lines = ["## Kompetenzverschiebung", "",
             "Welche Fähigkeiten an Arbeit hängen, die Menschen auch mit Agenten tragen (hohe Human Agency), und welche heute "
             "viel Arbeit binden. Steht ein Skill bei der Human Agency weit vor seinem heutigen Gewicht, gewinnt er an Bedeutung; "
             "umgekehrt verliert er. Grundlage ist die Bewertung, nicht die Befragung. Nach Shao et al. 2025 (Lohn gegen Human Agency), "
             "hier mit gebundener Arbeit als Wertmaß.", "",
             f"| Skill | Human Agency (1–5) | Rang | gebundene Arbeit ({unit}) | Rang | Tendenz |", "|---|---:|---:|---:|---:|---|"]
    for s in by_agency:
        gap = rw[s["id"]] - ra[s["id"]]
        trend = "gewinnt an Gewicht" if gap >= SHIFT_RANK_GAP else "verliert an Gewicht" if gap <= -SHIFT_RANK_GAP else "–"
        lines.append(f"| {s['name']} | {s['analysis']['human_agency']:.1f} | {ra[s['id']]} | {s['analysis']['bound_work']:.1f} "
                     f"| {rw[s['id']]} | {trend} |")
    lines.append("")
    return lines


def it_backlog(graph: dict[str, Any], title: str, agents: list[dict[str, Any]]) -> str:
    meta = graph["meta"]
    lines = [f"# {title} — Backlog für IT", "",
             f"{meta.get('organization', '')} · {meta.get('scope', '')} · Work-Graph Version {meta.get('version')}", "",
             "Der Arbeitsvorrat nach Wert: welche Agenten und Use Cases zuerst, wen sie betreffen, wo bisher niemand anfragt. "
             "Wo ein Agent ohne KI auskommt (Schnittstelle, Prozessänderung), steht das bei den Prozessen.", ""]
    lines += ["## Agenten", "", "| Wert # | Bau # | Agent | Status | Evidenz | Horizont | FTE-Äquiv. |", "|---:|---:|---|---|---|---|---:|"]
    for a in agents:
        fte = f1(a.get("fte_equivalent")) if a.get("fte_equivalent") is not None else "–"
        lines.append(f"| {a.get('priority_rank', '–')} | {a.get('sequence_rank', '–')} | {a['name']} | {a.get('status')} "
                     f"| {GRADE_LABEL.get(a.get('evidence_grade'), 'Heuristik')} | {a.get('horizon') or '–'} | {fte} |")
    reach = [r for r in wl.agent_reach(graph) if r["kind"] == "usecase"]
    if reach:
        lines += ["", "## Use Cases aus dem Register", "", "| Use Case | Rollen | FTE betroffen | Wert/Jahr (Team) |", "|---|---:|---:|---:|"]
        for r in reach:
            lines.append(f"| {r['name']} | {len(r['roles'])} | {f1(r['fte_total'])} | {f1(r['value_eur_declared'], 0)} |")
    lines += ["", "## Prozesse nach Band", ""]
    procs = [p for p in graph.get("processes", []) if p.get("value")]
    if procs:
        lines += ["| Prozess | Band | Wert | Ohne-KI-Schritte im besten Szenario |", "|---|---|---:|---:|"]
        bps: dict[str, list] = {}
        for b in graph.get("blueprints", []):
            bps.setdefault(b["process_id"], []).append(b)
        for p in sorted(procs, key=lambda x: (-(x["value"].get("score") or 0), x["name"])):
            non_ai = max((b.get("non_ai_steps") or 0 for b in bps.get(p["id"], [])), default=0)
            lines.append(f"| {p['name']} | {BAND_LABEL.get(p['value'].get('band'), '–')} | {f1(p['value'].get('score'))} | {non_ai} |")
    else:
        lines.append("Keine bewerteten Prozesse.")
    spots = wl.blind_spots(graph)
    lines += ["", "## Blindflecken", ""]
    lines += ([f"- **{s['name']}** ({BAND_LABEL[s['band']]}, Wert {f1(s['score'])}) — weder Agent noch Use Case deckt Aufgaben ab" for s in spots]
              or ["Keine."])
    lines += av.it_lines(graph)
    lines.append("")
    return "\n".join(lines) + "\n"
