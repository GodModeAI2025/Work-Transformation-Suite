---
name: agent-mapper
description: "Bündelt die delegier- und assistierbaren Aufgaben eines bewerteten Arbeitsgraphen (work-graph.json nach task-scorer) zu einer Agentenbibliothek aus wiederverwendbaren KI-Agenten und berechnet deterministisch je Agent, welche Rollen er zu wie viel Prozent abdeckt, FTE-Äquivalent, Build/Buy/Hybrid, Zeithorizont und Priorität; gleicht bestehende KI-Anwendungen des Unternehmens ab. Dritter Schritt der Work-Transformation-Suite. IMMER verwenden bei: Agentenbibliothek, Agentic Workforce Library, welche Agenten brauchen wir, Agenten zu Rollen zuordnen, Rollenabdeckung durch Agenten, Build or Buy für KI-Agenten, Agent-Katalog, Agentenlandkarte, Automatisierungs-Backlog priorisieren, 'welcher Agent übernimmt was', KI-Use-Cases aus Aufgaben ableiten, Agent Coverage — auch wenn der Nutzer nur fragt 'was sollen wir zuerst automatisieren' und ein bewerteter work-graph existiert."
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
