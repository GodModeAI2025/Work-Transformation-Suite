#!/usr/bin/env python3
"""
import_audit.py — liest die Antworten der Beschäftigtenbefragung aus 00_input/befragung/*.csv und
schreibt nur Zusammenfassungen je Aufgabe nach 20_graph/agency.json.

Aufruf:
    python3 <skill>/scripts/import_audit.py --project ./mein-projekt

Was hier passiert, ist Datenschutz in Code:

- Spalten, die eine Person benennen (Name, E-Mail, Personalnummer …), führen zum Abbruch. Ein
  Teilnehmercode, der wie eine E-Mail-Adresse aussieht, ebenso.
- Gezählt werden nur Antworten zu Aufgaben, die die Person selbst erledigt („bekannt = ja“).
- Eine Aufgabe erscheint erst ab AUDIT_MIN_GROUP Antworten, eine Rolle erst ab AUDIT_MIN_GROUP
  verschiedenen Teilnehmenden. Jeder einzelne Mittelwert braucht ebenso viele Antworten.
- In agency.json stehen weder Teilnehmercodes noch Einzelantworten noch Freitext.

Exit-Code 0 bei Erfolg (auch wenn alles unterdrückt wurde), 2 bei unzulässigen Eingaben.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

INPUT_DIR = "befragung"
OUTPUT = "agency.json"
FORBIDDEN_COLUMNS = {"name", "vorname", "nachname", "email", "e_mail", "mail", "personalnummer", "personal_nr",
                     "mitarbeiter", "mitarbeiterin", "person", "telefon", "handy", "geburtsdatum", "adresse",
                     "kostenstelle_person", "user", "user_id"}
SCALES = ["kernfaehigkeit", "sorge", "freude", "wunsch", "koerperlich", "unsicherheit", "fachwissen",
          "zwischenmenschlich", "zusammenarbeit"]
TRAITS = {"koerperlich": "physical", "unsicherheit": "uncertainty", "fachwissen": "expertise",
          "zwischenmenschlich": "interpersonal"}
YES = {"ja", "j", "yes", "y", "1", "x", "true"}
NO = {"nein", "n", "no", "0", "false", ""}
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.I)


def column_key(name: str) -> str:
    return wl.normalize_name(name).replace(" ", "_")


def scale(value: str) -> int | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        n = int(float(v.replace(",", ".")))
    except ValueError:
        return -1
    return n if 1 <= n <= 5 else -1


def codes(value: str, allowed: dict) -> tuple[list[str], list[str]]:
    raw = [wl.normalize_name(x) for x in re.split(r"[|,/]", value or "") if x.strip()]
    good = sorted({c for c in raw if c in allowed})
    bad = sorted({c for c in raw if c not in allowed})
    return good, bad


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    if len(vals) < wl.AUDIT_MIN_GROUP:
        return None
    return wl.round1(sum(vals) / len(vals))


def majority(levels: list[int]) -> int | None:
    """Mehrheit über H1–H5; bei Gleichstand gewinnt die höhere Beteiligung (die vorsichtigere Lesart)."""
    if len(levels) < wl.AUDIT_MIN_GROUP:
        return None
    counts = [levels.count(i) for i in range(1, 6)]
    best = max(counts)
    return max(i + 1 for i, c in enumerate(counts) if c == best)


def read_rows(project: Path, graph: dict) -> tuple[list[dict], list[dict], list[str], int]:
    folder = project / wl.DIR_INPUT / INPUT_DIR
    files = sorted(folder.glob("*.csv")) if folder.is_dir() else []
    if not files:
        wl.fail(f"Keine Antworten in {wl.relpath(folder)} (*.csv)", code=3)
    roles_by_name = {wl.normalize_name(r.get("name")): r for r in graph["roles"]}
    tasks = wl.index_by_id(graph["tasks"])
    tasks_by_role_name: dict[tuple[str, str], str] = {}
    for t in graph["tasks"]:
        tasks_by_role_name[(t.get("role_id"), wl.normalize_name(t.get("name")))] = t["id"]
    rows: dict[tuple[str, str], dict] = {}
    warnings: list[str] = []
    meta_files = []
    unfamiliar = 0
    for f in files:
        data = wl.read_csv(f)
        header = {column_key(c) for c in (data[0].keys() if data else [])}
        bad_cols = sorted(header & FORBIDDEN_COLUMNS)
        if bad_cols:
            wl.fail(f"{f.name}: Spalten {', '.join(bad_cols)} benennen Personen. Die Befragung arbeitet nur mit "
                    "selbst gewählten Codes; Spalten entfernen und erneut importieren.")
        meta_files.append({"file": f.name, "rows": len(data), "sha256": wl.sha256_file(f)})
        for n, raw in enumerate(data, start=2):
            row = {column_key(k): (v or "").strip() for k, v in raw.items() if k}
            who = row.get("teilnehmer", "")
            if not who:
                continue
            if EMAIL_RE.search(who):
                wl.fail(f"{f.name} Zeile {n}: Teilnehmercode sieht aus wie eine E-Mail-Adresse. Codes statt Adressen verwenden.")
            role = roles_by_name.get(wl.normalize_name(row.get("rolle")))
            if role is None:
                warnings.append(f"{f.name} Zeile {n}: Rolle {row.get('rolle')!r} nicht im Graphen, ignoriert")
                continue
            tid = row.get("aufgabe_id") or tasks_by_role_name.get((role["id"], wl.normalize_name(row.get("aufgabe"))))
            if not tid or tid not in tasks or tasks[tid].get("role_id") != role["id"]:
                warnings.append(f"{f.name} Zeile {n}: Aufgabe {row.get('aufgabe_id') or row.get('aufgabe')!r} gehört nicht "
                                f"zur Rolle {role['name']!r}, ignoriert")
                continue
            known = row.get("bekannt", "").lower()
            if known not in YES:
                if known not in NO:
                    warnings.append(f"{f.name} Zeile {n}: bekannt={row.get('bekannt')!r} unklar, als „nein“ gezählt")
                unfamiliar += 1
                continue
            rec = {"who": who, "role_id": role["id"], "task_id": tid}
            for s in SCALES:
                v = scale(row.get(s, ""))
                if v == -1:
                    warnings.append(f"{f.name} Zeile {n}: {s}={row.get(s)!r} liegt nicht in 1–5, ignoriert")
                    v = None
                rec[s] = v
            try:
                share = float((row.get("zeitanteil") or "").replace(",", ".").rstrip("%")) if row.get("zeitanteil") else None
            except ValueError:
                warnings.append(f"{f.name} Zeile {n}: zeitanteil={row.get('zeitanteil')!r} ist keine Zahl, ignoriert")
                share = None
            rec["zeitanteil"] = share if share is None or 0 <= share <= 100 else None
            for col, allowed, key in (("gruende_wunsch", wl.AUDIT_REASONS_AUTOMATION, "reasons_automation"),
                                      ("gruende_zusammenarbeit", wl.AUDIT_REASONS_COLLAB, "reasons_collab")):
                good, bad = codes(row.get(col, ""), allowed)
                if bad:
                    warnings.append(f"{f.name} Zeile {n}: unbekannte Codes in {col}: {', '.join(bad)}")
                rec[key] = good
            if rec["wunsch"] is None and rec["zusammenarbeit"] is None:
                warnings.append(f"{f.name} Zeile {n}: weder wunsch noch zusammenarbeit beantwortet, ignoriert")
                continue
            key = (who, tid)
            if key in rows:
                warnings.append(f"{f.name} Zeile {n}: Teilnehmer {who!r} hat die Aufgabe doppelt bewertet, die letzte Zeile gilt")
            rows[key] = rec
    return list(rows.values()), meta_files, warnings, unfamiliar


def aggregate(recs: list[dict]) -> tuple[dict, dict, int]:
    by_role: dict[str, set] = {}
    for r in recs:
        by_role.setdefault(r["role_id"], set()).add(r["who"])
    roles_ok = {rid for rid, who in by_role.items() if len(who) >= wl.AUDIT_MIN_GROUP}
    by_task: dict[str, list[dict]] = {}
    for r in recs:
        by_task.setdefault(r["task_id"], []).append(r)
    tasks_out: dict[str, dict] = {}
    suppressed = 0
    for tid in sorted(by_task):
        items = by_task[tid]
        if items[0]["role_id"] not in roles_ok or len(items) < wl.AUDIT_MIN_GROUP:
            suppressed += 1
            continue
        desire_vals = [i["wunsch"] for i in items if i["wunsch"] is not None]
        has_vals = [i["zusammenarbeit"] for i in items if i["zusammenarbeit"] is not None]
        has_major = majority(has_vals)
        if has_major is None:
            suppressed += 1
            continue
        reasons_a: dict[str, int] = {}
        reasons_c: dict[str, int] = {}
        for i in items:
            for c in i["reasons_automation"]:
                reasons_a[c] = reasons_a.get(c, 0) + 1
            for c in i["reasons_collab"]:
                reasons_c[c] = reasons_c.get(c, 0) + 1
        traits = {eng: mean([i[de] for i in items]) for de, eng in TRAITS.items()}
        block = {
            "respondents": len(items),
            "desire": mean(desire_vals),
            "desire_positive_pct": (wl.round1(100.0 * sum(1 for v in desire_vals if v > wl.ZONE_DESIRE_MIN) / len(desire_vals))
                                    if len(desire_vals) >= wl.AUDIT_MIN_GROUP else None),
            "has_desired": has_major,
            "has_desired_mean": mean(has_vals),
            "has_desired_counts": [has_vals.count(k) for k in range(1, 6)],
            "job_worry": mean([i["sorge"] for i in items]),
            "enjoyment": mean([i["freude"] for i in items]),
            "core_skill": mean([i["kernfaehigkeit"] for i in items]),
            "time_share_survey": mean([i["zeitanteil"] for i in items]),
            "traits": {k: v for k, v in traits.items() if v is not None},
            "reasons_automation": reasons_a,
            "reasons_collab": reasons_c,
        }
        tasks_out[tid] = {k: v for k, v in block.items() if v is not None}
    roles_out = {rid: {"respondents": len(by_role[rid])} for rid in sorted(roles_ok)}
    return tasks_out, roles_out, suppressed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = wl.resolve_project(args.project)
    graph = wl.load_latest_graph(project)
    if not graph:
        wl.fail("Kein Graph gefunden, zuerst work-graph-builder ausführen")
    recs, files, warnings, unfamiliar = read_rows(project, graph)
    tasks_out, roles_out, suppressed = aggregate(recs)
    data = {
        "meta": {
            "files": files,
            "min_group": wl.AUDIT_MIN_GROUP,
            "respondents": len({r["who"] for r in recs}),
            "answers": len(recs),
            "answers_unfamiliar": unfamiliar,
            "tasks_published": len(tasks_out),
            "tasks_suppressed": suppressed,
            "roles_published": len(roles_out),
        },
        "roles": roles_out,
        "tasks": tasks_out,
    }
    path = project / wl.DIR_GRAPH / OUTPUT
    wl.write_json(path, data)
    for w in warnings:
        print(f"HINWEIS  {w}")
    m = data["meta"]
    print(f"Geschrieben: {wl.relpath(path)} | Teilnehmende={m['respondents']} Antworten={m['answers']} "
          f"Aufgaben gezeigt={m['tasks_published']} unterdrückt={m['tasks_suppressed']} Rollen={m['roles_published']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
