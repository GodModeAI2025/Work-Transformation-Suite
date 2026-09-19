#!/usr/bin/env python3
"""
score_processes.py — priorisiert Prozesse nach ihrem Wert, nicht nach gebundener Arbeitszeit.

Aufruf:
    python3 <skill>/scripts/score_processes.py --project ./mein-projekt
                                               [--weights ./eigene-gewichte.json] [--force]

Warum nicht nach FTE: Die Agentenpriorisierung im Skill agent-mapper sortiert nach
FTE-Äquivalent. Für eine Opportunity Map ist das richtig — sie zeigt, wo viel Arbeitszeit
gebunden ist. Als alleiniger Wertmaßstab führt es aber zuverlässig zu Vorhaben, die viel
Arbeit einsparen, ohne dass Kunden, Qualität oder Durchlaufzeit sich messbar ändern.
Hier wird deshalb mehrdimensional bewertet; das FTE-Äquivalent bleibt sichtbar, aber es
entscheidet die Rangfolge nicht mehr allein.

Eingabe 20_graph/process_value.json (von Claude oder Fachexperten ausgefüllt):
    [{"process": "Kundenreklamation bis Lösung", "customer_impact": 8, ...}]
Fehlt die Datei, schreibt das Skript eine vorbefüllte Vorlage nach
20_graph/process_value_todo.json und hält mit Exit-Code 3 an.

Gewichte und Bänder stehen in assets/value-weights.json (versioniert, mit --weights
ersetzbar). Die verwendete Konfiguration wird mit in den Graphen geschrieben, damit
später nachvollziehbar bleibt, unter welchen Annahmen eine Rangfolge entstanden ist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402
import redesign_lib as rl  # noqa: E402
from validate_graph import validate  # noqa: E402

DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent / "assets" / "value-weights.json"


def load_weights(path: Path | None) -> dict[str, Any]:
    cfg = wl.read_json(path or DEFAULT_WEIGHTS)
    for key in ("factors", "composite", "bands"):
        if key not in cfg:
            wl.fail(f"Gewichtungsdatei unvollständig: '{key}' fehlt")
    total = sum(float(v) for v in cfg["composite"].values())
    if abs(total - 1.0) > 0.001:
        wl.fail(f"composite-Gewichte summieren auf {total}, erwartet 1.0")
    return cfg


def band_of(score: float, cfg: dict[str, Any]) -> str:
    for b in sorted(cfg["bands"], key=lambda b: -float(b["min_score"])):
        if score >= float(b["min_score"]):
            return b["band"]
    return cfg["bands"][-1]["band"]


def compute(values: dict[str, float], cfg: dict[str, Any]) -> dict[str, Any]:
    """Zusammengesetzter Wert aus Nutzen, Machbarkeit und Umkehrbarkeit.

    Alle drei Teile laufen auf der gleichen Skala 0..10, damit man sie direkt lesen kann:
      benefit  = gewichteter Mittelwert der Nutzenfaktoren
      ease     = 10 minus gewichteter Mittelwert der Aufwandsfaktoren
      score    = gewichtete Summe aus benefit, ease und Umkehrbarkeit
    Absichtlich linear und ohne Schwellen: Jede Nichtlinearität würde die Sensitivität
    unlesbar machen, und genau die ist hier das wichtigste Ergebnis.
    """
    factors = cfg["factors"]
    parts: dict[str, float] = {}
    for direction in ("benefit", "effort"):
        keys = [k for k, f in factors.items() if f["direction"] == direction]
        wsum = sum(float(factors[k]["weight"]) for k in keys)
        if wsum <= 0:
            parts[direction] = 0.0
            continue
        parts[direction] = sum(float(factors[k]["weight"]) * values.get(k, 0.0) for k in keys) / wsum
    benefit = parts["benefit"]
    ease = 10.0 - parts["effort"]
    rev = values.get("reversibility", 5.0)
    c = cfg["composite"]
    score = float(c["benefit"]) * benefit + float(c["ease"]) * ease + float(c["reversibility"]) * rev
    return {
        "benefit": wl.round1(benefit),
        "effort": wl.round1(parts["effort"]),
        "ease": wl.round1(ease),
        "reversibility": wl.round1(rev),
        "score": wl.round1(score),
        "band": band_of(wl.round1(score), cfg),
    }


def sensitivity(values: dict[str, float], cfg: dict[str, Any], base_band: str) -> dict[str, Any]:
    """Wechselt das Prioritätsband, wenn ein einzelner Faktor um ±1 danebenliegt?

    Das ist die Antwort auf Scheingenauigkeit: Ein Score von 6.8 gegenüber 6.9 bedeutet
    nichts, solange die Eingaben Schätzungen auf einer Zehnerskala sind. Ein Band, das
    bei ±1 in einem einzigen Faktor kippt, ist keine Entscheidungsgrundlage.
    """
    delta = float(cfg.get("sensitivity_delta", 1))
    flips = []
    scored_keys = list(cfg["factors"]) + ["reversibility"]
    for key in sorted(scored_keys):
        for sign in (-1.0, 1.0):
            probe = dict(values)
            probe[key] = wl.clamp(values.get(key, 0.0) + sign * delta, 0.0, 10.0)
            res = compute(probe, cfg)
            if res["band"] != base_band:
                flips.append({
                    "factor": key,
                    "change": int(sign * delta),
                    "band": res["band"],
                    "score": res["score"],
                })
    return {"delta": delta, "band_stable": not flips, "flips": flips}


def template(graph: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for pr in sorted(graph["processes"], key=lambda p: p["id"]):
        row: dict[str, Any] = {"process": pr["name"], "process_id": pr["id"]}
        for k in list(cfg["factors"]) + ["reversibility"]:
            row[k] = None
        row["rationale"] = ""
        hmin = rl.human_minutes_per_case(graph, pr["id"])
        row["_kontext"] = {
            "ist": wl.process_totals(graph, pr["id"]),
            "menschliche_minuten_je_fall": hmin,
            "fte_equivalent": rl.fte_equivalent(hmin, pr.get("volume_per_year")),
            "volume_per_year": pr.get("volume_per_year"),
            "regulated": pr.get("regulated", False),
        }
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--weights", default=None)
    ap.add_argument("--force", action="store_true", help="vorhandene Bewertungen überschreiben")
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden")
    if not graph["processes"]:
        wl.fail("Keine Prozesse im Graphen")
    cfg = load_weights(Path(args.weights) if args.weights else None)

    src = project / wl.DIR_GRAPH / "process_value.json"
    if not src.exists():
        todo = project / wl.DIR_GRAPH / "process_value_todo.json"
        wl.write_json(todo, template(graph, cfg))
        print(f"Geschrieben: {wl.relpath(todo)}")
        print(f"STOPP: {wl.relpath(src)} fehlt. Nächster Schritt: die Faktoren in der Vorlage "
              "auf der Skala 0..10 füllen (Anker stehen in assets/value-weights.json und "
              "references/value-rubric.md) und als process_value.json speichern.")
        return 3
    raw = wl.read_json(src)
    if not isinstance(raw, list):
        wl.fail("process_value.json muss eine Liste sein")

    by_name = {wl.normalize_name(p["name"]): p for p in graph["processes"]}
    by_id = {p["id"]: p for p in graph["processes"]}
    scored: dict[str, dict] = {}
    problems: list[str] = []
    factor_keys = list(cfg["factors"]) + ["reversibility"]

    for entry in sorted(raw, key=lambda e: str(e.get("process", e.get("process_id", "")))):
        key = str(entry.get("process_id") or entry.get("process") or "").strip()
        pr = by_id.get(key) or by_name.get(wl.normalize_name(key))
        if pr is None:
            problems.append(f"Bewertung für unbekannten Prozess {key!r} übersprungen")
            continue
        if pr["id"] in scored:
            problems.append(f"{pr['name']}: mehrfach bewertet, erste Bewertung gilt")
            continue
        values: dict[str, float] = {}
        missing = []
        for k in factor_keys:
            v = entry.get(k)
            if v is None or isinstance(v, bool):
                missing.append(k)
                continue
            try:
                values[k] = wl.clamp(float(v), 0.0, 10.0)
            except (TypeError, ValueError):
                missing.append(k)
        if missing:
            problems.append(f"{pr['name']}: Faktoren fehlen oder sind keine Zahl: "
                            f"{', '.join(sorted(missing))} — nicht bewertet")
            continue
        res = compute(values, cfg)
        res["factors"] = {k: wl.round1(values[k]) for k in sorted(values)}
        res["sensitivity"] = sensitivity(values, cfg, res["band"])
        res["rationale"] = str(entry.get("rationale", "")).strip()
        res["weights_version"] = cfg.get("config_version", "unversioniert")
        hmin = rl.human_minutes_per_case(graph, pr["id"])
        res["human_minutes_per_case"] = hmin
        res["fte_equivalent"] = rl.fte_equivalent(hmin, pr.get("volume_per_year"))
        scored[pr["id"]] = res

    for pr in graph["processes"]:
        if pr["id"] in scored:
            if pr.get("value") and not args.force:
                # Ohne --force bleibt eine vorhandene Bewertung stehen, außer sie ist
                # mit anderen Gewichten entstanden — dann wäre die Rangfolge inkonsistent.
                if pr["value"].get("weights_version") == scored[pr["id"]]["weights_version"]:
                    continue
            pr["value"] = scored[pr["id"]]

    ranked = sorted(
        [p for p in graph["processes"] if p.get("value")],
        key=lambda p: (-p["value"]["score"],
                       -(p["value"]["fte_equivalent"] or 0.0),
                       p["value"]["effort"],
                       p["name"]),
    )
    for i, p in enumerate(ranked, start=1):
        p["value"]["rank"] = i

    for m in problems:
        print(f"HINWEIS  {m}")
    errors, warnings = validate(graph)
    for e in errors:
        print(f"FEHLER   {e}")
    if errors:
        wl.fail("Ungültiger Graph, nicht geschrieben")
    path, version, changed = wl.save_graph_version(project, graph, "value")
    verb = "Geschrieben" if changed else "Unverändert"
    unstable = sum(1 for p in ranked if not p["value"]["sensitivity"]["band_stable"])
    print(f"{verb}: {wl.relpath(path)} (Version {version}) | bewertet={len(ranked)}/"
          f"{len(graph['processes'])} Gewichte={cfg.get('config_version')} "
          f"kippelige Bänder={unstable}")
    band_label = {b["band"]: b.get("label", b["band"]) for b in cfg["bands"]}
    for p in ranked:
        v = p["value"]
        flag = "" if v["sensitivity"]["band_stable"] else "  (Band kippt bei ±1)"
        fte = f", {v['fte_equivalent']} VZÄ" if v["fte_equivalent"] is not None else ""
        print(f"  {v['rank']}. {p['name']}: {v['score']} → {band_label.get(v['band'], v['band'])} "
              f"(Nutzen {v['benefit']}, Machbarkeit {v['ease']}{fte}){flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
