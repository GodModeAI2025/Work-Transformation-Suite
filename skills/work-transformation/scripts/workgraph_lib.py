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

SCHEMA_VERSION = "1.3"
SCHEMA_VERSIONS_SUPPORTED = ("1.0", "1.1", "1.2", "1.3")

# Feste Ordnerstruktur eines Projekts (relativ zum Projektordner)
DIR_INPUT = "00_input"
DIR_EXTRACTION = "10_extraction"
DIR_GRAPH = "20_graph"
DIR_REVIEW = "30_review"
DIR_OUTPUT = "40_output"
PROJECT_FILE = "project.json"
LATEST_GRAPH = "work-graph_latest.json"
# Quellenregister (Schema 1.3): treue Markdown-Fassung jeder Quelle unter 00_input/sources/,
# Register als JSON-Zeilen. Belege im Graphen verweisen als "src-<hash>@<fundstelle>" darauf.
DIR_SOURCES = "sources"
SOURCE_REGISTER = "register.jsonl"
# Stände (Schema 1.3): Wiederherstellungspunkte, verifizierte Freigabestände, Pflege-Lock.
DIR_SNAPSHOTS = "50_snapshots"
DIR_RELEASES = "60_releases"
LOCK_DIR = ".wts-lock"
RELEASE_LOG = "releases.jsonl"
# Was zu einem Stand gehört: alles, was Menschen oder Claude geschrieben haben, plus der
# aktuelle Graph. Erzeugte Ausgaben (40_output) nur in Freigabeständen, nie in Snapshots.
CONTROLLED_DIRS = (DIR_INPUT, DIR_EXTRACTION, DIR_GRAPH, DIR_REVIEW)
CONTROLLED_SKIP_PARTS = ("__pycache__", ".DS_Store", DIR_SNAPSHOTS, DIR_RELEASES, LOCK_DIR)
SOURCE_ID_RE = re.compile(r"^src-[0-9a-f]{12}$")
EVIDENCE_RE = re.compile(r"^(src-[0-9a-f]{12})@(\S.*)$")
# Belegstand einer Aussage: belegt (mindestens ein gültiger Beleg), geschätzt (ausdrücklich
# als Schätzung oder Vorschlag gekennzeichnet), unbelegt (weder noch). Unbelegt ist nicht
# falsch, aber sichtbar: Der Validator warnt, bei strenger Belegpflicht lehnt er ab.
# "reference": alle Belege zeigen auf die Referenzbibliothek, nicht auf Material des Hauses.
ENUM_EVIDENCE_STATUS = ["sourced", "reference", "estimated", "unsourced"]
ENUM_PLATFORM = ["microsoft", "google", "mischbetrieb", "unabhaengig"]
ENUM_EVIDENCE_POLICY = ["warn", "strict"]

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

# Schema 1.2: Realisierbarkeit, Zielbild, Adoption
# Wie wird frei werdende Kapazität einer Rolle aufgefangen? `none` heißt: gar nicht, das
# technische Potenzial bleibt dann Theorie.
ENUM_ABSORPTION = ["growth", "attrition", "redeployment", "none"]
ENUM_ADOPTION_STATUS = ["prioritized", "building", "in_use"]
ENUM_EVIDENCE_GRADE = ["heuristic", "expert_confirmed", "proven"]
# Lösungsklasse eines Soll-Schritts. Nicht jeder Schritt braucht KI: Wer 84 PDFs von Hand
# öffnet, braucht oft nur eine Schnittstelle.
ENUM_SOLUTION_CLASS = ["ai", "interface", "process_change", "rule_or_rpa"]
ENUM_TARGET_ROLE_BASIS = ["estimated", "expert_confirmed"]
ENUM_CLUSTER_STATUS = ["candidate", "confirmed", "rejected"]

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
    # Schema 1.2
    "target_role": "tr",
    "usecase": "uc",
    "adoption": "ad",
    "task_cluster": "tc",
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
    if meta.get("profile"):
        graph["meta"]["profile"] = dict(meta["profile"])
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
# Schema 1.2: Zielbild je Rolle, eigene Use Cases, aggregierter Nutzungsstand
COLLECTIONS_ADOPTION = ["target_roles", "usecases", "adoption"]
# Datenaufbereitung: Aufgabencluster über Rollen hinweg
COLLECTIONS_PREP = ["task_clusters"]
COLLECTIONS = (COLLECTIONS_CORE + COLLECTIONS_PROCESS + COLLECTIONS_REDESIGN
               + COLLECTIONS_GOVERNANCE + COLLECTIONS_ADOPTION + COLLECTIONS_PREP)

# Mindestgruppengröße für jede Nutzungsauswertung. Darunter wird nichts angezeigt: Eine
# Zahl für drei Stellen ist eine Aussage über drei Menschen.
ADOPTION_MIN_GROUP = 5
WORK_DAYS_PER_YEAR = 220
# Assistierte Arbeit setzt nur einen Teil der Zeit frei: KI verkürzt, ersetzt nicht.
ASSIST_FREED_FACTOR = 0.2


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
    # Schema 1.2
    "retained_task_ids", "delegated_task_ids", "merge_with_role_ids", "agent_ids_covered",
    # Schema 1.3
    "evidence", "source_evidence",
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


def executor_key(step: dict[str, Any]) -> str:
    """Wer einen Schritt ausführt, als vergleichbarer Schlüssel.

    Ist- und Soll-Schritte tragen `executor` in derselben Form, deshalb liefert dieselbe
    Funktion für beide den Schlüssel — nur so sind Übergaben zwischen Ist und Soll
    überhaupt vergleichbar.
    """
    ex = step.get("executor") or {}
    return f"{ex.get('type')}:{ex.get('id') or ex.get('name') or ''}"


def is_handover(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Ist der Übergang von Schritt a nach Schritt b eine Übergabe?

    Eine Übergabe ist ein Wechsel des Ausführenden, bei dem mindestens eine Seite ein
    Mensch ist. Das ist die Größe, die in einer Organisation tatsächlich etwas kostet:
    ein Postkorb, eine Wartezeit, ein Kontextverlust. Zwei Agenten, die innerhalb
    desselben Systems weiterreichen, kosten Millisekunden — sie als Übergabe zu zählen,
    würde jeden Entwurf mit mehreren Spezialagenten schlechter aussehen lassen als eine
    lange Kette derselben Sachbearbeitung, und das wäre schlicht falsch.

    Dieselbe Funktion gilt für Ist-Schritte und Blueprint-Schritte. Zwei verschiedene
    Definitionen hätten zur Folge, dass im Ist-Soll-Vergleich zwei verschiedene Größen
    nebeneinander stünden — ein Entwurf, der nichts ändert, sähe dann nach einer
    Verbesserung aus.
    """
    if executor_key(a) == executor_key(b):
        return False
    types = {(a.get("executor") or {}).get("type"), (b.get("executor") or {}).get("type")}
    return "human" in types


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
    by_id = {s["id"]: s for s in steps}
    handling = sum(float(s.get("handling_time_min") or 0) for s in steps)
    wait = sum(float(s.get("wait_time_min") or 0) for s in steps)
    rework = [float(s.get("rework_pct")) for s in steps if s.get("rework_pct") is not None]

    # Übergaben nach der gemeinsamen Regel (is_handover), damit Ist und Soll dieselbe
    # Größe messen. Die Kante liefert die Reihenfolge, nicht das Kriterium.
    handovers = 0
    for e in edges:
        a, b = by_id.get(e.get("from_step_id")), by_id.get(e.get("to_step_id"))
        if a is not None and b is not None and is_handover(a, b):
            handovers += 1
    # Medienbrüche bleiben getrennt erfasst: Sie beschreiben, WIE übergeben wird, nicht ob.
    # Für das Redesign sind sie der interessantere Befund, für den Vergleich taugen sie nicht,
    # weil ein Soll-Entwurf keine Medien modelliert.
    media_breaks = sum(1 for e in edges
                       if (e.get("handover") or "none") in ("email", "call", "meeting", "document"))
    return {
        "steps": len(steps),
        "handling_time_min": round1(handling),
        "wait_time_min": round1(wait),
        "lead_time_hours": round1((handling + wait) / 60.0),
        "human_touches": sum(1 for s in steps if step_has_human(s)),
        "automated_steps": sum(1 for s in steps if step_is_automated(s)),
        "handovers": handovers,
        "media_breaks": media_breaks,
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


# ---------------------------------------------------------------------------
# Schema 1.2: Reichweite, Blindflecken, Kapazität je Jobfamilie
# ---------------------------------------------------------------------------

def role_headcount(role: dict[str, Any]):
    """FTE-Basis einer Rolle: aus Positionen abgeleitet, sonst der gesetzte Headcount."""
    hc = role.get("headcount_from_positions")
    return role.get("headcount") if hc is None else hc


def day_value(role: dict[str, Any], fte: float):
    """Geschätzter Jahreswert frei werdender Zeit; nur mit Tagessatz, sonst None."""
    rate = role.get("day_rate_eur")
    if rate is None or fte is None:
        return None
    return round1(float(fte) * WORK_DAYS_PER_YEAR * float(rate))


def agent_reach(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Umgekehrte Sicht: Wen betrifft ein Agent oder Use Case?

    Je Eintrag die Rollen, deren Aufgaben er abdeckt, mit Zeitanteil und FTE. Das ist
    die Antwort auf „für wie viele Stellen gilt diese Automatisierung?“ — der Zeitanteil
    ist die gebundene Arbeit der abgedeckten Aufgaben, nicht die erwartete Ersparnis.
    """
    tasks = index_by_id(graph.get("tasks", []))
    roles = index_by_id(graph.get("roles", []))
    out = []
    items = ([("agent", a) for a in graph.get("agents", [])]
             + [("usecase", u) for u in graph.get("usecases", [])])
    for kind, it in items:
        per_role: dict[str, float] = {}
        for tid in it.get("task_ids", []):
            t = tasks.get(tid)
            if t and t.get("role_id") in roles:
                per_role[t["role_id"]] = per_role.get(t["role_id"], 0.0) + float(t.get("share_of_time") or 0)
        rows, fte_total, value_total, value_known = [], 0.0, 0.0, False
        for rid in sorted(per_role):
            r = roles[rid]
            hc = role_headcount(r)
            fte = round1(float(hc) * per_role[rid] / 100.0) if hc is not None else None
            if fte is not None:
                fte_total += fte
            val = day_value(r, fte)
            if val is not None:
                value_total += val
                value_known = True
            rows.append({"role_id": rid, "name": r.get("name"), "headcount": hc,
                         "time_share_pct": round1(per_role[rid]), "fte": fte, "value_eur": val})
        out.append({"id": it["id"], "name": it.get("name"), "kind": kind, "roles": rows,
                    "fte_total": round1(fte_total),
                    "value_eur_estimated": round1(value_total) if value_known else None,
                    "value_eur_declared": it.get("value_eur_per_year") if kind == "usecase" else None})
    out.sort(key=lambda x: (-x["fte_total"], x["name"] or "", x["id"]))
    return out


def blind_spots(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Prozesse mit hohem Wert, für die niemand einen Agenten oder Use Case anfragt.

    „Hoch“ heißt Band `now` oder `next`. „Angefragt“ heißt: Mindestens eine Aufgabe eines
    Schritts steht in einem Agenten oder einem Use Case. Wer nur den bedient, der am
    lautesten ruft, übersieht genau diese Liste.
    """
    covered: set[str] = set()
    for a in graph.get("agents", []):
        covered.update(a.get("task_ids", []))
    for u in graph.get("usecases", []):
        covered.update(u.get("task_ids", []))
    out = []
    for pr in graph.get("processes", []):
        v = pr.get("value") or {}
        if v.get("band") not in ("now", "next"):
            continue
        task_ids = {tid for s in steps_of(graph, pr["id"]) for tid in s.get("task_ids", [])}
        if task_ids & covered:
            continue
        out.append({"process_id": pr["id"], "name": pr.get("name"), "band": v.get("band"),
                    "score": v.get("score"), "tasks": len(task_ids)})
    out.sort(key=lambda x: (-(x["score"] or 0), x["name"] or ""))
    return out


def family_capacity(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Technisches und realisierbares Potenzial je Jobfamilie (Spur A)."""
    clusters = index_by_id(graph.get("job_clusters", []))
    families = index_by_id(graph.get("job_families", []))
    agg: dict[str, dict[str, Any]] = {}
    for r in graph.get("roles", []):
        an = r.get("analysis") or {}
        fam_id = (clusters.get(r.get("cluster_id")) or {}).get("family_id")
        row = agg.setdefault(fam_id, {"family_id": fam_id,
                                      "name": (families.get(fam_id) or {}).get("name", "–"),
                                      "roles": 0, "headcount": 0.0, "fte_technical": 0.0,
                                      "fte_realisable": 0.0, "roles_unassessed": 0,
                                      "roles_without_headcount": 0})
        row["roles"] += 1
        hc = role_headcount(r)
        if hc is None:
            row["roles_without_headcount"] += 1
            continue
        row["headcount"] += float(hc)
        if an.get("fte_released_technical") is not None:
            row["fte_technical"] += an["fte_released_technical"]
            if an.get("fte_realisable") is None:
                row["roles_unassessed"] += 1
            else:
                row["fte_realisable"] += an["fte_realisable"]
    out = sorted(agg.values(), key=lambda x: (-x["fte_technical"], x["name"]))
    for row in out:
        for f in ("headcount", "fte_technical", "fte_realisable"):
            row[f] = round1(row[f])
    return out


# ---------------------------------------------------------------------------
# Zusammenarbeit der Rollen (gemeinsam genutzt von derive_collaboration und dem Rollen-Setup)
# ---------------------------------------------------------------------------

COLLAB_HANDOVER_LABEL = {"none": "keine", "system": "System", "document": "Dokument", "email": "E-Mail", "ticket": "Ticket",
                   "call": "Telefon", "meeting": "Meeting"}
COLLAB_W_HANDOVER, COLLAB_W_POSITION, COLLAB_W_UNIT = 3, 2, 1


def collaboration_pairs(graph: dict[str, Any]) -> list[dict[str, Any]]:
    roles = index_by_id(graph["roles"])
    steps = index_by_id(graph.get("process_steps", []))
    pairs: dict[tuple[str, str], dict[str, Any]] = {}

    def entry(a: str, b: str) -> dict[str, Any]:
        key = (a, b) if a < b else (b, a)
        return pairs.setdefault(key, {"a": key[0], "b": key[1], "handovers": 0, "types": {}, "processes": set(),
                                      "positions": set(), "units": set()})

    for e in graph.get("process_edges", []):
        s1, s2 = steps.get(e.get("from_step_id")), steps.get(e.get("to_step_id"))
        if not s1 or not s2:
            continue
        r1, r2 = s1.get("role_id"), s2.get("role_id")
        if r1 in roles and r2 in roles and r1 != r2:
            p = entry(r1, r2)
            p["handovers"] += 1
            ht = e.get("handover") or "none"
            p["types"][ht] = p["types"].get(ht, 0) + 1
            p["processes"].add(e.get("process_id"))
    processes = index_by_id(graph.get("processes", []))
    units: dict[str, set[str]] = {}
    for pos in graph.get("positions", []):
        rids = sorted(rs["role_id"] for rs in pos.get("role_shares", []) if rs["role_id"] in roles)
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                entry(rids[i], rids[j])["positions"].add(pos.get("position_id") or pos["id"])
        if pos.get("org_unit"):
            units.setdefault(pos["org_unit"], set()).update(rids)
    for unit, rids in units.items():
        rl = sorted(rids)
        for i in range(len(rl)):
            for j in range(i + 1, len(rl)):
                entry(rl[i], rl[j])["units"].add(unit)

    out = []
    for p in pairs.values():
        strength = COLLAB_W_HANDOVER * p["handovers"] + COLLAB_W_POSITION * len(p["positions"]) + COLLAB_W_UNIT * len(p["units"])
        out.append({
            "role_a": roles[p["a"]]["name"], "role_b": roles[p["b"]]["name"], "role_a_id": p["a"], "role_b_id": p["b"],
            "handovers": p["handovers"],
            "handover_types": ", ".join(f"{COLLAB_HANDOVER_LABEL.get(k, k)} {v}×" for k, v in sorted(p["types"].items())),
            "processes": "; ".join(sorted(processes[x]["name"] for x in p["processes"] if x in processes)),
            "shared_positions": len(p["positions"]), "shared_units": "; ".join(sorted(p["units"])),
            "strength": strength,
        })
    out.sort(key=lambda r: (-r["strength"], r["role_a"], r["role_b"]))
    return out


# ---------------------------------------------------------------------------
# Schema 1.3: Quellenregister und Belege
# ---------------------------------------------------------------------------

def sources_dir(project: Path) -> Path:
    return project / DIR_INPUT / DIR_SOURCES


def load_source_register(project: Path) -> dict[str, dict[str, Any]]:
    """Registrierte Quellen je source_id. Fehlt das Register, ist das Ergebnis leer."""
    path = sources_dir(project) / SOURCE_REGISTER
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            fail(f"{relpath(path)} Zeile {n}: kein gültiges JSON ({e})")
        if isinstance(rec, dict) and rec.get("source_id"):
            out[rec["source_id"]] = rec
    return out


def parse_evidence(ref: Any):
    """Gibt (source_id, locator) zurück oder None, wenn der Beleg nicht die Form src-…@… hat."""
    if not isinstance(ref, str):
        return None
    m = EVIDENCE_RE.match(ref.strip())
    return (m.group(1), m.group(2).strip()) if m else None


def evidence_status(entity: dict[str, Any], estimated: bool = False, reference_ids: set | None = None) -> str:
    """Belegstand einer Aussage aus ihren Belegen und ihrer Kennzeichnung.

    Zeigen alle Belege auf Quellen der Art „reference“ (Referenzbibliothek), ist die Aussage
    „reference“: ein Vorrat, der am Haus noch bestätigt werden muss, kein Befund.
    """
    refs = [parse_evidence(r) for r in (entity.get("evidence") or []) if parse_evidence(r)]
    if refs:
        if reference_ids and all(sid in reference_ids for sid, _ in refs):
            return "reference"
        return "sourced"
    return "estimated" if estimated else "unsourced"


def reference_source_ids(project: Path) -> set:
    return {sid for sid, rec in load_source_register(project).items() if rec.get("kind") == "reference"}


def project_profile(project: Path) -> dict[str, str]:
    """Branche, Plattformprofil und Rechtsraum des Projekts (project.json: profile)."""
    prof = load_project_meta(project).get("profile") or {}
    return {"branche": str(prof.get("branche") or ""), "plattform": str(prof.get("plattform") or ""),
            "rechtsraum": str(prof.get("rechtsraum") or "")}


def library_dir() -> Path | None:
    """Referenzbibliothek: im eigenen Skill oder im Geschwister-Skill work-graph-builder."""
    skill = Path(__file__).resolve().parent.parent
    for cand in (skill / "library", skill.parent / "work-graph-builder" / "library"):
        if (cand / "branchen" / "index.json").exists():
            return cand
    return None


def legal_topics(graph: dict[str, Any], role: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    """Themen des Rechtsrahmens, die eine Rolle berühren: Stichwörter gegen Rolle, Cluster, Familie,
    Aufgaben und Skills; Branchenfilter aus dem Projektprofil. Ein Treffer ist ein Prüfauftrag."""
    profile = (graph.get("meta") or {}).get("profile") or {}
    raum = profile.get("rechtsraum") or "DE"
    data = load_library_json("rechtsraeume", f"{raum}.json")
    if not data:
        return []
    branche = profile.get("branche") or ""
    clusters = index_by_id(graph.get("job_clusters", []))
    families = index_by_id(graph.get("job_families", []))
    skills = index_by_id(graph.get("skills", []))
    cl = clusters.get(role.get("cluster_id")) or {}
    fam = families.get(cl.get("family_id")) or {}
    words = [role.get("name", ""), cl.get("name", ""), fam.get("name", "")]
    words += [t.get("name", "") for t in graph.get("tasks", []) if t.get("role_id") == role.get("id")]
    words += [skills.get(s.get("skill_id"), {}).get("name", "") for s in role.get("skills", [])]
    haystack = " " + normalize_name(" | ".join(words)) + " "
    out = []
    for t in data.get("themen", []):
        if "*" not in t.get("branchen", ["*"]) and branche not in t.get("branchen", []):
            continue
        kws = t.get("stichwoerter", [])
        if "*" in kws or any(normalize_name(k) and normalize_name(k) in haystack for k in kws):
            out.append(t)
    return out[:limit]


def platform_profile(graph: dict[str, Any]) -> dict[str, Any] | None:
    pid = ((graph.get("meta") or {}).get("profile") or {}).get("plattform") or ""
    return load_library_json("plattformen", f"{pid}.json") if pid in ENUM_PLATFORM else None


def platform_tool(profile: dict[str, Any], tool: str) -> str | None:
    """Dienst für ein abstraktes Werkzeug eines Vertrags (mail.send → Mail-Dienst des Profils)."""
    ns = str(tool).split(".")[0].strip().lower()
    return (profile.get("werkzeuge") or {}).get(ns)


def load_library_json(*parts: str) -> Any:
    base = library_dir()
    if base is None:
        return None
    p = base.joinpath(*parts)
    return read_json(p) if p.exists() else None


def anchor_slug(heading: str) -> str:
    """Anker einer Überschrift für Fundstellen: „Auftragssachbearbeiter (9 Stellen)“ → auftragssachbearbeiter-9-stellen."""
    return normalize_name(heading).replace(" ", "-")


def source_headings(body: str) -> list[tuple[int, int, str, str]]:
    """(Zeile, Ebene, Überschrift, Anker) für jede Markdown-Überschrift; Codeblöcke werden übersprungen."""
    out = []
    fenced = False
    for n, line in enumerate(body.splitlines(), start=1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            out.append((n, len(m.group(1)), m.group(2).strip(), anchor_slug(m.group(2))))
    return out


def split_frontmatter(text: str) -> tuple[list[str], str]:
    """Trennt den YAML-Kopf (Zeilen zwischen den ersten beiden ---) vom Rumpf; der Rumpf bleibt byteidentisch."""
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.S)
    if not m:
        return [], text
    return m.group(1).split("\n"), text[m.end():].lstrip("\n")


def resolve_locator(body: str, locator: str) -> tuple[bool, str]:
    """Prüft eine Fundstelle gegen den Quelltext: #anker, Ln, La-b. Freitext gilt als nicht prüfbar."""
    lines = body.splitlines()
    if locator.startswith("#"):
        anchors = {a for _, _, _, a in source_headings(body)}
        want = locator[1:]
        return (want in anchors, "" if want in anchors else f"Anker {locator!r} nicht in der Quelle")
    m = re.match(r"^L(\d+)(?:-(\d+))?$", locator)
    if m:
        a = int(m.group(1))
        b = int(m.group(2) or a)
        ok = 1 <= a <= b <= len(lines)
        return ok, "" if ok else f"Zeilen {locator} außerhalb der Quelle ({len(lines)} Zeilen)"
    return True, "Fundstelle ist Freitext und wird nicht geprüft"


# Zugangsdaten gehören in keine Quelle und in keinen Bericht. Die Muster sind bewusst eng:
# Formen, die in Fließtext praktisch nie zufällig vorkommen. Gemeldet wird Zeile und Art,
# nie der Treffer selbst, damit der Bericht ihn nicht ein zweites Mal verbreitet.
CREDENTIAL_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("api-key", re.compile(r"(?<![\w-])sk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}")),
    ("json-web-token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@<>\"'`]+:[^/\s:@<>\"'`]+@")),
)
_PLACEHOLDER_PASSWORDS = {"pass", "passwd", "password", "passwort", "pw", "pwd", "secret", "geheim", "token", "changeme"}


def _credential_placeholder(kind: str, match: str) -> bool:
    if kind == "url-credentials":
        password = match.rsplit("@", 1)[0].split("://", 1)[1].split(":", 1)[1]
        return password.lower() in _PLACEHOLDER_PASSWORDS or password[:1] in "${%*" or len(set(password.lower())) == 1
    if "example" in match.lower():
        return True
    body = max(re.split(r"[_.-]", match[4:]) or [""], key=len)
    return len(body) >= 12 and len(set(body.lower())) <= 2


def credential_findings(text: str) -> list[tuple[int, str]]:
    """(Zeile, Art) je Zeile, die wie ein Zugangsdatum aussieht."""
    out = []
    for n, line in enumerate(text.splitlines(), start=1):
        for kind, pat in CREDENTIAL_PATTERNS:
            if any(not _credential_placeholder(kind, m.group(0)) for m in pat.finditer(line)):
                out.append((n, kind))
                break
    return out


def portable_reference(value: str) -> bool:
    """Darf ein Verweis in einer Projektdatei stehen? Keine absoluten Pfade, kein Home, kein .. ."""
    v = (value or "").strip()
    if not v or v.lower().startswith("file:"):
        return False
    if re.match(r"^[a-z][a-z0-9+.-]+://", v, re.I):
        return True
    if v.startswith(("~/", "~\\")) or v.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", v):
        return False
    return ".." not in v.replace("\\", "/").split("/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def controlled_files(project: Path, with_output: bool = False) -> list[str]:
    """Relative Pfade aller Dateien, die einen Stand ausmachen, stabil sortiert.

    Ältere Graph-Versionen (work-graph_vNNN_*.json) gehören nicht dazu: Sie sind Geschichte,
    der Stand ist work-graph_latest.json plus alles, woraus er entstand.
    """
    out = [PROJECT_FILE] if (project / PROJECT_FILE).exists() else []
    dirs = list(CONTROLLED_DIRS) + ([DIR_OUTPUT] if with_output else [])
    for d in dirs:
        base = project / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(project)
            if any(part in CONTROLLED_SKIP_PARTS for part in rel.parts):
                continue
            if d == DIR_GRAPH and re.match(r"^work-graph_v\d{3}_", p.name):
                continue
            out.append(rel.as_posix())
    return out


def manifest_of(project: Path, files: list[str]) -> dict[str, str]:
    return {rel: sha256_file(project / rel) for rel in files}


def evidence_policy(project: Path) -> str:
    """Belegpflicht des Projekts (project.json: evidence_policy). Standard: warn."""
    pol = str(load_project_meta(project).get("evidence_policy") or "warn")
    return pol if pol in ENUM_EVIDENCE_POLICY else "warn"


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
