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

Schema 1.1 ergänzt den rollenlokalen Arbeitsgraphen (Rollen, Aufgaben, Skills) additiv um
die Prozessebene: outcomes, processes, process_steps, process_edges, systems, controls,
metrics sowie die Redesign-Artefakte blueprints und experiments und die Governance-
Sammlungen provenance und decisions. Projekte nach Schema 1.0 lassen sich verlustfrei
migrieren (migrate_graph); fehlende Sammlungen entstehen leer.
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

SCHEMA_VERSION = "1.1"
SCHEMA_VERSIONS_SUPPORTED = ("1.0", "1.1")

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

# --- Schema 1.1: Prozessebene ----------------------------------------------
# Wer einen Schritt ausführt. "rule" meint deterministische Regelwerke ohne Modell,
# "system" eine bestehende Systemfunktion; beides ist bewusst von "agent" getrennt,
# weil es andere Betriebs- und Prüfpflichten auslöst.
ENUM_EXECUTOR = ["human", "agent", "system", "rule"]
# Lean-Klassifikation eines Schrittes. Nur "waste" darf ohne Ersatz entfallen;
# "business_required" braucht beim Entfall eine dokumentierte Kontrolle als Ersatz.
ENUM_VALUE_TYPE = ["customer_value", "business_required", "waste"]
ENUM_HANDOVER = ["none", "system", "document", "email", "ticket", "call", "meeting"]
ENUM_CONTROL_KIND = ["regulatory", "financial", "safety", "privacy", "quality", "contractual"]
ENUM_CONTROL_MODE = ["preventive", "detective", "corrective"]
ENUM_METRIC_KIND = ["outcome", "quality", "risk", "cost", "time", "adoption"]
ENUM_METRIC_DIRECTION = ["lower_is_better", "higher_is_better"]
# Der wichtigste Unterschied der Suite: geschätzt ≠ vom Fachexperten bestätigt ≠ gemessen.
ENUM_VALUE_BASIS = ["estimated", "expert_confirmed", "observed"]
ENUM_DATA_CLASS = ["public", "internal", "confidential", "personal", "special_category"]

# --- Schema 1.1: Redesign ---------------------------------------------------
ENUM_SCENARIO = ["conservative", "balanced", "agent_native"]
# Die sechs Redesign-Operatoren (ESIA-Schule, um Parallelisierung und Human Gate erweitert).
ENUM_OPERATOR = ["eliminate", "simplify", "merge", "parallelize", "automate", "human_gate"]
ENUM_BLUEPRINT_STATUS = ["draft", "reviewed", "approved", "rejected"]
ENUM_PRIORITY_BAND = ["now", "next", "later", "hold"]

# --- Schema 1.1: Experimente ------------------------------------------------
ENUM_EXPERIMENT_DESIGN = ["ab_test", "shadow", "stepped_rollout", "pre_post"]
ENUM_EXPERIMENT_STATUS = ["draft", "ready", "running", "stopped", "completed"]

# --- Schema 1.1: Governance -------------------------------------------------
# Entscheidungsreichweite eines automatisierten Schrittes. Die drei Stufen lösen
# unterschiedliche Pflichten aus (siehe validate_graph.py und contract-format.md).
ENUM_DECISION_SCOPE = ["recommend", "execute_reversible", "execute_irreversible"]
ENUM_SOURCE_KIND = ["document", "interview", "system_export", "observation", "estimate", "model_inference"]
ENUM_PROVENANCE_STATUS = ["asserted", "reviewed", "verified", "disputed"]
ENUM_DECISION_TYPE = ["approve", "reject", "defer", "revoke"]

ID_PREFIX = {
    "job_family": "jf",
    "job_cluster": "jc",
    "role": "ro",
    "task": "ta",
    "skill": "sk",
    "agent": "ag",
    "position": "po",
    "course": "co",
    # Schema 1.1
    "outcome": "ou",
    "process": "pr",
    "process_step": "ps",
    "process_edge": "pe",
    "system": "sy",
    "control": "ct",
    "metric": "me",
    "blueprint": "bp",
    "experiment": "xp",
    "provenance": "pv",
    "decision": "dc",
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


def write_text(path: Path, text: str, newline: str = "\n") -> None:
    """Text mit fester Zeilenende-Konvention schreiben.

    Path.write_text kennt das Argument `newline` erst ab Python 3.10; die Suite läuft ab
    3.9. Wichtiger noch: Ohne feste Konvention schreibt dieselbe Eingabe unter Windows
    andere Bytes als unter Linux, und das Determinismusversprechen der Suite („gleiche
    Eingaben, gleiche Bytes") gälte nur je Betriebssystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)


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


def load_latest_graph(project: Path, migrate: bool = True) -> dict[str, Any] | None:
    """Aktuellen Graphen laden. Standardmäßig wird er im Speicher auf das aktuelle
    Schema gehoben, damit nachgelagerte Skripte nie Sammlungen abfragen müssen,
    die es in einem älteren Projekt noch nicht gibt. Auf der Platte ändert das nichts;
    geschrieben wird erst durch save_graph_version."""
    p = latest_graph_path(project)
    if not p.exists():
        return None
    graph = read_json(p)
    if migrate:
        migrate_graph(graph)
    return graph


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
    # Bewusst ohne Migration lesen: Verglichen wird, was auf der Platte steht, mit dem,
    # was geschrieben werden soll. Würde die gelesene Fassung vorher migriert, sähe ein
    # Schema-1.0-Projekt identisch aus und die Migration würde nie geschrieben.
    latest = load_latest_graph(project, migrate=False)
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

# Sammlungen des Arbeitsgraphen. Die ersten acht bilden den Ist-Zustand ab (Schema 1.0),
# die übrigen kamen mit Schema 1.1 dazu: Prozessebene, Redesign und Governance.
COLLECTIONS_CORE = [
    "job_families",
    "job_clusters",
    "roles",
    "tasks",
    "skills",
    "agents",
    "positions",
    "courses",
]
COLLECTIONS_PROCESS = [
    "outcomes",
    "systems",
    "controls",
    "metrics",
    "processes",
    "process_steps",
    "process_edges",
]
COLLECTIONS_REDESIGN = ["blueprints", "experiments"]
COLLECTIONS_GOVERNANCE = ["provenance", "decisions"]
COLLECTIONS = COLLECTIONS_CORE + COLLECTIONS_PROCESS + COLLECTIONS_REDESIGN + COLLECTIONS_GOVERNANCE


def empty_graph() -> dict[str, Any]:
    g: dict[str, Any] = {"meta": {"schema_version": SCHEMA_VERSION}}
    for c in COLLECTIONS:
        g[c] = []
    return g


def migrate_graph(graph: dict[str, Any]) -> list[str]:
    """Graph verlustfrei auf das aktuelle Schema heben. Gibt die Änderungen zurück.

    Migration ist rein additiv: fehlende Sammlungen entstehen leer, vorhandene Inhalte
    werden nicht angefasst. Ein Projekt nach Schema 1.0 bleibt damit nach der Migration
    fachlich identisch und kann ohne Neubewertung weiterlaufen.
    """
    notes: list[str] = []
    meta = graph.setdefault("meta", {})
    before = meta.get("schema_version")
    for c in COLLECTIONS:
        if not isinstance(graph.get(c), list):
            graph[c] = []
            if c not in COLLECTIONS_CORE:
                notes.append(f"Sammlung '{c}' leer ergänzt")
    if before != SCHEMA_VERSION:
        meta["schema_version"] = SCHEMA_VERSION
        notes.append(f"schema_version {before!r} -> {SCHEMA_VERSION!r}")
    return notes


# Nur Referenz-/Mengenlisten werden sortiert. Geordnete Listen (workflow_steps,
# step_ids, roles_covered, blueprint.steps) behalten ihre fachliche Reihenfolge.
SORTED_LIST_KEYS = {
    "task_ids", "skill_ids", "agent_ids", "source_refs", "overrides_applied",
    "prerequisites", "retained_skills", "declining_skills",
    # Schema 1.1
    "system_ids", "control_ids", "metric_ids", "baseline_metric_ids", "guardrail_metric_ids",
    "process_ids", "role_ids", "step_ref_ids", "from_step_ids", "removed_step_ids",
    "retained_control_ids", "dropped_control_ids", "data_classes", "inputs", "outputs",
    "tools", "read_permissions", "write_permissions", "audit_events", "blueprint_ids",
}


def _sort_lists_in(obj: Any) -> None:
    """Referenzlisten rekursiv sortieren, damit auch verschachtelte Objekte
    (Blueprint-Schritte, Vertragsteile) byteidentisch geschrieben werden."""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if key in SORTED_LIST_KEYS and isinstance(val, list) and all(isinstance(v, str) for v in val):
                obj[key] = sorted(set(val))
            elif key == "skills" and isinstance(val, list) and all(isinstance(v, dict) for v in val):
                val.sort(key=lambda s: s.get("skill_id", ""))
                for v in val:
                    _sort_lists_in(v)
            else:
                _sort_lists_in(val)
    elif isinstance(obj, list):
        for v in obj:
            _sort_lists_in(v)


def sort_graph(graph: dict[str, Any]) -> None:
    """Alle Sammlungen stabil nach ID sortieren; Referenzlisten in Objekten ebenfalls."""
    for c in COLLECTIONS:
        items = graph.get(c, [])
        if not isinstance(items, list):
            items = []
        items.sort(key=lambda x: x.get("id", ""))
        for it in items:
            _sort_lists_in(it)
        graph[c] = items


def index_by_id(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {it["id"]: it for it in items}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def round1(x: float) -> float:
    # Kaufmännisches Runden auf eine Nachkommastelle, unabhängig von Float-Artefakten
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Prozessebene (Schema 1.1)
# ---------------------------------------------------------------------------

def steps_of(graph: dict[str, Any], process_id: str) -> list[dict[str, Any]]:
    """Schritte eines Prozesses in fachlicher Reihenfolge (process.step_ids)."""
    by_id = index_by_id(graph.get("process_steps", []))
    proc = next((p for p in graph.get("processes", []) if p.get("id") == process_id), None)
    if proc is None:
        return []
    ordered = [by_id[sid] for sid in proc.get("step_ids", []) if sid in by_id]
    known = {s["id"] for s in ordered}
    rest = sorted((s for s in graph.get("process_steps", [])
                   if s.get("process_id") == process_id and s["id"] not in known),
                  key=lambda s: s["id"])
    return ordered + rest


def edges_of(graph: dict[str, Any], process_id: str) -> list[dict[str, Any]]:
    return sorted((e for e in graph.get("process_edges", []) if e.get("process_id") == process_id),
                  key=lambda e: e.get("id", ""))


def metric_value(metric: dict[str, Any], stage: str = "baseline"):
    """Wert einer Kennzahl auf einer bestimmten Stufe, samt Belastbarkeit.

    Die drei Stufen sind ausdrücklich verschiedene Dinge und werden nie vermischt:
      baseline  der heutige Wert (Ist)
      target    der zugesagte Wert eines Soll-Entwurfs
      observed  der im Pilot gemessene Wert des veränderten Prozesses

    Ein gemessener Pilotwert ist deshalb **kein** besserer Ausgangswert: Er beschreibt
    den neuen Prozess, nicht den alten. Wer beides zusammenwirft, vergleicht den
    Soll-Zustand mit sich selbst und findet überall Verbesserungen.

    Gibt (wert, basis) zurück; basis ist 'estimated', 'expert_confirmed' oder 'observed'.
    """
    block = metric.get(stage) or {}
    if block.get("value") is None:
        return None, None
    basis = block.get("basis")
    if stage == "observed":
        return block.get("value"), "observed"
    return block.get("value"), basis if basis in ENUM_VALUE_BASIS else "estimated"


def metric_best_known(metric: dict[str, Any]):
    """Der belastbarste vorliegende Wert einer Kennzahl, für Aussagen über den Stand
    des Wissens (nicht für Ist/Soll-Vergleiche). Gemessen schlägt bestätigt schlägt geschätzt."""
    for stage in ("observed", "baseline"):
        value, basis = metric_value(metric, stage)
        if value is not None:
            return value, basis, stage
    return None, None, None


def step_is_automated(step: dict[str, Any]) -> bool:
    return (step.get("executor") or {}).get("type") in ("agent", "system", "rule")


def step_has_human(step: dict[str, Any]) -> bool:
    """Ein Schritt bindet Menschen, wenn ein Mensch ihn ausführt oder ein Human Gate greift."""
    return (step.get("executor") or {}).get("type") == "human" or bool(step.get("human_gate"))


def process_totals(graph: dict[str, Any], process_id: str) -> dict[str, Any]:
    """Deterministische Ist-Kennzahlen eines Prozesses aus seinen Schritten und Kanten.

    Bewusst einfach gehalten: Summen statt Simulation. Wartezeiten und Bearbeitungszeiten
    werden addiert, weil ohne Prozess-Mining-Daten jede Verteilungsannahme Scheingenauigkeit
    wäre. Parallelität wird nur dort abgezogen, wo sie im Blueprint ausdrücklich modelliert ist.
    """
    steps = steps_of(graph, process_id)
    edges = edges_of(graph, process_id)
    handling = sum(float(s.get("handling_time_min") or 0) for s in steps)
    wait = sum(float(s.get("wait_time_min") or 0) for s in steps)
    rework = [float(s.get("rework_pct")) for s in steps if s.get("rework_pct") is not None]
    handovers = sum(1 for e in edges if (e.get("handover") or "none") != "none")
    return {
        "steps": len(steps),
        "handling_time_min": round1(handling),
        "wait_time_min": round1(wait),
        "lead_time_hours": round1((handling + wait) / 60.0),
        "human_touches": sum(1 for s in steps if step_has_human(s)),
        "automated_steps": sum(1 for s in steps if step_is_automated(s)),
        "handovers": handovers,
        "rework_pct": round1(sum(rework) / len(rework)) if rework else 0.0,
        "waste_steps": sum(1 for s in steps if s.get("value_type") == "waste"),
    }


# Einheiten, die als Stunden gelesen werden. Absichtlich klein gehalten: Was hier nicht
# steht, wird nicht umgerechnet, statt eine Einheit zu erraten.
_HOUR_UNITS = {"h", "std", "stunde", "stunden", "hour", "hours", "hrs"}
_DAY_UNITS = {"d", "tag", "tage", "day", "days", "werktage", "arbeitstage"}
_MINUTE_UNITS = {"min", "minute", "minuten", "minutes"}


def lead_time_gap(graph: dict[str, Any], process_id: str, tolerance_pct: float = 30.0):
    """Vergleicht die modellierte Durchlaufzeit mit einer gemessenen Baseline-Kennzahl.

    Ein Prozessmodell aus Interviews ist fast immer lückenhaft: Liegezeiten in Postkörben,
    Rückfragen und Wartetage auf Dritte tauchen nicht auf. Wenn die Summe der modellierten
    Schritte deutlich unter der gemessenen Durchlaufzeit liegt, fehlen Schritte — und dann
    rechnet jedes Redesign-Delta auf einer zu kleinen Grundmenge.

    Gibt None zurück, wenn es keine vergleichbare Kennzahl gibt, sonst ein Dict mit
    modelliertem Wert, gemessenem Wert und Abweichung in Prozent.
    """
    proc = next((p for p in graph.get("processes", []) if p.get("id") == process_id), None)
    if proc is None:
        return None
    modelled = process_totals(graph, process_id)["lead_time_hours"]
    metrics = index_by_id(graph.get("metrics", []))
    for mid in proc.get("baseline_metric_ids", []):
        m = metrics.get(mid)
        if not m or m.get("kind") != "time":
            continue
        unit = normalize_name(m.get("unit", "")).replace(" ", "")
        if unit in _HOUR_UNITS:
            factor = 1.0
        elif unit in _DAY_UNITS:
            factor = 24.0
        elif unit in _MINUTE_UNITS:
            factor = 1.0 / 60.0
        else:
            continue
        value, basis = metric_value(m, "baseline")
        if value is None:
            continue
        measured = float(value) * factor
        if measured <= 0:
            continue
        deviation = 100.0 * (modelled - measured) / measured
        if abs(deviation) <= tolerance_pct:
            return None
        return {
            "metric_id": mid, "metric": m.get("name"), "basis": basis,
            "modelled_hours": modelled, "measured_hours": round1(measured),
            "deviation_pct": round1(deviation),
        }
    return None


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
