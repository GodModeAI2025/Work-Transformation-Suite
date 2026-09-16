---
name: work-transformation
description: "Orchestriert die Work-Transformation-Suite: aus Stellenbeschreibungen oder Rollenlisten eines Bereichs entsteht ein Arbeitsgraph (Rollen, Aufgaben, Skills), jede Aufgabe wird nach KI-Automatisierbarkeit bewertet, Rollen als eliminiert/transformiert/augmentiert/stabil klassifiziert, Agenten mit Rollenabdeckung abgeleitet, Ausgabe als Dashboard, CSV und Bericht. Ruft work-graph-builder, task-scorer, agent-mapper und transformation-dashboard in fester Reihenfolge auf. IMMER verwenden bei: KI-Transformation eines Bereichs analysieren, AI Transformation Strategy, Work Architecture aufbauen, welche Rollen verändert KI, Agentic Workforce, Workforce-Transformation, 'analysier diese Abteilung auf KI-Potenzial', 'was können Agenten hier übernehmen', 'zerleg die Stellen und bewerte sie' — auch wenn der Nutzer nur Stellenbeschreibungen hochlädt und fragt, wo KI helfen kann, oder einen Projektordner mit work-graph.json nennt und 'weiter machen' sagt."
---

# work-transformation

Diese Suite baut einen Arbeitsgraphen (Rollen, Aufgaben, Skills) und bewertet ihn auf
KI-Wirkung, in vier Schritten mit einem gemeinsamen Datenformat
(`work-graph.json`) in einem Projektordner. Jeder Schritt ist ein eigener Skill mit eigener
SKILL.md; dieser Skill sagt dir, welcher Schritt dran ist, und hält die Arbeitsteilung sauber:
Du urteilst (Extraktion, Bewertung, Agentenbündelung), Skripte rechnen (IDs, Aggregation,
Klassifikation, Abdeckung, Dashboard). Nichts, was ein Skript berechnet, setzt du von Hand.

Die vier Skills liegen als Geschwisterordner neben diesem (`../work-graph-builder` usw.).
Skript-Pfade sind relativ zum jeweiligen Skill-Ordner, Projektpfade relativ zum Arbeitsverzeichnis.

## Ablauf in einem Bild

```
00_input/            Quellen (Mensch)
   │  work-graph-builder: Claude extrahiert → 10_extraction/extract_*.json
   ▼  build_graph.py → 20_graph/work-graph_v001_builder.json
   │  make_review_list.py → 30_review/review_v001.md  ← Fachexperten → overrides.csv
   ▼  apply_overrides.py → v002_review (nur wenn overrides.csv Zeilen enthält)
   │  task-scorer: export_scoring_sheet.py → Claude bewertet → 20_graph/scores.json
   ▼  score_roles.py → v003_scorer (Modus, HAS, Horizont, Disruptionstyp je Rolle)
   │  agent-mapper: export_agent_candidates.py → Claude bündelt → 20_graph/agents.json
   ▼  compute_coverage.py → v004_mapper (Abdeckung, FTE, Sourcing, Priorität)
   │  transformation-dashboard: build_dashboard.py
   ▼  40_output/dashboard_v004.html, roles/tasks/agents CSV, report.md
```

## Wie du vorgehst

### Zustand feststellen

Wenn der Nutzer einen Projektordner nennt oder „weiter machen" sagt:

```
python3 <skill>/scripts/run_pipeline.py --project ./projekte/<name>
```

Das Skript führt alle deterministischen Schritte aus, die möglich sind, und stoppt mit einer
klaren Meldung, sobald ein Artefakt fehlt, das nur du erzeugen kannst (Extraktionsdateien,
`scores.json`, `agents.json`). Diese Meldung ist deine Aufgabenliste. Lies dann die SKILL.md
des genannten Skills und arbeite den Schritt ab, danach wieder `run_pipeline.py`.

Wenn es noch kein Projekt gibt: erst `python3 ../work-graph-builder/scripts/init_project.py`,
Quellen nach `00_input/`, dann Skill `work-graph-builder`.

### Klärung am Anfang, einmal

Bevor du extrahierst, kläre mit dem Nutzer drei Dinge (oder entscheide sie selbst und sage es,
wenn niemand antwortet): Welcher Bereich genau (Scope, damit Jobfamilie/Cluster konsistent
werden)? Gibt es Headcounts je Rolle (ohne sie kein FTE-Äquivalent, die Analyse funktioniert
trotzdem)? Welche KI-Anwendungen laufen dort bereits (sonst schlägt der Mapper Vorhandenes vor)?
Mehr Fragen braucht es nicht; alles Weitere klärt das Expertenreview.

### Qualität statt Geschwindigkeit an drei Stellen

- Extraktion: 5–12 Aufgaben je Rolle, Verb-Objekt-Form, Zeitanteile in 5er-Schritten,
  Skillnamen aus der Taxonomie. Hier entsteht die Datenqualität, die alles Weitere trägt.
- Bewertung: Rubrik vollständig lesen, rollenweise bewerten, Kalibrierungsbeispiele als Anker.
  Eine zu optimistische 8 bei „Kulanz entscheiden" macht aus einer augmentierten Rolle eine
  eliminierte, und genau so ein Fehler kostet die Glaubwürdigkeit der ganzen Analyse.
- Agenten: wenige, wiederverwendbare Agenten mit konkreten Kontrollpunkten und Vorbedingungen.

### Reproduzierbarkeit

Die Skripte sind deterministisch: gleiche Eingaben, gleiche Bytes. IDs sind Hashes der Namen,
Referenzlisten sortiert, keine Zeitstempel (außer `--stamp` beim Dashboard). Jede Graph-Version
bleibt in `20_graph/` liegen; `project.json` zählt hoch. Ein Schritt ohne inhaltliche Änderung
legt keine neue Version an („Unverändert"), die Versionsnummern im Bild oben sind deshalb nur
ein Beispiel; ohne Overrides folgt auf v001_builder direkt v002_scorer. Manuelle Korrekturen gehören ausschließlich
in `30_review/overrides.csv`, sie werden bei jedem Lauf erneut angewendet und überleben so
alle Neuberechnungen. Wenn du selbst eine Bewertung ändern willst, ändere `scores.json` und
rechne mit `--force`; wenn ein Experte sie ändert, gehört es in die Overrides. So bleibt
nachvollziehbar, was Maschine und was Mensch entschieden hat.

`python3 <skill>/scripts/check_suite.py` prüft, ob alle Skills vorhanden, die gemeinsamen
Bibliotheksdateien identisch und die Frontmatter-Blöcke gültig sind.

### Was du am Ende lieferst

Dashboard (HTML), die drei CSVs und den Bericht aus `40_output/`, plus eine Einordnung in
wenigen Sätzen: Verteilung der Disruptionstypen, die drei priorisierten Agenten, Anteil der
expertengeprüften Rollen, und der Hinweis, dass die Bewertungen KI-generiert sind und ihre
Belastbarkeit erst nach dem Review feststeht. Wenn ein Ordner des Nutzers verbunden ist, lege
den Projektordner dort ab; er ist die eigentliche Arbeitsgrundlage, nicht das HTML.

## Grenzen, die du benennst

Die Suite liefert Stände, keine lebende Datenbank; keine Integration in SuccessFactors oder
andere HR-Systeme; kein Tracking, ob Agenten nach dem Rollout tatsächlich genutzt werden.
Für einen Bereich ist sie ein vollständiges Analysewerkzeug, vom Piloten mit 20–40 Rollen bis zu
über 200 Rollen in einem Lauf; für einen Konzernrollout ist sie die Machbarkeitsstudie, die vor
einem Kauf steht.
