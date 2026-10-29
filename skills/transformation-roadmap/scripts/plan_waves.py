#!/usr/bin/env python3
"""
plan_waves.py — verteilt Agenten und Use Cases auf Wellen und schreibt das Fahrplan-Raster.

Aufruf:
    python3 <skill>/scripts/plan_waves.py --project ./mein-projekt [--config wave-config.json]

Eingaben:
    20_graph/work-graph_latest.json   (Agenten, Use Cases, Rollen, Prozesse)
    30_review/wellen.csv              (optional) Entscheidungen: eintrag;welle;begruendung;entschieden_von;datum

Ausgaben (NNN = Graph-Version):
    40_output/fahrplan_vNNN.md     das Raster lesbar
    40_output/fahrplan_vNNN.html   dasselbe als Tafel mit einer Spalte je Welle
    40_output/fahrplan_vNNN.csv    eine Zeile je Vorhaben
    40_output/roadmap_vNNN.json    alles maschinenlesbar

Das Raster ist ein Vorschlag. Eine Welle gilt erst als bestätigt, wenn jede Zuordnung in ihr
durch eine benannte Person in wellen.csv entschieden wurde oder das Vorhaben schon läuft.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_lib as rl  # noqa: E402
import roadmap_views as rv  # noqa: E402
import workgraph_lib as wl  # noqa: E402
from render_lib import OPEN, eur, html_page, md_to_html, num  # noqa: E402

BOARD_CSS = """
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:12px;margin:1rem 0 2rem}
.col{border:1px solid var(--line);border-radius:8px;padding:.8rem;background:var(--soft)}
.col h3{margin:0 0 .2rem;font-size:1rem}
.col .sum{color:var(--muted);font-size:.85rem;margin:0 0 .6rem}
.card{background:var(--bg);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:.5rem .6rem;margin:.5rem 0}
.card.proposed{border-left-color:var(--warn)}
.card b{display:block}
.card small{color:var(--muted)}
"""


def render_md(p: dict, graph: dict, version: int) -> str:
    meta = graph.get("meta", {})
    lines = [f"# Fahrplan-Raster: {meta.get('scope') or meta.get('project') or 'Projekt'}", "",
             f"Graph-Version {version}. Das Raster ist ein Vorschlag, bis eine benannte Person die Zuordnung "
             "bestätigt hat. Zeiträume nennt es nur, wenn jemand sie festgelegt hat.", "",
             "## Überblick", "", rv.wave_overview(p), "", rv.VALUE_NOTE, "",
             "## Vorhaben je Welle", "", rv.wave_detail(p), "",
             "## Ohne Vorhaben", "", rv.gaps_block(p), "",
             "## Noch offen", ""]
    pts = rv.open_points(p, graph)
    lines += [f"- {x}" for x in pts] if pts else ["Nichts."]
    lines += ["", "## Wie das Raster entsteht", "",
              "Jedes Vorhaben erhält einen Score aus fünf Größen (Wert, Reichweite, Umsetzbarkeit, Reifegrad, "
              "Prozessrang). Fehlt eine Größe, rechnet der Score ohne sie und nennt das in der Spalte „Basis des Scores“ der "
              "Anlage. Laufende Vorhaben (Pilot, im Betrieb) liegen in der ersten Welle; schwere Vorhaben beginnen "
              "nicht dort; Orchestratoren folgen den Agenten, die sie steuern. Die Gewichte stehen in "
              "`assets/wave-config.json` und lassen sich pro Projekt ändern.", ""]
    return "\n".join(lines)


def render_board(p: dict, graph: dict, version: int) -> str:
    meta = graph.get("meta", {})
    cols = []
    for w in p["waves"]:
        cards = []
        for key in w["items"]:
            c = p["by_key"][key]
            pl = p["placement"][key]
            cls = "card" + (" proposed" if pl["state"] == "proposed" else "")
            score = num(c["score"]) if c["score"] is not None else "nicht bewertet"
            cards.append(f'<div class="{cls}"><b>{html.escape(c["name"] or "")}</b>'
                         f'<small>{rv.KIND_LABEL[c["kind"]]}, {html.escape(rv.STATUS_LABEL.get(c["status"], c["status"] or "–"))}'
                         f' | Score {score} | {html.escape(eur(c["value_eur"]))}</small><br>'
                         f'<small>{html.escape(rv.state_of(p, key))}</small>'
                         + (f'<br><small>Beschäftigte: {html.escape(rv.zone_text(c))}</small>' if c.get("zone") else "")
                         + '</div>')
        r = w["reach"]
        sums = (f'{html.escape(rv.period_of(w))} | {len(r["roles"])} Rollen | '
                f'{num(r["fte_total"]) if r["roles"] else "–"} FTE | {html.escape(eur(r["value_eur"]))}')
        cols.append(f'<section class="col"><h3>{html.escape(w["label"])}</h3><p class="sum">{sums}</p>'
                    + ("".join(cards) or "<small>Keine Vorhaben</small>") + "</section>")
    head = (f"<h1>Fahrplan-Raster: {html.escape(meta.get('scope') or meta.get('project') or 'Projekt')}</h1>"
            f'<p class="meta">Graph-Version {version}. Gelber Rand: Vorschlag, noch nicht bestätigt. '
            f"{html.escape(rv.VALUE_NOTE)}</p>")
    pts = rv.open_points(p, graph)
    tail = ("<h2>Noch offen</h2><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in pts) + "</ul>") if pts else ""
    return html_page(f"Fahrplan-Raster {meta.get('scope') or ''}".strip(), head + '<div class="board">' + "".join(cols)
                     + "</div>" + tail, BOARD_CSS)


def csv_rows(p: dict) -> list[dict]:
    rows = []
    for w in p["waves"]:
        for key in w["items"]:
            c = p["by_key"][key]
            pl = p["placement"][key]
            rows.append({"welle": w["id"], "vorhaben": c["name"], "art": rv.KIND_LABEL[c["kind"]],
                         "status": c["status"] or "", "score": "" if c["score"] is None else c["score"],
                         "score_basis": c["score_basis"], "wert_eur": "" if c["value_eur"] is None else c["value_eur"],
                         "wertquelle": c["value_source"], "fte": "" if c["fte"] is None else c["fte"],
                         "zuordnung": rl.PLACEMENT_LABEL[pl["state"]], "begruendung": pl["reason"],
                         "entschieden_von": pl["decided_by"],
                         "beschaeftigte": rv.zone_text(c) if c.get("zone") else ""})
    return rows


CSV_FIELDS = ["welle", "vorhaben", "art", "status", "score", "score_basis", "wert_eur", "wertquelle", "fte",
              "zuordnung", "begruendung", "entschieden_von", "beschaeftigte"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--config", default=None, help="eigene Konfiguration (Standard: assets/wave-config.json)")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph.get("agents") and not graph.get("usecases"):
        print("Hinweis: keine Agenten und keine Use Cases im Graphen. Nächster Schritt: Skill agent-mapper "
              "(Agentenbibliothek) oder Use Cases importieren; das Raster hat sonst nichts zu verteilen.")
        return 3
    cfg = rl.load_config(Path(args.config) if args.config else None)
    probe = rl.build_candidates(graph, cfg)
    decisions, warnings = rl.read_decisions(project, probe, cfg)
    p = rl.plan(graph, cfg, decisions)
    version = int(graph.get("meta", {}).get("version", 0))
    out = project / wl.DIR_OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    wl.write_text(out / f"fahrplan_v{version:03d}.md", render_md(p, graph, version))
    wl.write_text(out / f"fahrplan_v{version:03d}.html", render_board(p, graph, version))
    wl.write_csv(out / f"fahrplan_v{version:03d}.csv", csv_rows(p), CSV_FIELDS)
    data = rl.plan_to_json(p, graph)
    data["warnings"] = warnings
    wl.write_json(out / f"roadmap_v{version:03d}.json", data)
    for w in warnings:
        print(f"HINWEIS  {w}")
    print(f"Geschrieben: fahrplan_v{version:03d}.md/.html/.csv, roadmap_v{version:03d}.json | "
          f"Vorhaben={len(p['candidates'])} Wellen={len(p['waves'])} "
          f"entschieden={sum(1 for w in p['waves'] if w['state'] == 'settled')} Lücken={len(p['gaps'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
