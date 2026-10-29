# Beschäftigtenbefragung: Format, Skalen, Auswertung

## Antwortdatei

`00_input/befragung/*.csv`, Semikolon oder Komma, UTF-8. Eine Zeile je Person und Aufgabe.

| Spalte | Inhalt | Pflicht |
|---|---|---|
| `teilnehmer` | selbst gewählter Code, kein Name, keine E-Mail | ja |
| `rolle` | Rollenname wie im Graphen | ja |
| `aufgabe_id` | ID aus der Vorlage; leer erlaubt, dann zählt `aufgabe` (Name innerhalb der Rolle) | ja, eins von beiden |
| `aufgabe` | Aufgabenname | |
| `bekannt` | `ja` oder `nein`. Nur `ja` wird gezählt | ja |
| `erfahrung` | `einsteiger`, `durchschnitt`, `experte` | nein |
| `zeitanteil` | 10, 30, 50, 70 oder 100 (Prozent der eigenen Arbeitszeit) | nein |
| `kernfaehigkeit` | 1–5: wie eng die Aufgabe an den eigenen Kernfähigkeiten hängt | nein |
| `sorge` | 1–5: Sorge um den Arbeitsplatz, wenn KI die Aufgabe ganz übernähme | nein |
| `freude` | 1–5: wie gern man die Aufgabe erledigt | nein |
| `wunsch` | 1–5: wie sehr man möchte, dass KI sie vollständig erledigt | eins von `wunsch` und `zusammenarbeit` |
| `gruende_wunsch` | Codes, mit `\|` getrennt (siehe unten) | nein |
| `koerperlich`, `unsicherheit`, `fachwissen`, `zwischenmenschlich` | 1–5: Merkmale der Aufgabe | nein |
| `zusammenarbeit` | 1–5 = gewünschte Stufe H1–H5 | eins von `wunsch` und `zusammenarbeit` |
| `gruende_zusammenarbeit` | Codes, mit `\|` getrennt | nein |

Spalten, die Personen benennen (`name`, `vorname`, `nachname`, `email`, `personalnummer`, `telefon` …),
führen zum Abbruch. Freitext wird nicht gelesen.

### Codes

Gründe für den Wunsch: `zeit` (Zeit für wertvollere Arbeit), `wiederholung` (wiederholend oder mühsam),
`qualitaet` (Qualität steigt), `belastung` (belastend), `schwierig` (kompliziert), `menge` (mehr Menge).

Gründe für Zusammenarbeit: `koerperlich`, `entscheidung` (folgenreiche Entscheidungen, die man steuern
will), `fachwissen`, `kommunikation`, `pruefung` (braucht Prüfung oder Aufsicht), `dynamik` (ändert sich
laufend), `ethik` (ethische, sensible oder subjektive Anteile).

## Human Agency Scale

| Stufe | Bedeutung |
|---|---|
| H1 | Agent erledigt die Aufgabe allein |
| H2 | Agent braucht an wenigen Stellen Eingaben |
| H3 | Mensch und Agent als gleichberechtigtes Team, besser als jeder allein |
| H4 | Agent braucht Eingaben des Menschen, um die Aufgabe zu schaffen |
| H5 | ohne laufende Beteiligung des Menschen geht es nicht |

Höhere Stufen sind nicht besser. H1–H2 sprechen für Automatisierung, H3–H5 für Unterstützung.
Die Bewertung (`task-scorer`) leitet die technisch nötige Stufe aus Potenzial und Urteilsbedarf ab;
die Befragung liefert die gewünschte.

## Auswertung

**Mindestgruppe.** 5 Antworten je Aufgabe, 5 Teilnehmende je Rolle, 5 Werte je Mittelwert.
Darunter wird nichts gerechnet; die Aufgabe zählt als unterdrückt. Der Validator lehnt jede
Zusammenfassung mit weniger Antworten ab.

**Je Aufgabe** (`tasks[].agency`): `respondents`, `desire` (Mittel), `desire_positive_pct` (Anteil
über 3), `has_desired` (Mehrheit; bei Gleichstand die höhere Stufe), `has_desired_mean`,
`has_desired_counts`, `job_worry`, `enjoyment`, `core_skill`, `time_share_survey`, `traits`
(physical, uncertainty, expertise, interpersonal), `reasons_automation`, `reasons_collab`, dazu

- `zone`: green (Wunsch > 3 und Potenzial ≥ 6), red (Potenzial ≥ 6, Wunsch ≤ 3), opportunity
  (Wunsch > 3, Potenzial < 6), low (sonst).
- `has_gap` = gewünschte Stufe − nötige Stufe (−4 bis 4).

**Je Rolle** (`roles[].agency`), zeitanteilgewichtet über die befragten Aufgaben: `respondents`,
`tasks_rated`, `tasks_total`, `share_rated_pct`, `desire`, `has_desired_dominant`,
`has_required_dominant`, beide Verteilungen, `jsd` (Jensen-Shannon-Distanz, Basis 2), `friction`
(gering unter 0,25, mittel unter 0,45, sonst hoch), `zone_shares` (Prozent der befragten Zeit),
`gap_mean`, `coverage_pct` (Teilnehmende je Headcount).

## Rahmen der Befragung

Ein Fragebogen zu Tätigkeiten, Sorgen und Wünschen ist ein Personalfragebogen im Sinn von § 94 BetrVG
und braucht die Zustimmung des Betriebsrats; läuft er über ein elektronisches Werkzeug, kommt § 87
Abs. 1 Nr. 6 BetrVG hinzu. Im öffentlichen Dienst gilt das Personalvertretungsrecht. Datenschutz: Art. 5,
6 und 88 DSGVO, § 26 BDSG. Praktisch heißt das: Zweck vorher benennen, freiwillig, Codes statt Namen,
Auswertung nur ab Mindestgruppe, Rohdaten getrennt und befristet, keine Verwendung zur Leistungs- oder
Verhaltenskontrolle. Das ist ein Prüfauftrag, keine Rechtsberatung.

Ohne diesen Rahmen antwortet niemand ehrlich. Eine Befragung, der die Beschäftigten misstrauen, liefert
schlechtere Daten als gar keine.

## Was die Befragung nicht ist

- Kein Ersatz für die Bewertung: Beschäftigte kennen ihre Aufgaben, nicht immer den Stand der Technik.
- Keine Abstimmung: Eine Zone ist ein Gesprächsanlass, kein Veto.
- Keine Personalbeurteilung: Kein Ergebnis lässt sich auf eine Person zurückführen, und keines darf
  dafür verwendet werden.
