"""
agency_views.py — die Beschäftigtensicht im Dashboard und in den Berichten (Schema 1.4).

Zwei Achsen, die die Suite sonst nicht nebeneinander hat: was Technik kann (Automatisierungspotenzial
aus der Bewertung) und was die Menschen wollen, die die Arbeit tun (Wunsch aus der Befragung). Dazu
die Human Agency Scale zweimal: gewünscht und technisch nötig.

Alles hier sind Zusammenfassungen ab Mindestgruppe. Keine Zahl lässt sich auf eine Person zurückführen.
"""

from __future__ import annotations

import html
from typing import Any

import workgraph_lib as wl

ZONE_ORDER = ["green", "red", "opportunity", "low"]


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def f1(x: Any, nd: int = 1) -> str:
    return "–" if x is None else f"{float(x):.{nd}f}"


def has_agency(graph: dict[str, Any]) -> bool:
    return any(t.get("agency") for t in graph.get("tasks", []))


def rated_tasks(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in graph.get("tasks", []) if t.get("agency")]


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def landscape_svg(graph: dict[str, Any], zone_color: dict[str, str]) -> str:
    """Wunsch (1–5) gegen Automatisierungspotenzial (0–10); Punktgröße nach Zeitanteil."""
    W, H, P = 900, 480, 52
    roles = wl.index_by_id(graph["roles"])

    def X(v: float) -> float:
        return P + (W - 2 * P) * v / 10.0

    def Y(v: float) -> float:
        return H - P - (H - 2 * P) * (v - 1.0) / 4.0

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Wunsch der Beschäftigten gegen Automatisierungspotenzial je Aufgabe">']
    for i in range(0, 11, 2):
        out.append(f'<line class="grid" x1="{X(i):.1f}" y1="{Y(1):.1f}" x2="{X(i):.1f}" y2="{Y(5):.1f}"/>')
        out.append(f'<text class="axis" x="{X(i):.1f}" y="{H - P + 16}" text-anchor="middle">{i}</text>')
    for i in range(1, 6):
        out.append(f'<line class="grid" x1="{X(0):.1f}" y1="{Y(i):.1f}" x2="{X(10):.1f}" y2="{Y(i):.1f}"/>')
        out.append(f'<text class="axis" x="{P - 8}" y="{Y(i) + 4:.1f}" text-anchor="end">{i}</text>')
    cx, cy = X(wl.ZONE_CAPABILITY_MIN), Y(wl.ZONE_DESIRE_MIN)
    out.append(f'<line x1="{cx:.1f}" y1="{Y(1):.1f}" x2="{cx:.1f}" y2="{Y(5):.1f}" stroke="#999" stroke-dasharray="4 4"/>')
    out.append(f'<line x1="{X(0):.1f}" y1="{cy:.1f}" x2="{X(10):.1f}" y2="{cy:.1f}" stroke="#999" stroke-dasharray="4 4"/>')
    for (x, y, z, anchor) in [(0.2, 4.9, "opportunity", "start"), (9.8, 4.9, "green", "end"),
                              (0.2, 1.1, "low", "start"), (9.8, 1.1, "red", "end")]:
        out.append(f'<text class="qlabel" x="{X(x):.1f}" y="{Y(y) + 4:.1f}" text-anchor="{anchor}" fill="{zone_color[z]}">'
                   f'{esc(wl.AGENCY_ZONE_SHORT[z])}</text>')
    out.append(f'<text class="axis" x="{W / 2:.0f}" y="{H - 10}" text-anchor="middle">Automatisierungspotenzial laut Bewertung (0–10) →</text>')
    out.append(f'<text class="axis" transform="translate(14,{H / 2:.0f}) rotate(-90)" text-anchor="middle">Wunsch der Beschäftigten (1–5) →</text>')
    items = sorted(rated_tasks(graph), key=lambda t: (-(t.get("share_of_time") or 0), t["id"]))
    seen: dict[tuple[float, float], int] = {}
    for t in items:
        a = t["agency"]
        if a.get("desire") is None or t.get("automation_potential") is None:
            continue
        key = (round(float(t["automation_potential"]), 1), round(float(a["desire"]), 1))
        k = seen.get(key, 0)
        seen[key] = k + 1
        x, y = X(float(t["automation_potential"])) + 7 * k, Y(float(a["desire"]))
        rad = 4.0 + 10.0 * (float(t.get("share_of_time") or 0) / 100.0) ** 0.5
        col = zone_color.get(a.get("zone"), "#888")
        title = (f"{t['name']} ({roles.get(t['role_id'], {}).get('name', '')}): Wunsch {f1(a['desire'])}, "
                 f"Potenzial {f1(t['automation_potential'])}, HAS gewünscht H{a['has_desired']}, nötig H{t.get('has_level', '–')}, "
                 f"{a['respondents']} Antworten")
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" fill-opacity="0.8" stroke="#fff" stroke-width="1.5">'
                   f'<title>{esc(title)}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def has_matrix_html(graph: dict[str, Any]) -> str:
    """Aufgaben nach gewünschter (Zeilen) und technisch nötiger Stufe (Spalten)."""
    m = [[0] * 5 for _ in range(5)]
    for t in rated_tasks(graph):
        if t.get("has_level") is None:
            continue
        m[int(t["agency"]["has_desired"]) - 1][int(t["has_level"]) - 1] += 1
    total = sum(sum(r) for r in m) or 1
    peak = max(max(r) for r in m) or 1
    head = "".join(f"<th>H{j + 1} nötig</th>" for j in range(5))
    body = []
    for i in range(5):
        cells = []
        for j in range(5):
            v = m[i][j]
            alpha = 0.10 + 0.55 * v / peak if v else 0.0
            style = f"background:rgba(15,95,87,{alpha:.2f})"
            if i == j:
                style += ";font-weight:600;box-shadow:inset 0 0 0 2px #555"
            cells.append(f'<td style="{style}">{v or ""}</td>')
        body.append(f"<tr><th>H{i + 1} gewünscht</th>{''.join(cells)}</tr>")
    above = sum(m[i][j] for i in range(5) for j in range(5) if i > j)
    below = sum(m[i][j] for i in range(5) for j in range(5) if i < j)
    same = sum(m[i][i] for i in range(5))
    return (f'<table class="hasm" style="max-width:640px"><thead><tr><th>Aufgaben</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'
            f'<p class="meta" style="margin-top:8px">{same} von {total} Aufgaben stimmen überein · bei {above} wollen die Beschäftigten '
            f'mehr Beteiligung, als die Technik braucht · bei {below} weniger.</p>')


def roles_table_html(graph: dict[str, Any], zone_color: dict[str, str]) -> str:
    rows = []
    for r in sorted((r for r in graph["roles"] if r.get("agency")),
                    key=lambda x: (-(x["agency"].get("jsd") or 0), x.get("name") or "")):
        a = r["agency"]
        z = a.get("zone_shares") or {}
        bar = "".join(f'<i title="{esc(wl.AGENCY_ZONE_SHORT[k])} {z[k]:.0f} %" style="display:inline-block;height:10px;'
                      f'width:{z[k]:.0f}%;background:{zone_color[k]}"></i>' for k in ZONE_ORDER if z.get(k))
        cov = f"{f1(a.get('coverage_pct'), 0)} %" if a.get("coverage_pct") is not None else "–"
        rows.append(f"<tr><td>{esc(r['name'])}</td><td class=\"n\">{a['respondents']}</td><td class=\"n\">{cov}</td>"
                    f"<td class=\"n\">{f1(a.get('desire'))}</td><td>H{a.get('has_desired_dominant', '–')}</td>"
                    f"<td>H{a.get('has_required_dominant', '–')}</td>"
                    f"<td>{esc(wl.FRICTION_LABEL.get(a.get('friction'), '–'))} ({f1(a.get('jsd'), 2)})</td>"
                    f"<td style=\"min-width:160px\"><span style=\"display:flex;width:100%\">{bar}</span></td></tr>")
    return ("<table><thead><tr><th>Rolle</th><th class=\"n\">Teilnehmende</th><th class=\"n\">Abdeckung</th>"
            "<th class=\"n\">Wunsch</th><th>HAS gewünscht</th><th>HAS nötig</th><th>Reibung</th><th>Zonen</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def cluster_zones(graph: dict[str, Any]) -> list[dict[str, Any]]:
    clusters = wl.index_by_id(graph.get("job_clusters", []))
    roles = wl.index_by_id(graph["roles"])
    agg: dict[str, dict[str, float]] = {}
    for t in rated_tasks(graph):
        z = t["agency"].get("zone")
        r = roles.get(t["role_id"])
        if not z or not r:
            continue
        cid = r.get("cluster_id") or ""
        w = float(t.get("share_of_time") or 0) * float(wl.role_headcount(r) or 1)
        agg.setdefault(cid, {}).setdefault(z, 0.0)
        agg[cid][z] += w
    out = []
    for cid, zs in agg.items():
        tot = sum(zs.values()) or 1.0
        out.append({"name": (clusters.get(cid) or {}).get("name", "ohne Cluster"),
                    "shares": {k: wl.round1(100.0 * zs.get(k, 0.0) / tot) for k in ZONE_ORDER}})
    out.sort(key=lambda x: (-x["shares"]["red"], x["name"]))
    return out


def section(graph: dict[str, Any], zone_color: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    if not has_agency(graph):
        return "", []
    n_roles = sum(1 for r in graph["roles"] if r.get("agency"))
    rated = rated_tasks(graph)
    zones = {z: sum(1 for t in rated if t["agency"].get("zone") == z) for z in ZONE_ORDER}
    legend = "".join(f'<span><i style="background:{zone_color[z]}"></i>{esc(wl.AGENCY_ZONE_LABEL[z])} ({zones[z]})</span>'
                     for z in ZONE_ORDER)
    cl_rows = "".join(f"<tr><td>{esc(c['name'])}</td>" + "".join(f'<td class="n">{c["shares"][z]:.0f} %</td>' for z in ZONE_ORDER)
                      + "</tr>" for c in cluster_zones(graph))
    html_ = f"""<section id="beschaeftigte"><h2>Sicht der Beschäftigten</h2>
<p>Was die Menschen wollen, die die Arbeit tun, neben dem, was Technik kann. {len(rated)} Aufgaben in {n_roles} Rollen mit mindestens {wl.AUDIT_MIN_GROUP} Antworten; darunter wird nichts gezeigt. Eine Zone ist ein Gesprächsanlass, kein Urteil über Menschen und kein Veto.</p>
<div class="matrix">{landscape_svg(graph, zone_color)}</div>
<div class="legend">{legend}</div>
<h3 style="margin-top:18px">Beteiligung: gewünscht gegen technisch nötig</h3>
<p>Human Agency Scale H1 (Agent allein) bis H5 (ohne laufende Beteiligung geht es nicht). Die Diagonale ist Übereinstimmung; darunter wollen die Beschäftigten mehr Beteiligung, als die Bewertung braucht.</p>
{has_matrix_html(graph)}
<h3 style="margin-top:18px">Rollen</h3>
<p>Reibung ist die Jensen-Shannon-Distanz zwischen gewünschter und nötiger Verteilung über H1–H5 (0 deckungsgleich, 1 völlig verschieden). Abdeckung: Teilnehmende je Stelle.</p>
{roles_table_html(graph, zone_color)}
<h3 style="margin-top:18px">Zonen je Cluster</h3>
<table><thead><tr><th>Cluster</th>{"".join(f'<th class="n">{esc(wl.AGENCY_ZONE_SHORT[z])}</th>' for z in ZONE_ORDER)}</tr></thead><tbody>{cl_rows}</tbody></table>
<p class="meta" style="margin-top:8px">Anteile an der befragten Arbeitszeit, mit Stellen gewichtet, wo bekannt. Methodik nach Shao et al. 2025 (WORKBank), übertragen auf die Skalen der Suite.</p></section>"""
    return html_, [("#beschaeftigte", "Beschäftigte")]


# ---------------------------------------------------------------------------
# Berichte
# ---------------------------------------------------------------------------

def _covered(graph: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for a in graph.get("agents", []):
        out.update(a.get("task_ids", []))
    for u in graph.get("usecases", []):
        out.update(u.get("task_ids", []))
    return out


def hr_lines(graph: dict[str, Any]) -> list[str]:
    if not has_agency(graph):
        return []
    roles = wl.index_by_id(graph["roles"])
    rated = rated_tasks(graph)
    lines = ["", "## Sicht der Beschäftigten", "",
             f"Zusammenfassung der Befragung: nur Aufgaben mit mindestens {wl.AUDIT_MIN_GROUP} Antworten, keine Einzelangaben. "
             "Die Zonen sagen, wo eine Veränderung auf offene Türen trifft und wo sie gegen die Beschäftigten liefe.", "",
             "| Rolle | Teilnehmende | Wunsch (1–5) | Beteiligung gewünscht | nötig | Reibung |", "|---|---:|---:|---|---|---|"]
    for r in sorted((r for r in graph["roles"] if r.get("agency")), key=lambda x: (-(x["agency"].get("jsd") or 0), x["name"])):
        a = r["agency"]
        lines.append(f"| {r['name']} | {a['respondents']} | {f1(a.get('desire'))} | H{a.get('has_desired_dominant', '–')} "
                     f"| H{a.get('has_required_dominant', '–')} | {wl.FRICTION_LABEL.get(a.get('friction'), '–')} |")
    red = sorted((t for t in rated if t["agency"].get("zone") == "red"), key=lambda t: (t["agency"].get("desire") or 0, t["name"]))
    lines += ["", "### Zuerst nicht automatisieren (Vorsichtszone)", ""]
    lines += ([f"- **{t['name']}** ({roles[t['role_id']]['name']}): technisch machbar, Wunsch {f1(t['agency'].get('desire'))}, "
               f"Sorge {f1(t['agency'].get('job_worry'))}, Freude {f1(t['agency'].get('enjoyment'))}" for t in red]
              or ["Keine Aufgabe in der Vorsichtszone."])
    more = sorted((t for t in rated if (t["agency"].get("has_gap") or 0) >= 2), key=lambda t: (-t["agency"]["has_gap"], t["name"]))
    lines += ["", "### Mehr Beteiligung gewünscht, als die Technik braucht", ""]
    lines += ([f"- **{t['name']}** ({roles[t['role_id']]['name']}): gewünscht H{t['agency']['has_desired']}, nötig H{t['has_level']}"
               for t in more] or ["Keine Aufgabe mit einer Lücke von zwei Stufen oder mehr."])
    lines += ["", "Bevor eine dieser Aufgaben verändert wird: mit den Beschäftigten über die Gründe sprechen. "
                  "Wer gegen den erklärten Wunsch automatisiert, verliert Mitwirkung genau dort, wo man sie braucht."]
    return lines


def it_lines(graph: dict[str, Any]) -> list[str]:
    if not has_agency(graph):
        return []
    roles = wl.index_by_id(graph["roles"])
    covered = _covered(graph)
    rated = rated_tasks(graph)
    latent = sorted((t for t in rated if t["agency"].get("zone") in ("green", "opportunity") and t["id"] not in covered),
                    key=lambda t: (-(t["agency"].get("desire") or 0), t["name"]))
    lines = ["", "## Latente Nachfrage", "",
             "Aufgaben, die die Beschäftigten gern abgeben würden, für die aber weder Agent noch Use Case besteht. "
             "Freigabe heißt: heute machbar. Entwicklung heißt: gewünscht, braucht Werkzeug oder Daten.", ""]
    if latent:
        lines += ["| Aufgabe | Rolle | Zone | Wunsch | Potenzial | Hauptgrund |", "|---|---|---|---:|---:|---|"]
        for t in latent:
            rs = t["agency"].get("reasons_automation") or {}
            top = sorted(rs.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if rs else None
            lines.append(f"| {t['name']} | {roles[t['role_id']]['name']} | {wl.AGENCY_ZONE_SHORT[t['agency']['zone']]} "
                         f"| {f1(t['agency'].get('desire'))} | {f1(t.get('automation_potential'))} "
                         f"| {wl.AUDIT_REASONS_AUTOMATION.get(top, '–') if top else '–'} |")
    else:
        lines.append("Keine: Jede gewünschte Aufgabe hat ein Vorhaben.")
    red_agents = []
    tasks = wl.index_by_id(graph["tasks"])
    for a in graph.get("agents", []):
        zs = [tasks[t]["agency"]["zone"] for t in a.get("task_ids", []) if t in tasks and (tasks[t].get("agency") or {}).get("zone")]
        if zs and zs.count("red") * 2 > len(zs):
            red_agents.append(a["name"])
    lines += ["", "## Agenten auf Arbeit, die die Beschäftigten nicht abgeben wollen", ""]
    lines += ([f"- **{n}**: überwiegend Vorsichtszone. Vor dem Bau mit dem Fachbereich klären, ob unterstützen statt übernehmen reicht."
               for n in sorted(red_agents)] or ["Keine."])
    ad = [x for x in graph.get("adoption") or [] if not x.get("suppressed")]
    if ad:
        agents = wl.index_by_id(graph.get("agents", []))
        lines += ["", "## Nutzung gegen Wunsch", "",
                  "| Agent | Rolle | Wunsch der abgedeckten Aufgaben | in Nutzung |", "|---|---|---:|---:|"]
        for x in sorted(ad, key=lambda x: (agents.get(x.get("agent_id"), {}).get("name", ""), roles.get(x["role_id"], {}).get("name", ""))):
            ag = agents.get(x.get("agent_id"))
            if not ag:
                continue
            ds = [tasks[t]["agency"]["desire"] for t in ag.get("task_ids", [])
                  if t in tasks and tasks[t].get("role_id") == x["role_id"] and (tasks[t].get("agency") or {}).get("desire") is not None]
            if not ds:
                continue
            share = f"{100.0 * x['in_use'] / x['group_size']:.0f} %" if x.get("group_size") else "–"
            lines.append(f"| {ag['name']} | {roles.get(x['role_id'], {}).get('name', '–')} | {f1(sum(ds) / len(ds))} | {share} |")
        lines += ["", "Hoher Wunsch bei niedriger Nutzung heißt meist: Das Werkzeug passt nicht zur Arbeit, nicht dass niemand will."]
    return lines
