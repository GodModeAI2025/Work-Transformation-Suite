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

### 1b. Quellen registrieren

Jede Quelle, auf die sich der Graph berufen soll, kommt treu als Markdown ins Register:

```
python3 <skill>/scripts/register_source.py --project ./projekte/<name> --file 00_input/<datei>.md --title "<Titel>" [--kind document|interview|system_export|observation]
```

`.md`, `.txt`, `.csv`, `.tsv` und `.json` registriert das Skript selbst. PDF, Word, Excel und Bilder liest
du: Lege die treue Markdown-Fassung ab (Überschriften, Listen, Tabellen, Seiten- oder Folienmarken
erhalten, nichts zusammenfassen, nichts übersetzen) und registriere sie mit `--original <datei>`
und `--extractor claude`. Das Skript hasht den Inhalt zur `source_id`, lehnt Zugangsdaten und
absolute Pfade ab und nennt die Anker der Überschriften. Was nicht lesbar war, bekommt `--status partial`.

Ein Beleg hat dann die Form `src-<hash>@<fundstelle>`: Überschriftenanker (`#auftragssachbearbeiter-9-stellen`),
Zeile (`L12`), Bereich (`L12-18`) oder Freitext (Seite, Folie). `locate_source.py --source src-… --find "Zitat"`
liefert die Fundstelle zu einem Zitat. Trage je Rolle, Aufgabe, Prozess, Schritt, Kennzahl und Kontrolle
die Belege in die Extraktion ein (`evidence`, bei Kontrollen `source_evidence`). Was du aus dem Berufsbild
ergänzt, bleibt ohne Beleg und trägt `confidence: inferred`; das ist eine Schätzung, keine Lücke.

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

Hebt ein Projekt vom Schema 1.0 oder 1.1 auf 1.2: additiv, verlustfrei, idempotent. Die Migration rät
nichts — sie erzeugt insbesondere keine Prozesse aus `workflow_steps`. Diese Textliste
beschreibt den Ablauf innerhalb einer Rolle, nicht den Fluss über Rollen und Systeme hinweg;
daraus einen End-to-End-Prozess zu generieren, würde eine Genauigkeit vortäuschen, die die
Quelle nicht hergibt.

### 6. Prüfen und übergeben

```
python3 <skill>/scripts/validate_graph.py --project ./projekte/<name>
python3 <skill>/scripts/check_evidence.py --project ./projekte/<name>
```

`check_evidence.py` schreibt `30_review/belege_vNNN.md`: je Sammlung belegt, geschätzt, unbelegt, dazu jede
Fundstelle, die im Quelltext nicht aufgeht. Bei `evidence_policy: strict` in `project.json` hält die
Pipeline an, solange etwas unbelegt ist. Erfinde dann keinen Beleg: Registriere die Quelle, trage die
Fundstelle ein, oder kennzeichne den Eintrag als Schätzung.

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

## Ab Schema 1.2

**Interview statt Stellenbeschreibung.** Für Prozesse und Übergaben ist eine Stellenbeschreibung nur ein Drittel der Wahrheit.
Der Leitfaden `references/interview-leitfaden.md` hat drei Fragen (Schritte, Systeme, Gefühl), ein Nachfrageschema und die
Regel, zuerst zu prüfen, ob das Problem überhaupt ein KI-Fall ist. Was an einem Schritt hakt, kommt in `pain`.

**Prozesshaus.** `scripts/import_process_house.py --project … [--file 00_input/prozesshaus.csv]` liest ein vorhandenes Prozesshaus
als Prozessextraktion ein (Format im Skript). Es liefert Struktur, nicht Wirklichkeit.

**Kapazität.** Overrides kennen `absorption` (`growth`, `attrition`, `redeployment`, `none`), `absorption_pct` und `day_rate_eur`
je Rolle; `make_review_list.py` fragt danach.

**Rollenzuschnitt.** Hat eine Rolle zehn und mehr Aufgaben, oder teilt die Mehrheit ihrer Aufgabenpaare keinen Skill, markiert
die Review-Liste „Split prüfen“. In einer zu groben Rolle gehen beim Mitteln Kontext und Unterschiede verloren.

**Glossar.** `references/glossar.md` legt Rolle, Position, Aufgabe, Prozessschritt, Agent und Use Case fest und sagt, wie HR und
IT dieselben Wörter benutzen.

## Datenaufbereitung (ab 0.4)

Zuerst sichten, dann aufbereiten. Die Methoden und ihre Grenzen stehen in `references/datenaufbereitung.md`.

1. `scripts/inventory_sources.py` — Quellenarten, Lücken, vorgeschlagene Methoden (`30_review/quellen_inventar.md`). Biete die Vorschläge
   dem Nutzer an; wähle nicht still.
2. Nach dem Bauen des Graphen: `scripts/check_completeness.py` prüft jede Rolle gegen `assets/role-template.json`. Lücken werden nicht
   aufgefüllt; sie sagen, woher sie zu füllen wären (innen vor außen).
3. `scripts/dedupe_tasks.py` findet dieselbe Arbeit in mehreren Rollen. **Das sind Kandidaten.** Das Verfahren kennt Wörter, nicht
   Bedeutung; prüfe sie mit dem Fachexperten und trage Entscheidungen mit Namen in `30_review/task_clusters.csv` ein.
4. `scripts/derive_collaboration.py` leitet Zusammenarbeit aus Prozesskanten und Positionslisten ab — als Gesprächsvorlage.
5. `scripts/import_levels.py` ordnet Level Kostensätze zu (`00_input/levels.csv`); gesetzte Werte bleiben.
6. Allgemeine Regeln: Wenn ein Experte etwas über viele Rollen sagt („im Netzbetrieb ist alles reguliert“), schreibe eine Regelzeile mit Selektor
   (`cluster:`, `family:`, `role:`, `*`) in `overrides.csv`, nicht zwanzig Einzelzeilen.

Externe Stellenanzeigen ergänzen nur, was intern fehlt, und werden als `confidence: inferred` geführt.
