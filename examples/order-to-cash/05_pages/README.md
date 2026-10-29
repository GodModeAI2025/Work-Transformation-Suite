# Seiten: die kanonische Fassung

Jede Datei hier ist eine Rolle, eine Aufgabe, ein Agent oder ein Jobcluster. Der Kopf zwischen den
`---`-Zeilen trägt die Felder, der Rumpf die Texte. `compile_pages.py` übersetzt die Seiten in die
JSON-Register (`10_extraction/`, `20_graph/scores.json`, `20_graph/agents.json`); die Pipeline tut
das vor jedem Lauf. Wer etwas ändern will, ändert die Seite, nicht das Register.

Regeln für den Kopf: eine Ebene, Zeichenketten in Anführungszeichen oder nackt, Zahlen, true, false,
null, flache Listen (`- "x"` je Zeile oder `["a", "b"]`). Keine Einrückung, keine Objekte, keine
Tabulatoren. Fehler nennt `compile_pages.py` mit Datei und Zeile.

| Ordner | Seite | Pflichtfelder im Kopf | Abschnitte im Rumpf |
|---|---|---|---|
| clusters/ | Jobcluster | type, job_family, job_cluster | Jobfamilie, Jobcluster |
| roles/ | Rolle | type, name, cluster | Zweck, Beschreibung, Skills (Tabelle) |
| tasks/ | Aufgabe | type, name, role, share_of_time | Beschreibung, Schritte (Liste), Begründung der Bewertung |
| agents/ | Agent | type, name, pattern | Fähigkeit, Aufsicht, Vertrag (JSON-Block) |

Belege stehen als Liste `evidence` im Kopf (`src-<hash>@<fundstelle>`), Bewertungen als
`score_<feld>` in der Aufgabenseite. Aufgaben eines Agenten als `"Rolle > Aufgabe"`.
