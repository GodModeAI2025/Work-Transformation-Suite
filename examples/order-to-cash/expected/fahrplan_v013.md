# Fahrplan-Raster: Order-to-Cash

Graph-Version 13. Das Raster ist ein Vorschlag, bis eine benannte Person die Zuordnung bestätigt hat. Zeiträume nennt es nur, wenn jemand sie festgelegt hat.

## Überblick

| Welle | Zeitraum | Vorhaben | Rollen | FTE betroffen | Wert/Jahr (geschätzt) | Stand |
|---|---|---:|---:|---:|---:|---|
| Welle 1: Referenz und Grundlagen | ❓ offen | 5 | 4 | 18.4 | 1 808 400 € | entschieden oder läuft bereits |
| Welle 2: Ausweiten | ❓ offen | 4 | 3 | 4.6 | 457 600 € | teils entschieden |
| Welle 3: Breite | ❓ offen | 1 | 0 | – | nicht bewertet | Vorschlag |
| **Alle Wellen zusammen** |  | 10 | 5 | 21.6 | 2 136 640 € |  |

Wert ist die heute gebundene Arbeitszeit der betroffenen Aufgaben mal Tagessatz und damit eine Schätzung, was betroffen ist. Er sagt nicht, was eingespart wird.

## Vorhaben je Welle

### Welle 1: Referenz und Grundlagen

| Vorhaben | Art | Status | Score | Wert/Jahr | FTE | Zuordnung | Sicht der Beschäftigten |
|---|---|---|---:|---:|---:|---|---|
| Auftragserfassungs-Agent | Agent | Pilot | 7.8 | 665 280 € | 7.2 | läuft bereits | Freigabe 75 % |
| Fakturierungs-Agent | Agent | Pilot | 7.0 | 567 600 € | 6.0 | läuft bereits | Freigabe 80 % |
| Bonitäts-Agent | Agent | Pilot | 5.7 | 343 200 € | 3.0 | läuft bereits | nicht befragt |
| Zahlungszuordnungs-Agent | Agent | Pilot | 4.9 | 232 320 € | 2.2 | läuft bereits | nicht befragt |
| Zahlungseingang automatisch zuordnen | Use Case | Pilot | 3.5 | 48 000 € | 1.2 | läuft bereits | nicht befragt |

Voraussetzungen laut Agentenbibliothek:

- Auftragserfassungs-Agent: Digitalisierte Rahmenverträge; Freigabe Betriebsrat; Schreibzugriff ERP über Schnittstelle
- Fakturierungs-Agent: Abgestimmte Prüfregeln mit der Revision; Schnittstelle zum Archiv; Schreibzugriff ERP Faktura
- Bonitäts-Agent: Schnittstelle zur Bonitätsauskunft; Schreibzugriff ERP Kreditakte
- Zahlungszuordnungs-Agent: Schreibzugriff ERP offene Posten; Strukturierter Kontoauszugsimport

Betroffene Rollen:

| Rolle | Stellen | Zeitanteil | FTE | Wert/Jahr |
|---|---:|---:|---:|---:|
| Auftragssachbearbeiter | 9 | 80.0 % | 7.2 | 665 280 € |
| Fakturierungssachbearbeiter | 6 | 100.0 % | 6.0 | 567 600 € |
| Forderungsmanager | 4 | 55.0 % | 2.2 | 232 320 € |
| Kreditprüfer | 3 | 100.0 % | 3.0 | 343 200 € |

### Welle 2: Ausweiten

| Vorhaben | Art | Status | Score | Wert/Jahr | FTE | Zuordnung | Sicht der Beschäftigten |
|---|---|---|---:|---:|---:|---|---|
| Vertriebsklärungs-Assistent | Agent | geplant | 4.6 | 166 320 € | 1.8 | bestätigt (Teamleitung Order-to-Cash) | Nachrang 100 % |
| Mahnlauf-Agent | Agent | geplant | 3.6 | 105 600 € | 1.0 | bestätigt (Teamleitung Order-to-Cash) | nicht befragt |
| Auftragsbestätigung aus Bestelldaten | Use Case | Idee | 2.9 | 129 360 € | 1.4 | Vorschlag | Freigabe 100 % |
| Analyse- und Berichtscopilot | Agent | Vorschlag | 2.7 | 56 320 € | 0.4 | Vorschlag | nicht befragt |

Voraussetzungen laut Agentenbibliothek:

- Vertriebsklärungs-Assistent: Lesezugriff ERP
- Mahnlauf-Agent: Abgestimmte Ausschlussregeln mit dem Vertrieb
- Analyse- und Berichtscopilot: Lesezugriff auf das Berichtswesen

Betroffene Rollen:

| Rolle | Stellen | Zeitanteil | FTE | Wert/Jahr |
|---|---:|---:|---:|---:|
| Auftragssachbearbeiter | 9 | 35.0 % | 3.2 | 295 680 € |
| Forderungsmanager | 4 | 25.0 % | 1.0 | 105 600 € |
| Teamleitung Order-to-Cash | 1 | 40.0 % | 0.4 | 56 320 € |

### Welle 3: Breite

| Vorhaben | Art | Status | Score | Wert/Jahr | FTE | Zuordnung | Sicht der Beschäftigten |
|---|---|---|---:|---:|---:|---|---|
| Order-to-Cash-Orchestrator | Agent | Vorschlag | 2.7 | nicht bewertet | – | Vorschlag | nicht befragt |

Voraussetzungen laut Agentenbibliothek:

- Order-to-Cash-Orchestrator: Alle koordinierten Agenten im Pilotbetrieb; Gemeinsamer Fallzustand im ERP


## Ohne Vorhaben

Keine: Jeder Prozess mit hohem Rang hat mindestens ein Vorhaben.

## Noch offen

- Wellenzuordnung bestätigen (bisher Vorschlag): Welle 2: Ausweiten; Welle 3: Breite
- Zeiträume festlegen: Welle 1: Referenz und Grundlagen; Welle 2: Ausweiten; Welle 3: Breite
- Ohne Sicht der Beschäftigten (keine befragte Aufgabe): Analyse- und Berichtscopilot, Bonitäts-Agent, Mahnlauf-Agent, Zahlungseingang automatisch zuordnen, Zahlungszuordnungs-Agent
- Welle 1: Referenz und Grundlagen: 5 Vorhaben bei Kapazität 3 (laufende oder bestätigte Vorhaben zählen immer)

## Wie das Raster entsteht

Jedes Vorhaben erhält einen Score aus fünf Größen (Wert, Reichweite, Umsetzbarkeit, Reifegrad, Prozessrang). Fehlt eine Größe, rechnet der Score ohne sie und nennt das in der Spalte „Basis des Scores“ der Anlage. Laufende Vorhaben (Pilot, im Betrieb) liegen in der ersten Welle; schwere Vorhaben beginnen nicht dort; Orchestratoren folgen den Agenten, die sie steuern. Die Gewichte stehen in `assets/wave-config.json` und lassen sich pro Projekt ändern.
