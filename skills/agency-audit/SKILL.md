---
name: agency-audit
description: "Holt die Sicht der Beschäftigten in den Arbeitsgraphen: Fragebogen je Rolle (offene Fragen zur eigenen Arbeit, je Aufgabe Vertrautheit, Sorge, Freude, Automatisierungswunsch, vier Merkmale und gewünschte Beteiligung auf der Human Agency Scale H1–H5), Import der Antworten nur als Zusammenfassung ab Mindestgruppe, und daraus je Aufgabe die Zone (Freigabe, Vorsicht, Entwicklung, Nachrang), die Agency-Lücke zwischen gewünschter und technisch nötiger Beteiligung und je Rolle die Reibung. Ergebnis ist eine Prüfliste für Fachbereich, HR und Beschäftigtenvertretung; Dashboard, Berichte, Fahrplan, Verträge und Rollen.md nutzen die Zonen. Teil der Work-Transformation-Suite, nach task-scorer. IMMER verwenden bei: Beschäftigtenbefragung, Mitarbeiterbefragung zu KI, was wollen die Mitarbeitenden automatisieren, Akzeptanz, Widerstand, Human Agency, gewünschte Beteiligung, Wunsch gegen Machbarkeit, rote Zone, Freigabezone, 'wo dürfen wir automatisieren', 'was sagen die Leute dazu'."
---

# agency-audit

Die Bewertung der Suite sagt, was Technik kann und wie viel Mensch sie technisch braucht. Dieses
Skill fragt die Menschen, die die Arbeit tun: **Was würden Sie gern abgeben, und wie viel wollen Sie
bei dem Rest beteiligt sein?** Beides nebeneinander zeigt, wo eine Automatisierung auf offene Türen
trifft, wo sie gegen die Beschäftigten liefe und wo sie gewünscht ist, aber noch nicht geht.

Die Methodik folgt dem Auditrahmen von Shao et al. 2025 (Stanford, „Future of Work with AI Agents“,
WORKBank): Befragung der Beschäftigten je Aufgabe, Fähigkeitsbewertung daneben, vier Zonen, die
Human Agency Scale als gemeinsame Sprache. Übertragen auf ein Haus statt auf einen Arbeitsmarkt.

Die Arbeitsteilung bleibt: **Skripte rechnen, Menschen urteilen.** Claude schreibt hier keine
Antworten und schätzt keine Wünsche. Es bereitet den Fragebogen vor, erklärt die Auswertung und
formuliert Gesprächsanlässe aus der Prüfliste.

## Voraussetzungen

- Ein bewerteter Graph (`task-scorer`): Die Zone braucht das Automatisierungspotenzial, die Lücke
  die HAS-Stufe der Bewertung.
- **Vor dem Versand:** Zweck benannt, Beschäftigtenvertretung beteiligt, Rohdaten-Verantwortung
  und Löschfrist geklärt. Ein Fragebogen zu Tätigkeiten, Sorgen und Wünschen ist ein
  Personalfragebogen (§ 94 BetrVG, im öffentlichen Dienst das Personalvertretungsrecht). Der
  Rechtsraum DE der Referenzbibliothek führt das Thema `beschaeftigtenbefragung`; Fragebogen und
  Prüfliste zitieren es. Sag dem Nutzer das, bevor du einen Fragebogen erzeugst, und erzeuge ihn
  trotzdem: Abstimmen kann man nur, was vorliegt.

## Ablauf

### 1. Fragebogen erzeugen

```
python3 <skill>/scripts/export_audit_sheet.py --project ./projekte/<name> [--rollen "Rolle A;Rolle B"]
```

Ergebnis unter `30_review/befragung/`: je Rolle `fragebogen_<rolle>.md` (Rahmen, fünf offene
Fragen, Bewertungsfragen, Aufgabenliste, Stufen der Beteiligung) und `antworten_vorlage.csv` mit
einer Zeile je Rolle und Aufgabe. Format und Skalen: `references/befragung.md`.

Der Fragebogen kann in jedes Umfragewerkzeug übertragen werden. Entscheidend ist, dass die Antworten
am Ende in der Spaltenform der Vorlage vorliegen.

### 2. Antworten ablegen

Ausgefüllte CSV-Dateien nach `00_input/befragung/*.csv`. Jede Person trägt einen selbst gewählten
Code ein, keinen Namen. Dateien mit Spalten wie Name, E-Mail oder Personalnummer weist der Import
zurück.

### 3. Auswerten

```
python3 <skill>/scripts/import_audit.py --project ./projekte/<name>
python3 <skill>/scripts/score_agency.py --project ./projekte/<name>
```

`run_pipeline.py` macht beides selbst, sobald unter `00_input/befragung/` CSV-Dateien liegen.

- `import_audit.py` schreibt nur Zusammenfassungen je Aufgabe nach `20_graph/agency.json`. Gezählt
  werden Antworten zu Aufgaben, die die Person selbst erledigt. Eine Aufgabe erscheint ab
  5 Antworten, eine Rolle ab 5 Teilnehmenden; jeder Mittelwert braucht ebenso viele Werte.
- `score_agency.py` legt je Aufgabe `agency` an (Wunsch, gewünschte HAS-Stufe, Sorge, Freude,
  Merkmale, Gründe, **Zone**, **Lücke**) und je Rolle (Wunsch, dominante Stufen, **Reibung**,
  Zonenanteile, Abdeckung). Dazu `30_review/beschaeftigtensicht_vNNN.md`.

### 4. Ergebnis mit dem Nutzer besprechen

Lies die Prüfliste und sprich zuerst über die **Vorsichtszone** (machbar, nicht gewünscht): Dort
nicht zuerst automatisieren, sondern klären, warum. Dann die **Entwicklungszone** (gewünscht, noch
nicht machbar): Werkzeugbedarf. Dann die Lücken: Wo die Beschäftigten mehr Beteiligung wollen, als
die Technik braucht, gehört ein Kontrollpunkt in den Entwurf; wo sie weniger wollen, ist entweder die
Bewertung zu vorsichtig oder die Erwartung an KI zu hoch.

Formuliere daraus Gesprächsanlässe, keine Urteile über Menschen. Eine hohe Reibung in einer Rolle
heißt: Bewertung und Beschäftigte sehen die Arbeit verschieden. Wer recht hat, klärt das Gespräch.

## Was die Zonen bewirken

| Zone | Bedingung | Wirkung in der Suite |
|---|---|---|
| Freigabe | Wunsch über 3 und Potenzial ab 6 | Fahrplan darf früh planen |
| Vorsicht | Potenzial ab 6, Wunsch bis 3 | Fahrplan legt Vorhaben mit überwiegend roter Zone nicht in Welle 1 |
| Entwicklung | Wunsch über 3, Potenzial unter 6 | IT-Bericht führt sie als latente Nachfrage |
| Nachrang | weder noch | keine |

Ein Agent mit `decision_scope` „execute_…“ ohne Kontrollpunkt auf Aufgaben mit gewünschter Stufe H4
oder H5 erzeugt eine Warnung des Validators. Rollen.md nennt je Rolle, was die Befragten selbst wollen.

## Grenzen

- Eine Befragung misst Einschätzungen, keine Fähigkeiten. Wer Sorge um seinen Arbeitsplatz hat,
  antwortet vorsichtiger; das ist ein Befund, kein Messfehler.
- Teilnehmende sind nicht zufällig ausgewählt. Die Abdeckung je Rolle steht in der Prüfliste.
- Die Schwellen (Wunsch über 3, Potenzial ab 6, Reibung ab 0,25 und 0,45) sind Arbeitswerte und
  stehen als Konstanten in `workgraph_lib.py`.
- Nichts aus der Befragung ändert eine Bewertung. Wer eine Bewertung nach der Befragung korrigieren
  will, tut das über `overrides.csv` mit Name und Begründung.
