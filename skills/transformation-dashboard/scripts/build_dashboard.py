#!/usr/bin/env python3
"""
build_dashboard.py — erzeugt aus dem aktuellen work-graph ein eigenständiges
HTML-Dashboard (eine Datei, kein externes Laden), CSV-Exporte und einen
Markdown-Kurzbericht in 40_output/.

Ab Schema 1.1 ist die Prozessansicht die Hauptansicht: Ist-Fluss, entworfene
Soll-Szenarien und was sich zwischen ihnen ändert. Die Rollenansicht bleibt vollständig
erhalten, rückt aber dahinter — als Folgenansicht des Prozessredesigns. Das ist Absicht:
Sobald Organisationskästchen zuerst kommen, wird das Organigramm zum Designobjekt, und
genau das verhindert ein Redesign vom Ergebnis her.

Enthält der Graph keine Prozesse, verhält sich das Dashboard wie bisher und zeigt die
Rollenansicht zuerst.

Aufruf:
    python3 <skill>/scripts/build_dashboard.py --project ./mein-projekt [--stamp "..."] [--title "..."] [--theme ./mein-theme.json]

Ausgaben (NNN = Graph-Version):
    40_output/dashboard_vNNN.html
    40_output/roles_vNNN.csv, tasks_vNNN.csv, agents_vNNN.csv
    40_output/processes_vNNN.csv, blueprints_vNNN.csv (wenn Prozesse vorhanden)
    40_output/report_vNNN.md

Determinismus: Das HTML wird ausschließlich aus dem Graphen erzeugt, ohne
Zeitstempel, Zufall oder externe Ressourcen. Zweimal bauen ergibt identische Bytes.
--stamp fügt das Datum in die Kopfzeile ein (dann nicht mehr byte-identisch).

Gestaltung: Farben und Schriften kommen aus assets/theme.json (Standard) oder einer
mit --theme übergebenen Datei. Die kategorischen Standardfarben der Disruptionstypen
wurden mit einem Palettenvalidator geprüft (CVD-sicher); Orange/Grün liegen unter 3:1
Kontrast zur Fläche, deshalb tragen alle Punkte und Balken Textlabels und es gibt
eine Tabellenansicht.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

TYPE_ORDER = ["eliminated", "transformed", "augmented", "emerging", "stable", "unscored"]
TYPE_LABEL = {
    "eliminated": "Eliminiert",
    "transformed": "Transformiert",
    "augmented": "Augmentiert",
    "emerging": "Entstehend",
    "stable": "Stabil",
    "unscored": "Unbewertet",
}
DEFAULT_THEME_PATH = Path(__file__).resolve().parent.parent / "assets" / "theme.json"
THEME: dict[str, Any] = {}
TYPE_COLOR: dict[str, str] = {}
MODE_COLOR: dict[str, str] = {}


def load_theme(path: Path | None) -> None:
    """Theme laden (Standard: assets/theme.json neben dem Skript). Fehlende Schlüssel fallen auf den Standard zurück."""
    global THEME, TYPE_COLOR, MODE_COLOR
    base = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    if path:
        custom = json.loads(path.read_text(encoding="utf-8"))
        for k, v in custom.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v
    THEME = base
    TYPE_COLOR = dict(base["type_colors"])
    MODE_COLOR = dict(base["mode_colors"])
MODE_LABEL = {"manual": "manuell", "ai_assisted": "KI-unterstützt", "agent_delegated": "an Agent delegiert"}
HORIZON_LABEL = {"near": "kurzfristig", "mid": "mittelfristig", "long": "langfristig", None: "–"}
SOURCING_LABEL = {"build": "Build", "buy": "Buy", "hybrid": "Hybrid"}
STATUS_LABEL = {"proposed": "vorgeschlagen", "planned": "geplant", "pilot": "Pilot", "live": "live"}
EVIDENCE_LABEL = {"high": "belastbar", "medium": "teilweise geprüft", "low": "ungeprüft"}
EVIDENCE_COLOR = {"high": "#2E7D32", "medium": "#B26A00", "low": "#9A9A9A"}
STABILITY_LABEL = {"stable": "Einstufung stabil", "borderline": "Einstufung grenznah", "fragile": "Einstufung wackelig"}
SCENARIO_ORDER = ["conservative", "balanced", "agent_native"]
SCENARIO_LABEL = {"conservative": "Konservativ", "balanced": "Ausgewogen", "agent_native": "Agent-nativ"}
SCENARIO_HINT = {
    "conservative": "Heutige Kontrollen bleiben, KI assistiert.",
    "balanced": "Unnötige Schritte und Übergaben entfallen, Menschen behandeln Ausnahmen.",
    "agent_native": "Vom Zielzustand aus neu gebaut, Menschen an Verantwortungsgrenzen.",
}
OPERATOR_LABEL = {"eliminate": "Eliminiert", "simplify": "Vereinfacht", "merge": "Zusammengeführt",
                  "parallelize": "Parallelisiert", "automate": "Automatisiert", "human_gate": "Human Gate"}
EXECUTOR_LABEL = {"human": "Mensch", "agent": "Agent", "system": "System", "rule": "Regel"}
EXECUTOR_CLASS = {"human": "ex-human", "agent": "ex-agent", "system": "ex-system", "rule": "ex-rule"}
BASIS_LABEL = {"observed": "gemessen", "expert_confirmed": "bestätigt", "estimated": "geschätzt"}
BASIS_SHORT = {"observed": "gem.", "expert_confirmed": "best.", "estimated": "gesch."}
BAND_LABEL = {"now": "Jetzt", "next": "Als Nächstes", "later": "Später", "hold": "Zurückstellen"}
BAND_COLOR = {"now": "#2E7D32", "next": "#1C6CA8", "later": "#B26A00", "hold": "#6E6E6E"}
DESIGN_LABEL = {"ab_test": "A/B-Test", "shadow": "Schattenbetrieb",
                "stepped_rollout": "gestaffelter Rollout", "pre_post": "Vorher-Nachher"}
VALUE_TYPE_LABEL = {"customer_value": "Kundenwert", "business_required": "betrieblich nötig",
                    "waste": "ohne Wertbeitrag"}
FLOW_METRICS = [
    ("steps", "Schritte", 0),
    ("human_touches", "Human Touchpoints", 0),
    ("handovers", "Übergaben", 0),
    ("handling_time_min", "Bearbeitungszeit (min)", 1),
    ("wait_time_min", "Wartezeit (min)", 1),
    ("lead_time_hours", "Durchlaufzeit (h)", 1),
    ("rework_pct", "Nacharbeit (%)", 1),
    ("automated_steps", "automatisierte Schritte", 0),
]

ARCH_LABEL = {
    "control-heavy": "Kontrolle", "knowledge-heavy": "Wissen", "process-heavy": "Prozess",
    "relationship-heavy": "Beziehung", "creative-heavy": "Kreation", "physical-heavy": "Physisch",
}


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def fmt(x: Any, nd: int = 1) -> str:
    if x is None:
        return "–"
    return f"{float(x):.{nd}f}".replace(".", ",")


def pct(x: Any) -> str:
    return "–" if x is None else f"{float(x):.0f} %"


# ---------------------------------------------------------------------------
# Datenaufbereitung
# ---------------------------------------------------------------------------

def prepare(graph: dict[str, Any]) -> dict[str, Any]:
    clusters = wl.index_by_id(graph["job_clusters"])
    families = wl.index_by_id(graph["job_families"])
    skills = wl.index_by_id(graph["skills"])
    tasks_by_role: dict[str, list] = {}
    for t in graph["tasks"]:
        tasks_by_role.setdefault(t["role_id"], []).append(t)
    agents = wl.index_by_id(graph["agents"])

    roles = []
    for r in graph["roles"]:
        an = r.get("analysis") or {"scored": False}
        cl = clusters[r["cluster_id"]]
        fam = families[cl["family_id"]]
        rt = sorted(tasks_by_role.get(r["id"], []), key=lambda t: (-t["share_of_time"], t["name"]))
        roles.append({
            "id": r["id"], "name": r["name"], "cluster": cl["name"], "family": fam["name"],
            "level": r.get("level", ""), "headcount": r.get("headcount"), "archetype": r.get("archetype"),
            "regulated": r.get("regulated", False), "status": r.get("status"), "purpose": r.get("purpose", ""),
            "type": an.get("disruption_type", "unscored") if an.get("scored") else "unscored",
            "analysis": an, "tasks": rt,
            "skills": sorted(({"name": skills[s["skill_id"]]["name"], "level": s["level"], "importance": s["importance"]}
                              for s in r.get("skills", []) if s["skill_id"] in skills),
                             key=lambda s: (s["importance"] != "core", s["name"])),
        })
    roles.sort(key=lambda r: (-(r["analysis"].get("disruption_score") or -1), r["name"], r["id"]))

    ag_list = sorted(graph["agents"], key=lambda a: (a.get("priority_rank", 10**6), a["name"]))
    return {"roles": roles, "agents": ag_list, "agents_idx": agents, "clusters": clusters, "skills": skills}


def kpis(graph: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    roles = [r for r in data["roles"] if r["type"] != "unscored"]
    def weighted(key: str) -> float | None:
        if not roles:
            return None
        w = [(r["analysis"][key], r["headcount"] if r["headcount"] is not None else 1) for r in roles if r["analysis"].get(key) is not None]
        tot = sum(x[1] for x in w)
        return wl.round1(sum(x[0] * x[1] for x in w) / tot) if tot else None
    n_tasks = len(graph["tasks"])
    inferred = sum(1 for t in graph["tasks"] if t.get("confidence") == "inferred")
    return {
        "roles": len(data["roles"]), "roles_scored": len(roles), "tasks": n_tasks, "agents": len(graph["agents"]),
        "skills": len(graph["skills"]),
        "headcount": sum(r["headcount"] for r in data["roles"] if r["headcount"] is not None),
        "headcount_known": sum(1 for r in data["roles"] if r["headcount"] is not None),
        "share_delegated": weighted("share_agent_delegated"), "share_assisted": weighted("share_ai_assisted"),
        "share_core": weighted("share_human_core"), "disruption": weighted("disruption_score"),
        "inferred_pct": wl.round1(100.0 * inferred / n_tasks) if n_tasks else 0.0,
        "reviewed_roles": sum(1 for r in data["roles"] if r["status"] in ("reviewed", "approved")),
        "evidence": {lvl: sum(1 for r in roles if r["analysis"].get("evidence") == lvl) for lvl in ("high", "medium", "low")},
        "fragile": sum(1 for r in roles if r["analysis"].get("stability") == "fragile"),
        "borderline": sum(1 for r in roles if r["analysis"].get("stability") == "borderline"),
        "types": {t: sum(1 for r in data["roles"] if r["type"] == t) for t in TYPE_ORDER},
    }


# ---------------------------------------------------------------------------
# HTML-Bausteine
# ---------------------------------------------------------------------------

CSS = """
:root{--primary:__PRIMARY__;--accent:__ACCENT__;--gray:#e3e1de;--ink:#111;--ink2:#4a4a4a;--ink3:#7a7a7a;--surface:__SURFACE__;--card:#fff;--line:#e6e2de;
--f-head:__FONT_HEAD__;--f-text:__FONT_TEXT__;}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--ink);font-family:var(--f-text);font-size:15px;line-height:1.45}
header{background:var(--primary);color:#fff;padding:28px 32px}header h1{font-family:var(--f-head);font-size:28px;margin:0 0 6px;font-weight:700}
header .sub{opacity:.85;font-size:14px}header .sub b{color:#fff}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:0 32px;z-index:5;display:flex;gap:4px;overflow-x:auto}
nav a{display:block;padding:12px 14px;color:var(--primary);text-decoration:none;font-weight:600;border-bottom:3px solid transparent;white-space:nowrap}
nav a:hover{border-color:var(--accent)}
main{padding:24px 32px;max-width:1400px;margin:0 auto}section{margin:0 0 40px;scroll-margin-top:56px}
h2{font-family:var(--f-head);color:var(--primary);font-size:22px;margin:0 0 4px}h2+p{margin:0 0 16px;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.tile .v{font-family:var(--f-head);font-size:32px;color:var(--primary);line-height:1.1}.tile .l{font-size:13px;color:var(--ink3);margin-top:4px}
.bar{display:flex;height:22px;border-radius:4px;overflow:hidden;gap:2px;background:var(--surface)}
.bar span{display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff;font-weight:600;min-width:0;overflow:hidden;white-space:nowrap}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;margin:8px 0 0}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 12px;font-size:13px}
.filters label{display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border:1px solid var(--line);border-radius:14px;background:#fff;cursor:pointer}
.filters select{padding:4px 8px;border:1px solid var(--line);border-radius:6px;font:inherit}
.matrix{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;position:relative}
.matrix svg{width:100%;height:auto;display:block}.dot{cursor:pointer}.dot:hover circle{stroke:var(--ink);stroke-width:2}
.qlabel{font-size:11px;fill:#8a8a8a}.axis{font-size:11px;fill:#6a6a6a}.grid{stroke:#eee;stroke-width:1}
.tip{position:absolute;pointer-events:none;background:#111;color:#fff;font-size:12px;padding:6px 9px;border-radius:6px;display:none;max-width:280px;z-index:9}
.cards{display:grid;gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.card .head{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.score{width:56px;height:56px;border-radius:50%;border:3px solid;display:flex;align-items:center;justify-content:center;font-family:var(--f-head);font-size:20px;flex:none}
.card h3{margin:0;font-size:18px;font-family:var(--f-head);color:var(--primary)}.meta{font-size:13px;color:var(--ink3)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;border:1px solid var(--line);margin:2px 4px 0 0;color:var(--ink2);background:#fafafa}
.tag.t{color:#fff;border-color:transparent}
.logic{margin:10px 0 4px;font-weight:600;color:var(--ink)}.action{color:var(--ink2);font-size:14px}
.rows{display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;margin-top:10px}.rows .k{font-size:12px;color:var(--ink3)}
.mbar{height:8px;background:#eee;border-radius:4px;overflow:hidden;margin:3px 0 0}.mbar i{display:block;height:100%;background:var(--primary)}
details{margin-top:8px}summary{cursor:pointer;color:var(--primary);font-weight:600;font-size:14px}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f5f2ef;color:var(--ink2);font-weight:600;position:sticky;top:46px}td.n,th.n{text-align:right;white-space:nowrap}
.pill{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;color:#fff;font-weight:600;white-space:nowrap}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.col{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.col h4{margin:0 0 8px;font-size:15px;color:var(--primary);font-family:var(--f-head)}.col ul{margin:0;padding-left:18px;font-size:13px}.col li{margin:3px 0}
footer{padding:20px 32px;color:var(--ink3);font-size:12px;border-top:1px solid var(--line)}
.hidden{display:none!important}.nojs{margin:6px 0 10px;padding:8px 12px;border:1px solid #E6B800;background:#FFF8DB;border-radius:6px;font-size:13px;color:#5a4a00}
/* Szenarien umschalten ohne JavaScript: verborgene Radios steuern über
   :checked ~ die Sichtbarkeit der zugehörigen Tafel. Die Radios bleiben
   fokussierbar, damit die Umschaltung auch per Tastatur funktioniert. */
.tabs{position:relative}
.tabs>input{position:absolute;width:1px;height:1px;opacity:0;margin:0}
.tabbar{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}
.tabbar label{padding:6px 12px;border:1px solid var(--line);border-radius:14px;background:#fff;cursor:pointer;font-size:13px;font-weight:600;color:var(--ink2)}
.tabs>.panes>.pane{display:none}
.tabs>input:nth-of-type(1):checked~.panes>.pane:nth-child(1),
.tabs>input:nth-of-type(2):checked~.panes>.pane:nth-child(2),
.tabs>input:nth-of-type(3):checked~.panes>.pane:nth-child(3),
.tabs>input:nth-of-type(4):checked~.panes>.pane:nth-child(4){display:block}
.tabs>input:nth-of-type(1):checked~.tabbar label:nth-child(1),
.tabs>input:nth-of-type(2):checked~.tabbar label:nth-child(2),
.tabs>input:nth-of-type(3):checked~.tabbar label:nth-child(3),
.tabs>input:nth-of-type(4):checked~.tabbar label:nth-child(4){background:var(--primary);color:#fff;border-color:var(--primary)}
.tabs>input:focus-visible~.tabbar label{outline:2px solid var(--accent);outline-offset:2px}
.flow{display:flex;flex-wrap:wrap;align-items:stretch;gap:4px;margin:10px 0}
.flow .st{flex:1 1 150px;min-width:140px;border:1px solid var(--line);border-left:4px solid var(--ink3);border-radius:6px;padding:8px 10px;background:#fff;font-size:12px}
.flow .st b{display:block;font-size:13px;color:var(--ink);margin-bottom:3px}
.flow .st .who{color:var(--ink3)}
.flow .st.ex-human{border-left-color:#1C6CA8}.flow .st.ex-agent{border-left-color:#6A3FA0}
.flow .st.ex-system{border-left-color:#2E7D32}.flow .st.ex-rule{border-left-color:#B26A00}
.flow .st.gone{background:#f7f5f3;border-left-color:#c9c4bf;color:var(--ink3);text-decoration:line-through}
.flow .arr{align-self:center;color:var(--ink3);font-size:16px;flex:0 0 auto}
.gate{display:inline-block;margin-top:4px;font-size:11px;padding:1px 6px;border-radius:9px;background:#FFF3D6;color:#5a4a00;border:1px solid #E6C77A}
.delta-up{color:#2E7D32;font-weight:600}.delta-down{color:#B3261E;font-weight:600}.delta-flat{color:var(--ink3)}
.basis{font-size:11px;color:var(--ink3);white-space:nowrap}
.band{display:inline-block;padding:1px 8px;border-radius:9px;font-size:11px;color:#fff;font-weight:600}
.note{font-size:12px;color:var(--ink3);margin:6px 0 0}
.warnbox{margin:10px 0;padding:10px 12px;border:1px solid #E6B800;background:#FFF8DB;border-radius:6px;font-size:13px;color:#5a4a00}
@media(max-width:800px){main,header,nav,footer{padding-left:16px;padding-right:16px}.cols{grid-template-columns:1fr}.rows{grid-template-columns:1fr}}
"""

JS = """
(function(){
const roles=window.__ROLES__;
const nj=document.getElementById('nojs');if(nj){nj.remove();}
const tip=document.getElementById('tip');const matrix=document.getElementById('matrix-box');
function show(e,html){tip.innerHTML=html;tip.style.display='block';const r=matrix.getBoundingClientRect();tip.style.left=(e.clientX-r.left+12)+'px';tip.style.top=(e.clientY-r.top+12)+'px';}
function hide(){tip.style.display='none';}
document.querySelectorAll('.dot').forEach(d=>{const id=d.getAttribute('data-id');const r=roles[id];
 d.addEventListener('mousemove',e=>show(e,'<b>'+r.name+'</b><br>'+r.cluster+'<br>'+r.typeLabel+' · Score '+r.score+'<br>AP '+r.ap+' · Urteil '+r.hj+' · Hebel '+r.pb));
 d.addEventListener('mouseleave',hide);
 d.addEventListener('click',()=>{const c=document.getElementById('role-'+id);if(c){c.scrollIntoView({behavior:'smooth',block:'start'});c.style.outline='3px solid var(--accent)';setTimeout(()=>c.style.outline='',1800);}});});
function applyFilters(){const types=[...document.querySelectorAll('input[data-type]')].filter(i=>i.checked).map(i=>i.getAttribute('data-type'));
 const cl=document.getElementById('f-cluster').value;
 document.querySelectorAll('[data-role-type]').forEach(el=>{const ok=types.includes(el.getAttribute('data-role-type'))&&(cl===''||el.getAttribute('data-role-cluster')===cl);el.classList.toggle('hidden',!ok);});}
document.querySelectorAll('input[data-type]').forEach(i=>i.addEventListener('change',applyFilters));
document.getElementById('f-cluster').addEventListener('change',applyFilters);
})();
"""


def themed_css() -> str:
    return (CSS.replace("__PRIMARY__", THEME["primary"]).replace("__ACCENT__", THEME["accent"])
            .replace("__SURFACE__", THEME["surface"]).replace("__FONT_HEAD__", THEME["font_headline"])
            .replace("__FONT_TEXT__", THEME["font_text"]))


def tiles_html(k: dict[str, Any]) -> str:
    hc = f"{k['headcount']}" if k["headcount_known"] else "–"
    items = [
        (str(k["roles"]), "Rollen"), (str(k["tasks"]), "Aufgaben"), (str(k["skills"]), "Skills"),
        (str(k["agents"]), "Agenten"), (hc, "Headcount (bekannt)"),
        (fmt(k["disruption"]), "Ø Disruptionsscore"),
        (pct(k["share_delegated"]), "Zeit delegierbar"), (pct(k["share_assisted"]), "Zeit KI-unterstützt"),
        (pct(k["share_core"]), "Zeit menschlicher Kern"),
    ]
    return '<div class="tiles">' + "".join(f'<div class="tile"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in items) + "</div>"


def dist_html(k: dict[str, Any]) -> str:
    total = sum(k["types"].values()) or 1
    segs, leg = [], []
    for t in TYPE_ORDER:
        n = k["types"][t]
        if n == 0:
            continue
        w = 100.0 * n / total
        segs.append(f'<span style="width:{w:.2f}%;background:{TYPE_COLOR[t]}" title="{esc(TYPE_LABEL[t])}: {n}">{TYPE_LABEL[t]} {n}</span>')
        leg.append(f'<span><i style="background:{TYPE_COLOR[t]}"></i>{TYPE_LABEL[t]}: {n}</span>')
    return f'<div class="bar">{"".join(segs)}</div><div class="legend">{"".join(leg)}</div>'


def matrix_svg(roles: list[dict[str, Any]]) -> str:
    n_scored = sum(1 for r in roles if r["analysis"].get("scored"))
    W, P = 900, 50
    H = 520 if n_scored <= 25 else (700 if n_scored <= 50 else 860)
    def X(v: float) -> float:
        return P + (W - 2 * P) * v / 10.0
    def Y(v: float) -> float:
        return H - P - (H - 2 * P) * v / 10.0
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Rollenmatrix: Automatisierungspotenzial gegen menschliches Urteil">']
    for i in range(0, 11, 2):
        out.append(f'<line class="grid" x1="{X(i):.1f}" y1="{Y(0):.1f}" x2="{X(i):.1f}" y2="{Y(10):.1f}"/>')
        out.append(f'<line class="grid" x1="{X(0):.1f}" y1="{Y(i):.1f}" x2="{X(10):.1f}" y2="{Y(i):.1f}"/>')
        out.append(f'<text class="axis" x="{X(i):.1f}" y="{H - P + 16}" text-anchor="middle">{i}</text>')
        out.append(f'<text class="axis" x="{P - 8}" y="{Y(i) + 4:.1f}" text-anchor="end">{i}</text>')
    out.append(f'<line x1="{X(5):.1f}" y1="{Y(0):.1f}" x2="{X(5):.1f}" y2="{Y(10):.1f}" stroke="#ccc" stroke-dasharray="4 4"/>')
    out.append(f'<line x1="{X(0):.1f}" y1="{Y(5):.1f}" x2="{X(10):.1f}" y2="{Y(5):.1f}" stroke="#ccc" stroke-dasharray="4 4"/>')
    out.append(f'<text class="axis" x="{W / 2:.0f}" y="{H - 10}" text-anchor="middle">Automatisierungspotenzial (0–10) →</text>')
    out.append(f'<text class="axis" transform="translate(14,{H / 2:.0f}) rotate(-90)" text-anchor="middle">Menschliches Urteil (0–10) →</text>')
    for (x, y, lab) in [(0.3, 9.6, "Geschützt"), (9.7, 9.6, "Augmentiert"), (0.3, 0.4, "Stabil"), (9.7, 0.4, "Gefährdet")]:
        anchor = "start" if x < 5 else "end"
        out.append(f'<text class="qlabel" x="{X(x):.1f}" y="{Y(y) + 4:.1f}" text-anchor="{anchor}">{lab}</text>')
    # Deterministische Labelplatzierung: Punkte in fester Reihenfolge (Rollen-ID), je Label
    # feste Kandidatenliste; das erste kollisionsfreie Feld gewinnt. Versetzte Labels bekommen
    # eine Führungslinie. Textbreite wird mit 5.6 px je Zeichen geschätzt (10 px Schrift).
    CH, LH = 5.8, 14.0
    placed: list[tuple[float, float, float, float]] = []  # belegte Rechtecke (x1,y1,x2,y2)
    scored = [r for r in sorted(roles, key=lambda r: r["id"]) if r["analysis"].get("scored")]
    dots = []
    for r in scored:
        an = r["analysis"]
        x, y = X(float(an["automation_potential"])), Y(float(an["human_judgment"]))
        rad = 6 + (min(float(r["headcount"] or 0), 100) ** 0.5) * 0.8
        dots.append((r, x, y, rad))
        placed.append((x - rad, y - rad, x + rad, y + rad))

    def overlaps(box: tuple[float, float, float, float]) -> bool:
        x1, y1, x2, y2 = box
        if x1 < P or x2 > W - P or y1 < P or y2 > H - P:
            return True
        return any(not (x2 < a or x1 > c or y2 < b or y1 > d) for (a, b, c, d) in placed)

    for (r, x, y, rad) in dots:
        col = TYPE_COLOR[r["type"]]
        label = r["name"] if len(r["name"]) <= 34 else r["name"][:33] + "…"
        tw = len(label) * CH
        prefer_left = float(r["analysis"]["automation_potential"]) > 6.5
        sides = ["end", "start"] if prefer_left else ["start", "end"]
        cands: list[tuple[float, float, str]] = []
        for dy in (0, -LH, LH, -2 * LH, 2 * LH, -3 * LH, 3 * LH, -4 * LH, 4 * LH):
            for side in sides:
                for dx in (0, 14, 28, 42, 56, 70):
                    lx = x - rad - 3 - dx if side == "end" else x + rad + 3 + dx
                    cands.append((lx, y + dy, side))
        found = None
        for (cx, cy, side) in cands:
            box = (cx - tw if side == "end" else cx, cy - LH / 2, cx if side == "end" else cx + tw, cy + LH / 2)
            if not overlaps(box):
                found = (cx, cy, side)
                placed.append(box)
                break
        # Kein freier Platz: Label weglassen (Name bleibt als Tooltip und in der Tabelle), statt zu überlappen.
        text = ""
        leader = ""
        if found:
            lx, ly, anchor = found
            if abs(ly - y) > 1 or abs(abs(lx - x) - rad - 3) > 1:
                ex = lx - 2 if anchor == "start" else lx + 2
                leader = f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{ex:.1f}" y2="{ly:.1f}" stroke="#bbb" stroke-width="1"/>'
            text = f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="10" fill="#333" text-anchor="{anchor}">{esc(label)}</text>'
        an = r["analysis"]
        tip = f'{r["name"]} · {TYPE_LABEL[r["type"]]} · AP {fmt(an["automation_potential"])} · Urteil {fmt(an["human_judgment"])} · Score {fmt(an.get("disruption_score"))}'
        out.append(f'<g class="dot" data-id="{r["id"]}" data-role-type="{r["type"]}" data-role-cluster="{esc(r["cluster"])}"><title>{esc(tip)}</title>{leader}'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" fill-opacity="0.85" stroke="#fff" stroke-width="2"/>{text}</g>')
    out.append("</svg>")
    return "".join(out)


def role_card(r: dict[str, Any], agents_idx: dict[str, Any]) -> str:
    an = r["analysis"]
    col = TYPE_COLOR[r["type"]]
    hc = f"{r['headcount']} MA" if r["headcount"] is not None else "Headcount unbekannt"
    tags = [f'<span class="tag t" style="background:{col}">{TYPE_LABEL[r["type"]]}</span>']
    if r["archetype"]:
        tags.append(f'<span class="tag">{ARCH_LABEL.get(r["archetype"], r["archetype"])}</span>')
    if r["regulated"]:
        tags.append('<span class="tag">reguliert</span>')
    tags.append(f'<span class="tag">Status: {esc(r["status"])}</span>')
    if an.get("scored"):
        ev = an.get("evidence", "low")
        tags.append(f'<span class="tag" style="border-color:{EVIDENCE_COLOR[ev]};color:{EVIDENCE_COLOR[ev]}" title="{esc("; ".join(an.get("evidence_reasons", [])))}">Belastbarkeit: {EVIDENCE_LABEL[ev]}</span>')
        st = an.get("stability", "stable")
        fx = an.get("flip_examples") or []
        hint = (f' – z. B. {fx[0]["task"]}: {fx[0]["field"]} {fx[0]["delta"]:+d} → {TYPE_LABEL.get(fx[0]["new_type"], fx[0]["new_type"])}' if fx else "")
        flip_title = f"{an.get('flip_share', 0)} % der ±1-Änderungen kippen die Einstufung{hint}"
        tags.append(f'<span class="tag" title="{esc(flip_title)}">{STABILITY_LABEL.get(st, st)}</span>')
    if not an.get("scored"):
        body = '<p class="meta">Noch nicht bewertet (task-scorer ausführen).</p>'
    else:
        MODES = [("share_human_core", "manual"), ("share_ai_assisted", "ai_assisted"), ("share_agent_delegated", "agent_delegated")]

        def seg(k: str, m: str) -> str:
            v = float(an[k])
            text = f"{MODE_LABEL[m]} {v:.0f} %" if v >= 22 else (f"{v:.0f} %" if v >= 7 else "")
            return f'<span style="width:{v:.1f}%;background:{MODE_COLOR[m]}" title="{MODE_LABEL[m]} {v:.0f} %">{text}</span>'
        shares = "".join(seg(k, m) for k, m in MODES if float(an[k]) > 0)
        share_legend = "".join(f'<span><i style="background:{MODE_COLOR[m]}"></i>{MODE_LABEL[m]} {float(an[k]):.0f} %</span>' for k, m in MODES)
        def mrow(label: str, val: float, sub: str = "") -> str:
            return (f'<div><div class="k">{label} <b style="color:#111">{fmt(val)}/10</b> {sub}</div>'
                    f'<div class="mbar"><i style="width:{float(val) * 10:.0f}%"></i></div></div>')
        rows = [
            mrow("Automatisierungspotenzial", an["automation_potential"], f'<span class="meta">(KI/Software {fmt(an["automation_ai"])} · Physisch {fmt(an["automation_physical"])})</span>'),
            mrow("Menschliches Urteil nötig", an["human_judgment"]),
            mrow("Produktivitätshebel KI", an["productivity_boost"]),
            mrow("Datenlage", an["data_readiness"], f'<span class="meta">Bereitschaft: {esc(an["readiness"])}</span>'),
        ]
        core = ", ".join(an.get("retained_skills", [])) or "–"
        decl = ", ".join(an.get("declining_skills", [])) or "–"
        trows = []
        for t in r["tasks"]:
            sc = t.get("scores") or {}
            ag = ", ".join(agents_idx[a]["name"] for a in t.get("agent_ids", []) if a in agents_idx) or "–"
            mode = t.get("mode")
            pill = f'<span class="pill" style="background:{MODE_COLOR.get(mode, "#999")}">{MODE_LABEL.get(mode, "–")}</span>' if mode else "–"
            trows.append(f'<tr><td>{esc(t["name"])}<div class="meta">{esc(sc.get("rationale", ""))}</div></td><td class="n">{pct(t["share_of_time"])}</td>'
                         f'<td>{pill}</td><td class="n">{fmt(t.get("automation_potential"))}</td><td class="n">{fmt(sc.get("human_judgment"))}</td>'
                         f'<td class="n">{"H" + str(t["has_level"]) if t.get("has_level") else "–"}</td><td>{HORIZON_LABEL.get(t.get("horizon"), "–")}</td><td>{esc(ag)}</td></tr>')
        evidence_text = "; ".join(an.get("evidence_reasons", []))
        flip_pct = float(an.get("flip_share", 0) or 0)
        body = (f'<div class="bar" style="margin-top:10px">{shares}</div><div class="legend">{share_legend}</div>'
                f'<div class="logic">{esc(an["transformation_logic"])} · {esc(an["horizon_label"])}</div>'
                f'<div class="action">{esc(an["next_action"])}</div>'
                f'<div class="meta" style="margin-top:6px">Belastbarkeit: {esc(evidence_text)}. {flip_pct:.0f} % der Einzeländerungen um ±1 an Maschinenanteil, Urteilsbedarf oder Fehlergewicht würden die Einstufung ändern.</div>'
                f'<div class="rows">{"".join(rows)}</div>'
                f'<div class="rows"><div><div class="k">Skills, die gebraucht bleiben</div>{esc(core)}</div><div><div class="k">Skills mit sinkendem Bedarf</div>{esc(decl)}</div></div>'
                f'<details><summary>{len(r["tasks"])} Aufgaben im Detail</summary><table><thead><tr><th>Aufgabe</th><th class="n">Zeit</th><th>Modus</th><th class="n">AP</th><th class="n">Urteil</th><th class="n">HAS</th><th>Horizont</th><th>Agent</th></tr></thead><tbody>{"".join(trows)}</tbody></table></details>')
    score = fmt(an.get("disruption_score")) if an.get("scored") else "–"
    return (f'<div class="card" id="role-{r["id"]}" data-role-type="{r["type"]}" data-role-cluster="{esc(r["cluster"])}">'
            f'<div class="head"><div class="score" style="border-color:{col};color:{col}">{score}</div>'
            f'<div style="flex:1"><h3>{esc(r["name"])}</h3><div class="meta">{esc(r["family"])} › {esc(r["cluster"])} · {esc(r["level"] or "–")} · {esc(hc)} · <code>{r["id"]}</code></div>'
            f'<div>{"".join(tags)}</div><div class="meta" style="margin-top:6px">{esc(r["purpose"])}</div></div></div>{body}</div>')


def agents_html(agents: list[dict[str, Any]]) -> str:
    if not agents:
        return '<p class="meta">Noch keine Agenten (agent-mapper ausführen).</p>'
    rows = []
    for a in agents:
        fte = fmt(a.get("fte_equivalent")) if a.get("fte_equivalent") is not None else f'{fmt(a.get("coverage_points"))} Pkt.'
        cov = "".join(f'<li>{esc(rc["role"])}: <b>{pct(rc["coverage_pct"])}</b> der Rollenzeit ({len(rc["task_ids"])} Aufgaben)</li>' for rc in a.get("roles_covered", []))
        pre = "".join(f"<li>{esc(p)}</li>" for p in a.get("prerequisites", [])) or "<li>–</li>"
        detail = (f'<details><summary>Details</summary><p>{esc(a.get("capability"))}</p>'
                  f'<div class="rows"><div><div class="k">Abgedeckte Rollen</div><ul>{cov}</ul></div>'
                  f'<div><div class="k">Aufsicht</div><p>{esc(a.get("oversight") or "–")}</p><div class="k">Vorbedingungen</div><ul>{pre}</ul></div></div></details>')
        rows.append(f'<tr><td class="n">{a.get("priority_rank", "–")}</td><td class="n">{a.get("sequence_rank", "–")}</td><td><b>{esc(a["name"])}</b><div class="meta">{esc(a.get("pattern"))}'
                    f'{(" · " + esc(a["existing_system"])) if a.get("existing_system") else ""}</div>{detail}</td>'
                    f'<td>{STATUS_LABEL.get(a.get("status"), a.get("status"))}</td><td>{SOURCING_LABEL.get(a.get("sourcing"), "–")}</td>'
                    f'<td>{HORIZON_LABEL.get(a.get("horizon"), "–")}</td><td class="n">{a.get("complexity", "–")}/5</td>'
                    f'<td class="n">{a.get("roles_covered_count", 0)}</td><td class="n">{pct(a.get("avg_coverage_pct"))}</td><td class="n">{fte}</td></tr>')
    return ('<table><thead><tr><th class="n">Wert #</th><th class="n">Bau #</th><th>Agent</th><th>Status</th><th>Sourcing</th><th>Horizont</th><th class="n">Komplexität</th>'
            '<th class="n">Rollen</th><th class="n">Ø Abdeckung</th><th class="n">FTE-Äquiv.</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


def rollout_html(roles: list[dict[str, Any]], agents: list[dict[str, Any]]) -> str:
    cols = []
    for h, title in [("near", "Kurzfristig (0–2 Jahre)"), ("mid", "Mittelfristig (2–5 Jahre)"), ("long", "Langfristig (5+ Jahre)")]:
        ag = [a for a in agents if a.get("horizon") == h]
        ro = [r for r in roles if r["analysis"].get("horizon") == h]
        li_a = "".join(f'<li><b>{esc(a["name"])}</b> ({SOURCING_LABEL.get(a.get("sourcing"), "–")})</li>' for a in ag) or "<li>–</li>"
        li_r = "".join(f'<li>{esc(r["name"])} <span class="meta">({TYPE_LABEL[r["type"]]})</span></li>' for r in ro) or "<li>–</li>"
        cols.append(f'<div class="col"><h4>{title}</h4><div class="k meta">Agenten</div><ul>{li_a}</ul><div class="k meta" style="margin-top:8px">Rollen mit Veränderung</div><ul>{li_r}</ul></div>')
    return f'<div class="cols">{"".join(cols)}</div>'


def table_html(roles: list[dict[str, Any]]) -> str:
    rows = []
    for r in roles:
        an = r["analysis"]
        rows.append(f'<tr data-role-type="{r["type"]}" data-role-cluster="{esc(r["cluster"])}"><td>{esc(r["name"])}</td><td>{esc(r["cluster"])}</td>'
                    f'<td class="n">{r["headcount"] if r["headcount"] is not None else "–"}</td><td>{TYPE_LABEL[r["type"]]}</td>'
                    f'<td class="n">{fmt(an.get("disruption_score"))}</td><td class="n">{fmt(an.get("automation_potential"))}</td><td class="n">{fmt(an.get("human_judgment"))}</td>'
                    f'<td class="n">{fmt(an.get("productivity_boost"))}</td><td class="n">{pct(an.get("share_human_core"))}</td><td class="n">{pct(an.get("share_ai_assisted"))}</td>'
                    f'<td class="n">{pct(an.get("share_agent_delegated"))}</td><td>{HORIZON_LABEL.get(an.get("horizon"), "–")}</td><td>{EVIDENCE_LABEL.get(an.get("evidence"), "–")}</td><td>{STABILITY_LABEL.get(an.get("stability"), "–").replace("Einstufung ", "")}</td><td>{esc(r["status"])}</td></tr>')
    return ('<table><thead><tr><th>Rolle</th><th>Cluster</th><th class="n">MA</th><th>Typ</th><th class="n">Score</th><th class="n">AP</th><th class="n">Urteil</th>'
            '<th class="n">Hebel</th><th class="n">Kern</th><th class="n">Assist.</th><th class="n">Deleg.</th><th>Horizont</th><th>Belastbarkeit</th><th>Stabilität</th><th>Status</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


# ---------------------------------------------------------------------------
# Prozessansicht (Schema 1.1)
# ---------------------------------------------------------------------------

def name_index(graph: dict[str, Any]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for c in wl.COLLECTIONS:
        for it in graph.get(c, []):
            idx[it["id"]] = it
    return idx


def process_kpis(graph: dict[str, Any]) -> dict[str, Any]:
    """Portfoliokennzahlen der Prozessebene.

    Die Deltas werden über das jeweils beste entworfene Szenario je Prozess gebildet —
    nicht über alle Blueprints, sonst zählt ein Prozess mit drei Szenarien dreifach.
    """
    procs = graph.get("processes", [])
    best: dict[str, dict] = {}
    for bp in graph.get("blueprints", []):
        cur = best.get(bp["process_id"])
        score = (bp.get("delta", {}).get("lead_time_hours", {}) or {}).get("improvement") or 0
        if cur is None or score > (cur.get("delta", {}).get("lead_time_hours", {}) or {}).get("improvement", 0):
            best[bp["process_id"]] = bp
    lead_gain = [(b["delta"].get("lead_time_hours") or {}).get("improvement_pct")
                 for b in best.values()]
    lead_gain = [x for x in lead_gain if x is not None]
    touch_gain = sum((b["delta"].get("human_touches") or {}).get("improvement") or 0
                     for b in best.values())
    hand_gain = sum((b["delta"].get("handovers") or {}).get("improvement") or 0
                    for b in best.values())
    scored = [p for p in procs if p.get("value")]
    bands = {b: sum(1 for p in scored if p["value"]["band"] == b) for b in wl.ENUM_PRIORITY_BAND}
    return {
        "processes": len(procs),
        "steps": len(graph.get("process_steps", [])),
        "blueprints": len(graph.get("blueprints", [])),
        "scenarios_complete": sum(1 for p in procs if len({b["scenario"] for b in graph["blueprints"]
                                                           if b["process_id"] == p["id"]}) >= 3),
        "experiments": len(graph.get("experiments", [])),
        "approved": sum(1 for b in graph.get("blueprints", []) if b.get("status") == "approved"),
        "avg_lead_gain": round(sum(lead_gain) / len(lead_gain), 1) if lead_gain else None,
        "touch_gain": touch_gain,
        "handover_gain": hand_gain,
        "bands": bands,
        "scored": len(scored),
        "best": best,
    }


def process_tiles(pk: dict[str, Any]) -> str:
    items = [
        (str(pk["processes"]), "Prozesse"),
        (str(pk["steps"]), "Prozessschritte"),
        (f"{pk['scenarios_complete']}/{pk['processes']}", "mit drei Szenarien"),
        (str(pk["approved"]), "Blueprints freigegeben"),
        (str(pk["experiments"]), "Piloten geplant"),
        (pct(pk["avg_lead_gain"]) if pk["avg_lead_gain"] is not None else "–", "Ø Durchlaufzeitgewinn"),
        (f"{pk['touch_gain']:+g}", "Human Touchpoints"),
        (f"{pk['handover_gain']:+g}", "Übergaben"),
    ]
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>'
        for v, l in items) + "</div>"


def _delta_cell(d: dict[str, Any], nd: int = 1) -> str:
    """Eine Deltazelle: Soll-Wert, Veränderung und der Ist-Wert als Tooltip.

    Das Vorzeichen ist immer als Verbesserung gelesen — bei Kennzahlen, bei denen
    weniger besser ist, wurde es vorher gedreht. Sonst müsste man in jeder Zeile neu
    überlegen, ob ein Minus gut oder schlecht ist.
    """
    if not d:
        return '<td class="n">–</td>'
    imp = d.get("improvement")
    cls = "delta-flat" if not imp else ("delta-up" if imp > 0 else "delta-down")
    pctv = d.get("improvement_pct")
    extra = f" ({pctv:+g} %)" if pctv is not None else ""
    title = f"Ist {fmt(d.get('ist'), nd)} → Soll {fmt(d.get('soll'), nd)}"
    return (f'<td class="n" title="{esc(title)}">{fmt(d.get("soll"), nd)} '
            f'<span class="{cls}">{imp:+g}{extra}</span></td>')


def flow_html(graph: dict[str, Any], steps: list, names: dict, removed: set = frozenset()) -> str:
    """Ist- oder Soll-Fluss als Kette von Schrittkacheln."""
    parts = []
    for i, st in enumerate(steps):
        ex = st.get("executor") or {}
        etype = ex.get("type") or "human"
        who = ex.get("name") or names.get(ex.get("id"), {}).get("name") or EXECUTOR_LABEL.get(etype, etype)
        gone = st.get("id") in removed
        cls = "st gone" if gone else f"st {EXECUTOR_CLASS.get(etype, '')}"
        bits = [f'<b>{esc(st.get("name"))}</b>',
                f'<span class="who">{esc(EXECUTOR_LABEL.get(etype, etype))}: {esc(who)}</span>']
        t = st.get("handling_time_min")
        wv = st.get("wait_time_min")
        if t is not None or wv is not None:
            bits.append(f'<div>{fmt(t, 0)} min Arbeit · {fmt(wv, 0)} min Warten</div>')
        if st.get("operator"):
            bits.append(f'<div>{esc(OPERATOR_LABEL.get(st["operator"], st["operator"]))}</div>')
        if st.get("value_type"):
            bits.append(f'<div>{esc(VALUE_TYPE_LABEL.get(st["value_type"], ""))}</div>')
        if st.get("human_gate"):
            gate = st["human_gate"].get("when") or "Kontrollpunkt"
            bits.append(f'<span class="gate">Human Gate: {esc(gate)}</span>')
        parts.append(f'<div class="{cls}">{"".join(bits)}</div>')
        if i < len(steps) - 1:
            parts.append('<div class="arr">→</div>')
    return f'<div class="flow">{"".join(parts)}</div>' if parts else "<p>Keine Schritte erfasst.</p>"


def scenario_pane(graph: dict[str, Any], bp: dict[str, Any], names: dict) -> str:
    out = [f'<p>{esc(bp.get("summary") or SCENARIO_HINT.get(bp["scenario"], ""))}</p>']
    ops = ", ".join(f'{OPERATOR_LABEL[o]} {n}×'
                    for o, n in sorted((bp.get("operator_counts") or {}).items()) if n)
    out.append(f'<p class="meta">Operatoren: {esc(ops or "–")} · Status: {esc(bp.get("status", "draft"))}'
               + (f' · Agenten: {esc(", ".join(names.get(a, {}).get("name", a) for a in bp.get("agent_ids", [])))}'
                  if bp.get("agent_ids") else "") + '</p>')
    out.append(flow_html(graph, bp.get("steps", []), names))

    if bp.get("removed_steps"):
        rows = "".join(
            f'<tr><td>{esc(names.get(r["step_id"], {}).get("name", r["step_id"]))}</td>'
            f'<td>{esc(r.get("rationale", ""))}</td><td>{esc(r.get("replacement") or "–")}</td></tr>'
            for r in bp["removed_steps"])
        out.append('<details><summary>Gestrichene Schritte '
                   f'({len(bp["removed_steps"])})</summary>'
                   '<table><tr><th>Ist-Schritt</th><th>Begründung</th><th>Ersatz</th></tr>'
                   f'{rows}</table></details>')

    cov = bp.get("control_coverage") or {}
    if cov.get("replaced") or cov.get("dropped_control_ids"):
        rows = "".join(
            f'<tr><td>{esc(names.get(r["control_id"], {}).get("name", r["control_id"]))}</td>'
            f'<td>ersetzt</td><td>{esc(r.get("replacement", ""))}</td>'
            f'<td>{esc(r.get("approved_by") or "offen")}</td></tr>' for r in cov.get("replaced", []))
        rows += "".join(
            f'<tr><td>{esc(names.get(c, {}).get("name", c))}</td><td>gestrichen</td><td>–</td>'
            f'<td>–</td></tr>' for c in cov.get("dropped_control_ids", []))
        out.append('<details open><summary>Veränderte Kontrollen</summary>'
                   '<table><tr><th>Kontrolle</th><th>Wie</th><th>Ersatz</th><th>Freigabe</th></tr>'
                   f'{rows}</table></details>')

    metrics = wl.index_by_id(graph["metrics"])
    if bp.get("projected_metrics"):
        rows = []
        for m in bp["projected_metrics"]:
            met = metrics.get(m["metric_id"], {})
            base, basis = wl.metric_value(met, "baseline") if met else (None, None)
            rows.append(f'<tr><td>{esc(met.get("name", m["metric_id"]))}</td>'
                        f'<td class="n">{fmt(base)} <span class="basis">({esc(BASIS_SHORT.get(basis, "?"))})</span></td>'
                        f'<td class="n">{fmt(m.get("value"))} <span class="basis">({esc(BASIS_SHORT.get(m.get("basis"), "?"))})</span></td>'
                        f'<td>{esc(met.get("unit") or "")}</td></tr>')
        out.append('<details open><summary>Zugesagte Kennzahlen</summary>'
                   '<table><tr><th>Kennzahl</th><th class="n">Ausgangswert</th>'
                   f'<th class="n">Zielwert</th><th>Einheit</th></tr>{"".join(rows)}</table>'
                   '<p class="note">gesch. = geschätzt, best. = vom Fachexperten bestätigt, '
                   'gem. = im Pilot gemessen.</p></details>')

    facts = []
    for st in bp.get("steps", []):
        if st.get("rationale"):
            met = metrics.get(st.get("metric_id"), {}).get("name")
            facts.append(f'<li><b>{esc(st["name"])}</b> ({esc(OPERATOR_LABEL.get(st["operator"], ""))}): '
                         f'{esc(st["rationale"])}'
                         + (f' · Kennzahl: {esc(met)}' if met else "")
                         + (f' · Annahme: {esc(st["assumption"])}' if st.get("assumption") else "") + '</li>')
    if facts:
        out.append(f'<details><summary>Begründungen und Annahmen je Änderung ({len(facts)})</summary>'
                   f'<ul>{"".join(facts)}</ul></details>')
    if bp.get("open_assumptions"):
        out.append('<div class="warnbox"><b>Offene Annahmen:</b><ul>'
                   + "".join(f'<li>{esc(a)}</li>' for a in bp["open_assumptions"]) + '</ul></div>')
    if bp.get("risks"):
        out.append('<details><summary>Risiken</summary><ul>'
                   + "".join(f'<li>{esc(r)}</li>' for r in bp["risks"]) + '</ul></details>')
    if bp.get("proposed_agents"):
        out.append('<p class="note">Noch anzulegende Agenten: '
                   + esc(", ".join(bp["proposed_agents"])) + '</p>')
    return "".join(out)


def process_card(graph: dict[str, Any], pr: dict[str, Any], names: dict, n: int) -> str:
    ist = wl.process_totals(graph, pr["id"])
    ist_steps = wl.steps_of(graph, pr["id"])
    bps = sorted([b for b in graph["blueprints"] if b["process_id"] == pr["id"]],
                 key=lambda b: SCENARIO_ORDER.index(b["scenario"]) if b["scenario"] in SCENARIO_ORDER else 9)
    v = pr.get("value") or {}
    band = v.get("band")
    head = [f'<div class="head"><div><h3>{esc(pr["name"])}</h3>'
            f'<div class="meta">Auslöser: {esc(pr.get("trigger") or "–")} · '
            f'Ergebnis: {esc(names.get(pr.get("outcome_id"), {}).get("name", "–"))} · '
            f'Owner: {esc(names.get(pr.get("owner_role_id"), {}).get("name", "–"))}</div></div>']
    tags = []
    if band:
        tags.append(f'<span class="band" style="background:{BAND_COLOR.get(band, "#666")}">'
                    f'{esc(BAND_LABEL.get(band, band))} · Wert {fmt(v.get("score"))}</span>')
    if pr.get("regulated"):
        tags.append('<span class="tag">reguliert</span>')
    for dc in pr.get("data_classes", []):
        tags.append(f'<span class="tag">{esc(dc)}</span>')
    if pr.get("volume_per_year"):
        tags.append(f'<span class="tag">{int(pr["volume_per_year"])} Fälle/Jahr</span>')
    head.append("<div>" + "".join(tags) + "</div></div>")

    gap = wl.lead_time_gap(graph, pr["id"])
    if gap:
        head.append(f'<div class="warnbox">Das Prozessmodell erklärt {fmt(gap["modelled_hours"])} h '
                    f'von {fmt(gap["measured_hours"])} h gemessener Durchlaufzeit '
                    f'({gap["deviation_pct"]:+g} %). Es fehlen vermutlich Schritte oder Liegezeiten; '
                    'die Deltas unten rechnen auf der modellierten Grundmenge.</div>')
    if v and not (v.get("sensitivity") or {}).get("band_stable", True):
        flips = ", ".join(sorted({f["factor"] for f in v["sensitivity"]["flips"]}))
        head.append(f'<div class="warnbox">Prioritätsband kippt schon bei ±1 in: {esc(flips)}. '
                    'Die Einordnung ist eine Richtung, keine Rangfolge.</div>')

    # Vergleichstabelle Ist gegen alle Szenarien
    cmp_rows = []
    for key, label, nd in FLOW_METRICS:
        cells = "".join(_delta_cell((b.get("delta") or {}).get(key), nd) for b in bps)
        cmp_rows.append(f'<tr><td>{esc(label)}</td><td class="n">{fmt(ist.get(key), nd)}</td>{cells}</tr>')
    head_cells = "".join(f'<th class="n">{esc(SCENARIO_LABEL.get(b["scenario"], b["scenario"]))}</th>'
                         for b in bps)
    table = ('<table><tr><th>Kennzahl</th><th class="n">Ist</th>' + head_cells + "</tr>"
             + "".join(cmp_rows) + "</table>") if bps else ""

    # Umschaltbare Tafeln: Ist plus je Szenario eine
    tid = f"pr{n}"
    inputs, labels, panes = [], [], []
    options = [("Ist", flow_html(graph, ist_steps, names,
                                 removed=set().union(*[set(b.get("removed_step_ids", [])) for b in bps])
                                 if bps else set()))]
    for b in bps:
        options.append((SCENARIO_LABEL.get(b["scenario"], b["scenario"]), scenario_pane(graph, b, names)))
    for i, (label, body) in enumerate(options):
        checked = " checked" if i == 0 else ""
        inputs.append(f'<input type="radio" name="{tid}" id="{tid}-{i}"{checked}>')
        labels.append(f'<label for="{tid}-{i}">{esc(label)}</label>')
        panes.append(f'<div class="pane">{body}</div>')
    tabs = (f'<div class="tabs">{"".join(inputs)}<div class="tabbar">{"".join(labels)}</div>'
            f'<div class="panes">{"".join(panes)}</div></div>')

    extra = ""
    if not bps:
        extra = ('<p class="note">Noch kein Szenario entworfen. Skill process-redesigner: '
                 'export_process_candidates.py, dann drei Szenarien, dann build_blueprints.py.</p>')
    return (f'<div class="card" id="process-{esc(pr["id"])}">' + "".join(head)
            + table + tabs + extra + "</div>")


def processes_html(graph: dict[str, Any], names: dict) -> str:
    procs = sorted(graph["processes"],
                   key=lambda p: (-(p.get("value", {}) or {}).get("score", 0), p["name"]))
    return '<div class="cards">' + "".join(
        process_card(graph, pr, names, i) for i, pr in enumerate(procs)) + "</div>"


def experiments_html(graph: dict[str, Any], names: dict) -> str:
    xs = sorted(graph["experiments"], key=lambda x: x["id"])
    if not xs:
        return ('<p>Noch kein Pilot geplant. Ein Redesign ohne Messplan bleibt eine Meinung: '
                'process-redesigner/scripts/make_experiments.py erzeugt aus jedem geprüften '
                'Blueprint eine Karte mit Hypothese, Guardrails und Stoppregeln.</p>')
    metrics = wl.index_by_id(graph["metrics"])
    out = []
    for x in xs:
        guard = "".join(
            f'<li>{esc(metrics.get(g["metric_id"], {}).get("name", g["metric_id"]))}: '
            f'{"höchstens" if g.get("direction") == "max" else "mindestens"} {fmt(g.get("limit"))}</li>'
            for g in x.get("guardrails", []))
        stops = "".join(f'<li>{esc(r)}</li>' for r in x.get("stop_rules", []))
        res = ""
        if x.get("results"):
            res = ('<details open><summary>Gemessen</summary><ul>' + "".join(
                f'<li>{esc(metrics.get(r["metric_id"], {}).get("name", r["metric_id"]))}: '
                f'{fmt(r.get("value"))} ({esc(r.get("as_of") or "ohne Datum")})</li>'
                for r in x["results"]) + '</ul></details>')
        primary = metrics.get(x.get("primary_metric_id"), {})
        out.append(
            f'<div class="card"><div class="head"><div><h3>{esc(x["name"])}</h3>'
            f'<div class="meta">{esc(DESIGN_LABEL.get(x.get("design"), x.get("design")))} · '
            f'{x.get("duration_days")} Tage · rund {x.get("sample_size")} Fälle · '
            f'Status {esc(x.get("status"))} · Owner {esc(names.get(x.get("owner_role_id"), {}).get("name", "–"))}'
            f'</div></div></div>'
            f'<p><b>Hypothese:</b> {esc(x.get("hypothesis") or "–")}</p>'
            f'<p class="meta">{esc(x.get("design_rationale") or "")}</p>'
            f'<div class="cols"><div class="col"><h4>Primärmetrik</h4><ul><li>'
            f'{esc(primary.get("name", "–"))}: Ziel {fmt(x.get("target_value"))} '
            f'{esc(primary.get("unit") or "")}</li></ul></div>'
            f'<div class="col"><h4>Guardrails</h4><ul>{guard or "<li>keine</li>"}</ul></div>'
            f'<div class="col"><h4>Abbruch und Rückfall</h4><ul>{stops}'
            f'<li>Rollback: {esc(x.get("rollback") or "–")}</li></ul></div></div>{res}</div>')
    return '<div class="cards">' + "".join(out) + "</div>"


def governance_html(graph: dict[str, Any], names: dict) -> str:
    """Woher die Zahlen kommen und wer wofür geradesteht."""
    metrics = graph["metrics"]
    prov = graph["provenance"]
    by_target = {(p["entity_type"], p["entity_id"], p["field"]): p for p in prov}
    rows = []
    for m in sorted(metrics, key=lambda m: m["id"]):
        val, basis = wl.metric_value(m, "baseline")
        obs, _ = wl.metric_value(m, "observed")
        pv = by_target.get(("metrics", m["id"], "observed")) or by_target.get(("metrics", m["id"], "baseline"))
        rows.append(
            f'<tr><td>{esc(m["name"])}</td><td>{esc(names.get(m.get("process_id"), {}).get("name", "–"))}</td>'
            f'<td class="n">{fmt(val)} {esc(m.get("unit") or "")}</td>'
            f'<td>{esc(BASIS_LABEL.get(basis, "–"))}</td>'
            f'<td class="n">{fmt(obs) if obs is not None else "–"}</td>'
            f'<td>{esc(pv.get("source_ref") if pv else "keine Provenienz")}</td>'
            f'<td>{esc(pv.get("reviewer") or pv.get("author") or "–") if pv else "–"}</td></tr>')
    metric_table = ('<table><tr><th>Kennzahl</th><th>Prozess</th><th class="n">Ausgangswert (Ist)</th>'
                    '<th>Belastbarkeit</th><th class="n">Im Pilot gemessen</th><th>Quelle</th>'
                    '<th>Geprüft von</th></tr>' + "".join(rows) + "</table>") \
                   if rows else "<p>Keine Kennzahlen erfasst.</p>"

    gates = []
    for st in sorted(graph["process_steps"], key=lambda s: s["id"]):
        dec = st.get("decision") or {}
        if not dec.get("scope") or dec["scope"] == "recommend":
            continue
        gates.append(
            f'<tr><td>{esc(names.get(st.get("process_id"), {}).get("name", "–"))}</td>'
            f'<td>{esc(st["name"])}</td>'
            f'<td>{esc(EXECUTOR_LABEL.get((st.get("executor") or {}).get("type"), "–"))}</td>'
            f'<td>{esc(dec["scope"])}</td>'
            f'<td>{esc(names.get(dec.get("accountable_role_id"), {}).get("name", "–"))}</td>'
            f'<td>{esc(dec.get("escalation") or "–")}</td>'
            f'<td>{esc(st["human_gate"]["when"]) if st.get("human_gate") else "–"}</td></tr>')
    gate_table = ('<table><tr><th>Prozess</th><th>Schritt</th><th>Wer führt aus</th>'
                  '<th>Reichweite</th><th>Verantwortlich</th><th>Eskalation</th><th>Human Gate</th></tr>'
                  + "".join(gates) + "</table>") if gates else \
                 "<p>Keine Schritte mit ausführender Entscheidungsreichweite.</p>"

    dec_rows = "".join(
        f'<tr><td>{esc(d.get("date"))}</td><td>{esc(d.get("subject_type"))}</td>'
        f'<td>{esc(d.get("subject_name") or names.get(d.get("subject_id"), {}).get("name", d.get("subject_id")))}</td>'
        f'<td>{esc(d.get("decision"))}</td><td>{esc(d.get("decided_by"))}</td>'
        f'<td>{esc(d.get("rationale") or "–")}</td></tr>'
        for d in sorted(graph["decisions"], key=lambda d: (d.get("date", ""), d["id"])))
    dec_table = ('<table><tr><th>Datum</th><th>Gegenstand</th><th>Name</th><th>Entscheidung</th>'
                 '<th>Von</th><th>Begründung</th></tr>' + dec_rows + "</table>") if dec_rows else \
                "<p>Noch keine Freigabe im Entscheidungslog (30_review/decisions.csv).</p>"

    return (f'<h3>Herkunft der Zahlen</h3>{metric_table}'
            f'<h3>Automatisierte Entscheidungen und ihre Verantwortung</h3>{gate_table}'
            f'<h3>Entscheidungslog</h3>{dec_table}')



METHOD_PROCESS = (
    "<p><b>Prozessebene.</b> Die Ist-Kennzahlen eines Prozesses sind Summen über seine "
    "Schritte: Bearbeitungszeit und Wartezeit werden addiert, Übergaben aus den Kanten "
    "gezählt, Human Touchpoints aus ausführender Rolle und Human Gates. Als Übergabe zählt "
    "ein Wechsel des Ausführenden, bei dem mindestens eine Seite ein Mensch ist — ein "
    "Postkorb kostet Stunden, zwei Agenten im selben System reichen in Millisekunden weiter. "
    "Ist und Soll zählen nach derselben Regel; Medienbrüche (E-Mail, Telefon, Papier) stehen "
    "getrennt als Ist-Befund, weil ein Soll-Entwurf keine Übergabemedien modelliert. "
    "Bewusst keine "
    "Simulation — ohne Prozess-Mining-Daten wäre jede Verteilungsannahme Scheingenauigkeit. "
    "Im Soll-Szenario wird nur dort nicht addiert, wo Schritte ausdrücklich einer gemeinsamen "
    "Parallelgruppe zugeordnet sind; dann zählt für die Durchlaufzeit der längste von ihnen, "
    "die Arbeitsminuten bleiben die Summe. Die sechs Redesign-Operatoren (eliminieren, "
    "vereinfachen, zusammenführen, parallelisieren, automatisieren, Human Gate erhalten) "
    "folgen der ESIA-Schule der Prozessneugestaltung, erweitert um Parallelisierung und den "
    "ausdrücklichen Kontrollpunkt. Die Prozesspriorisierung ist eine gewichtete Rubrik aus "
    "Nutzen, Machbarkeit und Umkehrbarkeit; die Gewichte stehen versioniert in "
    "assets/value-weights.json. Zu jedem Prozess wird geprüft, ob sein Prioritätsband bei "
    "einer Abweichung von ±1 in einem einzelnen Faktor kippt — wenn ja, ist die Einordnung "
    "eine Richtung und keine Rangfolge.</p>"
)


def build_html(graph: dict[str, Any], data: dict[str, Any], k: dict[str, Any], title: str, stamp: str) -> str:
    meta = graph["meta"]
    clusters = sorted({r["cluster"] for r in data["roles"]})
    filt = "".join(f'<label><input type="checkbox" data-type="{t}" checked> <i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{TYPE_COLOR[t]}"></i> {TYPE_LABEL[t]}</label>' for t in TYPE_ORDER if k["types"][t])
    sel = '<select id="f-cluster"><option value="">Alle Cluster</option>' + "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in clusters) + "</select>"
    roles_js = {r["id"]: {"name": r["name"], "cluster": r["cluster"], "typeLabel": TYPE_LABEL[r["type"]],
                          "score": fmt(r["analysis"].get("disruption_score")), "ap": fmt(r["analysis"].get("automation_potential")),
                          "hj": fmt(r["analysis"].get("human_judgment")), "pb": fmt(r["analysis"].get("productivity_boost"))} for r in data["roles"]}
    cards = "".join(role_card(r, data["agents_idx"]) for r in data["roles"])
    stamp_html = f" · Stand {esc(stamp)}" if stamp else ""

    # Prozessansicht nur bauen, wenn es Prozesse gibt. Ein Projekt nach Schema 1.0
    # bekommt damit weiterhin genau das Dashboard, das es vorher hatte.
    names = name_index(graph)
    has_processes = bool(graph.get("processes"))
    if has_processes:
        pk = process_kpis(graph)
        nav_items = [("#prozesse", "Prozesse"), ("#szenarien", "Szenarien"),
                     ("#piloten", "Piloten"), ("#ueberblick", "Rollenüberblick"),
                     ("#matrix", "Rollenmatrix"), ("#rollen", "Rollenanalyse"),
                     ("#agenten", "Agentenbibliothek"), ("#governance", "Governance"),
                     ("#rollout", "Rollout"), ("#tabelle", "Tabelle"), ("#methodik", "Methodik")]
        process_sections = f"""
<section id="prozesse"><h2>Prozessportfolio</h2><p>Die Prozesse des Bereichs, sortiert nach ihrem Wert (mehrdimensional bewertet, nicht nach gebundener Arbeitszeit). Die Kennzahlen oben fassen je Prozess das jeweils wirksamste entworfene Szenario zusammen.</p>
{process_tiles(pk)}
<p class="meta" style="margin-top:10px">{pk['scored']} von {pk['processes']} Prozessen bewertet · Bänder: {" · ".join(f"{BAND_LABEL[b]} {n}" for b, n in pk['bands'].items() if n)} · Deltas stammen aus den Soll-Schritten der Blueprints, nicht aus Zusagen.</p></section>

<section id="szenarien"><h2>Ist und Soll je Prozess</h2><p>Je Prozess: der heutige Ablauf und die entworfenen Szenarien. Die Reiter schalten zwischen Ist und Szenario um; die Tabelle darüber zeigt alle Szenarien nebeneinander. Positive Zahlen sind immer Verbesserungen, auch bei Kennzahlen, bei denen weniger besser ist.</p>
{processes_html(graph, names)}</section>

<section id="piloten"><h2>Piloten und Messplan</h2><p>Aus einem geprüften Blueprint wird erst dann eine Entscheidungsgrundlage, wenn klar ist, was gemessen wird, welche Guardrails gelten und wann abgebrochen wird.</p>
{experiments_html(graph, names)}</section>
"""
        governance_section = f"""
<section id="governance"><h2>Governance und Herkunft der Zahlen</h2><p>Welche Zahl geschätzt, welche bestätigt und welche gemessen ist; wer eine automatisierte Entscheidung verantwortet; welche Freigaben im Log stehen.</p>
{governance_html(graph, names)}</section>
"""
        roles_intro = ("Folgenansicht des Prozessredesigns: Welche Rollen die entworfenen Prozesse "
                       "berühren. Sortiert nach Disruptionsscore. Je Rolle: Zeitverteilung, "
                       "Transformationslogik, nächster Schritt, Kennwerte, Skills und Aufgaben.")
    else:
        pk = None
        nav_items = [("#ueberblick", "Überblick"), ("#matrix", "Rollenmatrix"),
                     ("#rollen", "Rollenanalyse"), ("#agenten", "Agentenbibliothek"),
                     ("#rollout", "Rollout"), ("#tabelle", "Tabelle"), ("#methodik", "Methodik")]
        process_sections = ""
        governance_section = ""
        roles_intro = ("Sortiert nach Disruptionsscore. Je Rolle: Zeitverteilung, "
                       "Transformationslogik, nächster Schritt, Kennwerte, Skills und Aufgaben.")
    nav_html = "".join(f'<a href="{h}">{esc(t)}</a>' for h, t in nav_items)
    method_extra = METHOD_PROCESS if has_processes else ""
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{themed_css()}</style></head>
<body>
<header><h1>{esc(title)}</h1><div class="sub"><b>{esc(meta.get('organization') or '')}</b> · {esc(meta.get('scope') or '')} · Work-Graph Version {meta.get('version')} ({esc(meta.get('stage'))}){stamp_html}</div></header>
<nav>{nav_html}</nav>
<main>
{process_sections}
<section id="ueberblick"><h2>{'Rollenüberblick' if has_processes else 'Überblick'}</h2><p>Kennzahlen des analysierten Bereichs. Zeitanteile sind headcount-gewichtet, wo Headcounts bekannt sind ({k['headcount_known']} von {k['roles']} Rollen).</p>
{tiles_html(k)}<div style="height:14px"></div>{dist_html(k)}
<p class="meta" style="margin-top:10px">Datenqualität: {fmt(k['inferred_pct'], 0)} % der Aufgaben aus dem Berufsbild ergänzt (nicht aus Quelle) · {k['reviewed_roles']} von {k['roles']} Rollen durch Experten geprüft · Belastbarkeit: {k['evidence']['high']} belastbar, {k['evidence']['medium']} teilweise geprüft, {k['evidence']['low']} ungeprüft · Einstufung grenznah bei {k['borderline']}, wackelig bei {k['fragile']} Rollen. Unterschiede im Expositionswert unter 0,5 sind Rauschen; belastbar sind die Quadranten, nicht die Rangfolge innerhalb.</p></section>

<section id="matrix"><h2>Rollenmatrix</h2><p>Jede Rolle als Punkt: Automatisierungspotenzial gegen benötigtes menschliches Urteil. Punktgröße folgt dem Headcount. Klick springt zur Rollenkarte.</p>
<div class="filters">{filt}{sel}</div>
<div class="nojs" id="nojs">Die Filter, Tooltips und Sprungmarken brauchen JavaScript. In Datei-Vorschauen (Chat, Cloud-Speicher, E-Mail) wird es meist nicht ausgeführt: Datei herunterladen und direkt im Browser öffnen.</div>
<div class="matrix" id="matrix-box">{matrix_svg(data['roles'])}<div class="tip" id="tip"></div></div>
<div class="legend">{"".join(f'<span><i style="background:{TYPE_COLOR[t]}"></i>{TYPE_LABEL[t]}</span>' for t in TYPE_ORDER if k["types"][t])}</div></section>

<section id="rollen"><h2>Rollenanalyse</h2><p>{esc(roles_intro)}</p>
<div class="cards">{cards}</div></section>

<section id="agenten"><h2>Agentenbibliothek</h2><p>Wiederverwendbare Agenten. „Wert #" ordnet nach FTE-Äquivalent (Σ Abdeckung × Headcount), sonst nach Abdeckungspunkten; „Bau #" ist die empfohlene Reihenfolge (kurzfristig und einfach zuerst). Abdeckung = Zeitanteil × Automatisierungspotenzial der übernommenen Aufgaben.</p>
{agents_html(data['agents'])}</section>
{governance_section}
<section id="rollout"><h2>Rollout-Plan</h2><p>Abgeleitet aus Datenlage und Fehlerfolgen der Aufgaben: Was heute an Daten scheitert, ist mittelfristig.</p>
{rollout_html(data['roles'], data['agents'])}</section>

<section id="tabelle"><h2>Tabellenansicht</h2><p>Alle Rollenwerte als Tabelle (barrierefreie Alternative zur Matrix; Filter oben gelten auch hier).</p>
{table_html(data['roles'])}</section>

<section id="methodik"><h2>Methodik</h2>
<p>Aufgaben wurden nach sechs Kriterien (0–10) bewertet: Automatisierbarkeit durch KI/Software, durch Robotik, benötigtes menschliches Urteil, Produktivitätshebel, Datenlage, Fehlerfolgen. Ausführungsmodus: <em>an Agent delegiert</em> bei Potenzial ≥ 7, Urteil ≤ 3 und Fehlerfolge ≤ 5 (reguliert ≤ 3); <em>KI-unterstützt</em> bei Potenzial ≥ 4 oder Hebel ≥ 5; sonst <em>manuell</em>. Rollenwerte sind zeitanteilgewichtete Mittel. Disruptionsscore = 0,5·Potenzial + 0,3·Hebel + 0,2·(10 − Urteil). Typen: eliminiert (≥ 60 % delegierbar, Urteil ≤ 3), transformiert (≥ 30 % delegierbar oder Potenzial ≥ 6 bei Urteil ≤ 5), augmentiert (≥ 40 % automatisierbar oder Hebel ≥ 5), entstehend (neue Rolle), stabil. HAS = Human Agency Scale (H1 Agent allein … H5 Mensch unverzichtbar) nach Stanford WORKBank. Bewertungen sind KI-generiert und durch Expertenkorrekturen (Overrides) überschreibbar; der Status je Rolle zeigt den Prüfstand.</p>{method_extra}</section>
</main>
<footer>Erzeugt mit der Work-Transformation-Suite (work-graph-builder → task-scorer → agent-mapper → process-redesigner → transformation-dashboard) aus {esc(wl.LATEST_GRAPH)} Version {meta.get('version')}. Schema {esc(meta.get('schema_version'))}.</footer>
<script>window.__ROLES__={json.dumps(roles_js, ensure_ascii=False, sort_keys=True)};{JS}</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# CSV und Bericht
# ---------------------------------------------------------------------------

def export_csv(project: Path, graph: dict[str, Any], data: dict[str, Any], version: int) -> list[Path]:
    out = project / wl.DIR_OUTPUT
    paths = []
    rrows = []
    for r in data["roles"]:
        an = r["analysis"]
        rrows.append({"role_id": r["id"], "role": r["name"], "family": r["family"], "cluster": r["cluster"], "level": r["level"],
                      "headcount": r["headcount"], "archetype": r["archetype"], "regulated": r["regulated"], "status": r["status"],
                      "disruption_type": r["type"], "disruption_score": an.get("disruption_score"), "automation_potential": an.get("automation_potential"),
                      "human_judgment": an.get("human_judgment"), "productivity_boost": an.get("productivity_boost"), "data_readiness": an.get("data_readiness"),
                      "share_human_core": an.get("share_human_core"), "share_ai_assisted": an.get("share_ai_assisted"), "share_agent_delegated": an.get("share_agent_delegated"),
                      "horizon": an.get("horizon"), "readiness": an.get("readiness"), "evidence": an.get("evidence"), "stability": an.get("stability"), "flip_share": an.get("flip_share"), "next_action": an.get("next_action"),
                      "core_skills": "; ".join(an.get("retained_skills", [])), "declining_skills": "; ".join(an.get("declining_skills", []))})
    p = out / f"roles_v{version:03d}.csv"
    wl.write_csv(p, rrows, list(rrows[0].keys()) if rrows else ["role_id"])
    paths.append(p)

    roles_idx = {r["id"]: r for r in data["roles"]}
    trows = []
    for t in sorted(graph["tasks"], key=lambda t: (roles_idx[t["role_id"]]["name"], -t["share_of_time"], t["name"])):
        sc = t.get("scores") or {}
        trows.append({"task_id": t["id"], "role": roles_idx[t["role_id"]]["name"], "task": t["name"], "share_of_time": t["share_of_time"],
                      "frequency": t["frequency"], "nature": t["nature"], "confidence": t.get("confidence"), "status": t.get("status"),
                      "automation_ai": sc.get("automation_ai"), "automation_physical": sc.get("automation_physical"), "human_judgment": sc.get("human_judgment"),
                      "productivity_boost": sc.get("productivity_boost"), "data_readiness": sc.get("data_readiness"), "consequence_of_error": sc.get("consequence_of_error"),
                      "automation_potential": t.get("automation_potential"), "mode": t.get("mode"), "has_level": t.get("has_level"), "horizon": t.get("horizon"),
                      "agents": "; ".join(data["agents_idx"][a]["name"] for a in t.get("agent_ids", []) if a in data["agents_idx"]), "rationale": sc.get("rationale")})
    p = out / f"tasks_v{version:03d}.csv"
    wl.write_csv(p, trows, list(trows[0].keys()) if trows else ["task_id"])
    paths.append(p)

    arows = []
    for a in data["agents"]:
        arows.append({"agent_id": a["id"], "priority_rank": a.get("priority_rank"), "sequence_rank": a.get("sequence_rank"), "agent": a["name"], "pattern": a.get("pattern"), "status": a.get("status"),
                      "specificity": a.get("specificity"), "sourcing": a.get("sourcing"), "horizon": a.get("horizon"), "complexity": a.get("complexity"),
                      "roles_covered_count": a.get("roles_covered_count"), "avg_coverage_pct": a.get("avg_coverage_pct"), "coverage_points": a.get("coverage_points"),
                      "fte_equivalent": a.get("fte_equivalent"), "tasks": len(a.get("task_ids", [])), "existing_system": a.get("existing_system"),
                      "capability": a.get("capability"), "oversight": a.get("oversight"), "prerequisites": "; ".join(a.get("prerequisites", []))})
    p = out / f"agents_v{version:03d}.csv"
    wl.write_csv(p, arows, list(arows[0].keys()) if arows else ["agent_id"])
    paths.append(p)

    if graph.get("processes"):
        names = name_index(graph)
        prows = []
        for pr in sorted(graph["processes"],
                         key=lambda x: (-(x.get("value", {}) or {}).get("score", 0), x["name"])):
            t = wl.process_totals(graph, pr["id"])
            v = pr.get("value") or {}
            prows.append({
                "process_id": pr["id"], "process": pr["name"],
                "rank": v.get("rank"), "value_score": v.get("score"), "band": v.get("band"),
                "band_stable": (v.get("sensitivity") or {}).get("band_stable"),
                "benefit": v.get("benefit"), "ease": v.get("ease"),
                "fte_equivalent": v.get("fte_equivalent"),
                "outcome": names.get(pr.get("outcome_id"), {}).get("name"),
                "owner_role": names.get(pr.get("owner_role_id"), {}).get("name"),
                "volume_per_year": pr.get("volume_per_year"), "regulated": pr.get("regulated"),
                "status": pr.get("status"),
                "steps": t["steps"], "human_touches": t["human_touches"], "handovers": t["handovers"],
                "handling_time_min": t["handling_time_min"], "wait_time_min": t["wait_time_min"],
                "lead_time_hours": t["lead_time_hours"], "rework_pct": t["rework_pct"],
                "scenarios": len({b["scenario"] for b in graph["blueprints"] if b["process_id"] == pr["id"]}),
            })
        p = out / f"processes_v{version:03d}.csv"
        wl.write_csv(p, prows, list(prows[0].keys()) if prows else ["process_id"])
        paths.append(p)

        brows = []
        for b in sorted(graph["blueprints"], key=lambda b: b["id"]):
            row = {"blueprint_id": b["id"], "process": names.get(b["process_id"], {}).get("name"),
                   "scenario": b["scenario"], "name": b["name"], "status": b.get("status"),
                   "fte_equivalent": b.get("fte_equivalent")}
            for key, _label, _nd in FLOW_METRICS:
                row[f"soll_{key}"] = b["soll_totals"].get(key)
                row[f"delta_{key}"] = (b["delta"].get(key) or {}).get("improvement")
            for op in wl.ENUM_OPERATOR:
                row[f"op_{op}"] = (b.get("operator_counts") or {}).get(op, 0)
            row["open_assumptions"] = len(b.get("open_assumptions", []))
            brows.append(row)
        if brows:
            p = out / f"blueprints_v{version:03d}.csv"
            wl.write_csv(p, brows, list(brows[0].keys()))
            paths.append(p)
    return paths


def report_md(graph: dict[str, Any], data: dict[str, Any], k: dict[str, Any], title: str) -> str:
    meta = graph["meta"]
    lines = [f"# {title}", "", f"{meta.get('organization', '')} · {meta.get('scope', '')} · Work-Graph Version {meta.get('version')}", "",
             "## Kennzahlen", "",
             f"{k['roles']} Rollen ({k['roles_scored']} bewertet), {k['tasks']} Aufgaben, {k['skills']} Skills, {k['agents']} Agenten. "
             f"Headcount bekannt für {k['headcount_known']} Rollen ({k['headcount']} Personen). "
             f"Durchschnittlicher Disruptionsscore {fmt(k['disruption'])}. Zeitverteilung: {pct(k['share_core'])} menschlicher Kern, "
             f"{pct(k['share_assisted'])} KI-unterstützt, {pct(k['share_delegated'])} delegierbar. "
             f"{fmt(k['inferred_pct'], 0)} % der Aufgaben aus dem Berufsbild ergänzt; {k['reviewed_roles']} Rollen expertengeprüft.", "",
             "Verteilung: " + ", ".join(f"{TYPE_LABEL[t]} {k['types'][t]}" for t in TYPE_ORDER if k["types"][t]) + ".", "",
             "## Rollen nach Disruptionsscore", "", "| Rolle | Cluster | MA | Typ | Score | Kern | Assist. | Deleg. | Horizont | Belastbarkeit | Stabilität | Nächster Schritt |", "|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|"]
    for r in data["roles"]:
        an = r["analysis"]
        lines.append(f"| {r['name']} | {r['cluster']} | {r['headcount'] if r['headcount'] is not None else '–'} | {TYPE_LABEL[r['type']]} | {fmt(an.get('disruption_score'))} | "
                     f"{pct(an.get('share_human_core'))} | {pct(an.get('share_ai_assisted'))} | {pct(an.get('share_agent_delegated'))} | {HORIZON_LABEL.get(an.get('horizon'), '–')} | {EVIDENCE_LABEL.get(an.get('evidence'), '–')} | {STABILITY_LABEL.get(an.get('stability'), '–').replace('Einstufung ', '')} | {an.get('next_action', '–')} |")
    lines += ["", "## Agenten nach Priorität", "", "| Wert # | Bau # | Agent | Muster | Sourcing | Horizont | Rollen | Ø Abdeckung | FTE-Äquiv. |", "|---:|---:|---|---|---|---|---:|---:|---:|"]
    for a in data["agents"]:
        fte = fmt(a.get("fte_equivalent")) if a.get("fte_equivalent") is not None else "–"
        lines.append(f"| {a.get('priority_rank', '–')} | {a.get('sequence_rank', '–')} | {a['name']} | {a.get('pattern')} | {SOURCING_LABEL.get(a.get('sourcing'), '–')} | {HORIZON_LABEL.get(a.get('horizon'), '–')} | "
                     f"{a.get('roles_covered_count', 0)} | {pct(a.get('avg_coverage_pct'))} | {fte} |")
    if graph.get("processes"):
        pk = process_kpis(graph)
        names = name_index(graph)
        lines += ["", "## Prozessportfolio", "",
                  f"{pk['processes']} Prozess{'e' if pk['processes'] != 1 else ''} mit "
                  f"{pk['steps']} Schritten, {pk['scenarios_complete']} davon mit allen "
                  "drei Szenarien. "
                  f"{pk['blueprints']} Blueprints ({pk['approved']} freigegeben), "
                  f"{pk['experiments']} Piloten geplant."
                  + (f" Durchschnittlicher Durchlaufzeitgewinn im jeweils besten Szenario: "
                     f"{fmt(pk['avg_lead_gain'], 0)} %." if pk["avg_lead_gain"] is not None else ""),
                  "",
                  "| # | Prozess | Band | Wert | Ist-Durchlauf | Bestes Szenario | Soll-Durchlauf | Human Touchpoints | Übergaben |",
                  "|---:|---|---|---:|---:|---|---:|---|---|"]
        for pr in sorted(graph["processes"],
                         key=lambda x: (-(x.get("value", {}) or {}).get("score", 0), x["name"])):
            t = wl.process_totals(graph, pr["id"])
            v = pr.get("value") or {}
            best = pk["best"].get(pr["id"])
            flag = "" if (v.get("sensitivity") or {}).get("band_stable", True) else " (kippelig)"
            if best:
                d = best["delta"]
                lines.append(f"| {v.get('rank', '–')} | {pr['name']} | {BAND_LABEL.get(v.get('band'), '–')}{flag} "
                             f"| {fmt(v.get('score'))} | {fmt(t['lead_time_hours'])} h "
                             f"| {SCENARIO_LABEL.get(best['scenario'], '–')} "
                             f"| {fmt(best['soll_totals']['lead_time_hours'])} h "
                             f"| {t['human_touches']} → {best['soll_totals']['human_touches']} "
                             f"| {t['handovers']} → {best['soll_totals']['handovers']} |")
            else:
                lines.append(f"| {v.get('rank', '–')} | {pr['name']} | {BAND_LABEL.get(v.get('band'), '–')}{flag} "
                             f"| {fmt(v.get('score'))} | {fmt(t['lead_time_hours'])} h | noch keins "
                             f"| – | {t['human_touches']} | {t['handovers']} |")
        # Drei Eimer, nicht zwei. Eine Kennzahl ganz ohne Ausgangswert ist weder geschätzt
        # noch belegt — sie als „bestätigt oder gemessen" zu zählen, würde genau die Aussage
        # umkehren, für die dieser Satz da ist.
        buckets = {"belegt": 0, "geschätzt": 0, "ohne Ausgangswert": 0}
        for m in graph["metrics"]:
            _value, basis = wl.metric_value(m, "baseline")
            if basis in ("observed", "expert_confirmed"):
                buckets["belegt"] += 1
            elif basis == "estimated":
                buckets["geschätzt"] += 1
            else:
                buckets["ohne Ausgangswert"] += 1
        total = len(graph["metrics"])
        satz = (f"Belastbarkeit der Kennzahlen: {buckets['belegt']} von {total} Ausgangswerten "
                f"sind bestätigt oder gemessen, {buckets['geschätzt']} geschätzt")
        if buckets["ohne Ausgangswert"]:
            satz += (f", {buckets['ohne Ausgangswert']} ohne Ausgangswert (für diese lässt sich "
                     "kein Delta belegen)")
        satz += ". Jede Delta-Zahl in diesem Bericht ist aus den Soll-Schritten der Blueprints "
        satz += "gerechnet, nicht zugesagt."
        lines += ["", satz, ""]

    lines += ["", "## Hinweise", "",
              "Bewertungen sind KI-generiert nach einer festen Rubrik und durch Expertenkorrekturen überschreibbar. "
              "Rollen mit Status `generated` wurden noch nicht geprüft. Die Schwellen der Klassifikation stehen in der Rubrik des task-scorer. "
              "Belastbarkeit fasst zusammen, ob Zeitanteile aus der Quelle stammen, ob Experten geprüft haben und ob der Headcount bekannt ist; "
              "Stabilität sagt, wie viele Einzeländerungen um ±1 an einer Aufgabenbewertung die Rollenwirkung kippen würden. "
              "Unterschiede im Expositionswert unter 0,5 sind Rauschen.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--stamp", default=None, help="Optionaler Datumstext für die Kopfzeile (bricht Byte-Identität)")
    ap.add_argument("--theme", default=None, help="Theme-Datei (JSON) mit Farben und Schriften; Standard assets/theme.json")
    args = ap.parse_args()
    theme_path = None
    if args.theme:
        theme_path = Path(args.theme)
        if not theme_path.is_absolute():
            theme_path = Path.cwd() / theme_path
        if not theme_path.exists():
            wl.fail(f"Theme-Datei nicht gefunden: {wl.relpath(theme_path)}")
    load_theme(theme_path)
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    version = int(graph["meta"].get("version", 0))
    # Projektstammdaten (Name, Organisation, Scope) kommen aus project.json; sie können sich
    # ändern, ohne dass der Graph eine neue Version bekommt, deshalb hier aktuell überlagern.
    pmeta = wl.load_project_meta(project)
    for src, dst in (("name", "project"), ("organization", "organization"), ("scope", "scope")):
        if pmeta.get(src):
            graph["meta"][dst] = pmeta[src]
    title = args.title or f"KI-Transformationsdashboard — {graph['meta'].get('scope') or graph['meta'].get('project') or 'Arbeitsgraph'}"
    data = prepare(graph)
    k = kpis(graph, data)
    out = project / wl.DIR_OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / f"dashboard_v{version:03d}.html"
    wl.write_text(html_path, build_html(graph, data, k, title, args.stamp or ""))
    csvs = export_csv(project, graph, data, version)
    rep = out / f"report_v{version:03d}.md"
    wl.write_text(rep, report_md(graph, data, k, title))
    print(f"Geschrieben: {wl.relpath(html_path)}")
    for p in csvs + [rep]:
        print(f"Geschrieben: {wl.relpath(p)}")
    print(f"Rollen={k['roles']} bewertet={k['roles_scored']} Agenten={k['agents']} | " + ", ".join(f"{TYPE_LABEL[t]}={k['types'][t]}" for t in TYPE_ORDER if k["types"][t]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
