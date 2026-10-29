#!/usr/bin/env python3
"""
pages_lib.py — Markdown-Seiten mit flachem Frontmatter: lesen, prüfen, schreiben.

Die Seiten unter 05_pages/ sind die kanonische Fassung dessen, was Claude und Menschen über
Rollen, Aufgaben, Skills, Bewertungen und Agenten festhalten. compile_pages.py übersetzt sie in
die JSON-Register (10_extraction/extract_*.json, 20_graph/scores.json, 20_graph/agents.json),
export_pages.py erzeugt sie aus vorhandenen Registern.

Der Frontmatter-Vertrag ist bewusst klein, damit jeder Helfer ihn gleich liest:
- genau eine Ebene; Schlüssel aus Kleinbuchstaben, Ziffern und Unterstrich;
- Werte: Zeichenkette (in Anführungszeichen oder nackt), Zahl, true, false, null;
- Listen flach: inline als JSON-Array oder als Blockliste mit "- " je Zeile;
- keine verschachtelten Objekte, keine Anker, keine Tabulatoren, keine doppelten Schlüssel;
- Kommentarzeilen (#) nur am Anfang des Kopfs.
Was nicht passt, wird mit Dateiname und Zeile gemeldet; geraten wird nicht.

Im Rumpf gliedern Überschriften der zweiten Ebene (## …) die Abschnitte. Tabellen, nummerierte
Listen und JSON-Codeblöcke darin liest diese Bibliothek; alles andere bleibt Text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workgraph_lib as wl  # noqa: E402

DIR_PAGES = "05_pages"
PAGE_KINDS = {"cluster": "clusters", "role": "roles", "task": "tasks", "agent": "agents"}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NUMBER_RE = re.compile(r"^-?(0|[1-9]\d*)(\.\d+)?$")
UNSAFE_KEYS = {"__proto__", "constructor", "prototype"}


class PageError(ValueError):
    pass


def page_slug(text: str) -> str:
    return (wl.normalize_name(text).replace(" ", "-")[:64].strip("-")) or "seite"


# ---------------------------------------------------------------------------
# Frontmatter lesen
# ---------------------------------------------------------------------------

def _scalar(raw: str, where: str) -> Any:
    v = raw.strip()
    if v == "" or v == "null" or v == "~":
        return None
    if v == "true":
        return True
    if v == "false":
        return False
    if NUMBER_RE.match(v):
        return float(v) if "." in v else int(v)
    if v[0] == '"':
        try:
            out = json.loads(v)
        except json.JSONDecodeError as e:
            raise PageError(f"{where}: Zeichenkette nicht lesbar ({e.msg})")
        if not isinstance(out, str):
            raise PageError(f"{where}: Wert in Anführungszeichen muss eine Zeichenkette sein")
        return out
    if v[0] in "'[{&*|>!%@`":
        raise PageError(f"{where}: Wert {v[:20]!r} ist nicht erlaubt (nur \"…\", Zahl, true, false, null oder JSON-Liste)")
    return v


def _inline_list(raw: str, where: str) -> list:
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PageError(f"{where}: Liste nicht lesbar ({e.msg}); Listen sind JSON-Arrays, z. B. [\"a\", \"b\"]")
    if not isinstance(out, list) or any(isinstance(x, (list, dict)) for x in out):
        raise PageError(f"{where}: Liste darf nur Zeichenketten, Zahlen, true, false oder null enthalten")
    return out


def parse_frontmatter(text: str, source: str = "<seite>") -> tuple[dict[str, Any], str]:
    """Gibt (Kopf, Rumpf) zurück. Fehler nennen Datei und Zeile."""
    head, body = wl.split_frontmatter(text)
    if not head and not text.startswith("---"):
        raise PageError(f"{source}: kein Frontmatter (die Seite muss mit --- beginnen)")
    data: dict[str, Any] = {}
    i = 0
    comments_done = False
    while i < len(head):
        line = head[i]
        n = i + 2  # Zeile in der Datei: --- ist Zeile 1
        where = f"{source}:{n}"
        if "\t" in line:
            raise PageError(f"{where}: Tabulator im Frontmatter")
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith("#"):
            if comments_done:
                raise PageError(f"{where}: Kommentare nur am Anfang des Kopfs")
            i += 1
            continue
        comments_done = True
        if line.startswith(" "):
            raise PageError(f"{where}: eingerückte Zeile; verschachtelte Werte sind nicht erlaubt")
        m = re.match(r"^([^:]+):(.*)$", line)
        if not m:
            raise PageError(f"{where}: erwartet schlüssel: wert")
        key = m.group(1).strip()
        raw = m.group(2)
        if not KEY_RE.match(key) or key in UNSAFE_KEYS:
            raise PageError(f"{where}: Schlüssel {key!r} nicht erlaubt (a-z, 0-9, _)")
        if key in data:
            raise PageError(f"{where}: Schlüssel {key!r} doppelt")
        if raw.strip() == "" and i + 1 < len(head) and head[i + 1].lstrip().startswith("- "):
            items = []
            i += 1
            while i < len(head) and head[i].lstrip().startswith("- "):
                item_line = head[i]
                if "\t" in item_line:
                    raise PageError(f"{source}:{i + 2}: Tabulator im Frontmatter")
                item = item_line.lstrip()[2:]
                if item.strip().startswith(("[", "{")):
                    raise PageError(f"{source}:{i + 2}: verschachtelte Liste nicht erlaubt")
                items.append(_scalar(item, f"{source}:{i + 2}"))
                i += 1
            data[key] = items
            continue
        if raw.strip().startswith("["):
            data[key] = _inline_list(raw, where)
        elif raw.strip().startswith("{"):
            raise PageError(f"{where}: Objekte sind im Frontmatter nicht erlaubt; nutze flache Schlüssel oder einen JSON-Block im Rumpf")
        else:
            data[key] = _scalar(raw, where)
        i += 1
    return data, body


def dump_frontmatter(data: dict[str, Any], comments: list[str] | None = None) -> str:
    lines = ["---"] + [f"# {c}" for c in (comments or [])]
    for k, v in data.items():
        if not KEY_RE.match(k):
            raise PageError(f"Schlüssel {k!r} nicht erlaubt")
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if any(isinstance(x, (list, dict)) for x in v):
                raise PageError(f"{k}: Liste darf nicht verschachtelt sein")
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                lines += [f"  - {json.dumps(x, ensure_ascii=False)}" for x in v]
        elif isinstance(v, dict):
            raise PageError(f"{k}: Objekte gehören in einen JSON-Block im Rumpf")
        else:
            lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Rumpf: Abschnitte, Tabellen, Listen, JSON-Blöcke
# ---------------------------------------------------------------------------

def sections(body: str) -> dict[str, str]:
    """Text je Abschnitt (## Überschrift); Text vor der ersten Überschrift unter ''."""
    out: dict[str, str] = {}
    current = ""
    buf: list[str] = []
    fenced = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
        m = None if fenced else re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            out[current] = "\n".join(buf).strip("\n")
            current, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    out[current] = "\n".join(buf).strip("\n")
    return out


def table_rows(text: str) -> list[dict[str, str]]:
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    def cells(ln: str) -> list[str]:
        parts = re.split(r"(?<!\\)\|", ln.strip())
        return [p.strip().replace("\\|", "|") for p in parts[1:-1]]
    head = cells(lines[0])
    rows = []
    for ln in lines[2:]:
        vals = cells(ln)
        rows.append({head[i]: (vals[i] if i < len(vals) else "") for i in range(len(head))})
    return rows


def ordered_list(text: str) -> list[str]:
    return [re.sub(r"^\s*\d+[.)]\s+", "", ln).strip() for ln in text.splitlines() if re.match(r"^\s*\d+[.)]\s+", ln)]


def json_block(text: str, where: str) -> Any:
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise PageError(f"{where}: JSON-Block nicht lesbar ({e.msg}, Zeile {e.lineno} im Block)")


def prose(text: str) -> str:
    """Fließtext eines Abschnitts ohne Tabellen, Listen und Codeblöcke, als ein Absatz."""
    out, fenced = [], False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or ln.strip().startswith("|") or re.match(r"^\s*(\d+[.)]|[-*])\s+", ln):
            continue
        out.append(ln.strip())
    return " ".join(x for x in out if x).strip()


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(x: Any) -> str:
        return "" if x is None else str(x).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Seiten lesen und schreiben
# ---------------------------------------------------------------------------

def pages_dir(project: Path) -> Path:
    return project / DIR_PAGES


def read_page(path: Path, project: Path) -> dict[str, Any]:
    rel = path.relative_to(project).as_posix()
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"), rel)
    kind = meta.get("type")
    if kind not in PAGE_KINDS:
        raise PageError(f"{rel}: type muss einer von {', '.join(PAGE_KINDS)} sein")
    return {"path": rel, "meta": meta, "sections": sections(body), "body": body}


def read_all_pages(project: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Alle Seiten je Art, alphabetisch; Fehler gesammelt statt beim ersten abgebrochen."""
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in PAGE_KINDS}
    problems: list[str] = []
    base = pages_dir(project)
    if not base.is_dir():
        return out, problems
    for path in sorted(base.rglob("*.md")):
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        try:
            page = read_page(path, project)
        except PageError as e:
            problems.append(str(e))
            continue
        out[page["meta"]["type"]].append(page)
    return out, problems


def write_page(path: Path, meta: dict[str, Any], body: str, comments: list[str] | None = None) -> None:
    wl.write_text(path, dump_frontmatter(meta, comments) + "\n" + body.rstrip("\n") + "\n")


def has_pages(project: Path) -> bool:
    base = pages_dir(project)
    return base.is_dir() and any(p.suffix == ".md" and p.name.lower() != "readme.md" for p in base.rglob("*.md"))
