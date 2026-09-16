# Bewertungsrubrik für Aufgaben

Sechs Werte je Aufgabe, jeweils ganze Zahl 0–10, plus eine Begründung in ein bis zwei Sätzen.
Bewerte die Aufgabe so, wie sie in dieser Rolle mit den genannten Workflow-Schritten und
Systemen heute anfällt, nicht eine idealisierte Version. Bewerte den Stand der Technik von
heute (verfügbare LLM-Agenten, RPA, Dokumenten-KI, Prognosemodelle), nicht was in fünf Jahren
denkbar ist. Die Zeitfrage beantwortet `data_readiness`, nicht `automation_ai`.

## Die sechs Werte

### automation_ai — Wie viel der Aufgabe kann Software/KI heute übernehmen?

| Wert | Anker |
|---|---|
| 0–1 | Kein digitaler Zugriff auf die Aufgabe (rein physisch, rein zwischenmenschlich vor Ort) |
| 2–3 | KI kann Teilschritte vorbereiten (Recherche, Entwurf), der Kern bleibt beim Menschen: Verhandlung, Mitarbeitergespräch, Krisenentscheidung |
| 4–5 | Etwa die Hälfte der Schritte ist automatisierbar; der Mensch prüft, entscheidet oder ergänzt Kontext: komplexe Kundenanliegen, explorative Analysen, Konzeptarbeit |
| 6–7 | Der Großteil läuft automatisch, der Mensch behandelt Ausnahmen: Standard-Sachbearbeitung mit Sonderfällen, Berichte mit Interpretation, Ticket-Triage |
| 8–9 | Regelbasiert oder gut spezifiziert, strukturierte Ein- und Ausgaben, Ausnahmen selten: Datenübernahme, Plausibilisierung, Standardkorrespondenz, Terminabstimmung, Monitoring |
| 10 | Bereits heute vollständig automatisierbar ohne nennenswerten Qualitätsverlust |

Faustregeln: Wiederkehrend + regelbasiert + digitale Eingaben → hoch. Jeder Fall anders +
implizites Wissen + Verhandlung → niedrig. Marktkommunikation, Stammdatenpflege, Abgleiche,
Standardberichte und Terminkoordination liegen fast immer bei 7–9.

Live-Dialog (Telefon, Chat): Der Kanal senkt den Wert nicht automatisch. Standardanliegen mit
Systemzugriff (Abschlag ändern, Zählerstand erfassen, Statusauskunft) liegen bei 7–8, weil
Sprach- und Chatagenten sie heute lösen; Beratung mit Bedarfserkennung und Abschluss bei 4–5;
Beschwerde und Deeskalation bei 2–3. Entscheidend ist, was im Gespräch passiert, nicht dass es eines ist.

### automation_physical — Wie viel des körperlichen Anteils kann Robotik/Sensorik übernehmen?

| Wert | Anker |
|---|---|
| 0 | Aufgabe hat keinen physischen Anteil (dann immer 0, nicht raten) |
| 1–3 | Handarbeit in unstrukturierter Umgebung: Entstörung vor Ort, Montage im Bestand, Begehungen |
| 4–6 | Teilweise durch Sensorik, Drohnen, Fernwirktechnik ersetzbar: Inspektion, Zählerablesung, Zustandsüberwachung |
| 7–10 | Standardisierte physische Prozesse mit verfügbarer Automatisierung: Lager, Sortierung, Messung in fester Umgebung |

Bei `nature = cognitive` ist dieser Wert 0. Bei `physical` bildet er das Automatisierungspotenzial,
bei `mixed` der Mittelwert aus beiden. Fernwirk- und Fernsteuertechnik zählt mit: Wenn eine
Vor-Ort-Tätigkeit durch Fernbedienung aus der Leitstelle entfällt, ist das Automatisierung der
physischen Aufgabe (Wert 6–8), auch wenn ein Mensch die Fernbedienung auslöst.

### human_judgment — Wie viel menschliches Urteil braucht die Aufgabe für ein gutes Ergebnis?

| Wert | Anker |
|---|---|
| 0–2 | Ergebnis ist eindeutig richtig oder falsch, Regeln vollständig bekannt |
| 3–4 | Gelegentlich Ermessen bei klaren Kriterien; ein Vier-Augen-Blick reicht |
| 5–6 | Regelmäßige Abwägung mit Kontext: Kulanz, Priorisierung, Interpretation mehrdeutiger Daten |
| 7–8 | Verantwortung für Folgen, ethische oder rechtliche Wertung, Interessen ausgleichen |
| 9–10 | Strategische, personelle oder sicherheitskritische Entscheidung, die Menschen zurechenbar sein muss |

Menschliches Urteil ist nicht das Gegenteil von Automatisierbarkeit. Eine Aufgabe kann zu 80 %
automatisierbar sein und trotzdem an einer Stelle hohes Urteil verlangen; dann sind beide Werte hoch.

### productivity_boost — Wie viel schneller/besser wird ein Mensch mit KI-Unterstützung, wenn die Aufgabe bei ihm bleibt?

| Wert | Anker |
|---|---|
| 0–2 | Kaum Hebel: körperliche Arbeit, Gespräche, Warten |
| 3–4 | Kleine Hilfen: Vorlagen, Zusammenfassungen, Suche (10–20 % Zeitersparnis) |
| 5–6 | Substanzielle Hilfe: Entwürfe, Auswertungen, Recherche, Übersetzung (20–40 %) |
| 7–8 | KI liefert den Großteil, Mensch prüft und verfeinert (40–60 %) |
| 9–10 | Mensch wird zum Prüfer, Aufwand sinkt um mehr als 60 % |

### data_readiness — Liegen die nötigen Eingaben digital, strukturiert und zugänglich vor?

| Wert | Anker |
|---|---|
| 0–2 | Papier, Zuruf, verteiltes Kopfwissen, keine Schnittstelle |
| 3–5 | Digital, aber unstrukturiert oder in Silos (E-Mails, PDFs, Excel-Listen, Altsysteme ohne API) |
| 6–8 | Strukturiert in Kernsystemen (SAP, CRM, Ticketsystem) mit Schnittstelle oder Export |
| 9–10 | API-fähig, Datenqualität gesichert, Berechtigungen geklärt |

Dieser Wert bestimmt den Zeithorizont. Was heute an Daten scheitert, ist mittelfristig, nicht kurzfristig.

### consequence_of_error — Wie schwer wiegt ein unentdeckter Fehler?

| Wert | Anker |
|---|---|
| 0–2 | Leicht korrigierbar, intern, kein Schaden |
| 3 | Kunde oder Kollege merkt es, wird im normalen Prozess ohne Zusatzaufwand nachkorrigiert (Korrekturschreiben, erneuter Lauf) |
| 4–5 | Braucht aktive Nacharbeit oder Kulanz; Kunde beschwert sich; Fristen verschieben sich; Reputationskratzer |
| 6–8 | Finanzieller Schaden, Vertragsverletzung, Datenschutzvorfall, aufsichtliche Meldung |
| 9–10 | Gefahr für Personen, Versorgungssicherheit, Rechtsverstoß mit Haftung |

Regulierte Rollen (`regulated = true`): Delegation an Agenten nur bei consequence_of_error ≤ 3,
sonst ≤ 5. Das Skript setzt diese Regel; du musst nur ehrlich bewerten. Weil in regulierten
Rollen die Wahl zwischen 3 und 4 über Delegation entscheidet, stelle dir die Kontrollfrage: Würde
ein unentdeckter Fehler in diesem Schritt im normalen Prozess von selbst auffallen und ohne
Mehraufwand korrigiert (→ 3), oder bräuchte es jemanden, der aktiv nacharbeitet (→ 4)?

### rationale — Begründung

Ein bis zwei Sätze, die einem Fachexperten erlauben zu widersprechen. Nenne den entscheidenden
Grund für die Einordnung („Regelbasierte Marktkommunikation über EDIFACT, Ausnahmen nur bei
Datenfehlern") und, wo relevant, was der Delegation im Weg steht („Eingang kommt per Brief").

## Was das Skript daraus ableitet (nicht selbst setzen)

Automatisierungspotenzial AP: cognitive → automation_ai; physical → automation_physical;
mixed → Mittelwert.

Ausführungsmodus je Aufgabe, erste zutreffende Regel gewinnt:

1. `agent_delegated`: AP ≥ 7 und human_judgment ≤ 3 und consequence_of_error ≤ 5 (reguliert: ≤ 3)
2. `ai_assisted`: AP ≥ 4 oder productivity_boost ≥ 5
3. `manual`: sonst

HAS-Level (Human Agency Scale nach Stanford WORKBank, 1 = Agent allein, 5 = Mensch unverzichtbar):
H1: AP ≥ 8 und HJ ≤ 2 · H2: AP ≥ 6 und HJ ≤ 4 · H3: AP ≥ 4 und HJ ≤ 6 · H4: AP ≥ 2 · H5: sonst.

Zeithorizont (nur für nicht-manuelle Aufgaben): near = data_readiness ≥ 6 und
consequence_of_error ≤ 5 · mid = data_readiness ≥ 3 · long = sonst.

Rollenwerte sind zeitanteilgewichtete Mittel der Aufgabenwerte. Disruptionsscore =
0,5·AP + 0,3·productivity_boost + 0,2·(10 − human_judgment).

Disruptionstyp, erste zutreffende Regel gewinnt:

1. `emerging`: Rolle ist als neu markiert (`is_new`)
2. `eliminated`: ≥ 60 % der Zeit delegierbar und human_judgment (Rolle) ≤ 3
3. `transformed`: ≥ 30 % delegierbar oder (AP ≥ 6 und human_judgment ≤ 5)
4. `augmented`: ≥ 40 % delegier- oder assistierbar oder productivity_boost ≥ 5
5. `stable`: sonst

Rollenhorizont: near, wenn ≥ 30 % der Zeit kurzfristig automatisierbar; mid, wenn near+mid ≥ 30 %;
sonst long; null, wenn nichts automatisierbar.

Bereitschaft (`readiness`): zeitanteilgewichtete data_readiness der nicht-manuellen Aufgaben;
high ≥ 7, medium ≥ 4, sonst low. Sagt, ob die Datenlage den Start erlaubt.

Zeitanteile je Rolle: `share_human_core` = Anteil der Aufgaben im Modus manuell (das ist der Kern,
der beim Menschen bleibt), `share_ai_assisted`, `share_agent_delegated`. Eine Rolle mit 0 % Kern
und 90 % assistiert ist nicht „weg", sondern arbeitet durchgehend mit KI-Unterstützung.

Skills je Rolle: `retained_skills` hängen an manuellen oder assistierten Aufgaben (werden weiter
gebraucht), `declining_skills` überwiegend an delegierten Aufgaben (Bedarf sinkt).

Wo die abgeleiteten Werte stehen: je Aufgabe als Felder `automation_potential`, `mode`,
`has_level`, `horizon` direkt am Task-Objekt; je Rolle im Block `roles[].analysis`.

Belastbarkeit (`evidence`): Punkte für Zeitanteile aus Quelle (+2), Expertenreview (+2, freigegeben
+3), weniger als 20 % der Zeit aus abgeleiteten Aufgaben (+1), Headcount bekannt (+1);
high ≥ 5, medium ≥ 2, sonst low.

Kipp-Analyse (`stability`): Für jede Aufgabe werden Maschinenanteil, Urteilsbedarf und
Fehlergewicht einzeln um ±1 verändert und die Rollenwirkung neu berechnet. Anteil der
Änderungen, die die Wirkung kippen: 0 % stable, ≤ 10 % borderline, sonst fragile.

## Kalibrierungsbeispiele

| Aufgabe | ai | phys | HJ | PB | DR | CoE | Modus |
|---|---|---|---|---|---|---|---|
| Zählerstände plausibilisieren und ins Abrechnungssystem übernehmen | 9 | 0 | 2 | 7 | 8 | 3 | agent_delegated |
| Kulanzentscheidung bei Beschwerde treffen | 4 | 0 | 7 | 5 | 6 | 5 | ai_assisted |
| Monatlichen Standardbericht Netzverluste erstellen | 8 | 0 | 3 | 8 | 7 | 3 | agent_delegated |
| Störung an Ortsnetzstation vor Ort beheben | 1 | 2 | 6 | 2 | 4 | 9 | manual |
| Verhandlung mit Kommune über Konzessionsvertrag führen | 2 | 0 | 9 | 4 | 3 | 8 | manual |
| Vertragsentwurf gegen Musterklauseln prüfen | 7 | 0 | 5 | 7 | 6 | 6 | ai_assisted (HJ zu hoch für Delegation) |
| Mitarbeitergespräch führen | 1 | 0 | 9 | 2 | 2 | 6 | manual |
| Eingehende Kundenmails klassifizieren und weiterleiten | 9 | 0 | 1 | 8 | 7 | 2 | agent_delegated |

Quellen der Methodik: Stanford „Future of Work with AI Agents" (Shao et al. 2025, WORKBank,
Human Agency Scale H1–H5), Anthropic Economic Index (Automation vs. Augmentation auf
O*NET-Task-Ebene), Metriken kommerzieller AI-Transformation-Dashboards (Automation Potential,
Human Judgment, Disruption Score, Rollen-Typen). Die Schwellen sind Arbeitswerte für den Piloten und sollen mit
Expertenurteilen kalibriert werden; sie stehen als Konstanten am Kopf von `scripts/score_roles.py`.
