#!/usr/bin/env python3
"""
calibrate.py — vergleicht Expertenkorrekturen (Overrides auf scores.*) mit den
generierten Bewertungen aus scores.json und zeigt systematische Abweichungen je
Bewertungsfeld. Grundlage, um Anker in der Rubrik oder Schwellen im Scorer zu
kalibrieren, statt Bewertungen einzeln nachzuziehen.

Aufruf:
    python3 <skill>/scripts/calibrate.py --project ./mein-projekt

Ausgabe:
    30_review/calibration_vNNN.md mit
    - je Feld: Anzahl Korrekturen, mittlere Abweichung (Experte − generiert), Richtung
    - Liste der korrigierten Aufgaben mit alt/neu
    - Rollen, deren Rollenwirkung sich durch die Korrekturen geändert hat
    - Hinweis, ab wann eine Schwellen- oder Ankeranpassung sinnvoll ist

Deterministisch: reine Auswertung, keine Änderung am Graphen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

FIELDS = ["automation_ai", "automation_physical", "human_judgment", "productivity_boost", "data_readiness", "consequence_of_error"]
LABEL = {"automation_ai": "Maschinenanteil (KI/Software)", "automation_physical": "Robotikanteil", "human_judgment": "Urteilsbedarf",
         "productivity_boost": "Tandemgewinn", "data_readiness": "Datenreife", "consequence_of_error": "Fehlergewicht"}
MIN_N = 5
MIN_BIAS = 0.75


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    scores_path = project / wl.DIR_GRAPH / "scores.json"
    ov_path = project / wl.DIR_REVIEW / "overrides.csv"
    if not scores_path.exists() or not ov_path.exists():
        wl.fail("scores.json und overrides.csv werden benötigt")
    generated = wl.read_json(scores_path)
    rows = [r for r in wl.read_csv(ov_path) if (r.get("entity_type") or "").strip() == "task" and (r.get("field") or "").startswith("scores.")]
    tasks = wl.index_by_id(graph["tasks"])
    roles = wl.index_by_id(graph["roles"])

    deltas: dict[str, list[float]] = {f: [] for f in FIELDS}
    lines_detail = []
    for r in rows:
        tid = r["entity_id"].strip()
        f = r["field"].split(".", 1)[1]
        if tid not in tasks or tid not in generated or f not in FIELDS:
            continue
        try:
            new = float(str(r["value"]).replace(",", "."))
            old = float(generated[tid].get(f))
        except (TypeError, ValueError):
            continue
        deltas[f].append(new - old)
        lines_detail.append(f"| {roles[tasks[tid]['role_id']]['name']} | {tasks[tid]['name']} | {LABEL[f]} | {old:.0f} | {new:.0f} | {new - old:+.0f} | {r.get('reviewer', '')} |")

    version = graph["meta"].get("version", 0)
    out = [f"# Kalibrierungsbericht — Version {version}", "",
           f"{len(lines_detail)} Korrekturen an Bewertungsfeldern ausgewertet.", "",
           "## Systematik je Feld", "", "| Feld | Korrekturen | Ø Abweichung (Experte − generiert) | Lesart |", "|---|---:|---:|---|"]
    suggestions = []
    for f in FIELDS:
        d = deltas[f]
        if not d:
            continue
        mean = sum(d) / len(d)
        if len(d) >= MIN_N and abs(mean) >= MIN_BIAS:
            direction = "zu niedrig" if mean > 0 else "zu hoch"
            lesart = f"generierte Werte systematisch {direction}"
            suggestions.append(f"- {LABEL[f]}: {len(d)} Korrekturen, im Mittel {mean:+.1f}. Anker in der Rubrik für dieses Feld verschieben oder Kalibrierungsbeispiele ergänzen, statt weiter einzeln zu korrigieren.")
        elif len(d) >= MIN_N:
            lesart = "keine Systematik, Einzelfälle"
        else:
            lesart = "zu wenige Korrekturen für eine Aussage"
        out.append(f"| {LABEL[f]} | {len(d)} | {mean:+.2f} | {lesart} |")
    out += ["", "## Korrigierte Aufgaben", "", "| Rolle | Aufgabe | Feld | generiert | Experte | Δ | Reviewer |", "|---|---|---|---:|---:|---:|---|"] + (lines_detail or ["| – | – | – | – | – | – | – |"])

    # Rollenwirkung vor/nach: Vergleich generierte Scores (scores.json) vs. aktueller Graph
    changed = []
    try:
        from score_roles import aggregate_role  # noqa: E402
        import copy
        for r in graph["roles"]:
            rt = [t for t in graph["tasks"] if t["role_id"] == r["id"] and t.get("scores")]
            if not rt:
                continue
            base = copy.deepcopy(rt)
            touched = False
            for t in base:
                g = generated.get(t["id"])
                if g:
                    for f in FIELDS:
                        if f in g and float(g[f]) != float(t["scores"][f]):
                            t["scores"][f] = float(g[f])
                            touched = True
            if not touched:
                continue
            from score_roles import derive_task
            for t in base:
                derive_task(t, r)
            before = aggregate_role(r, base, {}).get("disruption_type")
            after = r.get("analysis", {}).get("disruption_type")
            if before != after:
                changed.append(f"- {r['name']}: {before} → {after}")
    except Exception as e:  # noqa: BLE001
        changed.append(f"- (Vergleich nicht möglich: {e})")
    out += ["", "## Rollen, deren Wirkung sich durch Korrekturen geändert hat", ""] + (changed or ["- keine"])
    out += ["", "## Empfehlung", ""] + (suggestions or [f"- Noch keine Systematik erkennbar (Schwelle: mindestens {MIN_N} Korrekturen je Feld mit mittlerer Abweichung ≥ {MIN_BIAS}). Weiter über Overrides korrigieren."])
    path = project / wl.DIR_REVIEW / f"calibration_v{version:03d}.md"
    wl.write_text(path, "\n".join(out) + "\n")
    print(f"Geschrieben: {wl.relpath(path)} | Korrekturen={len(lines_detail)} Felder mit Systematik={len(suggestions)} Rollen mit geänderter Wirkung={len([c for c in changed if not c.startswith('- keine')])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
