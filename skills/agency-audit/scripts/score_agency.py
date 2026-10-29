#!/usr/bin/env python3
"""
score_agency.py — führt Beschäftigtensicht und Bewertung zusammen: Zone je Aufgabe, Agency-Lücke,
Reibung je Rolle. Schreibt eine neue Graph-Version (Stufe „agency“) und eine Prüfliste.

Aufruf:
    python3 <skill>/scripts/score_agency.py --project ./mein-projekt

Eingaben: 20_graph/agency.json (import_audit.py) und der bewertete Graph (task-scorer).

Je Aufgabe (`tasks[].agency`):
- **Zone** aus Wunsch (1–5, Befragung) und Automatisierungspotenzial (0–10, Bewertung):
  Freigabe (gewünscht und machbar), Vorsicht (machbar, nicht gewünscht), Entwicklung (gewünscht,
  noch nicht machbar), Nachrang. Schwellen: ZONE_DESIRE_MIN und ZONE_CAPABILITY_MIN in workgraph_lib.
- **Agency-Lücke** = gewünschte HAS-Stufe minus technisch nötige HAS-Stufe. Positiv: Die Menschen
  wollen mehr beteiligt sein, als die Technik verlangt. Negativ: Sie trauen der Technik mehr zu,
  als die Bewertung hergibt.

Je Rolle (`roles[].agency`), zeitanteilgewichtet über die befragten Aufgaben:
- Wunsch, dominante gewünschte und nötige HAS-Stufe, Zonenanteile, mittlere Lücke.
- **Reibung**: Jensen-Shannon-Distanz zwischen gewünschter und nötiger HAS-Verteilung
  (0 = deckungsgleich, 1 = völlig verschieden); gering, mittel, hoch nach FRICTION_*.
- **Abdeckung**: Teilnehmende im Verhältnis zum Headcount, wo er bekannt ist.

Die Befragung ändert keine Bewertung. Sie legt eine zweite Sicht daneben.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
from validate_graph import validate  # noqa: E402

GAP_NOTE_MIN = 2  # ab dieser Lücke (in Stufen) steht eine Aufgabe in der Prüfliste


def dominant(dist: list[float]) -> int | None:
    if not sum(dist):
        return None
    best = max(dist)
    return max(i + 1 for i, v in enumerate(dist) if v == best)


def task_block(t: dict, agg: dict) -> dict:
    block = dict(agg)
    zone = wl.agency_zone(agg.get("desire"), t.get("automation_potential"))
    if zone:
        block["zone"] = zone
    if t.get("has_level") is not None:
        block["has_gap"] = int(agg["has_desired"]) - int(t["has_level"])
    return block


def role_block(role: dict, tasks: list[dict], respondents: int) -> dict | None:
    rated = [t for t in tasks if t.get("agency")]
    if not rated:
        return None
    w = [float(t.get("share_of_time") or 0) or 1.0 for t in rated]
    desire = [(t["agency"].get("desire"), wt) for t, wt in zip(rated, w) if t["agency"].get("desire") is not None]
    desired = wl.has_distribution([t["agency"]["has_desired"] for t in rated], w)
    with_level = [(t, wt) for t, wt in zip(rated, w) if t.get("has_level") is not None]
    required = wl.has_distribution([t["has_level"] for t, _ in with_level], [wt for _, wt in with_level])
    jsd = wl.jensen_shannon(desired, required)
    zones: dict[str, float] = {}
    for t, wt in zip(rated, w):
        z = t["agency"].get("zone")
        if z:
            zones[z] = zones.get(z, 0.0) + wt
    zsum = sum(zones.values())
    gaps = [(t["agency"]["has_gap"], wt) for t, wt in zip(rated, w) if t["agency"].get("has_gap") is not None]
    block = {
        "respondents": respondents,
        "tasks_rated": len(rated),
        "tasks_total": len(tasks),
        "share_rated_pct": wl.round1(100.0 * sum(float(t.get("share_of_time") or 0) for t in rated)
                                     / max(1.0, sum(float(t.get("share_of_time") or 0) for t in tasks))),
        "desire": wl.round1(sum(d * wt for d, wt in desire) / sum(wt for _, wt in desire)) if desire else None,
        "has_desired_dominant": dominant(desired),
        "has_required_dominant": dominant(required),
        "has_desired_dist": [round(x, 3) for x in desired],
        "has_required_dist": [round(x, 3) for x in required],
        "jsd": jsd,
        "friction": wl.friction_level(jsd),
        "zone_shares": {z: wl.round1(100.0 * v / zsum) for z, v in sorted(zones.items())} if zsum else {},
        "gap_mean": wl.round1(sum(g * wt for g, wt in gaps) / sum(wt for _, wt in gaps)) if gaps else None,
    }
    hc = wl.role_headcount(role)
    if hc:
        block["coverage_pct"] = wl.round1(100.0 * respondents / float(hc))
    return {k: v for k, v in block.items() if v is not None}


def review(graph: dict, meta: dict, version: int) -> str:
    roles = wl.index_by_id(graph["roles"])
    tasks = [t for t in graph["tasks"] if t.get("agency")]
    lines = [f"# Beschäftigtensicht — Prüfliste v{version:03d}", "",
             f"Grundlage: {meta.get('respondents', 0)} Teilnehmende, {meta.get('answers', 0)} Antworten zu bekannten Aufgaben, "
             f"{meta.get('tasks_published', 0)} Aufgaben ausgewertet, {meta.get('tasks_suppressed', 0)} unter der Mindestgruppe "
             f"von {meta.get('min_group', wl.AUDIT_MIN_GROUP)} unterdrückt.", "",
             "Diese Liste ist ein Gesprächsanlass für Fachbereich, HR und Beschäftigtenvertretung. Sie bewertet keine "
             "Person und keine Leistung; sie zeigt, wo die Sicht der Beschäftigten von der Bewertung abweicht.", ""]
    de = wl.load_library_json("rechtsraeume", "DE.json") or {}
    topic = next((t for t in de.get("themen", []) if t.get("id") == "beschaeftigtenbefragung"), None)
    if topic:
        lines += [f"Rechtsrahmen: {topic['thema']} ({topic['fundstelle']}). {topic['pflicht']}", ""]
    lines += ["## Rollen", "", "| Rolle | Teilnehmende | Wunsch (1–5) | HAS gewünscht | HAS nötig | Reibung | Freigabe | Vorsicht | Entwicklung | Nachrang |",
              "|---|---:|---:|---|---|---|---:|---:|---:|---:|"]
    for r in sorted((r for r in graph["roles"] if r.get("agency")), key=lambda x: (-(x["agency"].get("jsd") or 0), x["name"])):
        a = r["agency"]
        z = a.get("zone_shares", {})
        lines.append(f"| {r['name']} | {a['respondents']} | {a.get('desire', '–')} | H{a.get('has_desired_dominant', '–')} "
                     f"| H{a.get('has_required_dominant', '–')} | {wl.FRICTION_LABEL.get(a.get('friction'), '–')} ({a.get('jsd', '–')}) | "
                     + " | ".join(f"{z.get(k, 0):.0f} %" for k in ("green", "red", "opportunity", "low")) + " |")
    if not any(r.get("agency") for r in graph["roles"]):
        lines.append("| – | – | – | – | – | – | – | – | – | – |")

    def table(items, head, row):
        out = [head[0], head[1]]
        out += [row(t) for t in items] or ["| Keine | " + " | ".join("–" for _ in range(head[0].count("|") - 2)) + " |"]
        return out

    red = sorted((t for t in tasks if t["agency"].get("zone") == "red"),
                 key=lambda t: (t["agency"].get("desire") or 0, -(t.get("automation_potential") or 0), t["name"]))
    lines += ["", "## Vorsichtszone: machbar, aber nicht gewünscht", "",
              "Nicht zuerst automatisieren. Erst klären, warum: Sorge um den Arbeitsplatz, Freude an der Aufgabe, "
              "fehlendes Vertrauen in die Qualität. Wer hier gegen die Beschäftigten automatisiert, verliert sie für den Rest.", ""]
    lines += table(red, ["| Aufgabe | Rolle | Wunsch | Potenzial | Sorge | Freude |", "|---|---|---:|---:|---:|---:|"],
                   lambda t: f"| {t['name']} | {roles[t['role_id']]['name']} | {t['agency'].get('desire', '–')} "
                             f"| {wl.round1(t.get('automation_potential') or 0)} | {t['agency'].get('job_worry', '–')} | {t['agency'].get('enjoyment', '–')} |")
    opp = sorted((t for t in tasks if t["agency"].get("zone") == "opportunity"),
                 key=lambda t: (-(t["agency"].get("desire") or 0), t["name"]))
    lines += ["", "## Entwicklungszone: gewünscht, aber noch nicht machbar", "",
              "Hier warten die Beschäftigten auf Hilfe, die es noch nicht gibt: Kandidaten für Werkzeugbedarf, Datenaufbereitung "
              "oder einen Use Case, den jemand bauen sollte.", ""]
    lines += table(opp, ["| Aufgabe | Rolle | Wunsch | Potenzial | Hauptgrund |", "|---|---|---:|---:|---|"],
                   lambda t: f"| {t['name']} | {roles[t['role_id']]['name']} | {t['agency'].get('desire', '–')} "
                             f"| {wl.round1(t.get('automation_potential') or 0)} | {top_reason(t['agency'].get('reasons_automation'), wl.AUDIT_REASONS_AUTOMATION)} |")
    more = sorted((t for t in tasks if (t["agency"].get("has_gap") or 0) >= GAP_NOTE_MIN),
                  key=lambda t: (-t["agency"]["has_gap"], t["name"]))
    less = sorted((t for t in tasks if (t["agency"].get("has_gap") or 0) <= -GAP_NOTE_MIN),
                  key=lambda t: (t["agency"]["has_gap"], t["name"]))
    lines += ["", "## Mehr Beteiligung gewünscht, als die Technik verlangt", "",
              f"Lücke von {GAP_NOTE_MIN} Stufen oder mehr. Einen Kontrollpunkt einplanen, auch wenn die Bewertung ihn nicht braucht; "
              "die Begründung der Beschäftigten steht in der letzten Spalte.", ""]
    lines += table(more, ["| Aufgabe | Rolle | HAS gewünscht | HAS nötig | Hauptgrund |", "|---|---|---|---|---|"],
                   lambda t: f"| {t['name']} | {roles[t['role_id']]['name']} | H{t['agency']['has_desired']} | H{t.get('has_level')} "
                             f"| {top_reason(t['agency'].get('reasons_collab'), wl.AUDIT_REASONS_COLLAB)} |")
    lines += ["", "## Weniger Beteiligung gewünscht, als die Bewertung für nötig hält", "",
              "Die Beschäftigten trauen der Technik hier mehr zu als die Bewertung. Prüfen, ob die Bewertung zu vorsichtig ist, "
              "oder ob Erwartungen an KI geklärt werden müssen, bevor jemand blind vertraut.", ""]
    lines += table(less, ["| Aufgabe | Rolle | HAS gewünscht | HAS nötig |", "|---|---|---|---|"],
                   lambda t: f"| {t['name']} | {roles[t['role_id']]['name']} | H{t['agency']['has_desired']} | H{t.get('has_level')} |")
    lines.append("")
    return "\n".join(lines)


def top_reason(counts: dict | None, labels: dict) -> str:
    if not counts:
        return "–"
    code = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return labels.get(code, code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    src = project / wl.DIR_GRAPH / "agency.json"
    if not src.exists():
        wl.fail(f"{wl.relpath(src)} fehlt, zuerst import_audit.py ausführen", code=3)
    data = wl.read_json(src)
    agg_tasks = data.get("tasks", {})
    agg_roles = data.get("roles", {})
    unscored = 0
    for t in graph["tasks"]:
        t.pop("agency", None)
        if t["id"] in agg_tasks:
            t["agency"] = task_block(t, agg_tasks[t["id"]])
            if "zone" not in t["agency"]:
                unscored += 1
    by_role: dict[str, list[dict]] = {}
    for t in graph["tasks"]:
        by_role.setdefault(t.get("role_id"), []).append(t)
    for r in graph["roles"]:
        r.pop("agency", None)
        if r["id"] in agg_roles:
            block = role_block(r, by_role.get(r["id"], []), int(agg_roles[r["id"]]["respondents"]))
            if block:
                r["agency"] = block
    errors, warnings = validate(graph)
    for w in warnings:
        if "agency" in w or "Beteiligung" in w:
            print(f"WARNUNG  {w}")
    if errors:
        for e in errors:
            print(f"FEHLER   {e}")
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "agency")
    rev = project / wl.DIR_REVIEW / f"beschaeftigtensicht_v{version:03d}.md"
    wl.write_text(rev, review(graph, data.get("meta", {}), version))
    rated = [t for t in graph["tasks"] if t.get("agency")]
    zones = {z: sum(1 for t in rated if t["agency"].get("zone") == z) for z in wl.ENUM_AGENCY_ZONE}
    print(f"{'Geschrieben' if changed else 'Unverändert'}: {wl.relpath(path)} (Version {version}) | Aufgaben mit Befragung="
          f"{len(rated)} " + " ".join(f"{wl.AGENCY_ZONE_SHORT[z]}={n}" for z, n in zones.items())
          + (f" ohne Bewertung={unscored}" if unscored else ""))
    print(f"Geschrieben: {wl.relpath(rev)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
