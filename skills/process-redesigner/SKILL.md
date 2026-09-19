---
name: process-redesigner
description: "Entwirft aus einem analysierten Arbeitsgraphen KI-native Soll-Prozesse: je priorisiertem Prozess drei vergleichbare Szenarien (konservativ, ausgewogen, agent-nativ) mit den sechs Operatoren eliminieren, vereinfachen, zusammenführen, parallelisieren, automatisieren und Human Gate erhalten; rechnet Durchlaufzeit, Übergaben, Human Touchpoints und Nacharbeit gegen den Ist-Prozess, priorisiert Prozesse mehrdimensional statt nach FTE und erzeugt messbare Pilot- und A/B-Testkarten mit Guardrails. IMMER verwenden bei: Prozess neu denken, Greenfield-Redesign, 'wie sähe der Prozess aus, wenn wir ihn heute neu bauen würden', V2 des Unternehmens, End-to-End-Prozess mit KI neu schneiden, Soll-Prozess entwerfen, Szenarien vergleichen, Übergaben und Wartezeiten eliminieren, welche Schritte braucht es überhaupt noch, Pilot planen, A/B-Test für einen Prozess, Guardrails und Abbruchkriterien festlegen, Prozesse priorisieren."
---

# process-redesigner

Dieser Skill ist die zweite Hälfte der Suite. Die erste Hälfte (`work-graph-builder`,
`task-scorer`, `agent-mapper`) beantwortet: **Welche heutige Arbeit kann KI übernehmen?**
Dieser Skill beantwortet: **Wie sähe der Prozess aus, wenn man ihn vom gewünschten
Ergebnis aus neu bauen würde — und woran misst man, ob das besser ist?**

Der Unterschied ist nicht akademisch. Wenn fünf Rollen nacheinander dieselben Daten
prüfen, findet die Diagnose fünf automatisierbare Aufgaben und schlägt einen Agenten vor.
Ein echtes Redesign streicht vier Prüfungen, drei Übergaben und zwei Datenumformungen —
und der verbleibende Rest braucht gar keinen Agenten mehr. Wert entsteht auf der Ebene
des Ablaufs, nicht der Einzelaufgabe.

## Voraussetzung

Der Graph muss Prozesse enthalten (Schema 1.1). Wenn nicht:

```
python3 ../work-graph-builder/scripts/migrate_graph.py --project ./projekte/<name>
```

und danach Prozesse erfassen (Format: `../work-graph-builder/references/process-format.md`),
dann `build_processes.py`. Ohne Prozessebene hat dieser Skill nichts zu tun, und das ist
kein Fehler: Ein Projekt kann im Diagnosemodus bleiben.

## Ablauf

```
   export_process_candidates.py  → 20_graph/redesign_todo.json
   │                               30_review/redesign_briefing_vNNN.md
   ▼  DU entwirfst drei Szenarien → 20_graph/blueprints.json
   build_blueprints.py           → Graph-Version "redesign" (Deltas gerechnet)
   validate_blueprints.py        → Redesign-Regeln geprüft
   │  DU bewertest den Prozesswert → 20_graph/process_value.json
   ▼  score_processes.py          → Prioritätsbänder, Sensitivität
   make_experiments.py           → 20_graph/experiments_todo.json → experiments.json
   compare_scenarios.py          → 40_output/scenarios_vNNN.md und .csv
```

## Schritt 1: Kandidaten aufbereiten

```
python3 <skill>/scripts/export_process_candidates.py --project ./projekte/<name>
```

Liefert je Prozess den Ist-Fluss mit Zeiten, Kontrollen und Kennzahlen sowie maschinell
erkannte Ansatzpunkte: Liegezeiten im Verhältnis zur Arbeitszeit, Nacharbeitsquoten,
Medienbrüche bei Übergaben, mehrfach geprüfte gleiche Eingaben, Entscheidungen ohne
Kontrollpunkt. **Das sind Hinweise, keine Entscheidungen.** Lies das Briefing in
`30_review/`, bevor du entwirfst.

Wenn dort steht, dass das Modell die gemessene Durchlaufzeit nicht erklärt: erst die
Lücke schließen. Ein Redesign auf einem unvollständigen Ist-Modell rechnet auf einer zu
kleinen Grundmenge und verspricht Gewinne, die es im Betrieb nicht gibt.

## Schritt 2: Drei Szenarien entwerfen

Lies `references/redesign-rules.md` vollständig, bevor du das erste Mal entwirfst.
Format und Beispiel: `references/blueprint-format.md`.

Für jeden priorisierten Prozess **drei** Szenarien, die eine Leiter bilden:

- **Konservativ** — heutige Kontrollen bleiben unverändert, KI assistiert und senkt
  Bearbeitungszeit. Das ist die Untergrenze und der Vergleichsmaßstab.
- **Ausgewogen** — unnötige Schritte und Übergaben entfallen, KI führt zusammenhängende
  Teilketten aus, Menschen behandeln Ausnahmen.
- **Agent-nativ** — vom Zielzustand aus neu gebaut; Menschen greifen nur an begründeten
  Entscheidungs- und Verantwortungsgrenzen ein.

Jeder Soll-Schritt trägt genau einen der sechs Operatoren, eine Begründung, die betroffene
Kennzahl und die Annahme, an der die Änderung scheitern würde. Jeder gestrichene Schritt
trägt seine eigene Begründung.

Drei Dinge, die der Validator dir nicht durchgehen lässt, und warum:

1. **Alles nur `automate`.** Das ist KI auf dem Altprozess — genau der Fehler, den dieser
   Skill verhindern soll. Mindestens ein weiterer Operator muss begründet greifen.
2. **Pflichtkontrolle ersatzlos gestrichen.** Eine Kontrolle darf entfallen, aber nur mit
   dokumentiertem Ersatz und namentlicher Freigabe.
3. **Agent-nativ ohne einen einzigen Human Gate.** Wo niemand mehr eingreift, verantwortet
   auch niemand mehr etwas. Benenne die Grenze, statt sie zu verschweigen.

```
python3 <skill>/scripts/build_blueprints.py --project ./projekte/<name>
python3 <skill>/scripts/validate_blueprints.py --project ./projekte/<name>
```

`build_blueprints.py` rechnet die Soll-Kennzahlen aus deinen Schritten und stellt sie dem
Ist gegenüber. Du schreibst keine Deltas — du beschreibst den Ablauf, das Delta fällt an.
Schlägt der Entwurf Agenten vor, die es noch nicht gibt, sagt das Skript es; lege sie dann
über `../agent-mapper` an und lauf erneut.

## Schritt 3: Prozesswert bewerten

```
python3 <skill>/scripts/score_processes.py --project ./projekte/<name>
```

Beim ersten Lauf entsteht `20_graph/process_value_todo.json` mit Kontextdaten je Prozess.
Fülle die neun Faktoren auf der Skala 0..10 (Anker in `references/value-rubric.md`) und
speichere als `process_value.json`.

Das Ergebnis ist ein Prioritätsband (Jetzt, Als Nächstes, Später, Zurückstellen), keine
Rangliste auf zwei Nachkommastellen. Das Skript prüft zusätzlich, ob das Band schon
kippt, wenn ein einzelner Faktor um ±1 danebenliegt. **Wenn es kippt, sag das.** Eine
Rangfolge, die auf einer Schätzung von 6 gegenüber 7 beruht, ist keine Entscheidungsgrundlage.

## Schritt 4: Piloten planen

```
python3 <skill>/scripts/make_experiments.py --project ./projekte/<name>
```

Erzeugt beim ersten Lauf aus jedem geprüften oder freigegebenen Blueprint eine
Experimentkarte mit vorgeschlagenem Design, Laufzeit und Guardrails. Schärfe Hypothese,
Zielgruppe und Stoppregeln und speichere als `experiments.json`.
Format: `references/experiment-format.md`.

Nicht jeder Prozess verträgt einen A/B-Test. Das Skript schlägt deshalb deterministisch
eines von vier Designs vor — A/B, Schattenbetrieb, gestaffelter Rollout, Vorher-Nachher —
und begründet die Wahl. Übernimm die Begründung, oder ändere sie bewusst.

Liegen Messwerte vor, trage sie als `results` ein: Sie werden als `observed` auf die
Kennzahlen zurückgeschrieben, mit Provenienz. Ab da steht im Graphen und im Dashboard
„gemessen" statt „geschätzt" — der einzige Unterschied, der in einer
Transformationsdiskussion wirklich zählt.

## Schritt 5: Vergleich ausgeben

```
python3 <skill>/scripts/compare_scenarios.py --project ./projekte/<name>
```

Schreibt `40_output/scenarios_vNNN.md` und `.csv`: Ist und Szenarien nebeneinander,
Schritt für Schritt, mit Begründungen, veränderten Kontrollen und offenen Annahmen.
Das Dashboard (`../transformation-dashboard`) zeigt dieselben Daten interaktiv.

## Freigabe

Ein Blueprint wird nicht dadurch freigegeben, dass jemand `"status": "approved"` schreibt.
Freigaben gehören in `30_review/decisions.csv` und werden mit
`../work-graph-builder/scripts/apply_governance.py` angewendet. Der Validator lehnt einen
freigegebenen Blueprint ohne Eintrag im Entscheidungslog ab.

## Was du am Ende lieferst

Den Szenarienvergleich, die Prioritätsbänder mit dem Hinweis, welche davon kippelig sind,
die Experimentkarten — und drei Sätze Einordnung: welcher Prozess zuerst, welches Szenario
und warum, und welche Annahme das ganze Vorhaben trägt.

## Grenzen, die du benennst

Ein Soll-Prozess aus Interviews und Stellenbeschreibungen ist ein Entwurf, keine
Prognose. Die Suite kann aus Rollendaten kein Unternehmen verlässlich „neu bauen": Für
belastbare Soll-Prozesse braucht sie Prozessbeobachtungen, Systemdaten, Fachinterviews
und gemessene Ausgangswerte. Sag das, bevor jemand die Deltas in eine Budgetplanung trägt.

Und: KI bringt innerhalb ihrer Fähigkeitsgrenze erhebliche Gewinne, außerhalb verschlechtert
sie Ergebnisse. Deshalb sind Human Gates keine Zugeständnisse an die Skeptiker, sondern
Teil des Entwurfs.
