# Work-Transformation-Suite

Fünf Claude-Skills, die aus Stellenbeschreibungen eines Bereichs einen bewerteten Arbeitsgraphen
machen: Rollen, Aufgaben, Skills, KI-Automatisierbarkeit je Aufgabe, Disruptionstyp je Rolle,
Agentenbibliothek mit Rollenabdeckung und ein Dashboard. Das entspricht dem, was kommerzielle
Work-Orchestration-Plattformen als Rollen- und Aufgabenmodell mit KI-Bewertung anbieten, für Pilotbereiche mit 20–40 Rollen.

Überblicksseite: `docs/index.html` — als GitHub Pages veröffentlichbar (Settings → Pages → Branch
`main`, Ordner `/docs`), dann unter <https://godmodeai2025.github.io/Work-Transformation-Suite/>.

## Was drin ist

```
Work-Transformation-Suite/
├── README.md                     diese Anleitung
├── docs/index.html               Landingpage (GitHub Pages)
├── skills/
│   ├── work-transformation/      Orchestrator: Pipeline, Suite-Check
│   ├── work-graph-builder/       Schritt 1: Extraktion → work-graph.json, Review-Liste, Overrides
│   ├── task-scorer/              Schritt 2: Aufgabenbewertung → Modus, HAS, Horizont, Disruptionstyp
│   ├── agent-mapper/             Schritt 3: Agentenbibliothek → Abdeckung, FTE, Build/Buy, Priorität
│   └── transformation-dashboard/ Schritt 4: HTML-Dashboard, CSV, Bericht
└── dist/                         .skill-Pakete zum Speichern in Claude
```

Der durchgerechnete Beispielordner `examples/kundenservice-pilot/` (4 Rollen, 25 Aufgaben,
9 Agenten) gehört bewusst nicht ins Repository — es enthält nur die Skills. Das Beispiel kommt mit
dem Auslieferungspaket; ein lokal daneben gelegter Ordner `examples/` wird von `.gitignore`
ferngehalten, ebenso `projekte/` mit echten Projektdaten.

Jeder Skill: `SKILL.md` (Anweisungen für Claude), `scripts/` (Python, deterministisch), `references/`
(Rubrik, Taxonomie, Formate). Die Skills sind einzeln lauffähig; gemeinsame Bibliotheksdateien
(`workgraph_lib.py`, `validate_graph.py`, `apply_overrides.py`) liegen als identische Kopien in jedem
Skill, damit keiner vom anderen abhängt. `check_suite.py` prüft, dass die Kopien gleich sind.

## Installation

Voraussetzung: Python 3.9 oder neuer, keine zusätzlichen Pakete.

**In Claude (Cowork / claude.ai):** Die fünf `.skill`-Dateien aus `dist/` einzeln in den Chat ziehen
und auf „Skill speichern" klicken. Reihenfolge egal.

**In Claude Code:** Den Ordner `skills/` (oder die fünf Unterordner) nach `~/.claude/skills/` kopieren,
oder projektbezogen nach `<repo>/.claude/skills/`. Die Skills finden sich gegenseitig über den
Geschwister-Pfad `../<skillname>`, deshalb zusammen in einen Ordner legen.

**Ohne Claude, nur Skripte:** Alles funktioniert auch als reines Kommandozeilenwerkzeug; die
Urteilsschritte (Extraktion, Bewertung, Agentenbündelung) macht dann ein Mensch, indem er die
JSON-Vorlagen ausfüllt.

Prüfen: `python3 skills/work-transformation/scripts/check_suite.py` → „Suite OK".

## Pfade

Alle Skripte nehmen `--project <ordner>` und lösen ihn relativ zum aktuellen Arbeitsverzeichnis auf.
Innerhalb des Projekts sind alle Pfade fest und relativ (`00_input/`, `20_graph/` …). Skript-Pfade in
den SKILL.md-Dateien sind relativ zum jeweiligen Skill-Ordner. Es gibt keinen hart codierten
absoluten Pfad in der Suite; man kann den Projektordner verschieben, kopieren oder in Git legen.

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

Die Suite trennt strikt: **Claude urteilt, Skripte rechnen.** Claude liest Quellen und schreibt drei
JSON-Dateien (Extraktion, Bewertung, Agenten). Alles andere, also IDs, Zusammenführung,
Normalisierung, Klassifikation, Abdeckung, Dashboard, machen Skripte ohne Zufall und ohne
Zeitstempel. Gleiche Eingaben ergeben byteidentische Ausgaben; das wurde mit zwei unabhängigen
Läufen des Beispiels geprüft.

### Schritt 0: Projekt anlegen

```
python3 skills/work-graph-builder/scripts/init_project.py --project projekte/kundenservice \
  --name "Kundenservice Pilot" --organization "Meine Firma" --scope "Kundenservice – Vertrag und Abrechnung"
```

Quellen (Stellenbeschreibungen als PDF/Word/Markdown, Organigramme, SAP-Exporte) nach
`projekte/kundenservice/00_input/`.

### Schritt 1: work-graph-builder (Claude)

Sagen: „Bau den Arbeitsgraphen für projekte/kundenservice aus den Dateien in 00_input."
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

Die IDs stehen in der Review-Liste. Overrides gewinnen dauerhaft und überleben jeden Neulauf; sie
sind die einzige Stelle, an der Menschen den Graphen ändern. Nie direkt in `20_graph/` editieren.

### Schritt 2: task-scorer (Claude)

Sagen: „Bewerte die Aufgaben." Claude exportiert `20_graph/scores_todo.json`, bewertet jede Aufgabe
nach der Rubrik (`task-scorer/references/rubric.md`: sechs Werte 0–10 plus Begründung) und speichert
`20_graph/scores.json`. `score_roles.py` leitet daraus ab:

- je Aufgabe: Automatisierungspotenzial, Modus (manuell / KI-unterstützt / an Agent delegiert),
  HAS-Level H1–H5, Zeithorizont
- je Rolle: zeitanteilgewichtete Kennwerte, Anteile Kern/assistiert/delegiert, Disruptionsscore,
  Disruptionstyp (eliminiert / transformiert / augmentiert / entstehend / stabil), Transformationslogik,
  nächster Schritt, bleibende und sinkende Skills

Alle Schwellen stehen als Konstanten am Kopf von `task-scorer/scripts/score_roles.py` und sind in der
Rubrik erklärt. Wer kalibrieren will, ändert sie dort, nicht in den Bewertungen.

### Schritt 3: agent-mapper (Claude)

Sagen: „Leite die Agenten ab." Claude exportiert Kandidaten (`agents_todo.json`, nach Muster
gruppiert), fragt nach bereits laufenden KI-Anwendungen, bündelt die Aufgaben zu 6–15
wiederverwendbaren Agenten (`agents.json`, Muster aus `agent-mapper/references/agent-patterns.md`) und
lässt `compute_coverage.py` rechnen: Abdeckung je Rolle, FTE-Äquivalent, Build/Buy/Hybrid, Horizont,
Priorität.

### Schritt 4: transformation-dashboard (Skript)

`build_dashboard.py` erzeugt `40_output/dashboard_vNNN.html` (eine Datei, offline, Farben per Theme-Datei anpassbar),
drei CSVs und `report_vNNN.md`. Mit `--stamp "15.09.2026"` kommt ein Datum in die Kopfzeile.

### Alles auf einmal

```
python3 skills/work-transformation/scripts/run_pipeline.py --project projekte/kundenservice
```

führt alle Skript-Schritte aus und stoppt mit Exit-Code 3 und einer klaren Meldung, sobald eine
Claude-Eingabe fehlt („STOPP: keine scores.json … Nächster Schritt: Skill task-scorer"). Das ist auch
der Befehl für „weiter machen": Nach jeder Korrektur in `overrides.csv` oder `scores.json` einmal
laufen lassen, alles Nachgelagerte wird neu gerechnet, unveränderte Stände erzeugen keine neue Version.

## Belastbarkeit, Kipp-Analyse, Stellen und Kalibrierung

Vier Ergänzungen aus dem ersten echten Einsatz:

**Belastbarkeit je Rolle.** Jede Rolle trägt eine Stufe `evidence` (belastbar / teilweise geprüft /
ungeprüft), abgeleitet daraus, ob die Zeitanteile aus der Quelle stammen (`time_shares_source`),
ob Experten geprüft haben, wie viel aus abgeleiteten Aufgaben stammt und ob der Headcount bekannt
ist. Das Dashboard zeigt sie als Tag an jeder Rolle und in der Übersicht. Eine Rollenkarte, in der
alles „ungeprüft" ist, ist ein Gesprächsangebot, kein Ergebnis.

**Kipp-Analyse.** Für jede Aufgabe werden Maschinenanteil, Urteilsbedarf und Fehlergewicht um ±1
verändert und die Rollenwirkung neu berechnet. `stability` sagt, ob die Einstufung stabil,
grenznah oder wackelig ist, `flip_examples` nennt die Aufgabe, an der sie hängt. Genau diese
Aufgabe sollte der Experte zuerst prüfen.

**Stellen.** Prozessrollen sind keine Stellen. `00_input/positions.csv`
(`position_id;title;org_unit;role;share`) ordnet Stellen mit Anteilen den Rollen zu;
`import_positions.py` rechnet daraus Vollzeitäquivalente und Headcounts. Keine Personennamen.

**Kalibrierung.** `task-scorer/scripts/calibrate.py` vergleicht Expertenkorrekturen (Overrides auf
`scores.*`) mit den generierten Werten und meldet je Feld, ob die Experten systematisch anders
liegen. Ab fünf Korrekturen mit mittlerer Abweichung ≥ 0,75 sollte man den Anker in der Rubrik
verschieben statt weiter einzeln zu korrigieren.

## Versionierung

`project.json` zählt `graph_version` hoch. Jeder Schritt, der den Inhalt ändert, schreibt
`20_graph/work-graph_vNNN_<stage>.json` und aktualisiert `work-graph_latest.json`. Läuft ein Schritt
ohne inhaltliche Änderung, meldet er „Unverändert" und legt keine Version an. Alte Versionen bleiben
liegen; `diff` zwischen zwei Versionen zeigt genau, was sich geändert hat. Das ersetzt keine Datenbank
mit Freigabeworkflow, aber es reicht für einen Piloten und lässt sich in Git versionieren.

## Was „deterministisch" hier konkret heißt

- IDs sind SHA1-Hashes der normalisierten Namen (`ro_…`, `ta_…`, `sk_…`, `ag_…`). Gleicher Name,
  gleiche ID, in jedem Lauf und auf jedem Rechner. Ein umbenannter Task bekommt eine neue ID und
  verliert Bewertung und Overrides; deshalb Namen stabil halten.
- Alle Listen sind sortiert, JSON hat sortierte Schlüssel, keine Zeitstempel im Inhalt.
- Alle Regeln (Modus, HAS, Horizont, Disruptionstyp, Abdeckung, Priorität) sind Formeln mit
  Konstanten, keine KI-Entscheidungen.
- Rundung ist kaufmännisch auf eine Nachkommastelle; Rundungsreste gehen deterministisch auf das
  größte Element.
- Der einzige nicht-deterministische Teil ist Claudes Urteil in den drei JSON-Dateien. Die SKILL.md-
  Dateien halten ihn stabil durch feste Formate, Taxonomie, Ankerbeispiele und die Regel, vorhandene
  Namen wiederzuverwenden. Für die Bewertung gilt: Wer Werte ändern will, ändert `scores.json` (Claude)
  oder `overrides.csv` (Mensch), nie beides für dasselbe Feld.

## Das Beispiel nachvollziehen

Das Beispiel liegt nicht im Repository (siehe oben). Wer es aus dem Auslieferungspaket daneben
legt, rechnet es so nach:

```
python3 skills/work-transformation/scripts/run_pipeline.py --project examples/kundenservice-pilot
open examples/kundenservice-pilot/40_output/dashboard_v003.html
```

Das Beispiel enthält Extraktion, Bewertung und Agenten für einen fiktiven Kundenservice
(Vertragsmanagement, Abrechnung, Telefonie, Teamleitung). Es ist auch die Vorlage dafür, wie die drei
Claude-Dateien aussehen sollen.

## Grenzen

Kein Freigabeworkflow mit Rollen und Rechten, keine Integration in SuccessFactors oder andere
HR-Systeme, kein Tracking der Agentennutzung nach dem Rollout. Für genau diese drei Dinge verkaufen
kommerzielle Plattformen ihr Produkt. Für die Frage, ob eine solche Analyse für einen Bereich überhaupt belastbare
Ergebnisse liefert, und für Pilotbereiche bis etwa 40 Rollen, ist die Suite ausreichend.

## Weiterentwicklung

- Schwellen kalibrieren: 20–30 Aufgaben mit Expertenwerten sammeln, dann Konstanten in
  `score_roles.py` anpassen oder `autoresearch-skills` auf die Rubrik ansetzen.
- Skill-Taxonomie erweitern: `work-graph-builder/references/skill-taxonomy.md`, optional ESCO-Export
  in `00_input/esco/` mit `esco_uri` je Skill.
- Agentenmuster ergänzen: `agent-mapper/references/agent-patterns.md` plus `ALLOWED_PATTERNS` und
  `PATTERN_KEYWORDS` in den Mapper-Skripten.
- Dashboard-Layout: `CSS`, `JS` und Bausteinfunktionen in `build_dashboard.py`.

## Methodische Quellen

Stanford „Future of Work with AI Agents" (Shao et al. 2025, WORKBank, Human Agency Scale H1–H5,
arXiv 2506.06576); Anthropic Economic Index (Automation vs. Augmentation auf O*NET-Task-Ebene);
ESCO v1.2 (EU-Skill-Taxonomie); Metriken kommerzieller AI-Transformation-Dashboards (Automation Potential,
Human Judgment, Disruption Score, Rollen-Typen).

## Lizenz

Apache License 2.0, siehe `LICENSE`.
