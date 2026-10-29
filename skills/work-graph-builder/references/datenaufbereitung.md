# Datenaufbereitung: Methoden, Eingaben, Ergebnisse

Gute Analysen hängen weniger am Modell als an der Aufbereitung davor. Dieses Dokument beschreibt die Methoden, die
die Suite anbietet, wann sie sich lohnen und was sie ausdrücklich nicht tun. `inventory_sources.py` wählt aus dieser
Liste, was zu den vorliegenden Quellen passt, und schreibt den Vorschlag in `30_review/quellen_inventar.md`.

## Überblick

| # | Methode | Skript | Eingabe | Ergebnis | Ändert den Graphen |
|---|---|---|---|---|---|
| 0 | Quellenregister | `register_source.py`, `locate_source.py`, `check_evidence.py` | `00_input/<datei>` | treue Markdown-Fassung mit `source_id`, Belege `src-…@…` im Graphen, Belegbericht | nein (Belege kommen über die Extraktion) |
| 1 | Quelleninventar | `inventory_sources.py` | `00_input/` | Quellenarten, Lücken, vorgeschlagene Methoden | nein |
| 2 | Vollständigkeitsprüfung | `check_completeness.py` | Graph, `assets/role-template.json` | Füllgrad und Lücken je Rolle mit Hinweis, woher sie zu füllen wären | nein |
| 3 | Aufgabencluster | `dedupe_tasks.py` | Graph, optional `30_review/task_clusters.csv` | dieselbe Arbeit in mehreren Rollen | ja (`task_clusters`) |
| 4 | Zusammenarbeit | `derive_collaboration.py` | Graph (Prozesskanten, Positionen) | Rollenpaare mit Belegen | nein |
| 5 | Allgemeine Regeln | `apply_overrides.py` mit Selektoren | `30_review/overrides.csv` | eine Aussage wirkt auf viele Rollen | ja |
| 6 | Level und Kostensatz | `import_levels.py` | `00_input/levels.csv` | `day_rate_eur` je Rolle nach Level | ja |
| 7 | Referenzautomatisierungen | `export_agent_candidates.py` (agent-mapper) | `00_input/referenzautomatisierungen.csv` | `references` je Aufgabenkandidat | nein |
| 8 | Prozesshaus | `import_process_house.py` | `00_input/prozesshaus.csv` | `process_<quelle>.json` | über `build_processes.py` |
| 9 | Positionen | `import_positions.py` | `00_input/positions.csv` | Headcount und Stellen | ja |
| 10 | Interview | `interview-leitfaden.md` | Gespräch | Schritte, Systeme, Übergaben, `pain` | über Extraktion |

## 0. Quellenregister

Eine Quelle wird einmal treu nach Markdown gebracht und unter `00_input/sources/` mit `source_id` (Hash des Inhalts),
Titel, Herkunft und Datum registriert (`register.jsonl`). Der Graph beruft sich dann mit `src-<hash>@<fundstelle>` auf
eine Stelle in dieser Fassung: Überschriftenanker, Zeile, Bereich oder Freitext. `locate_source.py` zeigt die Anker und
findet Zitate; `check_evidence.py` zählt je Sammlung belegt, geschätzt und unbelegt und prüft, ob jede Fundstelle im
Quelltext aufgeht.

Drei Regeln: Der Inhalt wird nicht verändert (nicht zusammengefasst, nicht übersetzt). Das Original bleibt, wo es ist;
das Register merkt sich nur seinen Hash. Zugangsdaten und absolute Pfade stoppen die Aufnahme.

`evidence_policy` in `project.json` entscheidet, ob Unbelegtes gemeldet wird (`warn`, Standard) oder die Pipeline
anhält (`strict`).

## 1. Quelleninventar

Ordnet jede Datei in `00_input/` einer Quellenart zu (Stellenbeschreibung intern, Stellenanzeige extern, Positionsliste,
Level-/Tarifstruktur, Prozessbeschreibung, Prozesshaus, Kurs-/Zertifizierungsunterlage, Geschäftsbericht,
Produktbeschreibung, Referenzregister, Use-Case-Register, Nutzungsstand). Die Zuordnung ist eine Heuristik aus Dateiname und
Stichwörtern; PDF, Word und Excel kann das Skript nicht lesen und führt sie nach dem Namen mit dem Vermerk „Claude liest“.

Was die Quellenarten im Modell füllen können, steht im Bericht. Merksatz: Eine Stellenanzeige liefert Aufgaben, aber kein
Arbeitsumfeld; eine Positionsliste Zusammenarbeit, aber keine Aufgaben; ein Jahresbericht Kontext, aber keine Rolle.

**Innen vor außen.** Externe Stellenanzeigen ergänzen, was intern fehlt. Sie werden als `confidence: inferred` geführt und
erscheinen im Dashboard als „ergänzt“. Eine interne Quelle schlägt immer eine externe.

## 2. Vollständigkeitsprüfung

`assets/role-template.json` legt fest, was eine vollständige Rollenbeschreibung enthält: Zweck, Beschreibung, mindestens vier
Aufgaben, Zeitanteile aus der Quelle, Skills mit Niveau, Level, Headcount, Beleg für Zusammenarbeit, geklärte Regulierung.
Jeder Abschnitt hat ein Gewicht und einen Hinweis, woher er zu füllen ist. Wer die Vorlage kopiert und ändert
(`--template`), bestimmt, was in diesem Haus als vollständig gilt — zum Beispiel mehr Pflichtaufgaben oder eine
Compliance-Angabe.

Die Prüfung füllt nichts auf. Eine Lücke bleibt sichtbar, bis eine Quelle sie schließt; bis dahin steht in jeder Ausgabe
„geschätzt“ oder „ergänzt“.

## 3. Aufgabencluster

Findet gleiche Arbeit in verschiedenen Rollen: Namen und Beschreibungen werden normalisiert, in Wortstämme (fünf Zeichen)
zerlegt und per Jaccard-Ähnlichkeit verglichen, Schwelle 0,6. Aufgaben derselben Rolle werden nie zusammengelegt.

**Grenze:** Das Verfahren findet gleiche Wörter, nicht gleiche Bedeutung. „Rechnung prüfen“ und „Beleg kontrollieren“ erkennt
es nicht; „Rechnung prüfen“ und „Rechnung freigeben“ könnte es fälschlich zusammenlegen. Deshalb sind alle Cluster
zunächst `candidate`. Entscheidungen stehen in `30_review/task_clusters.csv`:

```
cluster_id;decision;reviewer;comment
tc_1a2b3c4d5e6f;confirmed;M. Muster;gleiche Prüfung
tc_9f8e7d6c5b4a;rejected;M. Muster;nur ähnlich geschrieben
```

Entscheidungen ohne `reviewer` werden nicht übernommen. Die Cluster-ID folgt der kleinsten Aufgaben-ID und bleibt über Läufe
stabil.

## 4. Zusammenarbeit

Belege nach Stärke: Übergabe im Prozess (stärkster Beleg, mit Art der Übergabe), gemeinsame Stelle, gleiche
Organisationseinheit (schwächster Beleg, zeigt Nähe). Das Ergebnis ist eine Gesprächsvorlage für den Fachbereich.

## 5. Allgemeine Regeln aus Expertenaussagen

Ein Experte sagt selten „Rolle X ist reguliert“, sondern „bei uns ist im Netzbetrieb alles reguliert“ oder „wir nutzen
generell SAP, kein Oracle“. Statt jede Rolle einzeln zu korrigieren, steht in `overrides.csv` eine Regelzeile mit Selektor:

```
entity_type;entity_id;field;value;reviewer;comment
role;cluster:Netzbetrieb;regulated;true;M. Muster;gilt für den ganzen Cluster
role;family:Finanzen und Controlling;absorption;attrition;M. Muster;Altersteilzeit-Welle
task;role:Kreditprüfer;status;reviewed;M. Muster;
role;*;level;Sachbearbeitung;M. Muster;Standardwert
```

Selektoren: `*`, `cluster:<Name>`, `family:<Name>`, `role:<Name>` (bei Aufgaben). Regelzeilen stehen oben, Einzelzeilen darunter
überstimmen sie. `delete` ist als Regel nicht erlaubt. Die Auflösung ist deterministisch (nach ID sortiert) und im Kommentar
mit `[Regel …]` vermerkt.

## 6. Level und Kostensatz

`00_input/levels.csv` (`level;label;day_rate_eur;description`) ordnet jedem Level einen Planwert Vollkosten je Arbeitstag zu;
Rollen mit passendem Level erhalten ihn als `day_rate_eur` (Quelle `level`). Ein gesetzter Wert bleibt unberührt. Daraus entsteht
der geschätzte Jahreswert in Reichweite und Kapazität. Es sind Planwerte je Level, keine Gehälter einzelner Personen.

## 7. Referenzautomatisierungen

`00_input/referenzautomatisierungen.csv`:

```
name;beschreibung;stichwoerter;quelle;evidenz
Zahlungsabgleich;Kontoauszugspositionen automatisch zuordnen;zahlungseing|zuordn;Herstellerdoku, Abschnitt 4;expert_confirmed
Mahnentwurf;Mahnstufe bestimmen, Text vorbereiten;mahn;Eigenes Projekt 2025;proven
```

`stichwoerter` mit `|` getrennt; ein Treffer, wenn ein Stichwort im Aufgabentext steht. `quelle` ist Pflicht (eine Referenz ohne
Quelle wird übersprungen), `evidenz` ist `heuristic` (Standard), `expert_confirmed` oder `proven`. `agents_todo.json` nennt
je Aufgabenkandidat bis zu drei Referenzen, die besten Belege zuerst.

**Die Referenzliste ist kuratiert, nicht gescrapt.** Ein Forenbeitrag, in dem jemand schreibt, er habe etwas automatisiert,
belegt nicht, dass es funktioniert, geschweige denn, dass es zum eigenen Haus passt. Deshalb steht der Evidenzgrad dabei, und
jeder Agent bleibt `heuristic`, bis ein Fachexperte die Passung bestätigt.

## Was die Suite bewusst nicht tut

- **Kein Scrapen öffentlicher Daten.** Die Suite liest, was ihr gegeben wird. Ein Marktdatensatz (Stellenanzeigen, Taxonomien wie ESCO) ist eine
  Eingabe, kein eingebauter Dienst.
- **Kein Modell zur Ähnlichkeit.** Aufgabencluster beruhen auf Wörtern. Wer semantische Ähnlichkeit braucht, lässt Claude die Kandidaten prüfen
  und trägt das Ergebnis in `task_clusters.csv` ein.
- **Kein automatisches Auffüllen.** Lücken bleiben Lücken.
