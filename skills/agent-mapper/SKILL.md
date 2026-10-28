---
name: agent-mapper
description: "Bündelt die delegier- und assistierbaren Aufgaben eines bewerteten Arbeitsgraphen (work-graph.json nach task-scorer) zu einer Agentenbibliothek aus wiederverwendbaren KI-Agenten und berechnet deterministisch je Agent, welche Rollen er zu wie viel Prozent abdeckt, FTE-Äquivalent, Build/Buy/Hybrid, Zeithorizont und Priorität; gleicht bestehende KI-Anwendungen des Unternehmens ab; baut auf Zuruf Rollen.md und Setup-Paket je Rolle (Kontext, Prompt, Skills, Tests, Tools). Dritter Schritt der Work-Transformation-Suite. IMMER verwenden bei: Agentenbibliothek, Agentic Workforce Library, welche Agenten brauchen wir, Agenten zu Rollen zuordnen, Rollenabdeckung durch Agenten, Build or Buy für KI-Agenten, Agent-Katalog, Agentenlandkarte, Automatisierungs-Backlog priorisieren, 'welcher Agent übernimmt was', KI-Use-Cases aus Aufgaben ableiten, Rollen-Setup, Agent für diese Rolle einrichten — auch wenn der Nutzer nur fragt 'was sollen wir zuerst automatisieren' und ein bewerteter work-graph existiert."
---

# agent-mapper

Ziel ist eine kurze Liste wiederverwendbarer Agenten, keine lange Liste von Bots. Ein Agent ist
eine Fähigkeit („Dokumente auslesen", „Marktkommunikation abwickeln"), die in vielen Rollen
Aufgaben übernimmt. Genau diese Bündelung macht aus 200 bewerteten Aufgaben ein Backlog von
zehn Vorhaben, das man priorisieren kann.

Du entscheidest, wie gebündelt wird; das Skript rechnet Abdeckung, Priorität, Sourcing und
Horizont. Voraussetzung: Projektordner mit Graph nach `task-scorer` (Aufgaben haben `mode`).

## Ablauf

### 1. Kandidaten exportieren

```
python3 <skill>/scripts/export_agent_candidates.py --project ./projekte/<name>
```

Schreibt `20_graph/agents_todo.json`: alle Aufgaben mit Modus `ai_assisted` oder
`agent_delegated`, nach einem Mustervorschlag gruppiert (Keyword-Heuristik aus
`references/agent-patterns.md`), plus bereits vorhandene Agenten. Der Vorschlag ist ein
Startpunkt, nicht die Wahrheit: „Rechnungen prüfen" und „Vertragsentwurf gegen Musterklauseln
prüfen" landen beide bei `quality-review`, gehören aber fachlich in verschiedene Agenten.

### 2. Bestehende KI-Anwendungen erfragen

Frage den Nutzer einmal, welche KI-Anwendungen oder Automatisierungen im Bereich schon laufen
(z. B. „Agent für Zählerstandsverarbeitung, live seit 2025"). Lege sie als Agenten mit
`status: live` und `existing_system` an und ordne ihnen die Aufgaben zu, die sie tatsächlich
abdecken. Ohne diesen Schritt schlägt die Analyse Dinge vor, die es schon gibt, und verliert
sofort Glaubwürdigkeit beim Fachbereich. Wenn der Nutzer nicht erreichbar ist, arbeite ohne
und sage das im Ergebnis.

### 3. Agenten definieren

Lies `references/agent-patterns.md` (Katalog, Namensregel, Zuordnungsregeln). Dann schreibe
`20_graph/agents.json` als Liste:

```json
[
  {
    "name": "Marktkommunikations-Agent Lieferantenwechsel",
    "pattern": "market-communication",
    "capability": "Nimmt An- und Abmeldungen sowie Stammdatenänderungen aus Portal und EDIFACT entgegen, prüft Vollständigkeit, legt Vorgänge in SAP IS-U an und löst die Marktkommunikation aus. Eskaliert Datenkonflikte an die Sachbearbeitung.",
    "specificity": "proprietary",
    "status": "proposed",
    "complexity": 4,
    "existing_system": null,
    "oversight": "Stichprobe 5 % täglich durch Sachbearbeitung; Vier-Augen-Prinzip bei jeder Ablehnung; kein autonomer Versand bei Kündigungen.",
    "prerequisites": ["Schreibzugriff SAP IS-U über zertifizierte Schnittstelle", "Regelwerk GPKE-Fristen als Konfiguration", "Beteiligung Betriebsrat (Leistungsüberwachung)"],
    "task_ids": ["ta_...", "ta_..."]
  }
]
```

Worauf es ankommt:

- Jede nicht-manuelle Aufgabe genau einem Agenten. Manuelle Aufgaben keinem. Das Skript weist
  Verstöße ab und meldet nicht zugeordnete Aufgaben.
- Richtwert 6–15 Agenten je Bereich. Wenn zwei Agenten dasselbe Muster und dieselben
  Vorbedingungen haben, sind sie einer.
- `capability` beschreibt Eingang, Verarbeitung, Ausgang und was eskaliert wird. Das ist der
  Text, den später jemand liest, der entscheiden muss, ob er das bauen lässt.
- `oversight` ist bei regulierten Rollen Pflicht und muss einen konkreten Kontrollpunkt nennen.
  „Mensch prüft" ist keiner; „Freigabe vor Versand bei Beträgen über 500 €" ist einer.
- `specificity` ehrlich einschätzen: Was ein Copilot heute kann, ist `generic`, auch wenn es
  sich energiewirtschaftlich anfühlt. `proprietary` ist es erst, wenn es an eigenen Prozessen
  oder Systemen hängt.

### 4. Abdeckung rechnen

```
python3 <skill>/scripts/compute_coverage.py --project ./projekte/<name>
```

Das Skript vergibt IDs (Hash des Agentennamens), verknüpft Aufgaben, berechnet je Agent die
Abdeckung je Rolle (Σ Zeitanteil × Automatisierungspotenzial/10, in Prozent der
Rollenarbeitszeit), das FTE-Äquivalent (wo Headcounts bekannt sind), Sourcing
(generic→buy, domain→hybrid, proprietary→build), den frühesten Horizont und zwei Rangfolgen:
`priority_rank` nach Wert (FTE-Äquivalent, sonst Abdeckungspunkte) und `sequence_rank` als
Bau-Reihenfolge (kurzfristiger Horizont und geringe Komplexität zuerst, dann Wert). Der wertvollste
Agent ist oft nicht der erste, den man baut; berichte beide Rangfolgen und sage, wo sie auseinanderfallen.
Ergebnis: neue Graph-Version `work-graph_vNNN_mapper.json`.

### 4b. Capability Contract je Agent, der gebaut werden soll

Ein Agent mit Namen, Muster und Aufgabenliste reicht für eine Portfoliodiskussion. Er reicht
nicht, um ihn zu bauen, zu betreiben oder freizugeben. Dafür braucht er einen Vertrag:
was ihn auslöst, worauf er zugreift, wie weit seine Entscheidung reicht, was passiert, wenn er
scheitert, und woran man merkt, dass er schlechter geworden ist.

Format und Regeln: `references/contract-format.md`. Der Vertrag steht als `contract` im
jeweiligen Eintrag von `agents.json`.

**Nenne keine Modellnamen.** Nicht aus Prinzipienreiterei, sondern weil Modelle schneller
wechseln als Prozesse: Ein Vertrag, der ein Modell festlegt, erzwingt bei jedem Wechsel eine
Prozessänderung und eine neue Freigabe. Was gebraucht wird, steht als Anforderung in
`capability_profile`. Der Validator lehnt konkrete Modellnamen ab.

Drei Regeln setzt der Validator durch. Alle drei stammen aus derselben Erfahrung:
Agentenprojekte scheitern nicht am Modell, sondern am Betrieb.

- Schreibrechte brauchen `audit_events` und `idempotency_key`. Eine Schreibaktion ohne Spur ist
  nicht prüfbar; ein Wiederholungslauf ohne Schlüssel schreibt doppelt.
- `decision_scope: execute_irreversible` braucht einen `human_checkpoint`. Was sich nicht
  zurücknehmen lässt, entscheidet kein Agent allein.
- Status `pilot` oder `live` braucht ein `evaluation_set`. Ohne Testmenge merkt niemand, wenn
  die Qualität nachlässt.

```
python3 <skill>/scripts/validate_contracts.py --project ./projekte/<name>
python3 <skill>/scripts/export_contracts.py --project ./projekte/<name>
```

`validate_contracts.py` prüft zusätzlich gegen den Prozess: Reicht die Entscheidungsreichweite
für die Schritte, die der Agent ausführt? Soll er in ein System schreiben, das ohne
Schnittstelle erfasst ist? Tragen seine Schritte Kontrollen, die der Vertrag nicht abbildet?

Ein Agent kann andere koordinieren (`orchestrates`). Der Orchestrator sollte dann keine eigenen
Schreibrechte haben — sonst ist im Fehlerfall nicht mehr feststellbar, wer geschrieben hat.

### 5. Ergebnis prüfen und berichten

Sieh dir `agents[]` im Graphen an. Nenne dem Nutzer die fünf Agenten mit höchstem Wert
(`priority_rank`) und die ersten drei der Bau-Reihenfolge (`sequence_rank`), jeweils mit
FTE-Äquivalent (oder Abdeckungspunkten), Sourcing, Horizont und der wichtigsten Vorbedingung. Weise auf nicht zugeordnete Aufgaben hin. Wenn ein einzelner Agent mehr als die
Hälfte aller Abdeckungspunkte trägt, ist er vermutlich zu breit geschnitten; schlage eine Teilung vor.

Nächster Schritt: `process-redesigner`, wenn Prozesse erfasst sind — sonst
`transformation-dashboard`.

## Ein Prozessschritt, mehrere Fähigkeiten

Im Diagnosemodus gilt: genau ein Agent je nicht-manueller Aufgabe. Für eine Opportunity Map ist
das die ehrlichere Darstellung, weil sich Abdeckungen dann addieren lassen.

Im Redesignmodus stimmt die Annahme nicht mehr. Ein Prozessschritt kann menschliche,
regelbasierte, systemische und agentische Fähigkeiten kombinieren, und ein Orchestrator
koordiniert mehrere Spezialagenten. `compute_coverage.py --shared-tasks` lässt
Überschneidungen zu, weist sie je Agent aus (`overlap_task_ids`) und meldet am Ende eine
bereinigte Gesamtabdeckung. **Diese bereinigte Zahl gehört in die Portfoliodiskussion** — die
Summe der Einzelagenten zählt dieselbe Arbeit mehrfach.

## Neue Rollen

Wenn die Agentenbibliothek eine Aufsichtsrolle nahelegt (z. B. „Agent Manager Kundenservice",
der Stichproben, Eskalationen und Regelpflege übernimmt), gehört sie als Rolle mit
`is_new: true` in eine Extraktionsdatei von `work-graph-builder`, nicht in `agents.json`.
Der Scorer klassifiziert sie dann als `emerging`.

## Ab Schema 1.2

- **Evidenzgrad.** Jeder Agent trägt `evidence_grade` (`heuristic`, `expert_confirmed`, `proven`; Standard `heuristic`). Ein
  Vorschlag aus Musterzuordnung ist keine geprüfte Passung. Setze `expert_confirmed` nur, wenn ein Fachexperte zugestimmt hat.
- **Use-Case-Register.** `scripts/import_usecases.py` liest `00_input/usecases.csv` (Name, Eigentümer, Wert, Aufgaben) ein.
  Daraus entsteht, für wie viele Rollen und FTE ein Use Case gilt.
- **Reichweite und Blindflecken.** `scripts/export_reach.py` schreibt `reach_vNNN.md/.csv`: je Agent und Use Case die betroffenen
  Rollen mit Zeitanteil und FTE, und die Prozesse im Band „Jetzt“ oder „Als Nächstes“, für die niemand etwas angefragt hat.
- **Nutzungsstand.** `scripts/import_adoption.py` liest `00_input/adoption.csv` (Agent, Rolle, priorisiert, im Bau, in Nutzung).
  Nur Rolle × Agent, nie Person × Agent. Rollen mit weniger als 5 Stellen werden unterdrückt gespeichert. Das ist Datenschutz
  als Regel: Der Validator lehnt jeden Satz darunter ab.
- **Skill-Export.** `scripts/export_skill.py [--agent "Name"]` macht aus dem Vertrag ein Skill-Gerüst (SKILL.md, deterministisches
  `run.py` mit Eingabeprüfung, Idempotenz, Konfidenzschwelle, Rückfall und Audit, Testmengen-Hülle, Nutzungsmeldung). Es ist ein
  Gerüst: Die Systemaufrufe fehlen, die Testmenge ist leer. Sag das so.

## Referenzautomatisierungen (ab 0.4)

Liegt `00_input/referenzautomatisierungen.csv` vor (Format in `work-graph-builder/references/datenaufbereitung.md`), nennt
`export_agent_candidates.py` je Aufgabenkandidat bis zu drei passende Referenzen mit Quelle und Evidenzgrad. Eine Referenz zeigt, dass es so etwas
gibt, nicht, dass es hier passt. Ohne Quelle wird sie nicht geführt; der Agent bleibt `heuristic`, bis ein Fachexperte die Passung bestätigt.

## Rollen-Setup auf Zuruf (ab 0.5)

Sagt der Nutzer, für welche Rolle er einen Arbeitsagenten braucht („Baue das Setup für den Forderungsmanager“), erzeugst du ein Paket:

```
python3 <skill>/scripts/build_role_setup.py --project ./projekte/<name> --list                    # Rollen mit Skill-Kandidaten
python3 <skill>/scripts/build_role_setup.py --project ./projekte/<name> --role "<Rolle>" [--skills 4]
python3 <skill>/scripts/check_role_setup.py --package 40_output/rollen_setup/<rolle> [--strict]
```

Das Paket enthält die Rollen.md (vorbelegt aus dem Graphen, Rest „offen“), Interview-Prompt, schlanken Agenten-Prompt, drei bis fünf Skills mit
Testfall-Gerüst, Tool-Tabelle und inaktive Routinen. Du sagst dem Nutzer ehrlich, was es ist: **ein Startpunkt, ungetestet, ohne Freigabe.**
Erfinde keinen Kontext, schreibe keine echten Testfälle und aktiviere keine Routine; das tun der Nutzer und der Test. Die Begründung der Struktur und die
Grenzen stehen in `references/rollen-setup.md`. Läuft das Skript erneut, überschreibt es bearbeitete Dateien nicht (`.vorschlag` daneben).

### Nur die Rollen.md, für eine oder mehrere Rollen

Will der Nutzer nur die Kontextdatei für ein Agenten-Harness (ohne Skills, Tools und Routinen):

```
python3 <skill>/scripts/build_rollen_md.py --project ./projekte/<name> --role "<Rolle>" [--role "<weitere Rolle>" | --role "A;B"] [--all] [--split]
```

Die **Rollen.md** hat fünf Abschnitte: 1) Firmenprofil (einmal), dann je Rolle 2) Rollenprofil (mit Zeitfressern), 3) Team-Kontext (Übergaben mit Kanal),
4) Prioritäten & Ziele (monatlich aktualisieren), 5) Arbeits- & Kommunikationsstil. Alles, was der Graph nicht weiß, steht als „❓ offen“; Abgeleitetes ist
als „bitte bestätigen“ markiert. Sag dem Nutzer, dass die offenen Felder aus einem Gespräch kommen müssen (Interview-Prompt im Setup-Paket), und erfinde
nichts. Mit `--split` entsteht je Rolle eine Datei.

### Den Rest nicht per Frage und Antwort erfragen (ab 0.7)

Was der Graph über eine Person nicht weiß, muss nicht nur per Interview kommen. Frage den Nutzer, ob er Material hat (freiwillig): eigene Texte, Meeting-Transkripte, Projektdokumente,
Firmentexte. Lege es unter `00_input/kontext/` ab (`firma/`, `<rolle>/texte`, `<rolle>/transkripte`, `<rolle>/projekte`), dann:

```
python3 <skill>/scripts/extract_context_evidence.py --project ./projekte/<name> [--role "<Rolle>"]
```

Das Ergebnis sind **Vorschläge mit Quelle, Fundstelle und Zitat** in `30_review/kontext_evidenz/`; `build_rollen_md.py` und `build_role_setup.py` zeigen sie als „✎ Vorschlag aus Dokument — bitte bestätigen“.
Was Skripte nicht lesen (PDF, Word, Mail, Kalender), liest du und trägst es im selben Format in `<rolle>.claude.json` ein — nur mit wörtlichem Zitat und Quelle, nichts ergänzt, nichts geschlossen.
Sag dem Nutzer: Vorschläge sind keine Tatsachen; ein Stilprofil gibt es erst ab drei Texten und 600 Wörtern; Transkripte enthalten Daten Dritter und gehören nur mit Einverständnis ins Projekt; Personennamen werden nicht gesucht.
Das Interview bleibt für Entscheidungen (Qualitätsverständnis, gewünschte Rückfrage, was nie ohne Rückfrage geschehen darf). Details: `references/kontext-aus-dokumenten.md`.
