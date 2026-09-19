# KI-Transformationsdashboard — Order-to-Cash

Beispiel GmbH · Order-to-Cash · Work-Graph Version 8

## Kennzahlen

5 Rollen (5 bewertet), 21 Aufgaben, 11 Skills, 8 Agenten. Headcount bekannt für 5 Rollen (23 Personen). Durchschnittlicher Disruptionsscore 6,6. Zeitverteilung: 6 % menschlicher Kern, 50 % KI-unterstützt, 44 % delegierbar. 19 % der Aufgaben aus dem Berufsbild ergänzt; 0 Rollen expertengeprüft.

Verteilung: Eliminiert 1, Transformiert 3, Augmentiert 1.

## Rollen nach Disruptionsscore

| Rolle | Cluster | MA | Typ | Score | Kern | Assist. | Deleg. | Horizont | Belastbarkeit | Stabilität | Nächster Schritt |
|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|
| Fakturierungssachbearbeiter | Order-to-Cash | 6 | Transformiert | 7,3 | 0 % | 50 % | 50 % | kurzfristig | teilweise geprüft | grenznah | Rolle um den menschlichen Kern neu definieren: delegierbare Aufgaben an Agenten, verbleibende Aufgaben zu einem neuen Profil bündeln, Skillplan aufsetzen. |
| Auftragssachbearbeiter | Order-to-Cash | 9 | Eliminiert | 6,8 | 0 % | 35 % | 65 % | kurzfristig | teilweise geprüft | wackelig | Aufgaben strukturiert an Agenten und Nachbarrollen umverteilen; Abhängigkeiten in Prozessen und Freigaben prüfen, bevor Kapazität abgebaut wird. |
| Kreditprüfer | Order-to-Cash | 3 | Transformiert | 6,7 | 0 % | 100 % | 0 % | kurzfristig | teilweise geprüft | stabil | Rolle um den menschlichen Kern neu definieren: delegierbare Aufgaben an Agenten, verbleibende Aufgaben zu einem neuen Profil bündeln, Skillplan aufsetzen. |
| Forderungsmanager | Order-to-Cash | 4 | Transformiert | 5,9 | 20 % | 50 % | 30 % | kurzfristig | teilweise geprüft | stabil | Rolle um den menschlichen Kern neu definieren: delegierbare Aufgaben an Agenten, verbleibende Aufgaben zu einem neuen Profil bündeln, Skillplan aufsetzen. |
| Teamleitung Order-to-Cash | Order-to-Cash | 1 | Augmentiert | 3,4 | 60 % | 40 % | 0 % | mittelfristig | ungeprüft | stabil | KI-Werkzeuge für die assistierbaren Aufgaben bereitstellen, Schulung und Qualitätssicherung einführen, Zeitgewinn in Kernaufgaben lenken. |

## Agenten nach Priorität

| Wert # | Bau # | Agent | Muster | Sourcing | Horizont | Rollen | Ø Abdeckung | FTE-Äquiv. |
|---:|---:|---|---|---|---|---:|---:|---:|
| 1 | 4 | Auftragserfassungs-Agent | document-extraction | Build | kurzfristig | 1 | 60 % | 5,4 |
| 2 | 5 | Fakturierungs-Agent | invoice-verification | Build | kurzfristig | 1 | 74 % | 4,4 |
| 3 | 2 | Bonitäts-Agent | data-reconciliation | Hybrid | kurzfristig | 1 | 72 % | 2,1 |
| 4 | 3 | Zahlungszuordnungs-Agent | data-reconciliation | Build | kurzfristig | 1 | 34 % | 1,4 |
| 5 | 7 | Mahnlauf-Agent | standard-correspondence | Hybrid | mittelfristig | 1 | 18 % | 0,7 |
| 6 | 6 | Vertriebsklärungs-Assistent | drafting-assistant | Hybrid | mittelfristig | 1 | 8 % | 0,7 |
| 7 | 1 | Analyse- und Berichtscopilot | analysis-copilot | Buy | kurzfristig | 1 | 22 % | 0,2 |
| 8 | 8 | Order-to-Cash-Orchestrator | workflow-orchestration | Hybrid | – | 0 | 0 % | – |

## Prozessportfolio

2 Prozesse mit 16 Schritten, 2 davon mit allen drei Szenarien. 6 Blueprints (1 freigegeben), 2 Piloten geplant. Durchschnittlicher Durchlaufzeitgewinn im jeweils besten Szenario: 93 %.

| # | Prozess | Band | Wert | Ist-Durchlauf | Bestes Szenario | Soll-Durchlauf | Human Touchpoints | Übergaben |
|---:|---|---|---:|---:|---|---:|---|---|
| 1 | Rechnung bis Zahlungseingang | Als Nächstes (kippelig) | 6,9 | 34,1 h | Agent-nativ | 3,5 h | 6 → 3 | 6 → 2 |
| 2 | Auftrag bis Rechnung | Als Nächstes | 6,3 | 42,5 h | Agent-nativ | 1,5 h | 10 → 3 | 9 → 3 |

Belastbarkeit der Kennzahlen: 4 von 6 Ausgangswerten sind bestätigt oder gemessen, 2 sind Schätzungen. Jede Delta-Zahl in diesem Bericht ist aus den Soll-Schritten der Blueprints gerechnet, nicht zugesagt.


## Hinweise

Bewertungen sind KI-generiert nach einer festen Rubrik und durch Expertenkorrekturen überschreibbar. Rollen mit Status `generated` wurden noch nicht geprüft. Die Schwellen der Klassifikation stehen in der Rubrik des task-scorer. Belastbarkeit fasst zusammen, ob Zeitanteile aus der Quelle stammen, ob Experten geprüft haben und ob der Headcount bekannt ist; Stabilität sagt, wie viele Einzeländerungen um ±1 an einer Aufgabenbewertung die Rollenwirkung kippen würden. Unterschiede im Expositionswert unter 0,5 sind Rauschen.
