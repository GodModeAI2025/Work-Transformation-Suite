# Work-Transformation-Suite

Sechs Claude-Skills mit zwei Betriebsarten.

**Diagnose.** Aus Stellenbeschreibungen eines Bereichs entsteht ein bewerteter Arbeitsgraph: Rollen,
Aufgaben, Skills, KI-Automatisierbarkeit je Aufgabe, Disruptionstyp je Rolle, Agentenbibliothek mit
Rollenabdeckung und ein Dashboard. Das entspricht dem, was kommerzielle Work-Orchestration-Plattformen
als Rollen- und Aufgabenmodell mit KI-Bewertung anbieten. Angefangen hat das mit Pilotbereichen von
20 bis 40 Rollen. Inzwischen ist es mit über 200 Rollen in einem Durchgang gelaufen.

**Redesign.** Aus diesen Daten plus einer Prozessaufnahme entstehen KI-native Soll-Prozesse: je
priorisiertem Prozess drei vergleichbare Szenarien, gerechnete Deltas bei Durchlaufzeit, Übergaben
und Human Touchpoints, ausführbare Capability Contracts für die Agenten und ein messbarer Pilotplan.

Der Unterschied ist nicht akademisch. Wenn fünf Rollen nacheinander dieselben Daten prüfen, findet
die Diagnose fünf automatisierbare Aufgaben und schlägt einen Agenten vor. Ein Redesign streicht vier
Prüfungen, drei Übergaben und zwei Datenumformungen — und der Rest braucht gar keinen Agenten mehr.
Wert entsteht auf der Ebene des Ablaufs, nicht der Einzelaufgabe.

Der Diagnosemodus bleibt für sich vollständig. Ein Projekt darf darin bleiben.

## Was drin ist

```
Work-Transformation-Suite/
├── README.md                     diese Anleitung
├── CHANGELOG.md                  was sich je Version geändert hat
├── docs/index.html               Landingpage (GitHub Pages)
├── .claude-plugin/               Plugin- und Marketplace-Manifest für Claude Code
├── .github/workflows/check.yml   Suite-Check und Tests bei Push und Pull Request
├── skills/
│   ├── work-transformation/      Orchestrator: Pipeline, Suite-Check
│   ├── work-graph-builder/       Schritt 1: Extraktion → work-graph.json, Prozessebene, Review, Governance
│   ├── task-scorer/              Schritt 2: Aufgabenbewertung → Modus, HAS, Horizont, Disruptionstyp
│   ├── agent-mapper/             Schritt 3: Agentenbibliothek → Abdeckung, Capability Contracts
│   ├── process-redesigner/       Schritt 4: Soll-Szenarien, Prozesswert, Piloten
│   └── transformation-dashboard/ Schritt 5: HTML-Dashboard, CSV, Bericht
├── examples/order-to-cash/       vollständiges Referenzprojekt mit erwartetem Ergebnis
├── tests/                        Testsuite (python -m unittest discover)
├── tools/                        Bibliothekskopien abgleichen, Pakete bauen, Beispiel auffrischen
└── dist/                         .skill-Pakete zum Speichern in Claude
```

Projektdaten gehören nicht ins Repository: `.gitignore` hält `projekte/` und die von der Pipeline
erzeugten Stände fern. Im Repository stehen die Skills und das Referenzbeispiel — dort allerdings nur
die Eingabedateien, nicht die Läufe.

Jeder Skill: `SKILL.md` (Anweisungen für Claude), `scripts/` (Python, deterministisch), `references/`
(Rubrik, Taxonomie, Formate). Die Skills sind einzeln lauffähig. Gemeinsame Bibliotheksdateien
(`workgraph_lib.py`, `validate_graph.py`, `apply_overrides.py`) liegen als identische Kopien in jedem
Skill, damit keiner vom anderen abhängt. `check_suite.py` prüft, dass die Kopien gleich sind,
`tools/sync_shared.py` zieht sie nach.

## Installation

Voraussetzung: Python 3.9 oder neuer, keine zusätzlichen Pakete.

### In Claude (Cowork oder claude.ai)

Die sechs `.skill`-Dateien aus `dist/` einzeln in den Chat ziehen und auf „Skill speichern“ klicken.
Reihenfolge egal.

### In Claude Code

Als Plugin, direkt aus diesem Repository:

```
/plugin marketplace add GodModeAI2025/Work-Transformation-Suite
/plugin install work-transformation-suite@work-transformation-suite
```

Oder von Hand: Den Ordner `skills/` (oder die sechs Unterordner) nach `~/.claude/skills/` kopieren,
projektbezogen auch nach `<repo>/.claude/skills/`. Die Skills finden sich gegenseitig über den
Geschwister-Pfad `../<skillname>`, deshalb zusammen in einen Ordner legen.

### Ohne Claude, mit den Skripten allein

Alles funktioniert auch als reines Kommandozeilenwerkzeug. Die Urteilsschritte (Extraktion,
Bewertung, Agentenbündelung) macht dann ein Mensch, indem er die JSON-Vorlagen ausfüllt.

Prüfen: `python3 skills/work-transformation/scripts/check_suite.py` → „Suite OK“. Der Check prüft
außer den Bibliothekskopien auch den Frontmatter jeder `SKILL.md` (Name gleich Ordnername,
Beschreibung höchstens 1024 Zeichen) und, im Repository, ob die Pakete in `dist/` zum Stand in
`skills/` passen. Wer einen Skill ändert, ruft danach `python3 tools/pack_skills.py` auf; das baut die Pakete
deterministisch neu. `python3 tools/sync_shared.py` gleicht die Bibliothekskopien ab.

Release: Ein Tag `vX.Y.Z` löst `.github/workflows/release.yml` aus. Der Workflow lässt die
gesamte Prüfung laufen, vergleicht Tag, Version in `.claude-plugin/plugin.json` und den
Changelog-Abschnitt (`tools/check_release.py`), und hängt die sechs `.skill`-Pakete mit
einer `SHA256SUMS`-Datei an das Release. Die Prüfsummen sind der einzige Beleg dafür, dass
eine heruntergeladene Paketdatei dem Stand des Tags entspricht.

Tests: `python3 -m unittest discover` führt die gesamte Suite aus, einschließlich eines vollständigen
Laufs des Referenzbeispiels unter `examples/order-to-cash/`. Die GitHub Action
`.github/workflows/check.yml` führt Check und Tests bei jedem Push und Pull Request auf Python 3.9,
3.11 und 3.13 aus.

## Pfade

Alle Skripte nehmen `--project <ordner>` und lösen ihn relativ zum aktuellen Arbeitsverzeichnis auf.
Innerhalb des Projekts sind alle Pfade fest und relativ (`00_input/`, `20_graph/` …). Skript-Pfade in
den SKILL.md-Dateien sind relativ zum jeweiligen Skill-Ordner. Es gibt keinen hart codierten
absoluten Pfad in der Suite. Der Projektordner lässt sich verschieben, kopieren, in Git legen.

Empfohlene Ablage: ein Ordner `projekte/` neben den Skills oder irgendwo auf dem Mac, den man mit
der Cowork-Session verbindet, z. B.

```
~/work-transformation-suite/
├── skills/            (Kopie der Suite oder Symlink)
└── projekte/
    └── kundenservice/ (ein Projektordner je Bereich)
```

Dann von `~/work-transformation-suite` aus: `python3 skills/work-transformation/scripts/run_pipeline.py --project projekte/kundenservice`.

## Der Ablauf

Die Suite trennt strikt: Claude urteilt, Skripte rechnen. Claude liest Quellen und schreibt die
Urteilsdateien (Extraktion, Bewertung, Agenten, Soll-Entwürfe, Prozesswert, Pilotpläne). Alles
andere, also IDs, Zusammenführung, Normalisierung, Klassifikation, Abdeckung, Deltas, Dashboard,
machen Skripte ohne Zufall und ohne Zeitstempel. Gleiche Eingaben ergeben byteidentische Ausgaben.
Der End-to-End-Test prüft genau das bei jedem Lauf.

Am schnellsten sieht man den Ablauf am Referenzbeispiel:

```
python3 skills/work-transformation/scripts/run_pipeline.py --project examples/order-to-cash
```

Fünf Rollen, 21 Aufgaben, zwei End-to-End-Prozesse, acht Agenten mit Verträgen, sechs Soll-Szenarien,
zwei Piloten — einer davon mit Messergebnissen. Was dabei entsteht und warum, steht in
`examples/order-to-cash/README.md`.

### Schritt 0: Projekt anlegen

```
python3 skills/work-graph-builder/scripts/init_project.py --project projekte/kundenservice \
  --name "Kundenservice Pilot" --organization "Meine Firma" --scope "Kundenservice – Vertrag und Abrechnung"
```

Quellen (Stellenbeschreibungen als PDF/Word/Markdown, Organigramme, SAP-Exporte) nach
`projekte/kundenservice/00_input/`.

### Schritt 1: work-graph-builder (Claude)

Sagen: „Bau den Arbeitsgraphen für projekte/kundenservice aus den Dateien in 00_input.“
Claude liest die Quellen, schreibt je Quelle `10_extraction/extract_<name>.json` (Format in
`work-graph-builder/references/extraction-format.md`) und ruft `build_graph.py` auf. Ergebnis:
`20_graph/work-graph_v001_builder.json` und `30_review/review_v001.md`.

Die Review-Liste ist für Fachexperten: je Rolle Aufgaben, Zeitanteile, Skills, fünf Fragen. Sie
brauchen fünf Minuten pro Rolle. Korrekturen kommen als Zeilen in `30_review/overrides.csv`:

```
entity_type;entity_id;field;value;reviewer;comment
role;ro_5cfc18da44e5;headcount;30;M. Muster;Stellenplan 2026
task;ta_0de7861cf28c;scores.human_judgment;8;M. Muster;Kulanz ist echtes Ermessen
task;ta_fb86d42a6741;status;approved;M. Muster;
task;ta_123456789abc;delete;true;M. Muster;macht eine andere Rolle
```

Die IDs stehen in der Review-Liste. Overrides gewinnen dauerhaft und überleben jeden Neulauf. Sie
sind die einzige Stelle, an der Menschen den Graphen ändern. Nie direkt in `20_graph/` editieren.

### Schritt 2: task-scorer (Claude)

Sagen: „Bewerte die Aufgaben.“ Claude exportiert `20_graph/scores_todo.json`, bewertet jede Aufgabe
nach der Rubrik (`task-scorer/references/rubric.md`: sechs Werte 0–10 plus Begründung) und speichert
`20_graph/scores.json`. `score_roles.py` leitet daraus ab:

- je Aufgabe: Automatisierungspotenzial, Modus (manuell / KI-unterstützt / an Agent delegiert),
  HAS-Level H1–H5, Zeithorizont
- je Rolle: zeitanteilgewichtete Kennwerte, Anteile Kern/assistiert/delegiert, Disruptionsscore,
  Disruptionstyp (eliminiert / transformiert / augmentiert / entstehend / stabil), Transformationslogik,
  nächster Schritt, bleibende und sinkende Skills

Alle Schwellen stehen als Konstanten am Kopf von `task-scorer/scripts/score_roles.py` und sind in der
Rubrik erklärt. Wer kalibrieren will, ändert sie dort, nicht in den Bewertungen.

### Schritt 2b: Prozesse aufnehmen (Claude, optional)

Für den Redesignmodus braucht die Suite, was in Stellenbeschreibungen nicht steht: den Fluss eines
Falls durch die Organisation. Sagen: „Nimm die Prozesse auf.“ Claude schreibt je Quelle
`10_extraction/process_<name>.json` (Format in `work-graph-builder/references/process-format.md`) und
ruft `build_processes.py` auf. Ergebnis: Prozesse, Schritte, Kanten, Systeme, Kontrollen und
Ausgangskennzahlen im Graphen.

Wichtig ist hier nur eines: **Bearbeitungszeit und Wartezeit getrennt erfassen.** In den meisten
Prozessen ist die Liegezeit der eigentliche Hebel, und wer beides vermischt, verliert ihn aus dem
Blick. Wenn die Summe der modellierten Schritte deutlich unter einer gemessenen Durchlaufzeit liegt,
sagt das Skript es — dann fehlen Schritte, und jedes spätere Delta rechnet auf zu kleiner Grundmenge.

Ein Projekt nach Schema 1.0 hebt `migrate_graph.py` verlustfrei auf 1.1. Die Migration rät nichts:
Sie legt die neuen Sammlungen leer an, mehr nicht.

### Schritt 3: agent-mapper (Claude)

Sagen: „Leite die Agenten ab.“ Claude exportiert Kandidaten (`agents_todo.json`, nach Muster
gruppiert), fragt nach bereits laufenden KI-Anwendungen, bündelt die Aufgaben zu 6–15
wiederverwendbaren Agenten (`agents.json`, Muster aus `agent-mapper/references/agent-patterns.md`) und
lässt `compute_coverage.py` rechnen: Abdeckung je Rolle, FTE-Äquivalent, Build/Buy/Hybrid, Horizont,
Priorität.

Für Agenten, die tatsächlich gebaut werden sollen, kommt ein **Capability Contract** dazu: Auslöser,
Ein- und Ausgaben, Lese- und Schreibrechte, Entscheidungsreichweite, Konfidenzschwelle,
Kontrollpunkt, Rückfallebene, Idempotenzschlüssel, Audit-Ereignisse, Servicezusage, Testmenge und
Kostendeckel (`agent-mapper/references/contract-format.md`). Der Vertrag nennt bewusst kein Modell —
Modelle wechseln schneller als Prozesse. `validate_contracts.py` prüft ihn zusätzlich gegen den
Prozess, in dem er läuft; `export_contracts.py` schreibt ihn als JSON und Markdown heraus.

### Schritt 4: process-redesigner (Claude, nur mit Prozessebene)

Sagen: „Entwirf die Soll-Prozesse.“ Der Ablauf im Detail steht in
`process-redesigner/SKILL.md`; in Kürze:

1. `export_process_candidates.py` legt je Prozess den Ist-Fluss und die maschinell erkannten
   Ansatzpunkte offen (Liegezeiten, Nacharbeit, Medienbrüche, mehrfach geprüfte gleiche Eingaben).
2. Claude entwirft **drei** Szenarien je Prozess — konservativ, ausgewogen, agent-nativ — mit den
   sechs Operatoren eliminieren, vereinfachen, zusammenführen, parallelisieren, automatisieren und
   Human Gate erhalten (`references/redesign-rules.md`, `references/blueprint-format.md`).
3. `build_blueprints.py` rechnet daraus Durchlaufzeit, Übergaben, Human Touchpoints und Nacharbeit
   und stellt sie dem Ist gegenüber. Claude schreibt keine Deltas; sie fallen an.
4. `validate_blueprints.py` prüft die Redesign-Regeln. Drei Dinge gehen nicht durch: ein Entwurf,
   der nur automatisiert; eine ersatzlos gestrichene Pflichtkontrolle; ein agent-natives Szenario
   ohne einen einzigen Human Gate.
5. `score_processes.py` priorisiert mehrdimensional statt nach FTE und sagt dazu, ob das
   Prioritätsband schon bei ±1 in einem einzelnen Faktor kippt (`references/value-rubric.md`).
6. `make_experiments.py` macht aus geprüften Entwürfen Pilotkarten mit Design, Guardrails,
   Stoppregeln und Rollback (`references/experiment-format.md`).
7. `compare_scenarios.py` schreibt den Vergleich als Markdown und CSV.

Freigaben laufen nicht über ein Feld im Graphen, sondern über `30_review/decisions.csv` und
`apply_governance.py`: mit Name, Datum und Begründung.

### Schritt 5: transformation-dashboard (Skript)

`build_dashboard.py` erzeugt `40_output/dashboard_vNNN.html` (eine Datei, offline, Farben per Theme-Datei anpassbar),
die CSV-Exporte und `report_vNNN.md`. Mit `--stamp "15.09.2026"` kommt ein Datum in die Kopfzeile.

Sobald Prozesse im Graphen liegen, ist die Prozessansicht die Hauptansicht: Ist-Fluss, Szenarien zum
Umschalten, Delta-Kennzahlen, veränderte Kontrollen, offene Annahmen, Pilotkarten und ein
Governance-Abschnitt, der zeigt, welche Zahl geschätzt, welche bestätigt und welche gemessen ist.
Die Rollenansicht bleibt vollständig erhalten, rückt aber dahinter — als Folgenansicht des
Prozessredesigns. Das ist Absicht: Sobald Organisationskästchen zuerst kommen, wird das Organigramm
zum Designobjekt, und genau das verhindert ein Redesign vom Ergebnis her.

### Alles auf einmal

```
python3 skills/work-transformation/scripts/run_pipeline.py --project projekte/kundenservice
```

führt alle Skript-Schritte aus und stoppt mit Exit-Code 3 und einer klaren Meldung, sobald eine
Claude-Eingabe fehlt („STOPP: keine scores.json … Nächster Schritt: Skill task-scorer“). Das ist auch
der Befehl für „weiter machen“: Nach jeder Korrektur in `overrides.csv` oder `scores.json` einmal
laufen lassen, alles Nachgelagerte wird neu gerechnet, unveränderte Stände erzeugen keine neue Version.

`--until builder|processes|scorer|mapper|redesign|dashboard` hält früher an. `--skip-redesign`
überspringt die Soll-Entwürfe, auch wenn Prozesse erfasst sind. Ohne Prozesse sagt die Pipeline, dass
sie im Diagnosemodus bleibt, und läuft normal durch.

## Damit aus der Analyse kein Scheinergebnis wird

Sechs Vorkehrungen. Die ersten vier stammen aus dem ersten echten Einsatz, die letzten beiden kamen
mit dem Redesignmodus dazu — dort ist die Versuchung größer, weil jede Zahl über einen Prozess, den
es noch nicht gibt, eine Schätzung ist.

### Belastbarkeit je Rolle

Jede Rolle trägt eine Stufe `evidence` (belastbar / teilweise geprüft /
ungeprüft), abgeleitet daraus, ob die Zeitanteile aus der Quelle stammen (`time_shares_source`),
ob Experten geprüft haben, wie viel aus abgeleiteten Aufgaben stammt und ob der Headcount bekannt
ist. Das Dashboard zeigt sie als Tag an jeder Rolle und in der Übersicht. Eine Rollenkarte, in der
alles „ungeprüft“ ist, ist ein Gesprächsangebot, kein Ergebnis.

### Kipp-Analyse

Für jede Aufgabe werden Maschinenanteil, Urteilsbedarf und Fehlergewicht um ±1
verändert und die Rollenwirkung neu berechnet. `stability` sagt, ob die Einstufung stabil,
grenznah oder wackelig ist, `flip_examples` nennt die Aufgabe, an der sie hängt. Genau diese
Aufgabe sollte der Experte zuerst prüfen.

### Stellen

Prozessrollen sind keine Stellen. `00_input/positions.csv`
(`position_id;title;org_unit;role;share`) ordnet Stellen mit Anteilen den Rollen zu.
`import_positions.py` rechnet daraus Vollzeitäquivalente und Headcounts. Keine Personennamen.

### Kalibrierung

`task-scorer/scripts/calibrate.py` vergleicht Expertenkorrekturen (Overrides auf
`scores.*`) mit den generierten Werten und meldet je Feld, ob die Experten systematisch anders
liegen. Ab fünf Korrekturen mit mittlerer Abweichung ≥ 0,75 sollte man den Anker in der Rubrik
verschieben statt weiter einzeln zu korrigieren.

### Geschätzt, bestätigt, gemessen

Jede Kennzahl trägt ihre Belastbarkeit (`estimated`, `expert_confirmed`, `observed`) und, sobald
sie Evidenz behauptet, einen `provenance`-Eintrag mit Quelle, Fundstelle, Ersteller, Reviewer und
Konfidenz. Wer `observed` schreibt, ohne die Fundstelle zu liefern, kommt am Validator nicht
vorbei — eine behauptete Messung ohne Beleg ist schlechter als eine ehrliche Schätzung, weil sie
sich nicht widerlegen lässt.

Die drei Stufen einer Kennzahl sind strikt getrennt: `baseline` ist der heutige Wert, `target` die
Zusage eines Entwurfs, `observed` das Ergebnis eines Piloten. Ein gemessener Pilotwert überschreibt
den Ausgangswert ausdrücklich **nicht**; sonst verglichen sich Soll und Soll, und jedes Redesign
sähe gut aus. Dashboard und Bericht zeigen beide Spalten nebeneinander.

Dazu kommt eine Plausibilitätsprüfung, die erfahrungsgemäß oft anschlägt: Liegt die Summe der
modellierten Prozessschritte deutlich unter einer gemessenen Durchlaufzeit, sagt das Skript es. Dann
fehlen Schritte oder Liegezeiten — und jedes Delta darunter rechnet auf zu kleiner Grundmenge.

### Bänder statt Rangliste

Prozesse landen in „Jetzt“, „Als Nächstes“, „Später“ oder „Zurückstellen“, nicht auf Platz 1 bis n.
Zu jedem Prozess wird zusätzlich geprüft, ob das Band schon kippt, wenn ein einzelner Faktor um ±1
danebenliegt; wenn ja, steht das im Dashboard und im Bericht. Ein Score von 6,8 gegenüber 6,9
bedeutet nichts, solange die Eingaben Schätzungen auf einer Zehnerskala sind. Ein kippeliges Band
ist auch kein Mangel, sondern ein Befund: Es zeigt, welchen einen Faktor man mit einem Fachexperten
klären sollte, statt über die Reihenfolge zu streiten.

## Versionierung

`project.json` zählt `graph_version` hoch. Jeder Schritt, der den Inhalt ändert, schreibt
`20_graph/work-graph_vNNN_<stage>.json` und aktualisiert `work-graph_latest.json`. Läuft ein Schritt
ohne inhaltliche Änderung, meldet er „Unverändert“ und legt keine Version an. Alte Versionen bleiben
liegen. `diff` zwischen zwei Versionen zeigt, was sich geändert hat. Das ersetzt keine Datenbank mit
Freigabeworkflow, aber es reicht für einen Piloten und lässt sich in Git versionieren.

## Was „deterministisch“ hier konkret heißt

- IDs sind SHA1-Hashes der normalisierten Namen (`ro_…`, `ta_…`, `sk_…`, `ag_…`). Gleicher Name,
  gleiche ID, in jedem Lauf und auf jedem Rechner. Ein umbenannter Task bekommt eine neue ID und
  verliert Bewertung und Overrides. Deshalb Namen stabil halten.
- Alle Listen sind sortiert, JSON hat sortierte Schlüssel, keine Zeitstempel im Inhalt.
- Alle Regeln (Modus, HAS, Horizont, Disruptionstyp, Abdeckung, Priorität) sind Formeln mit
  Konstanten, keine KI-Entscheidungen.
- Rundung ist kaufmännisch auf eine Nachkommastelle. Rundungsreste gehen deterministisch auf das
  größte Element.
- Der einzige nicht-deterministische Teil ist Claudes Urteil in den Eingabedateien (`extract_*.json`,
  `process_*.json`, `scores.json`, `agents.json`, `blueprints.json`, `process_value.json`,
  `experiments.json`). Die SKILL.md-Dateien halten ihn stabil durch feste Formate, Taxonomie,
  Ankerbeispiele und die Regel, vorhandene Namen wiederzuverwenden. Für die Bewertung gilt: Wer
  Werte ändern will, ändert `scores.json` (Claude) oder `overrides.csv` (Mensch), nie beides für
  dasselbe Feld. Für Freigaben gilt: ausschließlich `30_review/decisions.csv`.
- Der End-to-End-Test rechnet das Referenzbeispiel bei jedem Lauf neu und vergleicht Prüfsummen
  aller Ausgaben. Determinismus ist damit nicht behauptet, sondern geprüft — auf Python 3.9, 3.11
  und 3.13.

## Grenzen

Keine Integration in SuccessFactors oder andere HR-Systeme, kein Tracking der Agentennutzung nach dem
Rollout, keine Prozess-Mining-Anbindung. Für genau diese Dinge verkaufen kommerzielle Plattformen ihr
Produkt. Für die Frage, ob eine solche Analyse für einen Bereich überhaupt belastbare Ergebnisse
liefert, reicht die Suite. Der Ablauf ist am Pilotbereich mit 20 bis 40 Rollen entstanden und bis über
200 Rollen in einem Dashboard gelaufen.

Für den Redesignmodus gilt eine zusätzliche Grenze, die man laut sagen sollte: **Ein Soll-Prozess aus
Interviews und Stellenbeschreibungen ist ein Entwurf, keine Prognose.** Die Suite kann aus Rollendaten
kein Unternehmen verlässlich „neu bauen“. Für belastbare Soll-Prozesse braucht sie
Prozessbeobachtungen, Systemdaten, Fachinterviews und gemessene Ausgangswerte. Wo die fehlen, steht
überall „geschätzt“ — im Graphen, im Bericht und im Dashboard. Diese Kennzeichnung ist kein Schmuck:
Sie ist der Unterschied zwischen einer Entscheidungsgrundlage und einer Folienzahl.

Freigaben kennt die Suite als nachvollziehbares Log (`30_review/decisions.csv`) mit Name, Datum und
Begründung — nicht als Workflow mit Rollen, Rechten und Benachrichtigungen.

## Weiterentwicklung

- Schwellen kalibrieren: 20–30 Aufgaben mit Expertenwerten sammeln, dann Konstanten in
  `score_roles.py` anpassen oder `autoresearch-skills` auf die Rubrik ansetzen.
- Prozesswert anders gewichten: `process-redesigner/assets/value-weights.json` kopieren, Gewichte
  ändern, neue `config_version` vergeben und mit `--weights` übergeben.
- Skill-Taxonomie erweitern: `work-graph-builder/references/skill-taxonomy.md`, optional ESCO-Export
  in `00_input/esco/` mit `esco_uri` je Skill.
- Agentenmuster ergänzen: `agent-mapper/references/agent-patterns.md` plus `ALLOWED_PATTERNS` und
  `PATTERN_KEYWORDS` in den Mapper-Skripten.
- Dashboard-Layout: `CSS`, `JS` und Bausteinfunktionen in `build_dashboard.py`.
- Prozessdaten aus Prozess-Mining statt aus Interviews: `build_processes.py` liest ein einfaches
  JSON-Format; ein Export aus einem Mining-Werkzeug lässt sich darauf abbilden. Damit werden aus
  geschätzten Liegezeiten gemessene — der größte Qualitätssprung, den dieses Modell kennt.

## Methodische Quellen

**Diagnose.** Stanford, „Future of Work with AI Agents“ (Shao et al. 2025, WORKBank, Human Agency
Scale H1–H5, arXiv 2506.06576). Anthropic Economic Index, Automation gegen Augmentation auf
O*NET-Task-Ebene. ESCO v1.2, die EU-Skill-Taxonomie. Dazu die Metriken kommerzieller
AI-Transformation-Dashboards: Automation Potential, Human Judgment, Disruption Score, Rollen-Typen.

**Redesign.** Die Operatorenfolge eliminieren → vereinfachen → zusammenführen → automatisieren
stammt aus der ESIA-Schule der Prozessneugestaltung; ergänzt sind Parallelisierung und der
ausdrückliche Kontrollpunkt. Die Begründung, warum der Hebel auf der Ebene des Ablaufs und nicht der
Einzelaufgabe liegt, liefert
[MIT Sloan zur Verkettung von Aufgaben](https://mitsloan.mit.edu/ideas-made-to-matter/how-ai-reshaping-workflows-and-redefining-jobs)
(Demirer, Horton, Immorlica, Lucier: „Chaining Tasks, Redefining Work“). Die Gegenrichtung —
dass KI außerhalb ihrer Fähigkeitsgrenze Ergebnisse verschlechtert und Expertenurteil deshalb
Designbestandteil bleibt — findet sich bei
[MIT Sloan zur Produktivität hochqualifizierter Arbeit](https://mitsloan.mit.edu/ideas-made-to-matter/how-generative-ai-can-boost-highly-skilled-workers-productivity).
Für das Vorgehen von der Wertschöpfungskette und vom Geschäftsziel aus:
[SAP zu generativer KI in der Prozessexzellenz](https://www.sap.com/blogs/ext-generative-ai-for-business-process-excellence).

**Governance.** Die Regel, dass ein irreversibler automatisierter Schritt einen benannten
menschlichen Kontrollpunkt braucht, folgt der Logik von
[Artikel 14 der EU-KI-Verordnung](https://artificialintelligenceact.eu/article/14/) (wirksame
menschliche Aufsicht über Hochrisiko-Systeme). Die Suite ist kein Compliance-Werkzeug und behauptet
keine Konformität; sie sorgt dafür, dass die Angaben, die eine solche Prüfung braucht, überhaupt
erfasst und nachvollziehbar sind.

## Lizenz

Apache License 2.0, siehe `LICENSE`.
