"""
rollen_md.py — die fünf Abschnitte einer Rollen.md aus dem Arbeitsgraphen.

Eine Rollen.md ist die eine Datei, die ein Agenten-Harness als Kontext lädt, damit es weiß, wer hier arbeitet:

    1) Firmenprofil           Was das Unternehmen tut und für wen. Damit ordnet die KI Aufgaben im richtigen Markt ein.
    2) Rollenprofil           Was die Person tut und womit sie arbeitet: Verantwortung, Tools, wiederkehrende Aufgaben, Zeitfresser.
    3) Team-Kontext           Mit wem sie arbeitet, wen sie wann einbezieht und über welchen Kanal was läuft.
    4) Prioritäten & Ziele    Woran gerade gearbeitet wird. Der lebendigste Abschnitt; einmal im Monat aktualisieren.
    5) Arbeits- & Kommunikationsstil   Wie sie arbeitet und klingt, inklusive Do's und Don'ts für KI-Texte.

Jede Zeile trägt ihre Herkunft: „✓ Graph“ stammt aus dem Arbeitsgraphen, „❓ offen“ weiß er nicht. Die Funktionen erfinden
nichts. Was ein Graph über eine Person nicht wissen kann (Prioritäten, Tonalität, Do's und Don'ts), bleibt offen, bis jemand es
sagt; abgeleitete Hinweise sind als „abgeleitet — bitte bestätigen“ gekennzeichnet.
"""

from __future__ import annotations

from typing import Any

import json
from pathlib import Path

import workgraph_lib as wl
import export_skill as es
import extract_context_evidence as xe

OPEN = "❓ offen"
PROPOSED = "✎ Vorschlag aus Dokument — bitte bestätigen"
GRAPH = "✓ Graph"
DERIVED = "✓ abgeleitet — bitte bestätigen"
FREQ_LABEL = {"daily": "täglich", "weekly": "wöchentlich", "monthly": "monatlich", "quarterly": "quartalsweise", "adhoc": "bei Bedarf"}
MODE_LABEL = {"manual": "manuell", "ai_assisted": "KI-unterstützt", "agent_delegated": "an Agent delegiert"}
SCOPE_LABEL = {"recommend": "schlägt vor, entscheidet nicht", "execute_reversible": "führt aus, umkehrbar",
               "execute_irreversible": "führt aus, nicht umkehrbar"}
HANDOVER_LABEL = {"none": "ohne Übergabe", "system": "System", "document": "Dokument", "email": "E-Mail", "ticket": "Ticket",
                  "call": "Telefon", "meeting": "Meeting"}
ZEITFRESSER_TOP = 3
WAIT_MIN_HINT = 60.0
REWORK_PCT_HINT = 10.0


def line(label: str, value: Any, source: str = GRAPH) -> str:
    if value in (None, "", [], {}):
        return f"- **{label}:** {OPEN}"
    return f"- **{label}:** {value} _({source})_"


def entries_for(ev: list[dict[str, Any]] | None, key: str) -> list[dict[str, Any]]:
    return [e for e in (ev or []) if e.get("field") == key and e.get("confidence") != "none"]


def note_for(ev: list[dict[str, Any]] | None, key: str) -> str:
    return next((e["text"] for e in (ev or []) if e.get("field") == key and e.get("confidence") == "none"), "")


def fld(label: str, key: str, ev: list[dict[str, Any]] | None, value: Any = None, source: str = GRAPH) -> str:
    """Wert aus dem Graphen, sonst Vorschlag aus einem Dokument, sonst offen. Nie stillschweigend erfunden."""
    if value not in (None, "", [], {}):
        return line(label, value, source)
    es_ = entries_for(ev, key)
    if es_:
        texts = " · ".join(e["text"] for e in es_[:3])
        src = "; ".join(f"{e['source']} ({e['locator']})" for e in es_[:3])
        return f"- **{label}:** {texts} _({PROPOSED}; Quelle: {src})_"
    note = note_for(ev, key)
    return f"- **{label}:** {OPEN}" + (f" _({note})_" if note else "")


def load_evidence(project: Path, role_names: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Vorschläge aus `30_review/kontext_evidenz/` (Skript und Claude), geprüft: ohne Zitat und Quelle kein Eintrag."""
    root = project / wl.DIR_REVIEW / "kontext_evidenz"
    problems: list[str] = []
    out: dict[str, Any] = {"firma": [], "roles": {}}
    if not root.is_dir():
        return out, problems

    def read(paths):
        items = []
        for p in sorted(paths):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                problems.append(f"{p.name}: kein gültiges JSON")
                continue
            ok, probs = xe.validate_entries(doc.get("entries", []))
            problems.extend(f"{p.name}: {x}" for x in probs)
            items.extend(ok)
        return items

    out["firma"] = read(root.glob("firma*.json"))
    for name in role_names:
        slug = es.slug(name)
        out["roles"][name] = read(p for p in root.glob(f"{slug}*.json") if p.name == f"{slug}.json" or p.name.startswith(f"{slug}."))
    return out, problems


def task_weight(t: dict[str, Any]) -> float:
    ap = t.get("automation_potential")
    return float(t.get("share_of_time") or 0) * (float(ap) / 10.0 if ap is not None else 0.5)


def role_steps(graph: dict[str, Any], role: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in graph["process_steps"] if s.get("role_id") == role["id"]]


def role_tasks(graph: dict[str, Any], role: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted((t for t in graph["tasks"] if t.get("role_id") == role["id"]),
                  key=lambda t: (-float(t.get("share_of_time") or 0), t["name"]))


def systems_of(graph: dict[str, Any], role: dict[str, Any]) -> list[str]:
    systems = wl.index_by_id(graph["systems"])
    names = {systems[sid]["name"] for s in role_steps(graph, role) for sid in s.get("system_ids", []) if sid in systems}
    tids = {t["id"] for t in role_tasks(graph, role)}
    for a in graph["agents"]:
        c = a.get("contract") if isinstance(a.get("contract"), dict) else {}
        if tids & set(a.get("task_ids", [])):
            names.update(systems[sid]["name"] for sid in c.get("system_ids", []) if sid in systems)
    skills = wl.index_by_id(graph["skills"])
    names.update(skills[s["skill_id"]]["name"] for s in role.get("skills", []) if skills.get(s["skill_id"], {}).get("kind") == "tool")
    return sorted(names)


def handovers(graph: dict[str, Any], role: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Andere Rolle -> was geht an sie (to), was kommt von ihr (from), je Kanal gezählt, und in welchen Prozessen."""
    steps = wl.index_by_id(graph["process_steps"])
    roles = wl.index_by_id(graph["roles"])
    procs = wl.index_by_id(graph["processes"])
    out: dict[str, dict[str, Any]] = {}
    for e in graph["process_edges"]:
        a, b = steps.get(e.get("from_step_id")), steps.get(e.get("to_step_id"))
        if not a or not b:
            continue
        ra, rb = a.get("role_id"), b.get("role_id")
        if ra == rb or role["id"] not in (ra, rb):
            continue
        other, direction = (rb, "to") if ra == role["id"] else (ra, "from")
        if other not in roles:
            continue
        d = out.setdefault(other, {"to": {}, "from": {}, "processes": set(), "steps": set()})
        ht = e.get("handover") or "none"
        d[direction][ht] = d[direction].get(ht, 0) + 1
        d["processes"].add(procs.get(e.get("process_id"), {}).get("name", ""))
        d["steps"].add(a["name"] if direction == "to" else b["name"])
    return out


def channels(d: dict[str, int]) -> str:
    return ", ".join(f"{HANDOVER_LABEL.get(k, k)} {v}×" for k, v in sorted(d.items()))


def gates_of(graph: dict[str, Any], role: dict[str, Any]) -> list[str]:
    roles = wl.index_by_id(graph["roles"])
    out = []
    for s in role_steps(graph, role):
        hg = s.get("human_gate")
        if isinstance(hg, dict) and hg.get("when"):
            out.append(f"{hg['when']} → {roles.get(hg.get('role_id'), {}).get('name', 'Mensch')} (Schritt „{s['name']}“)")
        dec = s.get("decision")
        if isinstance(dec, dict) and dec.get("scope"):
            txt = f"Entscheidung „{s['name']}“: {SCOPE_LABEL.get(dec['scope'], dec['scope'])}"
            if dec.get("escalation"):
                txt += f"; Eskalation: {dec['escalation']}"
            out.append(txt)
    return out


# ---------------------------------------------------------------------------
# Abschnitte
# ---------------------------------------------------------------------------

def firmenprofil(graph: dict[str, Any], roles: list[dict[str, Any]], ev: list[dict[str, Any]] | None = None) -> list[str]:
    meta = graph["meta"]
    rids = {r["id"] for r in roles}
    proc_ids = {s["process_id"] for s in graph["process_steps"] if s.get("role_id") in rids}
    procs = [p for p in graph["processes"] if p["id"] in proc_ids] or graph["processes"]
    beneficiaries = sorted({p.get("beneficiary") for p in procs if p.get("beneficiary")})
    regulated = any(r.get("regulated") for r in roles)
    return ["## 1) Firmenprofil", "",
            "_Was das Unternehmen tut und für wen. Damit ordnet die KI Aufgaben im richtigen Markt ein._", "",
            line("Organisation", meta.get("organization")), line("Bereich", meta.get("scope")), line("Sprache", meta.get("language")),
            fld(xe.FIELD_KEYS["firma.geschaeftsmodell"], "firma.geschaeftsmodell", ev),
            fld(xe.FIELD_KEYS["firma.kunden"], "firma.kunden", ev, ", ".join(beneficiaries)),
            fld(xe.FIELD_KEYS["firma.markt"], "firma.markt", ev), fld(xe.FIELD_KEYS["firma.produkte"], "firma.produkte", ev),
            fld(xe.FIELD_KEYS["firma.sprachgebrauch"], "firma.sprachgebrauch", ev),
            line("Regulatorischer Rahmen", "mindestens eine der Rollen ist als reguliert eingestuft — Ergebnisse müssen nachvollziehbar sein") if regulated
            else f"- **Regulatorischer Rahmen:** {OPEN} (keine Rolle als reguliert eingestuft; das ist eine Annahme)", ""]


def rollenprofil(graph: dict[str, Any], role: dict[str, Any], ev: list[dict[str, Any]] | None = None) -> list[str]:
    clusters = wl.index_by_id(graph["job_clusters"])
    skills = wl.index_by_id(graph["skills"])
    tasks = role_tasks(graph, role)
    core = [f"{skills.get(s['skill_id'], {'name': s['skill_id']})['name']} (Niveau {s['level']}/5)"
            for s in role.get("skills", []) if s.get("importance") == "core" and skills.get(s["skill_id"], {}).get("kind") != "tool"]
    L = ["### 2) Rollenprofil", "",
         "_Was du tust und womit du arbeitest: Verantwortung, Tools, wiederkehrende Aufgaben, Zeitfresser._", "",
         line("Rolle", role["name"]), line("Zweck", role.get("purpose")), line("Verantwortung", role.get("description")),
         line("Jobcluster", clusters.get(role.get("cluster_id"), {}).get("name")), line("Level", role.get("level")),
         line("Reguliert", "ja — Ergebnisse müssen nachvollziehbar und begründet sein" if role.get("regulated")
              else "nein (Annahme, ggf. vom Fachexperten bestätigt)"),
         line("Tools und Systeme", "; ".join(systems_of(graph, role))), line("Kern-Skills", "; ".join(core)),
         "- **Wiederkehrende Aufgaben:**"]
    if tasks:
        for t in tasks:
            bits = [FREQ_LABEL.get(t.get("frequency"), t.get("frequency") or "–"), f"{float(t.get('share_of_time') or 0):.0f} % der Zeit"]
            if t.get("mode"):
                bits.append(MODE_LABEL.get(t["mode"], t["mode"]))
            L.append(f"  - {t['name']} — {', '.join(bits)} _({GRAPH})_")
    else:
        L.append(f"  - {OPEN}")
    # Zeitfresser: gebundene Zeit, Schmerzpunkte aus der Prozessaufnahme, Wartezeit und Rückläufer
    top = sorted(tasks, key=lambda t: (-float(t.get("share_of_time") or 0), t["name"]))[:ZEITFRESSER_TOP]
    pains = [f"„{s['pain']}“ (Schritt {s['name']})" for s in role_steps(graph, role) if (s.get("pain") or "").strip()]
    st = role_steps(graph, role)
    waits = [f"Schritt „{s['name']}“: {float(s['wait_time_min']):.0f} Min Liegezeit"
             for s in sorted((x for x in st if float(x.get("wait_time_min") or 0) >= WAIT_MIN_HINT),
                             key=lambda x: (-float(x["wait_time_min"]), x["name"]))[:ZEITFRESSER_TOP]]
    rework = [f"Schritt „{s['name']}“: {float(s['rework_pct']):.0f} % Rückläufer"
              for s in sorted((x for x in st if float(x.get("rework_pct") or 0) >= REWORK_PCT_HINT),
                              key=lambda x: (-float(x["rework_pct"]), x["name"]))[:ZEITFRESSER_TOP]]
    L.append("- **Zeitfresser (aus den Daten):**")
    derived = [f"größte gebundene Zeit: {t['name']} ({float(t.get('share_of_time') or 0):.0f} %)" for t in top] + \
              [f"Reibung laut Prozessaufnahme: {p}" for p in pains] + \
              [f"längste Liegezeit — {w}" for w in waits] + [f"meiste Rückläufer — {r}" for r in rework]
    L += [f"  - {d} _({DERIVED if not d.startswith('Reibung') else GRAPH})_" for d in derived] or [f"  - {OPEN}"]
    L += [fld(xe.FIELD_KEYS["rolle.zeitfresser"], "rolle.zeitfresser", ev), ""]
    gates = gates_of(graph, role)
    L.insert(L.index("- **Wiederkehrende Aufgaben:**"), line("Wo ein Mensch entscheidet", "; ".join(gates)))
    return L


def team_kontext(graph: dict[str, Any], role: dict[str, Any], ev: list[dict[str, Any]] | None = None) -> list[str]:
    roles = wl.index_by_id(graph["roles"])
    hmap = handovers(graph, role)
    L = ["### 3) Team-Kontext", "",
         "_Mit wem du arbeitest, wen du wann einbeziehst und über welchen Kanal was läuft._", ""]
    if hmap:
        L.append("- **Zusammenarbeit und Kanäle:**")
        for rid in sorted(hmap, key=lambda r: (roles[r]["name"], r)):
            d = hmap[rid]
            parts = []
            if d["to"]:
                parts.append(f"du gibst weiter ({channels(d['to'])})")
            if d["from"]:
                parts.append(f"du bekommst ({channels(d['from'])})")
            procs = "; ".join(sorted(p for p in d["processes"] if p))
            L.append(f"  - {roles[rid]['name']} — {', '.join(parts)}" + (f" — {procs}" if procs else "") + f" _({GRAPH})_")
    else:
        L.append(f"- **Zusammenarbeit und Kanäle:** {OPEN} (keine Übergaben im Graphen erfasst)")
    units = sorted({p["org_unit"] for p in graph["positions"] if p.get("org_unit") and any(rs["role_id"] == role["id"] for rs in p.get("role_shares", []))})
    gates = gates_of(graph, role)
    L += [line("Organisationseinheit", "; ".join(units)),
          line("Wen du wann einbeziehst (Entscheidungen, Eskalation)", "; ".join(gates)),
          line("Führungskraft und Ansprechpersonen (Namen)", None),
          fld(xe.FIELD_KEYS["team.kanaele"], "team.kanaele", ev), ""]
    return L


def prioritaeten(graph: dict[str, Any], role: dict[str, Any], ev: list[dict[str, Any]] | None = None) -> list[str]:
    steps = role_steps(graph, role)
    proc_ids = sorted({s["process_id"] for s in steps})
    outcomes = sorted({o["name"] for p in graph["processes"] if p["id"] in proc_ids for o in graph["outcomes"] if o["id"] == p.get("outcome_id")})
    metrics = []
    for m in graph["metrics"]:
        if m.get("process_id") in proc_ids:
            v, b = wl.metric_value(m, "baseline")
            metrics.append(m["name"] + (f" (heute {v} {m.get('unit', '')}, {b})" if v is not None else ""))
    first = [t["name"] for t in sorted(role_tasks(graph, role), key=lambda t: (-task_weight(t), t["name"]))[:3]]
    return ["### 4) Prioritäten & Ziele", "",
            "_Woran du gerade arbeitest. Der lebendigste Abschnitt: einmal im Monat aktualisieren._", "",
            fld(xe.FIELD_KEYS["prio.aktuell"], "prio.aktuell", ev), fld(xe.FIELD_KEYS["prio.ziele"], "prio.ziele", ev),
            line("Stand dieser Angaben (Monat)", None),
            line("Ergebnisse, auf die die Prozesse der Rolle einzahlen", "; ".join(outcomes)),
            line("Kennzahlen der Prozesse", "; ".join(metrics)),
            line("Wo Unterstützung sich zuerst lohnt (Zeitanteil × Automatisierbarkeit)", "; ".join(first), DERIVED),
            line("Woran du merkst, dass es gut läuft", None), ""]


def stil(graph: dict[str, Any], role: dict[str, Any], ev: list[dict[str, Any]] | None = None) -> list[str]:
    tasks = role_tasks(graph, role)
    coe = max((float((t.get("scores") or {}).get("consequence_of_error", 0)) for t in tasks), default=0.0)
    do_hints = []
    if role.get("regulated"):
        do_hints.append("Grundlage und Quelle jeder Aussage nennen (die Rolle ist reguliert)")
    if coe >= 6:
        do_hints.append("Unsicherheit und offene Punkte benennen, statt sie zu glätten (bei mindestens einer Aufgabe wäre ein Fehler teuer)")
    dos = [line("Do's für KI-Texte", "; ".join(do_hints), DERIVED)] if do_hints else []
    if entries_for(ev, "stil.dos") or not do_hints:
        dos.append(fld("Do's aus deinen eigenen Texten" if do_hints else "Do's für KI-Texte", "stil.dos", ev))
    return ["### 5) Arbeits- & Kommunikationsstil", "",
            "_Wie du arbeitest und wie du klingst, inklusive Do's und Don'ts für KI-Texte._", "",
            line("Qualitätsverständnis (was ist ein gutes Ergebnis?)", None),
            fld(xe.FIELD_KEYS["stil.format"], "stil.format", ev),
            line("Wie viel Rückfrage ist gewünscht?", None), line("Was der Agent nie ohne Rückfrage tun soll", None),
            fld(xe.FIELD_KEYS["stil.ton"], "stil.ton", ev), *dos,
            fld(xe.FIELD_KEYS["stil.donts"], "stil.donts", ev), ""]


# ---------------------------------------------------------------------------
# Zusammenbau
# ---------------------------------------------------------------------------

def compose(graph: dict[str, Any], roles: list[dict[str, Any]], title: str = "Rollen", evidence: dict[str, Any] | None = None) -> tuple[str, int, int]:
    """Eine Rollen.md für eine oder mehrere Rollen. Gibt (Text, Zeilen aus dem Graphen, offene Felder) zurück."""
    roles = sorted(roles, key=lambda r: (r["name"], r["id"]))
    head = ["---", "dokument: Rollen.md", "version: 1", "rollen:"] + [f"  - {r['name']}" for r in roles] + \
           ["stand: offen", "pflege: Abschnitt 4 einmal im Monat aktualisieren, die übrigen bei Veränderung", "---", "",
            f"# {title}", "",
            "Diese Datei sagt einem Agenten, wer hier arbeitet. Lade zuerst **1) Firmenprofil**, dann die Abschnitte der Rolle, in der gerade gearbeitet wird. "
            f"Zeilen mit „{GRAPH}“ stammen aus dem Arbeitsgraphen und sind nur so gut wie er; „{OPEN}“ weiß der Graph nicht — dann nachfragen, nicht raten. "
            "Zeilen mit „abgeleitet“ oder „✎ Vorschlag aus Dokument“ sind Vorschläge mit Quelle, die die Person bestätigen soll.", ""]
    evidence = evidence or {"firma": [], "roles": {}}
    body = firmenprofil(graph, roles, evidence.get("firma"))
    for r in roles:
        ev = evidence.get("roles", {}).get(r["name"])
        body += [f"## Rolle: {r['name']}", ""] + rollenprofil(graph, r, ev) + team_kontext(graph, r, ev) + prioritaeten(graph, r, ev) + stil(graph, r, ev)
    text = "\n".join(head + body).rstrip("\n") + "\n"
    return text, text.count(GRAPH) + text.count(DERIVED), text.count(OPEN)
