---
name: task-scorer
description: "Bewertet jede Aufgabe eines Arbeitsgraphen (work-graph.json aus work-graph-builder) nach Automatisierungspotenzial, menschlichem Urteil, Produktivitätshebel, Datenlage und Fehlerfolgen und leitet daraus deterministisch Ausführungsmodus (manuell / KI-unterstützt / an Agent delegiert), Human-Agency-Level, Zeithorizont sowie je Rolle Disruptionsscore und Disruptionstyp (eliminiert, transformiert, augmentiert, entstehend, stabil) mit Handlungsempfehlung ab. Zweiter Schritt der Work-Transformation-Suite. IMMER verwenden bei: Aufgaben bewerten, Automatisierungspotenzial, KI-Potenzial je Rolle, welche Rollen verändert KI, Disruptionsanalyse, Human Agency Scale, HAS-Level, Automatisierung vs. Augmentation, AI Transformation Strategy, Rollenmatrix, 'was kann ein Agent übernehmen', 'welche Jobs sind betroffen', Rollenbewertung wie bei kommerziellen Work-Architecture-Plattformen, Workforce-Impact von KI — auch wenn der Nutzer nur fragt 'wie stark trifft KI diese Abteilung' und ein Projektordner mit work-graph existiert."
---

# task-scorer

Du bewertest Aufgaben, das Skript rechnet Rollen. Deine Bewertung ist der einzige
nicht-deterministische Schritt; alles danach (Modus, HAS-Level, Horizont, Rollenaggregation,
Disruptionstyp, Empfehlungstexte) folgt festen Regeln aus `references/rubric.md`, die als
Konstanten in `scripts/score_roles.py` stehen. Ändere Schwellen nur dort, nie durch
Nachjustieren deiner Werte, damit das Ergebnis erklärbar bleibt.

Voraussetzung: ein Projektordner mit `20_graph/work-graph_latest.json` (aus `work-graph-builder`).
Skript-Pfade relativ zum Skill-Ordner, Projektpfade relativ zum Arbeitsverzeichnis.

## Ablauf

### 1. Bewertungsvorlage exportieren

```
python3 <skill>/scripts/export_scoring_sheet.py --project ./projekte/<name>
```

Schreibt `20_graph/scores_todo.json`: alle noch unbewerteten Aufgaben, rollenweise gruppiert,
mit Kontext (`_context`: Rolle, Cluster, Archetyp, reguliert, Beschreibung, Workflow-Schritte,
Zeitanteil, Skills). Mit `--all` auch bereits bewertete Aufgaben (für Neubewertung).

### 2. Bewerten

Lies `references/rubric.md` vollständig, bevor du die erste Zahl setzt. Dann fülle je Aufgabe
die sechs Felder `automation_ai`, `automation_physical`, `human_judgment`,
`productivity_boost`, `data_readiness`, `consequence_of_error` (ganze Zahlen 0–10) und
`rationale` aus und speichere das Ergebnis als `20_graph/scores.json`. Den `_context`-Block
kannst du mitkopieren oder weglassen, das Skript ignoriert ihn.

Was eine gute Bewertung ausmacht:

- Bewerte rollenweise in der Reihenfolge der Vorlage, damit du innerhalb einer Rolle
  konsistent bleibst. Vergleiche Aufgaben derselben Rolle gegeneinander: Wenn „Kundenmails
  klassifizieren" eine 9 bekommt, kann „Standardantworten versenden" keine 5 sein.
- Nutze die Kalibrierungsbeispiele in der Rubrik als Anker. Wenn du unsicher bist, ob 6 oder 7:
  Welche der beiden Ankerbeschreibungen passt besser? Nicht mitteln.
- Bewerte den Stand der Technik von heute, nicht die Zukunft. Die Zukunft steckt in
  `data_readiness`: Was an Daten scheitert, wird mittelfristig, nicht unmöglich.
- `automation_physical` ist 0 für rein kognitive Aufgaben. Nicht raten.
- `rationale` so schreiben, dass ein Fachexperte in einem Satz widersprechen kann.
  „Regelbasiert" allein reicht nicht; nenne den Schritt, der die Einordnung trägt.
- Bei regulierten Rollen die Fehlerfolge nicht beschönigen: Delegation scheitert dort an
  `consequence_of_error > 3`, und das ist richtig so.
- Bei mehr als etwa 60 Aufgaben: in Blöcken je Rolle arbeiten, nach jedem Block speichern,
  damit nichts verloren geht. Das Skript nimmt Teilstände an (`--force` nur bei Neubewertung).

### 3. Rechnen

```
python3 <skill>/scripts/score_roles.py --project ./projekte/<name>
```

Das Skript übernimmt `scores.json` (nur für Aufgaben ohne Scores; `--force` nur nötig, wenn der
Graph noch alte Scores enthält, die ersetzt werden sollen), wendet
Score-Overrides aus `30_review/overrides.csv` an (`task;<id>;scores.human_judgment;7;...`),
leitet Modus/HAS/Horizont ab, aggregiert je Rolle und schreibt eine neue Graph-Version
`work-graph_vNNN_scorer.json`. Es meldet Hinweise (fehlende Felder, unbekannte IDs) und die
Verteilung der Disruptionstypen.

Je Rolle stehen in `analysis` zusätzlich zwei Einordnungen, die du im Bericht immer nennst:

- `evidence` (Belastbarkeit: high / medium / low, mit `evidence_reasons`): ob Zeitanteile aus
  der Quelle stammen, ob Experten geprüft haben, wie viel aus abgeleiteten Aufgaben stammt und
  ob der Headcount bekannt ist. Eine Rolle mit `low` ist eine plausible Geschichte, keine Messung.
- `stability` (stable / borderline / fragile, mit `flip_share` und `flip_examples`): die
  Kipp-Analyse prüft für jede Aufgabe, ob eine Änderung um ±1 an Maschinenanteil, Urteilsbedarf
  oder Fehlergewicht die Rollenwirkung ändert. `fragile` heißt, dass die Einstufung an einer
  einzelnen Bewertung hängt; nenne dann das Beispiel aus `flip_examples`, damit der Experte genau
  diese Aufgabe zuerst prüft. Unterschiede im Expositionswert unter 0,5 sind Rauschen; belastbar
  sind Quadranten, nicht Rangfolgen innerhalb eines Quadranten.

### 4. Plausibilisieren, bevor du übergibst

Lies die Rollenwerte aus dem Graphen (`roles[].analysis`; je Aufgabe stehen `mode`, `has_level`,
`horizon`, `automation_potential` direkt am Task-Objekt) und prüfe drei Dinge:

- Gibt es Rollen mit `eliminated`, die reguliert sind oder hohes Urteil verlangen? Dann ist
  vermutlich eine Aufgabenbewertung zu optimistisch. Korrigiere in `scores.json` und rechne
  mit `--force` neu, oder trage einen Override ein.
- Ist die Verteilung plausibel? In einer typischen Sachbearbeitungsabteilung landen die meisten
  Rollen bei `transformed` oder `augmented`; nur `stable` oder nur `eliminated` ist ein Warnsignal.
- Passen `retained_skills` (bleiben gebraucht) und `declining_skills` (Bedarf sinkt) zu dem, was ein Personaler erwarten würde?

Berichte dem Nutzer je Rolle: Disruptionstyp, Score, Anteile (menschlicher Kern = manuell /
KI-assistiert / an Agent delegiert),
Horizont und die zwei wichtigsten Begründungen. Sage, welche Bewertungen du für unsicher
hältst und Expertenreview brauchen. Nächster Schritt: `agent-mapper`.

## Expertenkalibrierung

Wenn Fachexperten Bewertungen korrigieren, gehören die Korrekturen als Overrides in
`30_review/overrides.csv` (Feld `scores.<name>`), nicht in `scores.json`. Overrides gewinnen bei
jedem Lauf. Nach einer Review-Runde:

```
python3 <skill>/scripts/calibrate.py --project ./projekte/<name>
```

Der Bericht `30_review/calibration_vNNN.md` zeigt je Bewertungsfeld, ob die Experten systematisch
höher oder niedriger liegen als die generierten Werte (ab fünf Korrekturen mit mittlerer
Abweichung ≥ 0,75), und welche Rollenwirkungen sich durch die Korrekturen geändert haben. Bei
einer Systematik verschiebst du den Anker in `references/rubric.md` oder die Schwelle in
`scripts/score_roles.py`, statt still weiter einzeln zu korrigieren; sag dem Nutzer, was du
änderst und warum.
