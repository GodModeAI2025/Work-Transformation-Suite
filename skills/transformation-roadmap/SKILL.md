---
name: transformation-roadmap
description: "Verteilt die Agenten und Use Cases eines bewerteten Arbeitsgraphen auf Wellen (Fahrplan-Raster) und erzeugt daraus die Unterlagen für eine Entscheidungsrunde: Entscheidungsvorlage, Einseiter für HR, Anhang mit allen Vorhaben und Methodik, je als Markdown und HTML. Zahlen und Tabellen kommen aus dem Graphen (Jobarchitektur heute und künftig, betroffene Rollen und Stellen, Wert, Reichweite, Pilotstand), Erzählendes aus Textfeldern mit Quelle; offene Felder bleiben sichtbar offen. Wellen sind Vorschläge, bis eine benannte Person sie bestätigt. Letzter Schritt der Work-Transformation-Suite. IMMER verwenden bei: Fahrplan, Roadmap, Wellenplan, Dreijahresplan, Welle 1 2 3, Reihenfolge der Automatisierungen, welche Automation zuerst, Entscheidungsvorlage, Beschlussvorlage, Unterlage für HR, Einseiter, Jobarchitektur der Zukunft darstellen, Potenzialliste für den Lenkungskreis, 'was sollen wir als Nächstes bauen', 'bereite das für die Runde auf'."
---

# transformation-roadmap

Dieses Skill beantwortet zwei Fragen, die nach der Analyse kommen: **In welcher Reihenfolge**
gehen wir die Vorhaben an, und **was legen wir einer Runde vor**, die darüber entscheidet. Es
rechnet nichts Neues über die Arbeit selbst; es ordnet an, was `task-scorer`, `agent-mapper`
und `process-redesigner` ermittelt haben, und hält fest, was noch ein Mensch entscheiden muss.

Die Aufteilung ist dieselbe wie überall in der Suite: **Skripte rechnen, Claude und Menschen
urteilen.** Das Raster ist deterministisch. Die Texte der Unterlagen schreiben Claude oder eine
Person, jeder Text mit Quelle.

## Voraussetzungen

- Ein Graph mit Agenten oder Use Cases (`agent-mapper`). Ohne sie hält das Skill mit Exit-Code 3 an
  und nennt den nächsten Schritt.
- Für Wert und FTE: Stellenzahl und Tagessatz je Rolle (`positions.csv`, `levels.csv`). Fehlen sie,
  steht „nicht bewertet“ da, nicht null.
- Für die Jobarchitektur künftig: das Zielbild der Rollen (`task-scorer/build_target_roles.py`).
- Optional: Prozesse mit Prioritätsband (`process-redesigner`) und Piloten.

## Ablauf

### 1. Raster bauen

```
python3 <skill>/scripts/plan_waves.py --project ./projekte/<name> [--config eigene-wave-config.json]
```

Ergebnis in `40_output/` (NNN = Graph-Version): `fahrplan_vNNN.md`, `.html` (Tafel mit einer Spalte je
Welle), `.csv` und `roadmap_vNNN.json`.

Wie das Raster entsteht, steht in `references/wellenlogik.md`. Kurz: Jedes Vorhaben erhält einen Score
aus Wert, Reichweite, Umsetzbarkeit, Reifegrad und Prozessrang. Laufende Vorhaben liegen in Welle 1,
schwere beginnen dort nicht, Orchestratoren folgen den Agenten, die sie steuern. Fehlende Größen
fehlen auch im Score und werden benannt. Liegt eine Befragung vor (Skill `agency-audit`), trägt jedes Vorhaben seine
überwiegende Zone; liegt mehr als die Hälfte seiner befragten Arbeit in der Vorsichtszone, beginnt es nicht in Welle 1, außer
jemand entscheidet es in `wellen.csv` (`max_red_zone_share_first_wave`).

### 2. Entscheidungen festhalten

Das Raster ist ein Vorschlag. Eine Zuordnung gilt erst, wenn eine benannte Person sie entschieden hat.
Das steht in `30_review/wellen.csv`:

```
eintrag;welle;begruendung;entschieden_von;datum
Mahnlauf-Agent;2;Ausschlussregeln noch nicht abgestimmt;Name der Person;2026-06-10
```

Zeilen ohne `entschieden_von` zählen nicht und werden gemeldet. Zeiträume setzt das Raster nicht
selbst; sie kommen als `period` je Welle in die Konfiguration. Bis dahin steht „❓ offen“ da.

### 3. Texte sammeln (Claude)

Die Unterlagen haben Textfelder, die kein Graph kennt: Anlass und Ziel, Pilot und Referenz, Vorgehen,
gewünschter Beschluss, Kernbotschaft für HR, Beteiligung und Rahmen. Claude füllt sie aus Material, das
die Person bereitstellt (Gesprächsnotizen, Transkripte, Mails, Auswertungen), und schreibt sie nach
`30_review/dokumente/texte.json`. Format und Regeln: `references/dokumente.md`.

Zwei Regeln sind hart. Jeder Text braucht eine Quelle; ohne sie wird er nicht übernommen. Und nichts wird
erfunden: Gibt das Material zu einem Feld nichts her, bleibt es leer und damit sichtbar offen.

### 4. Unterlagen bauen

```
python3 <skill>/scripts/build_documents.py --project ./projekte/<name> [--strict]
```

Ergebnis in `40_output/dokumente/`, je `.md` und `.html` (zum Drucken als PDF):

| Dokument | Inhalt |
|---|---|
| `entscheidungsvorlage` | Anlass, Ausgangslage, Jobarchitektur heute und künftig, Potenziale, Wellen, Pilotstand, Vorgehen, Beschluss, offene Punkte, Grenzen |
| `hr-einseiter` | Rollen im Überblick in einfacher Sprache, was sich ändert, was HR entscheiden kann |
| `anhang-potenziale` | alle Vorhaben mit Score, Basis, Wertquelle, Zuordnung; Rollen je Welle; Lücken |
| `methodik` | drei Arten von Zahlen, Berechnung von Wert und Score, Grenzen |

Jedes Dokument nennt oben seinen **Stand**: *Entwurf*, solange Textfelder offen sind oder Wellen nur
Vorschlag sind, sonst *versandfertig*. Mit `--strict` endet der Lauf mit Code 1, wenn etwas nicht
versandfertig ist.

### 5. Prüfen, bevor etwas rausgeht

- Stimmt jede Zahl mit dem Graphen überein? Die Tabellen kommen von dort; Texte nur lesen, nicht nachrechnen.
- Steht „geschätzt“ nirgends als „gemessen“? Beobachtete Werte stammen nur aus Piloten.
- Passt die Sprache zur Runde? Wörter, die in den Textfeldern nicht vorkommen sollen, trägt die Konfiguration unter
  `flag_words` ein; das Skript meldet Funde und streicht nichts.
- Sagt die Unterlage etwas über einzelne Personen? Sie darf es nicht.
- Liegt ein Vorhaben in Welle 1, obwohl die Beschäftigten die Arbeit nicht abgeben wollen? Dann steht es unter „Noch offen“;
  sprich es in der Runde an.

## Was das Skill nicht tut

- Es erfindet keine Zeiträume, keine Wellenentscheidungen und keine Zusagen zu Stellen.
- Es rechnet keine Einsparung. Wert und FTE beschreiben gebundene Arbeit.
- Es entscheidet nicht, was HR oder die Runde beschließt; es zeigt, was offen ist.
- Es erzeugt kein Word-Dokument. Markdown lässt sich überall weiterverarbeiten, das HTML druckt als PDF.

## Dateien

- `scripts/plan_waves.py`, `scripts/build_documents.py`: die beiden Aufrufe
- `scripts/roadmap_lib.py`: Kandidaten, Score, Wellen, Jobarchitektur
- `scripts/roadmap_views.py`: Tabellenbausteine, die Raster und Unterlagen teilen
- `scripts/render_lib.py`: Zahlenformat, Markdown, HTML
- `assets/wave-config.json`: Wellen, Kapazität, Gewichte, Schwellen (pro Projekt kopieren und anpassen)
- `references/wellenlogik.md`, `references/dokumente.md`
