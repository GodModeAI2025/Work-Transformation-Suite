# Work-Transformation-Suite

Acht Claude-Skills mit zwei Betriebsarten und einer zweiten Stimme.

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

**Beschäftigtensicht.** Die Bewertung sagt, was Technik kann. Eine Befragung der Beschäftigten sagt, was sie
abgeben wollen und wie viel sie beteiligt bleiben wollen (Skill `agency-audit`, Auditrahmen nach Shao et al. 2025).
Beides nebeneinander ergibt vier Zonen je Aufgabe: Freigabe, Vorsicht, Entwicklung, Nachrang. Dashboard, Berichte,
Fahrplan, Verträge und Rollen.md nutzen sie. Ausgewertet wird nur ab fünf Antworten je Aufgabe.

**Zwei Spuren, ein Graph.** Spur B ist das Prozessredesign: Ketten, Übergaben, Wert je Prozess. Das ist der
belastbarere Weg, weil eine einzelne Rolle nur Teile eines Ablaufs sieht — fünfmal 2,8 gesparte Stunden sind keine
zehn, wenn die Übergaben bleiben. Spur A ist die Rollenaggregation je Jobfamilie: technisches und realisierbares
Potenzial, Zielbild je Rolle. Sie ist schneller und gröber und der richtige Anfang, solange noch keine
Prozessaufnahme vorliegt. Der Bericht sagt, welche Spur ihn trägt.

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
│   ├── agency-audit/             Schritt 2a: Beschäftigtenbefragung → Zonen, Agency-Lücke, Reibung
│   ├── agent-mapper/             Schritt 3: Agentenbibliothek → Abdeckung, Capability Contracts
│   ├── process-redesigner/       Schritt 4: Soll-Szenarien, Prozesswert, Piloten
│   ├── transformation-dashboard/ Schritt 5: HTML-Dashboard, CSV, Bericht
│   └── transformation-roadmap/   Schritt 6: Wellenraster, Entscheidungsvorlage, HR-Einseiter
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

Die acht `.skill`-Dateien aus `dist/` einzeln in den Chat ziehen und auf „Skill speichern“ klicken.
Reihenfolge egal.

### In Claude Code

Als Plugin, direkt aus diesem Repository:

```
/plugin marketplace add GodModeAI2025/Work-Transformation-Suite
/plugin install work-transformation-suite@work-transformation-suite
```

Oder von Hand: Den Ordner `skills/` (oder die acht Unterordner) nach `~/.claude/skills/` kopieren,
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
Changelog-Abschnitt (`tools/check_release.py`), und hängt die acht `.skill`-Pakete mit
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

### Schritt 0a: Profil des Hauses und Referenzbibliothek

```
python3 skills/work-graph-builder/scripts/init_project.py --project projekte/netz --name "Netz" \
  --branche energieversorgung --plattform microsoft --rechtsraum DE
python3 skills/work-graph-builder/scripts/seed_from_library.py --project projekte/netz --branche energieversorgung --cluster Netzbetrieb
```

Branche, Plattformprofil und Rechtsraum stehen in `project.json`. Die Referenzbibliothek
(`skills/work-graph-builder/library/`) liefert dazu einen Vorrat: Branchenpakete mit typischen Rollen und Aufgaben
(`allgemein`, `bauwirtschaft`, `energieversorgung`, `wasserversorgung`, `automobilindustrie`, `maschinenbau`, `chemie_pharma`,
`gesundheitswesen`, `oeffentliche_verwaltung`, `handel`, `logistik`, `banken`, `versicherungen`), den Rechtsrahmen Deutschland
als Themen mit Gesetz und Fundstelle, und vier Plattformprofile (`microsoft`, `google`, `mischbetrieb`, `unabhaengig`) mit den
Diensten je Agentenmuster. `seed_from_library.py` kopiert ausgewählte Rollen als Seiten ins Projekt, registriert die Quelle des
Pakets als „reference“ und überschreibt nie, was schon da ist. Übernommene Einträge haben den Belegstand „reference“; sie
werden am Haus angepasst und bestätigt. Review-Liste und Rollen.md nennen je Rolle die berührten Rechtsthemen (Prüfaufträge,
keine Rechtsberatung), Verträge und Tool-Anbindungen die Umsetzung auf dem Plattformprofil (Vorschlag, kein
Beschaffungsentscheid). `library_catalog.py` zeigt den Bestand. Regeln: `skills/work-graph-builder/references/referenzbibliothek.md`.

### Schritt 0b: Quellen registrieren

```
python3 skills/work-graph-builder/scripts/register_source.py --project projekte/kundenservice \
  --file 00_input/stellenbeschreibungen.md --title "Stellenbeschreibungen Kundenservice"
```

Jede Quelle, auf die sich der Graph berufen soll, liegt danach treu als Markdown unter `00_input/sources/`,
mit `source_id` (Hash des Inhalts), Titel, Herkunft und Datum in `register.jsonl`. PDF, Word und Excel liest
Claude und legt die treue Fassung ab (`--original <datei>` hält den Hash des Originals fest, kopiert es
aber nicht). Der Inhalt wird nicht verändert; Zugangsdaten und absolute Pfade stoppen die Aufnahme.

Belege im Graphen haben die Form `src-<hash>@<fundstelle>` (Überschriftenanker, Zeile, Bereich oder
Freitext). `locate_source.py` zeigt Anker und findet Zitate, `check_evidence.py` zählt je Sammlung belegt,
geschätzt und unbelegt und prüft jede Fundstelle gegen den Quelltext (`30_review/belege_vNNN.md`). Mit
`evidence_policy: strict` in `project.json` hält die Pipeline an, solange eine Aussage ohne Herkunft im
Graphen steht; der Standard `warn` meldet sie nur.

### Schritt 0c: Seiten statt Register

Seit Schema 1.3 kann ein Projekt Rollen, Aufgaben, Skills, Bewertungen und Agenten als Markdown-Seiten unter
`05_pages/` führen (Format: `skills/work-graph-builder/references/seiten-format.md`). Liegen Seiten vor, sind sie
die Wahrheit: `compile_pages.py` übersetzt sie vor jedem Pipeline-Lauf in die JSON-Register, und die Register sind
nur noch abgeleitet. Der Kopf jeder Seite ist flach (eine Ebene, keine Objekte), der Rumpf trägt Zweck,
Beschreibung, Skills, Schritte, Begründung und beim Agenten den Vertrag als JSON-Block. Fehler meldet der Compiler
mit Datei und Zeile, geraten wird nicht. `export_pages.py` holt ein bestehendes Projekt einmalig auf Seiten.
Prozesse, Blueprints und Experimente bleiben JSON, weil ihre Struktur verschachtelt ist.

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

Zwei optionale Merkmale je Aufgabe, `interpersonal` und `tacit_expertise` (auf Seiten `score_interpersonal`,
`score_tacit_expertise`), heben die HAS-Stufe auf mindestens H4 beziehungsweise H3. Je Skill entsteht die
**Kompetenzverschiebung** (nötige Human Agency gegen heute gebundene Arbeit), der HR-Bericht stellt sie gegenüber.
`score_roles.py` meldet, wenn auffällig viele Rollen überwiegend H1 sind. Für eine **Zweitbewertung** füllt eine
zweite Person oder ein zweiter, unabhängiger Lauf dieselbe Vorlage aus; `compare_scores.py` zeigt Übereinstimmung je
Feld (Anteil innerhalb ±1, Krippendorffs Alpha) und die Aufgaben, die eine Klärung brauchen.

### Schritt 2a: agency-audit (Befragung, optional)

Sagen: „Bereite eine Befragung der Beschäftigten vor.“ Vorher klären: Zweck, Beteiligung der
Beschäftigtenvertretung (ein solcher Fragebogen ist ein Personalfragebogen nach § 94 BetrVG), Rohdaten und Löschfrist.

```
python3 skills/agency-audit/scripts/export_audit_sheet.py --project projekte/kundenservice
# Antworten als CSV nach 00_input/befragung/ legen, dann
python3 skills/agency-audit/scripts/import_audit.py --project projekte/kundenservice
python3 skills/agency-audit/scripts/score_agency.py --project projekte/kundenservice
```

Der Fragebogen fragt je Aufgabe Vertrautheit, Sorge um den Arbeitsplatz, Freude, den Wunsch nach Automatisierung,
vier Merkmale und die gewünschte Beteiligung auf der Human Agency Scale. Der Import weist Spalten mit Namen,
E-Mail oder Personalnummer zurück, zählt nur Aufgaben, die jemand selbst erledigt, und schreibt nur Zusammenfassungen
ab fünf Antworten. `score_agency.py` legt je Aufgabe Zone und Agency-Lücke an (gewünschte minus nötige Stufe), je
Rolle die Reibung (Jensen-Shannon-Distanz der beiden Verteilungen), und schreibt `30_review/beschaeftigtensicht_vNNN.md`.
`run_pipeline.py` macht das selbst, sobald Antworten vorliegen. Format: `skills/agency-audit/references/befragung.md`.

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

Ein Projekt nach Schema 1.0 oder 1.1 hebt `migrate_graph.py` verlustfrei auf 1.2. Die Migration rät nichts:
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

Liegt eine Befragung vor, kommt der Abschnitt „Sicht der Beschäftigten“ dazu: Landschaft aus Wunsch und
Automatisierungspotenzial je Aufgabe, Matrix der Beteiligung (gewünscht gegen nötig), Reibung je Rolle, Zonen je Cluster.

### Schritt 6: transformation-roadmap (Skript, Texte von Claude)

Verteilt Agenten und Use Cases auf Wellen und baut daraus die Unterlagen für eine Entscheidungsrunde.

```
python3 skills/transformation-roadmap/scripts/plan_waves.py --project projekte/kundenservice
python3 skills/transformation-roadmap/scripts/build_documents.py --project projekte/kundenservice
```

- **Raster:** `fahrplan_vNNN.md/.html/.csv` und `roadmap_vNNN.json`. Jedes Vorhaben erhält einen Score aus Wert, Reichweite,
  Umsetzbarkeit, Reifegrad und Prozessrang; fehlende Größen fehlen auch im Score und werden benannt. Laufende Vorhaben
  liegen in Welle 1, Orchestratoren folgen den Agenten, die sie steuern. Betroffene Rollen und FTE je Welle zählen
  jede Aufgabe einmal. Liegt eine Befragung vor, beginnt ein Vorhaben, dessen Arbeit überwiegend in der Vorsichtszone
  liegt, nicht in Welle 1, außer jemand entscheidet es.
- **Entscheidungen:** `30_review/wellen.csv` (`eintrag;welle;begruendung;entschieden_von;datum`). Ohne benannte Person
  bleibt eine Zuordnung Vorschlag. Zeiträume setzt das Raster nicht selbst.
- **Unterlagen** in `40_output/dokumente/`: Entscheidungsvorlage, Einseiter für HR, Anhang mit allen Vorhaben, Methodik, je als
  Markdown und HTML. Tabellen kommen aus dem Graphen; Anlass, Pilot, Vorgehen, Beschluss und Kernbotschaft stehen als
  Textfelder in `30_review/dokumente/texte.json`, jedes mit Quelle. Was das Material nicht hergibt, bleibt „❓ offen“.
  Jedes Dokument nennt oben seinen Stand (Entwurf oder versandfertig); mit `--strict` wird ein Entwurf zum Fehler.

Regeln und Grenzen: `skills/transformation-roadmap/references/wellenlogik.md` und `dokumente.md`.

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

## Realisierbarkeit, Zielbild und Nutzungsstand (ab Schema 1.2)

Alles in diesem Abschnitt ist optional und additiv. Ein Projekt, das nichts davon füttert, läuft unverändert.

### Technisch möglich gegenüber auffangbar

Die Bewertung sagt, wie viel Arbeit technisch frei wird. Ob daraus Produktivität entsteht, hängt davon ab, ob die
Organisation die Zeit auffängt: durch Wachstum, durch Fluktuation und Altersteilzeit oder durch Umbesetzung. Sonst
startet man zwanzig Automatisierungen und bekommt einen Effekt, der nirgends ankommt.

An der Rolle stehen dazu Overrides: `absorption` (`growth`, `attrition`, `redeployment`, `none`), optional
`absorption_pct` und `day_rate_eur`. Daraus rechnet `score_roles.py` je Rolle `fte_released_technical` und
`fte_realisable`. **Fehlt die Angabe, bleibt die Zahl leer — „nicht bewertet“ ist nicht „null“.** Das Dashboard zeigt
beide Werte je Jobfamilie nebeneinander.

### Zielbild je Rolle

`build_target_roles.py` leitet aus den Aufgabenmodi ab, was je Rolle bleibt, wie viele FTE danach übrig sind, was
davon die Organisation auffangen kann und welche Rollen im selben Cluster sich zusammenlegen ließen. Das ist ein Entwurf
aus Schätzungen. Welche Rollen das Unternehmen künftig will, ist eine Strategiefrage, die diese Zahlen vorbereiten, aber
nicht beantworten.

### Reichweite, Blindflecken und Use-Case-Register

`import_usecases.py` liest die eigenen Use Cases (`00_input/usecases.csv`). `export_reach.py` beantwortet danach zwei
Fragen: Für wie viele Rollen und FTE gilt dieser Agent oder Use Case, und welche hochwertigen Prozesse hat bisher
niemand angefragt? Letzteres ist die Liste, die man nicht sieht, wenn man nur bedient, was am lautesten gefordert wird.

### Nutzungsstand, nur aggregiert

`import_adoption.py` liest, in wie vielen Stellen einer Rolle ein Agent priorisiert, im Bau oder in Nutzung ist. Nur Rolle
× Agent, nie Person × Agent. Rollen mit weniger als fünf Stellen werden unterdrückt gespeichert, ohne Zahlen, und der
Validator lehnt jeden Satz darunter ab. Eine Quote für drei Stellen wäre eine Aussage über drei Menschen. Capability
Contracts dürfen eine `telemetry` mit `level: "aggregate"` tragen; Felder wie Person oder Fallinhalt lehnt der Validator ab.

### Kein KI-Fall

Jeder Soll-Schritt kann eine `solution_class` tragen: `ai`, `interface`, `process_change` oder `rule_or_rpa`. Wer
84 PDFs von Hand öffnet, braucht eine Schnittstelle, kein Sprachmodell. Der Szenarienvergleich zählt die Schritte ohne KI.
Dazu gehört der Interviewleitfaden in `work-graph-builder/references/interview-leitfaden.md`: drei Fragen (Schritte,
Systeme, Gefühl), das Feld `pain` am Prozessschritt und die Regel, zuerst zu fragen, ob ein Schritt überhaupt gebraucht wird.

### Rahmen vor dem Pilot

Piloten tragen `frame_confirmed` und `frame_note`. Ohne bestätigten Rahmen — Beschäftigtenvertretung beteiligt, Zusagen
zur Beschäftigung benannt, Zweck der Erhebung klar — warnt der Validator vor dem Start. Wer weiß, dass seine Antworten zur
eigenen Ersetzung führen können, antwortet vorsichtig, und die Datenlage wird schlechter statt besser.

### Skill-Export

`export_skill.py` macht aus einem Capability Contract das Gerüst eines Skills: `SKILL.md`, ein deterministisches
`run.py` (Eingabeprüfung, Idempotenz, Konfidenzschwelle, Kontrollpunkt, Rückfall, Audit), eine Hülle für die Testmenge und
eine Nutzungsmeldung, die nur Zählwerte schickt. Es ist ein Gerüst: Die Systemaufrufe sind `TODO`, die Testmenge leer.
Eine Skill-Anweisung allein ist ein Prompt; was deterministisch sein soll, gehört in ein Skript.

### Aufgabenkarte

Neben der Rollenmatrix zeigt das Dashboard alle bewerteten Aufgaben auf einer Karte und in einer Rangliste. Die Rangliste
sortiert nach **Exposition** (Automatisierungspotenzial ÷ 10 × gebundene Arbeit), die **Fehlerfolge** steht daneben. Eine
Aufgabe mit hoher Exposition und hoher Fehlerfolge bekommt den Hinweis „Fehler teuer“: Dort gehört ein Mensch in den Ablauf.

### Datenaufbereitung: sichten, vorschlagen, anbieten

Gute Analysen hängen mehr an der Aufbereitung als am Modell. `inventory_sources.py` sichtet `00_input/`, ordnet jede Datei einer
Quellenart zu (interne Stellenbeschreibung, externe Anzeige, Positionsliste, Level-Struktur, Prozessbeschreibung, Kursunterlage,
Geschäftsbericht, …), zeigt, welche Teile des Modells noch ohne Quelle sind, und schlägt die passenden Methoden vor — mit Befehl. Die
Suite bietet sie an und wählt nicht still. Katalog mit Eingaben, Ergebnissen und Grenzen:
`skills/work-graph-builder/references/datenaufbereitung.md`.

| Methode | Skript | Zweck |
|---|---|---|
| Quellenregister | `register_source.py`, `locate_source.py`, `check_evidence.py` | Quellen treu als Markdown mit `source_id` führen, Belege `src-…@…` je Aussage, Belegbericht mit Fundstellenprüfung |
| Vollständigkeitsprüfung | `check_completeness.py` | Rolle gegen eine anpassbare Vorlage prüfen; Lücken nennen, woher sie zu füllen sind. Füllt nichts auf |
| Aufgabencluster | `dedupe_tasks.py` | Dieselbe Arbeit in mehreren Rollen finden. Kandidaten, bis ein Fachexperte mit Namen bestätigt |
| Zusammenarbeit | `derive_collaboration.py` | Rollenpaare mit Belegen: Übergabe im Prozess, gemeinsame Stelle, gleiche Einheit |
| Allgemeine Regeln | `apply_overrides.py` mit Selektoren | Eine Expertenaussage wirkt auf alle betroffenen Rollen (`cluster:`, `family:`, `role:`, `*`) |
| Level und Kostensatz | `import_levels.py` | Planwert je Arbeitstag nach Level; gesetzte Werte bleiben |
| Referenzautomatisierungen | `export_agent_candidates.py` | Kuratiertes Register mit Quelle und Evidenzgrad; Treffer erscheinen bei den Agentenkandidaten |

Ehrlich zu den Grenzen: Die Aufgabencluster beruhen auf gleichen Wörtern, nicht auf gleicher Bedeutung. Die Suite scrapt keine öffentlichen
Daten und füllt keine Lücken still auf; was sie nicht aus einer Quelle hat, bleibt „ergänzt“ oder „geschätzt“.

### Rollen.md: eine Datei, die ein Agenten-Harness als Kontext lädt

Für eine oder mehrere ausgewählte Rollen erzeugt `build_rollen_md.py` die **Rollen.md** mit fünf Abschnitten:

| Abschnitt | Was drinsteht | Aus dem Graphen |
|---|---|---|
| 1) Firmenprofil | Was das Unternehmen tut und für wen; damit ordnet die KI Aufgaben im richtigen Markt ein | Organisation, Bereich, Empfänger der Prozessergebnisse. Geschäftsmodell, Markt, Produkte bleiben offen |
| 2) Rollenprofil | Verantwortung, Tools, wiederkehrende Aufgaben, Zeitfresser | Zweck, Aufgaben mit Häufigkeit und Zeitanteil, Systeme, Entscheidungsräume; Zeitfresser aus gebundener Zeit, Reibung der Prozessaufnahme, Liegezeit und Rückläufern |
| 3) Team-Kontext | Mit wem, wen wann einbeziehen, über welchen Kanal was läuft | Übergaben mit Richtung und Kanal (System, E-Mail, Ticket, …), Eskalationen, Organisationseinheit |
| 4) Prioritäten & Ziele | Woran gerade gearbeitet wird; der lebendigste Abschnitt, einmal im Monat aktualisieren | Prozessergebnisse und Kennzahlen; die Prioritäten selbst bleiben offen |
| 5) Arbeits- & Kommunikationsstil | Wie die Person arbeitet und klingt, mit Do's und Don'ts für KI-Texte | fast alles offen; abgeleitete Hinweise sind als „bitte bestätigen“ markiert |

```
python3 skills/agent-mapper/scripts/build_rollen_md.py --project <projekt> --role "Forderungsmanager"
python3 skills/agent-mapper/scripts/build_rollen_md.py --project <projekt> --role "Forderungsmanager;Kreditprüfer"
python3 skills/agent-mapper/scripts/build_rollen_md.py --project <projekt> --all --split
```

Mehrere Rollen landen in einer Datei: das Firmenprofil einmal, danach je Rolle die Abschnitte 2 bis 5. Mit `--split` bekommt jede Rolle ihre eigene Datei. Der
Graph kennt eine Person nicht: Was er nicht weiß, steht als „❓ offen“ und wird nicht erfunden; das Interview aus dem Setup-Paket füllt es. Ein erneuter Lauf
überschreibt keine bearbeitete Datei (neuer Stand als `.vorschlag`).

### Den Rest nicht erfragen, sondern aus Material holen

Ein Graph kennt keine Person: nicht ihre Prioritäten, nicht ihren Ton, nicht, was sie nervt. Das lässt sich im Interview erfragen — oder aus Material holen, das ohnehin
existiert. Material unter `00_input/kontext/` (`firma/`, `<rolle>/texte`, `<rolle>/transkripte`, `<rolle>/projekte`) wertet `extract_context_evidence.py` aus und liefert
**Vorschläge mit Quelle, Fundstelle und Zitat**:

| Feld | Material | Verfahren |
|---|---|---|
| Geschäftsmodell, Kunden, Produkte, Markt, Fachbegriffe | Firmentexte | Sätze mit typischen Mustern, Zählung von Branchenbegriffen |
| Zeitfresser, Kanäle, Prioritäten, Ziele | Transkripte, Projektdokumente | Zeilen mit Reibungs-, Kanal-, Prioritäts- und Zielwörtern |
| Tonalität, Formate, Do's | eigene Texte | **Messung**: Anrede je Text, Satzlänge, Listenanteil, wiederkehrende Wendungen, Schlussformel |
| Don'ts | eigene Texte | typische KI-Floskeln, die in den eigenen Texten nie vorkommen |

In der Rollen.md erscheinen sie als „✎ Vorschlag aus Dokument, bitte bestätigen“, nie als Tatsache. Ein Stilprofil entsteht erst ab drei Texten und 600 Wörtern; darunter steht
„zu wenig Material“. Ein Eintrag ohne Zitat und Quelle wird abgelehnt. Was Skripte nicht lesen (PDF, Word, Mail, Kalender), liest Claude und trägt es im selben Format ein
(`<rolle>.claude.json`). E-Mail-Adressen, Telefonnummern und Anreden mit Namen werden maskiert, Personennamen nicht gesucht; Transkripte enthalten Daten Dritter und gehören nur mit
Einverständnis ins Projekt. Was bleibt (Qualitätsverständnis, gewünschte Rückfrage), klärt das Interview. Details und Grenzen: `skills/agent-mapper/references/kontext-aus-dokumenten.md`.

Für ein ganzes Team entsteht beim Aufruf mit mehreren Rollen zusätzlich `Teamstart.md`, eine Agenda für einen Mini-Hackathon (Rahmen, Rollen.md, Agent, erste Skills, Erfolgsmoment),
und je Rolle ein `skill-ideen-prompt.md`, der aus der gefüllten Rollen.md fünf lohnende Skills vorschlagen lässt.

### Setup-Paket je Rolle: ein Arbeitsagent auf Zuruf

Die Analyse sagt, welche Aufgaben sich lohnen. Eine Person braucht außerdem etwas, das sie am Montagmorgen öffnen kann. Auf Zuruf („Baue das Setup für
den Forderungsmanager“) erzeugt `build_role_setup.py` für genau diese Rolle ein Paket nach der Struktur eines persönlichen KI-Setups:

| Datei | Inhalt | Woher |
|---|---|---|
| `kontext/Rollen.md` | Die fünf Abschnitte: Firmenprofil, Rollenprofil, Team-Kontext, Prioritäten & Ziele, Arbeits- & Kommunikationsstil | vorbelegt aus dem Graphen, Rest „❓ offen“ |
| `kontext/interview-prompt.md` | Interview, das die offenen Felder füllt; verbietet Erfinden | eigener Text |
| `agent/systemprompt.md` | Schlank: Kontext laden, einordnen, Skill wählen, prüfen, bei Lücke fragen. Keine Aufgaben | eigener Text |
| `skills/<skill>/` | Drei bis fünf Skills nach Zeitanteil × Automatisierbarkeit, mit `evals/cases.json` (mindestens fünf Fälle) und Testprotokoll | Capability Contract oder Aufgabendaten |
| `tools/anbindungen.md` | Systeme der Rolle, Datenklassen, Zugriff; Freigabe „offen“ | Graph |
| `routinen/routinen.json` | Zeit- und ereignisbasierte Vorschläge, **alle inaktiv** | Graph |
| `pflege/pflege.md` | Wie das Setup lebendig bleibt | eigener Text |

`check_role_setup.py` sagt, wie weit ein Paket ist: **entwurf** (unter fünf echten Testfällen), **im Test**, **live-reif** (fünf echte Fälle, zwei Schleifen,
alle bestanden). Eine Routine darf nur für live-reife Skills aktiv sein; sonst meldet `--strict` einen Fehler. Erst erweitern, dann automatisieren.

Was das Paket nicht ist: Es ist ungetestet, ohne Freigabe von Systemzugriffen und ohne Aussage zur Zeitersparnis. Kontext, den der Graph nicht kennt
(Geschäftsmodell, Prioritäten, was „gut“ heißt), bleibt offen, bis jemand ihn nennt. Die Testfälle sind Gerüste; echte Fälle trägt der Nutzer ein. Ein erneuter
Lauf überschreibt keine bearbeitete Datei, der neue Stand liegt als `.vorschlag` daneben. Begründung und Grenzen:
`skills/agent-mapper/references/rollen-setup.md`.

### Zwei Berichte, ein Graph

Das Dashboard schreibt neben `report_vNNN.md` zwei Fassungen: `report_hr_vNNN.md` (Kapazität, Zielbild, Rahmen — in der Sprache
„Rolle verändert sich“) und `report_it_vNNN.md` (Backlog nach Wert, Use Cases, Prozessbänder, Blindflecken). Mit Befragung nennt der HR-Bericht die Vorsichtszone und die
Aufgaben, bei denen mehr Beteiligung gewünscht ist, der IT-Bericht die latente Nachfrage (gewünscht, ohne Vorhaben),
Agenten auf ungewollter Arbeit und Nutzung gegen Wunsch. Der HR-Bericht enthält außerdem die Kompetenzverschiebung. Ein Glossar in
`work-graph-builder/references/glossar.md` legt fest, wie die Wörter von HR und IT zueinander stehen.

Weitere Hilfen: `import_process_house.py` übernimmt ein vorhandenes Prozesshaus als Prozessextraktion;
die Review-Liste markiert Rollen mit zehn und mehr Aufgaben oder auffällig fremden Aufgabenpaaren mit „Split prüfen“; jeder Agent
trägt einen Evidenzgrad (`heuristic`, `expert_confirmed`, `proven`), weil ein Vorschlag aus Mustern keine geprüfte Passung ist.

## Stände: Snapshots, Freigaben, Pflege-Lock

Ein Projektordner ist der ganze Stand. Damit er auf einem geteilten Laufwerk belastbar bleibt, gibt es im
Orchestrator vier Skripte (alle `--project <ordner>`):

| Skript | Was es tut |
|---|---|
| `snapshot_project.py [--label …]` | Wiederherstellungspunkt unter `50_snapshots/`: Eingaben, Extraktionen, Review, aktueller Graph, mit Hash je Datei. Ausgaben nicht, die entstehen neu |
| `restore_project.py --snapshot <ordner> [--dry-run]` | stellt einen Snapshot byteidentisch wieder her; sichert vorher den jetzigen Stand |
| `release_project.py --version X.Y.Z` | friert einen geprüften Stand ein: Manifest unter `60_releases/<version>/`, verkettete Zeile in `releases.jsonl`. Vorbedingungen: Validator ohne Fehler, bei Belegpflicht strict nichts unbelegt, Ausgaben vorhanden, kein fremder Pflegeanspruch, Version höher als die letzte |
| `verify_release.py [--version …]` | prüft, ob der Ordner noch dem Freigabestand entspricht: verändert, fehlt, neu; und ob die Kette der Freigaben geschlossen ist |
| `project_lock.py acquire\|verify\|heartbeat\|release\|withdraw\|status` | Pflegeanspruch in `.wts-lock/`: wer ihn hält, darf schreiben; `run_pipeline.py` hält bei fremdem Anspruch an. Abgelaufene Ansprüche werden nur mit `--take-over --reason` übernommen und protokolliert. Der Token liegt außerhalb des Projekts (0600) und steht nirgends im Klartext |

Allein arbeitend braucht niemand das Lock. In einem Team ersetzt es nicht die Absprache, aber es verhindert, dass
zwei Läufe denselben Graphen gleichzeitig schreiben.

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

Keine Integration in SuccessFactors oder andere HR-Systeme, keine Telemetrie der Agentennutzung (nur ein
aggregierter Stand je Rolle und Agent), keine Prozess-Mining-Anbindung. Für genau diese Dinge verkaufen kommerzielle Plattformen ihr
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
Scale H1–H5, arXiv 2506.06576). Daraus stammen auch der Auditrahmen des Skills `agency-audit` (Befragung je
Aufgabe, Wunsch gegen Machbarkeit, vier Zonen, Jensen-Shannon-Distanz zwischen gewünschter und nötiger
Beteiligung), die Zweitbewertung und die Kompetenzverschiebung. Anthropic Economic Index, Automation gegen Augmentation auf
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
