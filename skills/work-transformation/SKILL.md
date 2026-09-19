---
name: work-transformation
description: "Orchestriert die Work-Transformation-Suite in zwei Modi. Diagnose: aus Stellenbeschreibungen eines Bereichs entsteht ein Arbeitsgraph (Rollen, Aufgaben, Skills), jede Aufgabe wird nach KI-Automatisierbarkeit bewertet, Rollen als eliminiert/transformiert/augmentiert/stabil klassifiziert, Agenten mit Rollenabdeckung und Capability Contracts abgeleitet. Redesign: aus Prozessaufnahmen entstehen KI-native Soll-Prozesse in drei Szenarien, mehrdimensional priorisiert, mit gerechneten Deltas und messbarem Pilotplan. Ausgabe als Dashboard, CSV und Bericht. IMMER verwenden bei: KI-Transformation eines Bereichs analysieren, AI Transformation Strategy, Work Architecture aufbauen, welche Rollen verändert KI, Agentic Workforce, Prozess neu denken, 'analysier diese Abteilung auf KI-Potenzial', 'was können Agenten hier übernehmen', 'wie sähe der Prozess aus, wenn wir ihn heute neu bauen würden' — auch wenn der Nutzer nur Stellenbeschreibungen hochlädt oder einen Projektordner nennt und 'weiter machen' sagt."
---

# work-transformation

Diese Suite beantwortet zwei Fragen, und die Reihenfolge ist wichtig.

**Diagnose:** Welche heutige Arbeit kann KI übernehmen? Dafür baut sie einen Arbeitsgraphen
(Rollen, Aufgaben, Skills) und bewertet ihn.

**Redesign:** Wie sähe der Prozess aus, wenn man ihn vom gewünschten Ergebnis aus neu bauen
würde — und woran misst man, ob das besser ist? Dafür braucht sie zusätzlich eine
Prozessaufnahme.

Der Unterschied ist nicht akademisch. Wenn fünf Rollen nacheinander dieselben Daten prüfen,
findet die Diagnose fünf automatisierbare Aufgaben und schlägt einen Agenten vor. Ein
Redesign streicht vier Prüfungen, drei Übergaben und zwei Datenumformungen — und der Rest
braucht gar keinen Agenten mehr.

Die Diagnose ist für sich vollständig. Ein Projekt darf darin bleiben; der Redesignmodus
schaltet sich ein, sobald Prozesse erfasst sind.

Jeder Schritt ist ein eigener Skill mit eigener SKILL.md; dieser Skill sagt dir, welcher
Schritt dran ist, und hält die Arbeitsteilung sauber: Du urteilst (Extraktion, Bewertung,
Agentenbündelung, Soll-Entwürfe, Prozesswert, Pilotpläne), Skripte rechnen (IDs, Aggregation,
Klassifikation, Abdeckung, Deltas, Dashboard). **Nichts, was ein Skript berechnet, setzt du
von Hand — vor allem kein Delta.**

Die Skills liegen als Geschwisterordner neben diesem (`../work-graph-builder` usw.).
Skript-Pfade sind relativ zum jeweiligen Skill-Ordner, Projektpfade relativ zum Arbeitsverzeichnis.

## Ablauf in einem Bild

```
00_input/            Quellen (Mensch)
   │  work-graph-builder: Claude extrahiert → 10_extraction/extract_*.json
   ▼  build_graph.py → 20_graph/work-graph_vNNN_builder.json
   │  make_review_list.py → 30_review/review_vNNN.md  ← Fachexperten → overrides.csv
   ▼  apply_overrides.py (nur wenn overrides.csv Zeilen enthält)
   │  work-graph-builder: Claude nimmt Prozesse auf → 10_extraction/process_*.json   [optional]
   ▼  build_processes.py → Prozesse, Schritte, Kanten, Systeme, Kontrollen, Kennzahlen
   │  task-scorer: export_scoring_sheet.py → Claude bewertet → 20_graph/scores.json
   ▼  score_roles.py → Modus, HAS, Horizont, Disruptionstyp je Rolle
   │  agent-mapper: export_agent_candidates.py → Claude bündelt → 20_graph/agents.json
   ▼  compute_coverage.py → Abdeckung, FTE, Sourcing, Priorität, Capability Contracts
   │  process-redesigner: export_process_candidates.py                               [nur mit Prozessen]
   │  → Claude entwirft drei Szenarien je Prozess → 20_graph/blueprints.json
   ▼  build_blueprints.py → Soll-Kennzahlen und Deltas · validate_blueprints.py
   │  → Claude bewertet den Prozesswert → 20_graph/process_value.json
   ▼  score_processes.py → Prioritätsbänder mit Sensitivität
   │  → Claude schärft die Pilotkarten → 20_graph/experiments.json
   ▼  make_experiments.py · compare_scenarios.py → 40_output/scenarios_vNNN.md
   │  apply_governance.py ← 30_review/decisions.csv (Freigaben, zuletzt angewendet)
   ▼  transformation-dashboard: build_dashboard.py
      40_output/dashboard_vNNN.html, CSV-Exporte, report_vNNN.md
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

Wenn das Projekt aus einer älteren Version stammt (Schema 1.0): einmal
`python3 ../work-graph-builder/scripts/migrate_graph.py --project ./projekte/<name>`.
Die Migration ist additiv und verlustfrei; sie legt die Prozesssammlungen leer an und rät nichts.

### Klärung am Anfang, einmal

Bevor du extrahierst, kläre mit dem Nutzer vier Dinge (oder entscheide sie selbst und sage es,
wenn niemand antwortet): Welcher Bereich genau (Scope, damit Jobfamilie/Cluster konsistent
werden)? Gibt es Headcounts je Rolle (ohne sie kein FTE-Äquivalent, die Analyse funktioniert
trotzdem)? Welche KI-Anwendungen laufen dort bereits (sonst schlägt der Mapper Vorhandenes vor)?
Und: Soll es bei der Diagnose bleiben, oder sollen auch Soll-Prozesse entworfen werden?

Die vierte Frage entscheidet über den Aufwand. Für den Redesignmodus brauchst du eine
Prozessaufnahme — Auslöser, Schritte, Übergaben, Bearbeitungs- und Wartezeiten, Kontrollen,
Ausgangskennzahlen. Das steht nicht in Stellenbeschreibungen. Es kommt aus Interviews,
Systemexporten oder Prozessbeobachtung. Sag das, bevor jemand erwartet, dass aus einem Stapel
Stellenbeschreibungen ein Soll-Betriebsmodell fällt.

Mehr Fragen braucht es nicht; alles Weitere klärt das Expertenreview.

### Qualität statt Geschwindigkeit an drei Stellen

- Extraktion: 5–12 Aufgaben je Rolle, Verb-Objekt-Form, Zeitanteile in 5er-Schritten,
  Skillnamen aus der Taxonomie. Hier entsteht die Datenqualität, die alles Weitere trägt.
- Bewertung: Rubrik vollständig lesen, rollenweise bewerten, Kalibrierungsbeispiele als Anker.
  Eine zu optimistische 8 bei „Kulanz entscheiden" macht aus einer augmentierten Rolle eine
  eliminierte, und genau so ein Fehler kostet die Glaubwürdigkeit der ganzen Analyse.
- Agenten: wenige, wiederverwendbare Agenten mit konkreten Kontrollpunkten und Vorbedingungen.
  Für alles, was gebaut werden soll, einen Capability Contract (`../agent-mapper/references/contract-format.md`):
  Auslöser, Rechte, Reichweite, Rückfallebene, Audit, Testmenge. Ohne Modellnamen.
- Soll-Entwürfe: drei Szenarien, die sich wirklich unterscheiden, mit Begründung, betroffener
  Kennzahl und Annahme je Änderung. Der häufigste Fehler ist, alles zu automatisieren statt
  zuerst zu streichen — der Validator lehnt das ab, und er hat recht.
- Prozesswert: Bänder, keine Rangliste. Wenn ein Band schon bei ±1 in einem einzelnen Faktor
  kippt, sag es. Eine Reihenfolge, die auf einer Schätzung von 6 gegenüber 7 beruht, trägt
  keine Investitionsentscheidung.

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

Dashboard (HTML), die CSV-Exporte und den Bericht aus `40_output/`, plus eine Einordnung in
wenigen Sätzen.

**Im Diagnosemodus:** Verteilung der Disruptionstypen, die drei priorisierten Agenten, Anteil
der expertengeprüften Rollen, und der Hinweis, dass die Bewertungen KI-generiert sind und ihre
Belastbarkeit erst nach dem Review feststeht.

**Im Redesignmodus** zusätzlich: welcher Prozess zuerst und warum (mit dem Hinweis, ob sein
Prioritätsband stabil ist), welches Szenario du empfiehlst und was es gegenüber dem
konservativen bringt, welche Pflichtkontrollen dafür angefasst werden müssen und wer sie
freigeben muss, und welche einzelne Annahme das ganze Vorhaben trägt.

Sag dazu, wie viele der Zahlen geschätzt und wie viele gemessen sind. Das ist der Satz, der
darüber entscheidet, ob die Analyse als Entscheidungsgrundlage taugt oder als Foliensatz endet.

Wenn ein Ordner des Nutzers verbunden ist, lege den Projektordner dort ab; er ist die
eigentliche Arbeitsgrundlage, nicht das HTML.

## Grenzen, die du benennst

Die Suite liefert Stände, keine lebende Datenbank; keine Integration in SuccessFactors oder
andere HR-Systeme; kein Tracking, ob Agenten nach dem Rollout tatsächlich genutzt werden.
Für einen Bereich ist sie ein vollständiges Analysewerkzeug, vom Piloten mit 20–40 Rollen bis zu
über 200 Rollen in einem Lauf; für einen Konzernrollout ist sie die Machbarkeitsstudie, die vor
einem Kauf steht.

Für den Redesignmodus kommt eine Grenze dazu, die du aktiv aussprechen musst: **Ein Soll-Prozess
aus Interviews und Stellenbeschreibungen ist ein Entwurf, keine Prognose.** Die Suite kann aus
Rollendaten kein Unternehmen verlässlich „neu bauen“. Für belastbare Soll-Prozesse braucht sie
Prozessbeobachtungen, Systemdaten und gemessene Ausgangswerte. Sag das, bevor jemand die Deltas
in eine Budgetplanung trägt.

Und noch eines: KI bringt innerhalb ihrer Fähigkeitsgrenze erhebliche Gewinne, außerhalb
verschlechtert sie Ergebnisse. Human Gates sind deshalb keine Zugeständnisse an Skeptiker,
sondern Teil des Entwurfs. Ein Szenario ohne benannte Verantwortungsgrenze ist kein mutiges
Szenario, sondern ein unfertiges.
