# Referenzbeispiel: Order-to-Cash

Ein vollständiges Projekt der Work-Transformation-Suite — von den Quelldokumenten bis zu
freigegebenen Soll-Prozessen und einem ausgewerteten Pilot. Es dient drei Zwecken:

1. **Zum Nachlesen.** Alle Eingabeformate einmal an einem realistischen Fall ausgefüllt.
2. **Zum Ausprobieren.** Die Pipeline läuft ohne weitere Eingaben durch.
3. **Als Test.** `tests/test_end_to_end.py` rechnet dieses Projekt bei jedem Lauf neu und
   vergleicht das Ergebnis mit `expected/`.

Die Daten sind erfunden. Sie bilden einen Order-to-Cash-Bereich eines mittelständischen
Industrieunternehmens nach und enthalten keine echten Personen-, Kunden- oder
Unternehmensdaten.

## Ausprobieren

```
python3 skills/work-transformation/scripts/run_pipeline.py --project examples/order-to-cash
```

Danach liegen in `40_output/` das Dashboard, der Szenarienvergleich, die Capability
Contracts, drei CSV-Exporte und der Bericht. Ein zweiter Lauf ändert nichts und legt keine
neue Graph-Version an — die Suite verspricht gleiche Eingaben, gleiche Bytes.

Zurücksetzen: die erzeugten Dateien stehen in `.gitignore`, `git clean -Xfd examples/`
entfernt sie.

## Was drin ist

| Datei | Wer schreibt sie | Inhalt |
|---|---|---|
| `00_input/*.md` | Mensch | Stellenbeschreibungen und Prozessaufnahme |
| `10_extraction/extract_*.json` | Claude | 5 Rollen, 21 Aufgaben, 11 Skills |
| `10_extraction/process_*.json` | Claude | 2 End-to-End-Prozesse, 16 Schritte, 4 Kontrollen, 6 Kennzahlen |
| `20_graph/scores.json` | Claude | Bewertung aller 21 Aufgaben nach sechs Kriterien |
| `20_graph/agents.json` | Claude | 8 Agenten mit Capability Contracts, davon einer als Orchestrator |
| `20_graph/blueprints.json` | Claude | 6 Soll-Szenarien (drei je Prozess) |
| `20_graph/process_value.json` | Claude/Fachexperte | Neun Wertfaktoren je Prozess |
| `20_graph/experiments.json` | Claude/Fachexperte | Zwei Piloten, einer mit Messergebnissen |
| `30_review/decisions.csv` | Mensch | Fünf Entscheidungen, darunter eine Freigabe |
| `expected/` | Testlauf | Erwartetes Endergebnis mit Prüfsummen |

## Was das Beispiel zeigen soll

**Der Ist-Prozess ist der Befund, nicht der Entwurf.** „Auftrag bis Rechnung" braucht
gemessene 42 Stunden, davon rund 40 Stunden Liegezeit. Zehn Schritte, neun Übergaben,
vier Rollen. Einer der Schritte — die Excel-Nachverfolgungsliste — existiert nur, weil ein
System eine Information nicht ausweist.

**Drei Szenarien, die wirklich verschieden sind.** Konservativ behält jede Kontrolle und
kommt auf 30 Stunden. Ausgewogen legt Schritte zusammen, streicht die Liste und kommt auf
6 Stunden. Agent-nativ lässt Auftragsannahme und Bonitätsprüfung gleichzeitig laufen und
kommt auf 1,5 Stunden — mit zwei Menschen an den Stellen, an denen es um Verantwortung
geht. Alle drei behalten jede Pflichtkontrolle.

**Wert schlägt Arbeitszeit.** „Auftrag bis Rechnung" bindet 22,7 Vollzeitäquivalente,
„Rechnung bis Zahlungseingang" nur 14,9 — trotzdem steht der zweite Prozess vorn. Er ist
billiger zu integrieren, leichter umzustellen und jederzeit zurückdrehbar. Eine
FTE-Sortierung hätte die umgekehrte Reihenfolge ergeben.

**Bänder statt Rangliste.** Beide Prozesse landen im Band „Als Nächstes", und bei einem
kippt das Band schon, wenn ein einzelner Faktor um 1 danebenliegt. Das steht so im
Dashboard. Eine Rangfolge auf zwei Nachkommastellen wäre hier eine Lüge.

**Geschätzt, bestätigt, gemessen bleiben unterscheidbar.** Vier der sechs Ausgangswerte
stammen aus ERP-Exporten und tragen ihre Fundstelle, zwei sind Schätzungen und sind als
solche markiert. Ein abgeschlossener A/B-Test hat drei Werte gemessen; sie stehen als
`observed` im Graphen, mit Provenienz — und überschreiben den Ist-Wert ausdrücklich nicht.

**Freigaben haben Namen.** Der gemessene Blueprint ist freigegeben, zwei weitere sind
bewusst zurückgestellt, mit Begründung und Datum. Der Status kommt aus
`30_review/decisions.csv`, nicht aus einem Feld, das jemand gesetzt hat.

## Den erwarteten Stand neu erzeugen

Wenn sich das Ergebnis absichtlich ändert (neue Regel, korrigierte Rechnung):

```
python3 tools/refresh_example.py
```

Das schreibt `expected/work-graph_final.json`, `expected/manifest.json` und die lesbaren
Endartefakte neu. Der Commit sollte begründen, warum sich das Ergebnis ändert — ein
stillschweigend aktualisierter Snapshot macht den Test wertlos.
