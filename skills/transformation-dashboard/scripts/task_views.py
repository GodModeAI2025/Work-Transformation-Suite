"""
task_views.py — die Aufgabenansicht des Dashboards: alle bewerteten Aufgaben quer über alle
Rollen auf einer Karte und in einer Rangliste.

Die Rollenmatrix beantwortet „welche Rolle ist betroffen?“. Diese Ansicht beantwortet die
Frage darunter: **welche einzelne Aufgabe** bindet viel Arbeit, lässt sich gut automatisieren
und sollte zuerst angesehen werden — und wo ein Fehler so teuer wäre, dass Automatisierbarkeit
allein nicht reicht.

Zwei Zahlen werden bewusst getrennt, weil „gefährlich“ zwei Dinge meinen kann:

- **Exposition** = Automatisierungspotenzial/10 × gebundene Arbeit. Wie viel Arbeit hängt an der
  Aufgabe, und wie viel davon ist technisch angreifbar? Sie ordnet die Rangliste.
- **Fehlerfolge** (0–10). Was kostet ein unentdeckter Fehler? Eine Aufgabe mit hoher Exposition
  und hoher Fehlerfolge ist ein Kandidat für einen Menschen im Prozess, nicht für volle
  Delegation.

Gebundene Arbeit ist FTE (Headcount × Zeitanteil), wo der Headcount bekannt ist, sonst der
Zeitanteil der Rolle in Prozent. Beides gemischt wird nie verglichen: Ohne Headcount für alle
bewerteten Rollen rechnet die Ansicht durchgehend mit Prozent.
"""

from __future__ import annotations

import html
import json
import math
from typing import Any

import workgraph_lib as wl

TOP_N = 25
CAUTION_COE = 6.0  # ab hier ist ein Fehler teuer genug für einen Kontrollpunkt


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def f1(x: Any, nd: int = 1) -> str:
    return "–" if x is None else f"{float(x):.{nd}f}"


def rows(graph: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Bewertete Aufgaben mit Gewicht und Exposition. Gibt (Zeilen, Einheit) zurück."""
    roles = wl.index_by_id(graph["roles"])
    scored = [t for t in graph["tasks"] if t.get("scores") and t.get("mode") and t["role_id"] in roles]
    use_fte = bool(scored) and all(wl.role_headcount(roles[t["role_id"]]) is not None for t in scored)
    out = []
    for t in sorted(scored, key=lambda t: t["id"]):
        r = roles[t["role_id"]]
        hc = wl.role_headcount(r)
        share = float(t.get("share_of_time") or 0)
        weight = float(hc) * share / 100.0 if use_fte else share
        ap = float(t.get("automation_potential") or 0)
        sc = t["scores"]
        out.append({
            "id": t["id"], "name": t["name"], "role_id": r["id"], "role": r["name"],
            "ap": ap, "hj": float(sc["human_judgment"]), "coe": float(sc["consequence_of_error"]),
            "pb": float(sc["productivity_boost"]), "mode": t["mode"], "has": t.get("has_level"),
            "horizon": t.get("horizon"), "share": share, "weight": round(weight, 2),
            "exposure": round(ap / 10.0 * weight, 2),
            "caution": float(sc["consequence_of_error"]) >= CAUTION_COE and ap >= 4.0,
            "agents": len(t.get("agent_ids", [])),
        })
    return out, ("FTE" if use_fte else "% der Rollenzeit")


def _spread(items: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    """Versatz für Punkte, die auf derselben Rasterstelle landen (Werte sind meist ganzzahlig).
    Goldener Winkel, feste Reihenfolge: gleiche Eingabe, gleiche Bytes."""
    groups: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for it in items:
        groups.setdefault((round(it["ap"], 1), round(it["hj"], 1)), []).append(it)
    off: dict[str, tuple[float, float]] = {}
    for grp in groups.values():
        for i, it in enumerate(sorted(grp, key=lambda x: x["id"])):
            if len(grp) == 1:
                off[it["id"]] = (0.0, 0.0)
            else:
                ang = i * 2.399963
                rad = 0.07 * math.sqrt(i + 0.5)  # in Skaleneinheiten (0–10)
                off[it["id"]] = (rad * math.cos(ang), rad * math.sin(ang))
    return off


def matrix_svg(items: list[dict[str, Any]], mode_color: dict[str, str], unit: str) -> str:
    W, H, P = 900, 560, 50

    def X(v: float) -> float:
        return P + (W - 2 * P) * v / 10.0

    def Y(v: float) -> float:
        return H - P - (H - 2 * P) * v / 10.0

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Aufgabenmatrix: Automatisierungspotenzial gegen menschliches Urteil, Punktgröße nach gebundener Arbeit">']
    for i in range(0, 11, 2):
        out.append(f'<line class="grid" x1="{X(i):.1f}" y1="{Y(0):.1f}" x2="{X(i):.1f}" y2="{Y(10):.1f}"/>')
        out.append(f'<line class="grid" x1="{X(0):.1f}" y1="{Y(i):.1f}" x2="{X(10):.1f}" y2="{Y(i):.1f}"/>')
        out.append(f'<text class="axis" x="{X(i):.1f}" y="{H - P + 16}" text-anchor="middle">{i}</text>')
        out.append(f'<text class="axis" x="{P - 8}" y="{Y(i) + 4:.1f}" text-anchor="end">{i}</text>')
    out.append(f'<line x1="{X(5):.1f}" y1="{Y(0):.1f}" x2="{X(5):.1f}" y2="{Y(10):.1f}" stroke="#ccc" stroke-dasharray="4 4"/>')
    out.append(f'<line x1="{X(0):.1f}" y1="{Y(5):.1f}" x2="{X(10):.1f}" y2="{Y(5):.1f}" stroke="#ccc" stroke-dasharray="4 4"/>')
    out.append(f'<text class="axis" x="{W / 2:.0f}" y="{H - 10}" text-anchor="middle">Automatisierungspotenzial der Aufgabe (0–10) →</text>')
    out.append(f'<text class="axis" transform="translate(14,{H / 2:.0f}) rotate(-90)" text-anchor="middle">Menschliches Urteil (0–10) →</text>')
    for (x, y, lab) in [(0.3, 9.6, "Mensch trägt"), (9.7, 9.6, "KI unterstützt"), (0.3, 0.4, "Routine, schwer automatisierbar"), (9.7, 0.4, "Delegierbar")]:
        anchor = "start" if x < 5 else "end"
        out.append(f'<text class="qlabel" x="{X(x):.1f}" y="{Y(y) + 4:.1f}" text-anchor="{anchor}">{lab}</text>')
    maxw = max((i["weight"] for i in items), default=1.0) or 1.0
    off = _spread(items)
    top = {i["id"] for i in sorted(items, key=lambda i: (-i["exposure"], i["id"]))[:6]}
    # Große zuerst, damit kleine Punkte nicht unter großen verschwinden.
    ordered = sorted(items, key=lambda i: (-i["weight"], i["id"]))
    geo = {}
    placed: list[tuple[float, float, float, float]] = []
    for it in ordered:
        dx, dy = off[it["id"]]
        x, y = X(it["ap"] + dx), Y(it["hj"] + dy)
        rad = 3.5 + 11.0 * math.sqrt(it["weight"] / maxw)
        geo[it["id"]] = (x, y, rad)
        placed.append((x - rad, y - rad, x + rad, y + rad))

    def free(box):
        x1, y1, x2, y2 = box
        if x1 < P or x2 > W - 4 or y1 < 8 or y2 > H - P:
            return False
        return not any(not (x2 < a or x1 > c or y2 < b or y1 > d) for (a, b, c, d) in placed)

    labels: dict[str, str] = {}
    for it in sorted((i for i in items if i["id"] in top), key=lambda i: (-i["exposure"], i["id"])):
        x, y, rad = geo[it["id"]]
        nm = it["name"] if len(it["name"]) <= 28 else it["name"][:27] + "…"
        tw = len(nm) * 5.8
        for ddy in (0, -14, 14, -28, 28, -42, 42):
            for side in (("start", "end") if it["ap"] < 7 else ("end", "start")):
                for ddx in (0, 16, 32, 48):
                    lx = x + rad + 3 + ddx if side == "start" else x - rad - 3 - ddx
                    box = (lx, y + ddy - 7, lx + tw, y + ddy + 7) if side == "start" else (lx - tw, y + ddy - 7, lx, y + ddy + 7)
                    if free(box):
                        placed.append(box)
                        lead = (f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{lx:.1f}" y2="{y + ddy:.1f}" stroke="#bbb"/>'
                                if ddy or ddx else "")
                        labels[it["id"]] = f'{lead}<text x="{lx:.1f}" y="{y + ddy + 4:.1f}" font-size="10" fill="#333" text-anchor="{side}">{esc(nm)}</text>'
                        break
                if it["id"] in labels:
                    break
            if it["id"] in labels:
                break
    for it in ordered:
        x, y, rad = geo[it["id"]]
        col = mode_color.get(it["mode"], "#888")
        ring = ' stroke="#111" stroke-width="2"' if it["caution"] else ' stroke="#fff" stroke-width="1.5"'
        out.append(f'<g class="tdot" data-id="{it["id"]}" data-mode="{it["mode"]}" data-role="{esc(it["role_id"])}">'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" fill-opacity="0.8"{ring}/>{labels.get(it["id"], "")}</g>')
    out.append("</svg>")
    return "".join(out)


TASK_JS = """
(function(){
const data=window.__TASKS__;const tip=document.getElementById('ttip');const box=document.getElementById('task-matrix-box');
if(!tip||!box){return;}
function show(e,h){tip.innerHTML=h;tip.style.display='block';const r=box.getBoundingClientRect();tip.style.left=(e.clientX-r.left+12)+'px';tip.style.top=(e.clientY-r.top+12)+'px';}
document.querySelectorAll('.tdot').forEach(d=>{const t=data[d.getAttribute('data-id')];
 d.addEventListener('mousemove',e=>show(e,'<b>'+t.name+'</b><br>'+t.role+'<br>'+t.modeLabel+' · HAS '+t.has+'<br>AP '+t.ap+' · Urteil '+t.hj+' · Fehlerfolge '+t.coe+'<br>Exposition '+t.exposure+(t.caution?'<br><b>Fehler teuer: Kontrollpunkt prüfen</b>':'')));
 d.addEventListener('mouseleave',()=>{tip.style.display='none';});
 d.addEventListener('click',()=>{const c=document.getElementById('role-'+d.getAttribute('data-role'));if(c){c.scrollIntoView({behavior:'smooth',block:'start'});c.style.outline='3px solid var(--accent)';setTimeout(()=>c.style.outline='',1800);}});});
function apply(){const modes=[...document.querySelectorAll('input[data-tmode]')].filter(i=>i.checked).map(i=>i.getAttribute('data-tmode'));
 const role=document.getElementById('f-trole').value;
 document.querySelectorAll('[data-mode]').forEach(el=>{const ok=modes.includes(el.getAttribute('data-mode'))&&(role===''||el.getAttribute('data-role')===role);el.classList.toggle('hidden',!ok);});}
document.querySelectorAll('input[data-tmode]').forEach(i=>i.addEventListener('change',apply));
document.getElementById('f-trole').addEventListener('change',apply);
})();
"""


STATUS_LABEL = {"candidate": "Kandidat (ungeprüft)", "confirmed": "bestätigt"}


def clusters_html(graph: dict[str, Any]) -> str:
    """Dieselbe Arbeit in mehreren Rollen. Verworfene Cluster erscheinen nicht."""
    cl = [c for c in graph.get("task_clusters", []) if c.get("status") != "rejected"]
    if not cl:
        return ""
    roles = wl.index_by_id(graph["roles"])
    rows = "".join(
        f'<tr><td>{esc(c["name"])}</td><td class="n">{c["roles_count"]}</td><td class="n">{c["tasks_count"]}</td>'
        f'<td class="n">{f1(c["fte"]) if c.get("fte") is not None else f1(c["share_sum"], 0) + " %"}</td>'
        f'<td class="n">{f1(c["similarity_min"], 2)}</td><td>{esc(STATUS_LABEL.get(c["status"], c["status"]))}</td>'
        f'<td>{esc(", ".join(roles[r]["name"] for r in c["role_ids"] if r in roles))}</td></tr>'
        for c in sorted(cl, key=lambda c: (-c["roles_count"], -(c.get("fte") or 0), c["name"], c["id"])))
    return f"""<h3 style="font-family:var(--f-head);color:var(--primary);margin:22px 0 4px">Wiederkehrende Aufgaben über Rollen</h3>
<p class="meta" style="margin:0 0 8px">Dieselbe Arbeit unter ähnlichem Namen in mehreren Rollen. Je mehr Rollen sie trägt, desto eher lohnt ein gemeinsamer Agent. Die Zuordnung beruht auf gleichen Wörtern, nicht auf gleicher Bedeutung; „Kandidat“ heißt: noch kein Fachexperte hat sie bestätigt (<code>30_review/task_clusters.csv</code>).</p>
<div class="scroller"><table><thead><tr><th>Aufgabe</th><th class="n">Rollen</th><th class="n">Aufgaben</th><th class="n">Arbeit</th><th class="n">Ähnlichkeit ab</th><th>Stand</th><th>Rollen</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def section(graph: dict[str, Any], mode_color: dict[str, str], mode_label: dict[str, str],
            horizon_label: dict[Any, str]) -> tuple[str, str, str]:
    """(HTML, Skript, Nav-Eintrag). Leer, wenn keine bewerteten Aufgaben vorliegen."""
    items, unit = rows(graph)
    if not items:
        return "", "", ""
    ranked = sorted(items, key=lambda i: (-i["exposure"], -i["coe"], i["name"], i["id"]))

    def tr(i: dict[str, Any], n: int | None) -> str:
        flag = ' <span class="meta" title="Automatisierbar, aber ein Fehler wäre teuer: Kontrollpunkt prüfen">⚠ Fehler teuer</span>' if i["caution"] else ""
        rank = f'<td class="n">{n}</td>' if n is not None else ""
        return (f'<tr data-mode="{i["mode"]}" data-role="{esc(i["role_id"])}">{rank}<td>{esc(i["name"])}{flag}</td><td>{esc(i["role"])}</td>'
                f'<td class="n">{f1(i["weight"], 2)}</td><td class="n">{f1(i["ap"])}</td><td class="n">{f1(i["hj"], 0)}</td>'
                f'<td class="n">{f1(i["coe"], 0)}</td><td class="n">{f1(i["exposure"], 2)}</td><td>{esc(mode_label.get(i["mode"], i["mode"]))}</td>'
                f'<td class="n">{"H" + str(i["has"]) if i["has"] else "–"}</td><td>{esc(horizon_label.get(i["horizon"], "–"))}</td></tr>')

    head = (f'<th>Aufgabe</th><th>Rolle</th><th class="n">Arbeit ({unit})</th><th class="n">AP</th><th class="n">Urteil</th>'
            '<th class="n">Fehlerfolge</th><th class="n">Exposition</th><th>Modus</th><th class="n">HAS</th><th>Horizont</th>')
    top_rows = "".join(tr(i, n) for n, i in enumerate(ranked[:TOP_N], start=1))
    all_rows = "".join(tr(i, None) for i in ranked)
    modes_present = [m for m in ("agent_delegated", "ai_assisted", "manual") if any(i["mode"] == m for i in items)]
    filt = "".join(f'<label><input type="checkbox" data-tmode="{m}" checked> <i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{mode_color.get(m, "#888")}"></i> {esc(mode_label[m])}</label>'
                   for m in modes_present)
    role_sel = ('<select id="f-trole"><option value="">Alle Rollen</option>'
                + "".join(f'<option value="{esc(rid)}">{esc(nm)}</option>' for rid, nm in sorted({(i["role_id"], i["role"]) for i in items}, key=lambda x: (x[1], x[0])))
                + "</select>")
    legend = "".join(f'<span><i style="background:{mode_color.get(m, "#888")}"></i>{esc(mode_label[m])}</span>' for m in modes_present)
    n_caution = sum(1 for i in items if i["caution"])
    js_data = {i["id"]: {"name": i["name"], "role": i["role"], "modeLabel": mode_label.get(i["mode"], i["mode"]), "has": i["has"] or "–",
                         "ap": f1(i["ap"]), "hj": f1(i["hj"], 0), "coe": f1(i["coe"], 0), "exposure": f1(i["exposure"], 2),
                         "caution": i["caution"]} for i in items}
    body = f"""<section id="aufgaben"><h2>Aufgabenkarte</h2><p>Alle {len(items)} bewerteten Aufgaben quer über alle Rollen. Jede Aufgabe ein Punkt: Automatisierungspotenzial gegen menschliches Urteil, Größe nach gebundener Arbeit ({esc(unit)}), Farbe nach Ausführungsmodus. Ein schwarzer Rand heißt: automatisierbar, aber ein Fehler wäre teuer (Fehlerfolge ≥ {CAUTION_COE:.0f}). Klick springt zur Rollenkarte.</p>
<div class="filters">{filt}{role_sel}</div>
<div class="matrix" id="task-matrix-box">{matrix_svg(items, mode_color, unit)}<div class="tip" id="ttip"></div></div>
<div class="legend">{legend}<span><i style="background:#fff;border:2px solid #111"></i>Fehler teuer</span></div>
<h3 style="font-family:var(--f-head);color:var(--primary);margin:22px 0 4px">{"Alle " + str(len(ranked)) + " Aufgaben" if len(ranked) <= TOP_N else "Die " + str(TOP_N) + " Aufgaben"} nach Exposition</h3>
<p class="meta" style="margin:0 0 8px">Exposition = Automatisierungspotenzial ÷ 10 × gebundene Arbeit. Sie sagt, wo der größte angreifbare Arbeitsblock liegt — nicht, was automatisiert werden <em>soll</em>. {n_caution} Aufgaben tragen den Hinweis „Fehler teuer“: Dort gehört ein Mensch in den Ablauf, auch wenn die Exposition hoch ist.</p>
<div class="scroller"><table><thead><tr><th class="n">#</th>{head}</tr></thead><tbody>{top_rows}</tbody></table></div>
<details><summary>Alle {len(items)} Aufgaben als Tabelle (barrierefreie Alternative zur Karte)</summary><div class="scroller"><table><thead><tr>{head}</tr></thead><tbody>{all_rows}</tbody></table></div></details>
{clusters_html(graph)}
</section>"""
    script = f"window.__TASKS__={json.dumps(js_data, ensure_ascii=False, sort_keys=True)};{TASK_JS}"
    return body, script, "#aufgaben"
