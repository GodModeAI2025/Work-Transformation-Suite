#!/usr/bin/env python3
"""
workgraph_lib.py — gemeinsame Hilfsfunktionen für alle Skills der Work-Transformation-Suite.

Diese Datei liegt identisch in jedem Skill unter scripts/, damit jeder Skill
eigenständig installierbar bleibt. Änderungen bitte in allen Kopien nachziehen
(scripts/check_lib_sync.py im Orchestrator prüft das).

Determinismus-Regeln, die hier umgesetzt sind:
- IDs entstehen aus einem SHA1-Hash des normalisierten Namens (plus Kontext),
  nie aus Zufall oder Zeit. Gleicher Name => gleiche ID, in jedem Lauf.
- Alle Listen werden vor dem Schreiben stabil sortiert (nach ID).
- JSON wird mit sort_keys=True, festem Einzug und ensure_ascii=False geschrieben.
- Kein Zeitstempel im Inhalt, außer der Aufrufer verlangt ihn ausdrücklich.
- Alle Pfade werden relativ zum Projektordner aufgelöst, nie absolut hart codiert.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"

# Feste Ordnerstruktur eines Projekts (relativ zum Projektordner)
DIR_INPUT = "00_input"
DIR_EXTRACTION = "10_extraction"
DIR_GRAPH = "20_graph"
DIR_REVIEW = "30_review"
DIR_OUTPUT = "40_output"
PROJECT_FILE = "project.json"
LATEST_GRAPH = "work-graph_latest.json"

# Erlaubte Aufzählungswerte (Validator prüft dagegen)
ENUM_FREQUENCY = ["daily", "weekly", "monthly", "quarterly", "adhoc"]
ENUM_NATURE = ["cognitive", "physical", "mixed"]
ENUM_STATUS = ["generated", "reviewed", "approved"]
ENUM_MODE = ["manual", "ai_assisted", "agent_delegated"]
ENUM_HORIZON = ["near", "mid", "long"]
ENUM_ARCHETYPE = [
    "control-heavy",
    "knowledge-heavy",
    "process-heavy",
    "relationship-heavy",
    "creative-heavy",
    "physical-heavy",
]
ENUM_DISRUPTION = ["eliminated", "transformed", "augmented", "emerging", "stable"]
ENUM_SKILL_KIND = ["knowledge", "skill", "competence", "tool"]
ENUM_SKILL_IMPORTANCE = ["core", "supporting"]
ENUM_AGENT_STATUS = ["proposed", "planned", "pilot", "live"]
ENUM_SOURCING = ["build", "buy", "hybrid"]
ENUM_SPECIFICITY = ["generic", "domain", "proprietary"]

ID_PREFIX = {
    "job_family": "jf",
    "job_cluster": "jc",
    "role": "ro",
    "task": "ta",
    "skill": "sk",
    "agent": "ag",
    "position": "po",
    "course": "co",
}


# ---------------------------------------------------------------------------
# Normalisierung und IDs
# ---------------------------------------------------------------------------

def normalize_name(text: str) -> str:
    """Kleinschreibung, Umlaute vereinheitlicht, Whitespace/Sonderzeichen reduziert.

    Wird für Duplikat-Erkennung und ID-Bildung genutzt. Muss stabil bleiben:
    eine Änderung hier ändert alle IDs in bestehenden Projekten.
    """
    if text is None:
        return ""
    t = unicodedata.normalize("NFKD", str(text))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower().replace("ß", "ss")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split()).strip()


def make_id(kind: str, *parts: str) -> str:
    """Deterministische ID: <prefix>_<12 hex> aus normalisierten Teilen."""
    prefix = ID_PREFIX[kind]
    key = "|".join(normalize_name(p) for p in parts)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


# ---------------------------------------------------------------------------
# Dateizugriff (immer relativ zum Projektordner)
# ---------------------------------------------------------------------------

def resolve_project(project_arg: str) -> Path:
    """Projektordner relativ zum aktuellen Arbeitsverzeichnis auflösen."""
    p = Path(project_arg)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def project_dirs(project: Path) -> dict[str, Path]:
    return {
        "input": project / DIR_INPUT,
        "extraction": project / DIR_EXTRACTION,
        "graph": project / DIR_GRAPH,
        "review": project / DIR_REVIEW,
        "output": project / DIR_OUTPUT,
    }


def ensure_dirs(project: Path) -> None:
    for d in project_dirs(project).values():
        d.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delimiter))


def load_project_meta(project: Path) -> dict[str, Any]:
    pf = project / PROJECT_FILE
    if pf.exists():
        return read_json(pf)
    return {
        "name": project.name,
        "organization": "",
        "scope": "",
        "language": "de",
        "graph_version": 0,
    }


def save_project_meta(project: Path, meta: dict[str, Any]) -> None:
    write_json(project / PROJECT_FILE, meta)


def latest_graph_path(project: Path) -> Path:
    return project / DIR_GRAPH / LATEST_GRAPH


def load_latest_graph(project: Path) -> dict[str, Any] | None:
    p = latest_graph_path(project)
    return read_json(p) if p.exists() else None


def next_version(project: Path) -> int:
    meta = load_project_meta(project)
    return int(meta.get("graph_version", 0)) + 1


def _content_without_meta(graph: dict[str, Any]) -> str:
    g = {k: v for k, v in graph.items() if k != "meta"}
    return json.dumps(g, ensure_ascii=False, sort_keys=True)


def save_graph_version(project: Path, graph: dict[str, Any], stage: str) -> tuple[Path, int, bool]:
    """Neue Version schreiben, latest aktualisieren, Zähler in project.json erhöhen.

    stage: kurzer Name des schreibenden Schritts (builder|review|positions|scorer|mapper)

    Idempotenz: Ist der Inhalt (ohne meta) identisch mit der aktuellen latest-Datei,
    wird keine neue Version angelegt; zurück kommt der Pfad der bestehenden Version.
    So erzeugt ein wiederholter Lauf ohne neue Eingaben keine Versionsflut.
    """
    meta = load_project_meta(project)
    sort_graph(graph)
    latest = load_latest_graph(project)
    if latest is not None and _content_without_meta(latest) == _content_without_meta(graph):
        graph["meta"] = latest.get("meta", {})
        version = int(latest["meta"].get("version", meta.get("graph_version", 0)))
        existing = project / DIR_GRAPH / f"work-graph_v{version:03d}_{latest['meta'].get('stage', stage)}.json"
        return existing, version, False
    version = int(meta.get("graph_version", 0)) + 1
    graph.setdefault("meta", {})
    graph["meta"]["version"] = version
    graph["meta"]["stage"] = stage
    graph["meta"]["schema_version"] = SCHEMA_VERSION
    graph["meta"]["project"] = meta.get("name", project.name)
    graph["meta"]["organization"] = meta.get("organization", "")
    graph["meta"]["scope"] = meta.get("scope", "")
    graph["meta"]["language"] = meta.get("language", "de")
    sort_graph(graph)
    gdir = project / DIR_GRAPH
    path = gdir / f"work-graph_v{version:03d}_{stage}.json"
    write_json(path, graph)
    write_json(latest_graph_path(project), graph)
    meta["graph_version"] = version
    save_project_meta(project, meta)
    return path, version, True


# ---------------------------------------------------------------------------
# Graph-Struktur
# ---------------------------------------------------------------------------

COLLECTIONS = [
    "job_families",
    "job_clusters",
    "roles",
    "tasks",
    "skills",
    "agents",
    "positions",
    "courses",
]


def empty_graph() -> dict[str, Any]:
    g: dict[str, Any] = {"meta": {"schema_version": SCHEMA_VERSION}}
    for c in COLLECTIONS:
        g[c] = []
    return g


# Nur Referenz-/Mengenlisten werden sortiert. Geordnete Listen (workflow_steps,
# roles_covered) behalten ihre fachliche Reihenfolge.
SORTED_LIST_KEYS = {"task_ids", "skill_ids", "agent_ids", "source_refs", "overrides_applied",
                    "prerequisites", "retained_skills", "declining_skills"}


def sort_graph(graph: dict[str, Any]) -> None:
    """Alle Sammlungen stabil nach ID sortieren; Referenzlisten in Objekten ebenfalls."""
    for c in COLLECTIONS:
        items = graph.get(c, [])
        items.sort(key=lambda x: x.get("id", ""))
        for it in items:
            for key, val in list(it.items()):
                if key in SORTED_LIST_KEYS and isinstance(val, list) and all(isinstance(v, str) for v in val):
                    it[key] = sorted(set(val))
                elif key == "skills" and isinstance(val, list):
                    val.sort(key=lambda s: s.get("skill_id", ""))
        graph[c] = items


def index_by_id(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {it["id"]: it for it in items}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def round1(x: float) -> float:
    # Kaufmännisches Runden auf eine Nachkommastelle, unabhängig von Float-Artefakten
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fail(msg: str, code: int = 2) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    print(msg)


def relpath(path: Path, base: Path | None = None) -> str:
    """Pfad relativ zum Arbeitsverzeichnis (oder base) für Ausgaben."""
    base = base or Path.cwd()
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return str(path)
