# Seiten unter `05_pages/`: die kanonische Fassung

Ab Schema 1.3 kann ein Projekt seine Rollen, Aufgaben, Skills, Bewertungen und Agenten als
Markdown-Seiten führen. Liegen Seiten unter `05_pages/`, sind sie die Wahrheit: `compile_pages.py`
übersetzt sie vor jedem Pipeline-Lauf in die JSON-Register (`10_extraction/extract_<cluster>.json`,
`20_graph/scores.json`, `20_graph/agents.json`). Wer etwas ändern will, ändert die Seite.

Ein Projekt ohne Seiten läuft wie bisher über die Register. `export_pages.py` erzeugt die Seiten
einmalig aus vorhandenen Registern; danach gilt die Seite.

Prozesse (`process_*.json`), Blueprints und Experimente bleiben JSON: Ihre Struktur ist verschachtelt
(Schritte mit Ausführenden, Kanten, Kennzahlen mit drei Wertstufen), und ein flaches Frontmatter würde
sie verfälschen. Das ist die bewusste Grenze dieser Schicht.

## Frontmatter-Vertrag

- Die Seite beginnt mit `---`, der Kopf endet mit `---`.
- Eine Ebene. Schlüssel aus `a-z`, `0-9`, `_`.
- Werte: Zeichenkette (`"…"` oder nackt), Zahl, `true`, `false`, `null`.
- Listen flach: Blockliste mit `  - "x"` je Zeile oder inline als JSON-Array `["a", "b"]`.
- Nicht erlaubt: Einrückung außer in Blocklisten, Objekte, verschachtelte Listen, Tabulatoren, doppelte
  Schlüssel, YAML-Anker. Kommentarzeilen (`#`) nur am Anfang des Kopfs.
- Fehler nennt `compile_pages.py` mit Datei und Zeile. Geraten wird nicht; die Register bleiben unverändert.

Im Rumpf gliedern Überschriften der zweiten Ebene (`## …`) die Abschnitte. Fließtext wird zu einem Absatz
zusammengezogen; Tabellen, nummerierte Listen und `json`-Codeblöcke werden gelesen, wo das Format sie vorsieht.

## Seitentypen

### Jobcluster `clusters/<slug>.md`

```
---
type: "cluster"
job_family: "Finanzen und Controlling"
job_cluster: "Order-to-Cash"
source: "Stellenbeschreibungen Order-to-Cash, Stand 2026-01"
---

## Jobfamilie

Kaufmännische Abwicklung, Rechnungslegung und Forderungsmanagement.

## Jobcluster

Vom eingehenden Auftrag bis zum zugeordneten Zahlungseingang.
```

Je Cluster entsteht eine Extraktionsdatei; `source` ist ihr Quellvermerk.

### Rolle `roles/<slug>.md`

Kopf: `type: "role"`, `name`, `cluster` (Name des Jobclusters, Pflicht), `level`, `headcount`, `archetype`,
`regulated`, `is_new`, `time_shares_source` (`source` oder `estimated`), `evidence` (Liste von Belegen
`src-<hash>@<fundstelle>`). Rumpf: `## Zweck`, `## Beschreibung`, `## Skills` als Tabelle
`| Skill | Art | Kategorie | Niveau | Bedeutung |` (Art: knowledge, skill, competence, tool; Niveau 1 bis 5;
Bedeutung core oder supporting).

### Aufgabe `tasks/<rolle>--<aufgabe>.md`

Kopf: `type: "task"`, `name`, `role` (Name der Rolle, Pflicht), `share_of_time`, `frequency`, `nature`,
`confidence` (`source` oder `inferred`), `skills` (Liste von Skillnamen der Rolle), `evidence`. Die Bewertung
steht als sechs Felder `score_automation_ai`, `score_automation_physical`, `score_human_judgment`,
`score_productivity_boost`, `score_data_readiness`, `score_consequence_of_error` (ganze Zahlen 0 bis 10) im Kopf;
entweder alle sechs oder keines. Optional zwei Merkmale als `true`/`false`: `score_interpersonal` (die Aufgabe lebt von
Beziehung, Einfühlung oder Verhandlung) und `score_tacit_expertise` (sie hängt an Erfahrung, die nirgends
aufgeschrieben ist). Rumpf: `## Beschreibung`, `## Schritte` (nummerierte Liste),
`## Begründung der Bewertung` (Pflicht, sobald Bewertungen gesetzt sind).

### Agent `agents/<slug>.md`

Kopf: `type: "agent"`, `name`, `pattern` (aus `agent-patterns.md`), `specificity`, `status`, `complexity`,
`existing_system`, `prerequisites` (Liste), `orchestrates` (Liste von Agentennamen), `tasks` (Liste
`"Rolle > Aufgabe"`). Rumpf: `## Fähigkeit`, `## Aufsicht`, `## Vertrag` mit dem Capability Contract als
`json`-Codeblock (Format: `agent-mapper/references/contract-format.md`). Der Vertrag bleibt JSON, weil er
verschachtelte Teile hat (Kontrollpunkt, Testmenge, Kostengrenze).

## Determinismus

Dieselben Seiten ergeben dieselben Registerbytes. Die Reihenfolge der Seiten ist egal: Rollen werden nach
Namen, Aufgaben in Seitenreihenfolge je Rolle, Agenten nach Namen sortiert. IDs entstehen wie bisher aus
den Namen (`ro_`, `ta_`, `ag_`); eine umbenannte Seite ergibt eine neue ID.

`05_pages/.compiled.json` merkt sich, welche Registerdateien der letzte Lauf erzeugt hat. Eine
Extraktionsdatei ohne Seite wird beim nächsten Lauf entfernt, damit kein Cluster weiterlebt, den niemand
mehr pflegt.
