---
name: work-graph-builder
description: "Baut aus Stellenbeschreibungen, Organigrammen, SAP/HR-Exporten oder bloßen Rollenlisten einen strukturierten Arbeitsgraphen (Jobfamilien, Jobcluster, Rollen, Aufgaben mit Zeitanteilen, Skills mit Niveau) als versionierte work-graph.json in einem Projektordner, inklusive Review-Liste für Fachexperten und Übernahme von Expertenkorrekturen. Erster Schritt der Work-Transformation-Suite (danach task-scorer, agent-mapper, transformation-dashboard). IMMER verwenden bei: Work Architecture, Job-Architektur, Jobarchitektur, Skill-Architektur, Rollenprofile strukturieren, Stellenbeschreibungen in Aufgaben zerlegen, Tätigkeitsprofile, Job-Cluster, Jobfamilien, Skills-Taxonomie aufbauen, Rollen für KI-Analyse vorbereiten, 'welche Aufgaben hat diese Rolle', Analyse wie bei kommerziellen Work-Architecture-Plattformen, Skills-based Organization, Workforce-Daten strukturieren — auch wenn der Nutzer nur sagt 'zerleg mir diese Stellen in Aufgaben' oder Stellenbeschreibungen hochlädt und eine Struktur will."
---

# work-graph-builder

Du erzeugst die Datenbasis, auf der alle weiteren Skills der Suite arbeiten: eine
`work-graph.json` mit Rollen, Aufgaben und Skills. Der Wert liegt in der Struktur, nicht in
schönen Texten. Jede Aufgabe, die du hier sauber mit Zeitanteil und Skills anlegst, wird später
bewertet, Agenten zugeordnet und im Dashboard gezeigt. Was hier fehlt, fehlt überall.

Skript-Pfade unten sind relativ zum Ordner dieses Skills (`<skill>` = Verzeichnis dieser SKILL.md).
Projektpfade sind relativ zum Arbeitsverzeichnis. Nichts hart codieren.

## Arbeitsteilung: was du tust, was Skripte tun

Du liest die Quellen und schreibst Extraktionsdateien (Urteil, Sprache, Fachwissen).
Die Skripte machen alles, was reproduzierbar sein muss: IDs, Zusammenführung, Deduplizierung,
Normalisierung, Validierung, Versionierung. Schreibe nie selbst in `20_graph/`.

## Ablauf

### 1. Projekt anlegen oder öffnen

```
python3 <skill>/scripts/init_project.py --project ./projekte/<name> --name "<Titel>" --organization "<Firma>" --scope "<Bereich>"
```

Existiert das Projekt schon, meldet das Skript den aktuellen Versionsstand. Quelldokumente
gehören nach `00_input/`. Wenn der Nutzer Dateien im Chat hochgeladen hat, kopiere sie dorthin
(Dateiname beibehalten), damit `source` in der Extraktion auf etwas Nachvollziehbares zeigt.

### 2. Quellen lesen und Extraktionsdateien schreiben

Lies `references/extraction-format.md` (Format, Pflichtfelder) und
`references/skill-taxonomy.md` (kanonische Skillnamen). Dann je Quelle eine Datei
`10_extraction/extract_<slug>.json`.

Regeln, die die Ergebnisse stabil und vergleichbar halten:

- Eine Rolle bekommt 5 bis 12 Aufgaben, die zusammen die ganze Arbeitszeit abdecken. Weniger
  ist zu grob für die Bewertung, mehr zersplittert die Zeitanteile so, dass jede Aufgabe unter
  5 % fällt und nichts mehr messbar ist.
- Aufgabennamen in Verb-Objekt-Form („Zählerstände plausibilisieren"). Gleiche Aufgabe in
  verschiedenen Rollen gleich benennen; die ID hängt trotzdem an der Rolle, das ist gewollt.
- Zeitanteile schätzt du aus der Quelle, sonst aus dem Berufsbild; kennzeichne die Herkunft
  je Aufgabe mit `confidence` und je Rolle mit `time_shares_source` (`source` nur, wenn die
  Anteile wirklich in der Quelle stehen oder der Nutzer sie genannt hat, sonst `estimated`).
  Prozessrollenbeschreibungen nennen fast nie Zeitanteile; dann ist `estimated` die ehrliche
  Antwort, und die Rolle bekommt im Dashboard die Belastbarkeit „ungeprüft", bis ein Experte
  die Anteile bestätigt. Runde auf 5er-Schritte, damit Reviewer nicht über Scheingenauigkeit stolpern.
- Skillnamen aus der Taxonomie übernehmen, wenn passend. Maximal 5 Skills je Rolle als `core`.
- `archetype`: was die Rolle im Kern bindet. control-heavy = Prüfen, Freigeben, Regeln
  einhalten; knowledge-heavy = Analysieren, Wissen anwenden; process-heavy = Vorgänge
  abarbeiten; relationship-heavy = Menschen überzeugen, betreuen, führen; creative-heavy =
  Neues entwerfen; physical-heavy = vor Ort, an Anlagen.
- `regulated`: true, wenn Gesetze oder Aufsicht die Ausführung binden (Netzbetrieb,
  Handel, Arbeitssicherheit, Datenschutz, Abrechnung nach MsbG). Der Scorer setzt dann
  strengere Regeln für Delegation.
- Jobfamilie und Jobcluster über alle Dateien identisch schreiben, sonst entstehen Dubletten.
- Alphabetische Reihenfolge innerhalb von Listen (Skills, Aufgaben nach Zeitanteil absteigend,
  bei Gleichstand alphabetisch). Das ändert nichts an IDs, macht Diffs aber lesbar.
- Wenn die Quelle dünn ist (nur ein Rollentitel), ergänze aus dem Berufsbild, aber markiere
  alles als `inferred` und sage dem Nutzer, dass hier Expertenreview besonders nötig ist.
- Wenn es schon einen Graphen gibt (`20_graph/work-graph_latest.json`), lies ihn zuerst und
  verwende vorhandene Rollen- und Aufgabennamen unverändert weiter. Ein umbenannter Task bekommt
  eine neue ID und verliert seine Bewertung.

### 3. Graph bauen

```
python3 <skill>/scripts/build_graph.py --project ./projekte/<name>
```

Das Skript führt alle `extract_*.json` zusammen, vergibt IDs, normalisiert Zeitanteile auf
100 je Rolle, dedupliziert Skills, übernimmt Bewertungen aus der Vorversion und validiert.
Bei FEHLER wird nichts geschrieben: korrigiere die genannte Extraktionsdatei und wiederhole.
WARNUNGEN (z. B. Rolle ohne Aufgaben) darfst du stehen lassen, solltest sie aber dem Nutzer nennen.

### 4. Review-Liste erzeugen

```
python3 <skill>/scripts/make_review_list.py --project ./projekte/<name> [--cluster "<Clustername>"]
```

Ergebnis `30_review/review_vNNN.md`: je Rolle Aufgaben, Skills, fünf Ja/Nein-Fragen.
Gib dem Nutzer diese Datei; sie ist für Fachexperten gedacht, nicht für dich.

### 5. Korrekturen einspielen

Korrekturen kommen als Zeilen in `30_review/overrides.csv`
(`entity_type;entity_id;field;value;reviewer;comment`). Wenn der Nutzer Korrekturen im Chat
nennt („die Rolle hat 14 Leute, nicht 24"), trage sie selbst in die CSV ein, die IDs stehen in
der Review-Liste. Dann:

```
python3 <skill>/scripts/apply_overrides.py --project ./projekte/<name>
```

Overrides gewinnen dauerhaft über generierte Werte und überleben neue Architekt-Läufe.
Objekte mit Override bekommen `status=reviewed`.

### 5b. Stellen zuordnen (optional, aber wichtig für Personalfragen)

Prozessrollen sind keine Stellen: Eine Person trägt oft mehrere Rollen mit Anteilen. Wenn der
Nutzer eine Stellenliste hat (ohne Personennamen), lege sie als `00_input/positions.csv` ab
(`position_id;title;org_unit;role;share`, eine Zeile je Rolle einer Stelle) und führe aus:

```
python3 <skill>/scripts/import_positions.py --project ./projekte/<name>
```

Das Skript rechnet daraus Vollzeitäquivalente je Rolle (`headcount_from_positions`), setzt
fehlende Headcounts und legt `positions[]` im Graphen an. Damit werden FTE-Äquivalente der
Agenten und die Punktgrößen der Rollenkarte belastbar. `run_pipeline.py` ruft das Skript
automatisch auf, wenn die Datei existiert. Frage nach dieser Liste, sobald der Nutzer Aussagen
über Stellen oder Kapazitäten erwartet; ohne sie beschreibt die Analyse Rollen, nicht Menschen.

### 5c. Prozesse aufnehmen (nur für den Redesignmodus)

Stellenbeschreibungen sagen, **wer was tut**. Sie sagen nicht, **wie ein Fall durch die
Organisation läuft**. Für Soll-Prozesse braucht die Suite das zweite: Auslöser, Schritte,
Übergaben, Bearbeitungs- und Wartezeiten, Systeme, Kontrollen, Ergebnis und Ausgangskennzahlen.

Lies `references/process-format.md` und schreibe je Quelle
`10_extraction/process_<quelle>.json`, dann:

```
python3 <skill>/scripts/build_processes.py --project ./projekte/<name>
```

Drei Dinge entscheiden über die Qualität:

1. **Bearbeitungszeit und Wartezeit trennen.** In den meisten Prozessen ist die Liegezeit der
   eigentliche Hebel. Wer beides in eine Zahl schreibt, verliert ihn.
2. **Übergaben mitschreiben.** Jeder Wechsel der ausführenden Rolle ist eine Kante mit
   `handover`. Übergaben per E-Mail oder Meeting sind die typischen Wartezeitquellen — und
   später die lohnendsten Redesign-Ziele.
3. **Belastbarkeit angeben.** `estimated`, `expert_confirmed` oder `observed`. Wer
   `observed` schreibt, liefert einen `provenance`-Eintrag mit; sonst lehnt der Validator ab.
   Das ist Absicht: Eine behauptete Messung ohne Fundstelle ist schlechter als eine ehrliche
   Schätzung, weil sie sich nicht widerlegen lässt.

Wenn das Skript meldet, dass das Modell die gemessene Durchlaufzeit nicht erklärt, fehlen
Schritte oder Liegezeiten. Schließe die Lücke, bevor jemand darauf ein Redesign rechnet.

Kein Prozess erfasst? Dann bleibt das Projekt im Diagnosemodus, und das ist ein vollständiges
Ergebnis, keine halbe Sache.

### 5d. Freigaben festhalten

Freigabestände gehören nicht in ein Feld im Graphen, sondern in `30_review/decisions.csv`:

```
subject_type;subject_id;decision;rationale;decided_by;role;date;supersedes
blueprints;Auftrag bis Rechnung — Übergaben entfallen;approve;Pilot bestätigt;M. Berger;Leitung Finanzen;2026-06-08;
```

```
python3 <skill>/scripts/apply_governance.py --project ./projekte/<name>
```

`approve`, `reject`, `defer` und `revoke` setzen die Status von Blueprints, Prozessen, Rollen,
Aufgaben und Experimenten. `decided_by` und `date` sind Pflicht — eine Freigabe ohne Namen und
Datum ist keine Freigabe. Die Datei wird bei jedem Lauf erneut angewendet und überlebt jede
Neuberechnung.

### 5e. Ein altes Projekt migrieren

```
python3 <skill>/scripts/migrate_graph.py --project ./projekte/<name> [--dry-run]
```

Hebt ein Projekt vom Schema 1.0 auf 1.1: additiv, verlustfrei, idempotent. Die Migration rät
nichts — sie erzeugt insbesondere keine Prozesse aus `workflow_steps`. Diese Textliste
beschreibt den Ablauf innerhalb einer Rolle, nicht den Fluss über Rollen und Systeme hinweg;
daraus einen End-to-End-Prozess zu generieren, würde eine Genauigkeit vortäuschen, die die
Quelle nicht hergibt.

### 6. Prüfen und übergeben

```
python3 <skill>/scripts/validate_graph.py --project ./projekte/<name>
```

Nenne dem Nutzer: Version, Anzahl Rollen/Aufgaben/Skills, Anteil `inferred`, offene Warnungen,
und dass der nächste Schritt der Skill `task-scorer` ist. Wenn Prozesse erfasst sind, nenne
zusätzlich je Prozess Schritte, Human Touchpoints, Übergaben und Durchlaufzeit — und sag dazu,
wie viele der Ausgangswerte gemessen und wie viele geschätzt sind.

## Determinismus, kurz

Gleiche Eingaben ergeben denselben Graphen: IDs sind Hashes der Namen, Listen sind sortiert,
JSON ist mit sortierten Schlüsseln geschrieben, kein Zeitstempel im Inhalt. Der einzige nicht
deterministische Schritt ist deine Extraktion. Halte ihn so stabil wie möglich, indem du dich
an das Format, die Taxonomie und vorhandene Namen hältst.

## Typische Fehler

- Familien-/Clusternamen variieren zwischen Dateien: Dubletten. Vorher festlegen, dann durchziehen.
- Aufgaben als Substantive („Rechnungsprüfung"): schlecht bewertbar. Verb-Objekt-Form.
- 20 Aufgaben mit je 5 %: nichts ist mehr relevant. Zusammenfassen.
- Skills als Firmenjargon („IS-U-Kenner"): nicht vergleichbar. Taxonomienamen.
- Manuell in `20_graph/` editiert: geht beim nächsten Lauf verloren. Overrides benutzen.
- Prozessschritte als Klickfolgen modelliert („Maske öffnen", „Feld füllen"): das ist
  Bildschirmarbeit, kein Prozess. Fünf bis fünfzehn Schritte je Prozess.
- Wartezeit in die Bearbeitungszeit gerechnet: verdeckt den größten Hebel.
- Prozess ohne `outcome`: dann lässt er sich nicht redesignen, weil unklar ist, was erhalten
  bleiben muss.
