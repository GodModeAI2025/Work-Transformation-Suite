# Katalog kanonischer Agentenmuster

Zweck: gleiche Fähigkeiten über Rollen hinweg unter einem Namen bündeln. Ein Agent im Graphen ist
eine wiederverwendbare Fähigkeit, nicht ein Bot je Rolle. „Regulatorik-Monitor" deckt Aufgaben
in Netz, Handel und Compliance ab; das ist der Punkt.

Namensregel: `<Muster>-Agent` plus optional Domänenzusatz, z. B. „Dokumentenextraktions-Agent
Netzanschluss". Das Muster (Spalte `pattern`) muss aus dieser Liste stammen; der Name darf spezifischer sein.

| pattern | Was der Agent tut | Typische Aufgabenwörter | specificity (Default) |
|---|---|---|---|
| document-extraction | Strukturierte Daten aus Dokumenten, Mails, Formularen ziehen | erfassen, übernehmen, auslesen, prüfen auf Vollständigkeit | generic |
| classification-routing | Eingänge klassifizieren, priorisieren, weiterleiten | sichten, zuordnen, weiterleiten, triagieren | generic |
| data-reconciliation | Datensätze abgleichen, Abweichungen melden | abgleichen, plausibilisieren, prüfen, konsolidieren | domain |
| master-data-maintenance | Stammdaten anlegen, ändern, bereinigen | anlegen, pflegen, ändern, aktualisieren | domain |
| standard-correspondence | Standardschreiben, Bestätigungen, Antworten erzeugen und versenden | beantworten, bestätigen, versenden, informieren | generic |
| report-generation | Wiederkehrende Berichte aus Systemdaten erstellen | berichten, reporten, auswerten, zusammenstellen | domain |
| anomaly-detection | Auffälligkeiten in Zeitreihen/Transaktionen erkennen | überwachen, kontrollieren, erkennen, melden | domain |
| forecasting | Prognosen aus historischen Daten erstellen | prognostizieren, planen, schätzen, vorhersagen | domain |
| regulatory-monitor | Gesetzes-/Regeländerungen verfolgen und Auswirkungen aufbereiten | verfolgen, beobachten, bewerten Änderungen | domain |
| knowledge-qa | Fragen aus Dokumentenbeständen beantworten | recherchieren, nachschlagen, beantworten, erklären | generic |
| scheduling-coordination | Termine, Einsätze, Ressourcen koordinieren | terminieren, planen, koordinieren, abstimmen | generic |
| ticket-resolution | Standardanliegen bis zur Lösung bearbeiten | bearbeiten, lösen, klären, erledigen | domain |
| conversational-assistant | Kunden- oder Mitarbeiter-Dialog per Chat/Voice führen (Auskunft, Selfservice, Störungsmeldung) | Chatbot, Voicebot, auskunft geben, melden per Chat | domain |
| contract-change-handling | Vertrags- und Tarifänderungen prozessieren | ändern, wechseln, kündigen, verlängern | proprietary |
| market-communication | Marktkommunikation (EDIFACT, GPKE/GeLi) abwickeln | melden, übermitteln, anmelden, abmelden | proprietary |
| meter-data-processing | Messwerte verarbeiten, ersetzen, freigeben | ablesen, ersetzen, freigeben, verarbeiten Messwerte | proprietary |
| invoice-verification | Rechnungen prüfen, kontieren, freigeben vorbereiten | prüfen, kontieren, freigeben Rechnungen | domain |
| compliance-check | Vorgänge gegen Regeln/Checklisten prüfen | prüfen auf Konformität, freigeben, dokumentieren | domain |
| quality-review | Ergebnisse (Texte, Daten, Code) gegen Kriterien prüfen | reviewen, prüfen, kontrollieren Qualität | generic |
| drafting-assistant | Entwürfe für Texte, Konzepte, Präsentationen liefern | entwerfen, formulieren, erstellen Konzept | generic |
| analysis-copilot | Explorative Analysen, Szenarien, Visualisierungen | analysieren, auswerten, modellieren, vergleichen | generic |
| meeting-assistant | Protokolle, Aufgaben, Nachverfolgung aus Meetings | protokollieren, nachhalten, zusammenfassen | generic |
| onboarding-guide | Neue Mitarbeitende, Kunden oder Partner durch Prozesse führen | einführen, erklären, begleiten | domain |
| workflow-orchestration | Mehrschrittige Prozesse zwischen Systemen ausführen | auslösen, weitergeben, abschließen, nachhalten | proprietary |
| inspection-support | Sensorik/Bilder auswerten, Befunde vorschlagen (physisch) | inspizieren, begehen, prüfen Zustand | domain |
| dispatch-optimization | Einsätze, Routen, Reihenfolgen optimieren | disponieren, einplanen, zuweisen | domain |

## Zuordnungsregeln

- Jede nicht-manuelle Aufgabe (mode `ai_assisted` oder `agent_delegated`) bekommt genau einen
  Agenten. Ein Agent kann beliebig viele Aufgaben aus beliebig vielen Rollen abdecken.
- Manuelle Aufgaben bekommen keinen Agenten. Ausnahme: keine.
- Lieber wenige Agenten mit vielen Aufgaben als einer je Aufgabe. Richtwert: 6–15 Agenten für
  einen Bereich mit 20–40 Rollen. Wenn du über 20 kommst, fasse nach Muster zusammen.
- Bereits laufende KI-Anwendungen des Unternehmens (Liste vom Nutzer) als Agenten mit
  `status: live` (oder `pilot`) und Feld `existing_system` anlegen; Aufgaben, die sie schon
  abdecken, zuordnen. Deckt ein bestehendes System eine Aufgabe nur teilweise ab, entscheidet der
  überwiegende Teil: Übernimmt es mehr als die Hälfte der Aufgabe, gehört die Aufgabe zu ihm,
  sonst zu dem vorgeschlagenen Agenten, der den Rest übernimmt; das Feld `capability` des
  bestehenden Agenten beschreibt die Lücke.
- `specificity`: generic = am Markt als Produkt/Copilot verfügbar; domain = branchenspezifisch,
  Konfiguration nötig; proprietary = hängt an eigenen Prozessen/Systemen, muss gebaut werden.
- `oversight`: wer prüft was (Stichprobe, Vier-Augen bei Betrag > X, Freigabe vor Versand).
  Bei regulierten Rollen Pflichtfeld mit konkretem Kontrollpunkt.
- `prerequisites`: Datenzugänge, Schnittstellen, Berechtigungen, Betriebsratsthemen. Konkret.
- `complexity` 1–5: 1 = Konfiguration eines Standardtools, 3 = Integration in ein Kernsystem,
  5 = mehrere Systeme, neue Datenpipelines, Prozessänderung.
