# Capability Contracts

Je Agent: was ihn auslöst, worauf er zugreifen darf, wo ein Mensch entscheidet, was passiert, wenn er scheitert, und woran man merkt, dass er schlechter wird.

Die Verträge nennen keine Modellnamen. Sie beschreiben die gebrauchte Fähigkeit, damit ein Modellwechsel eine Beschaffungsentscheidung bleibt und keine Prozessänderung erzwingt.

| Agent | Status | Reichweite | Schreibrechte | Kontrollpunkt |
|---|---|---|---|---|
| Vertriebsklärungs-Assistent | planned | schlägt vor, entscheidet nicht | — | — |
| Auftragserfassungs-Agent | pilot | führt aus, umkehrbar | ERP: Auftragsbestätigung, ERP: Auftragskopf und -positionen | role: Auftragssachbearbeiter; role_id: ro_5d42f48ee610; sla_minutes: 240; when: Konfidenz unter 0,9, kein gültiger Rahmenvertrag, oder Abweichung im Preis über 2 Prozent |
| Mahnlauf-Agent | planned | führt aus, umkehrbar | ERP: Mahnvorschlagsliste (Entwurfsstatus) | role: Teamleitung Order-to-Cash; role_id: ro_e70a9399feff; sla_minutes: 1440; when: Mahnstufe 3 oder höher, oder Kunde mit laufender Klärung |
| Analyse- und Berichtscopilot | proposed | schlägt vor, entscheidet nicht | — | — |
| Bonitäts-Agent | pilot | schlägt vor, entscheidet nicht | ERP: Kreditakte (Vorschlag, Begründung, Quelle) | role: Kreditprüfer; role_id: ro_71b3185c093f; sla_minutes: 480; when: immer vor Wirksamkeit des Limits; zusätzlich bei Konfidenz unter 0,85 |
| Order-to-Cash-Orchestrator | proposed | führt aus, umkehrbar | — | role: Teamleitung Order-to-Cash; role_id: ro_e70a9399feff; sla_minutes: 480; when: Fall ohne Fortschritt über der vereinbarten Frist, oder widersprüchliche Ergebnisse zweier Agenten |
| Fakturierungs-Agent | pilot | führt aus, umkehrbar | ERP: Rechnungsentwurf, ERP: Versandvermerk nach Freigabe | role: Fakturierungssachbearbeiter; role_id: ro_1d3cedfc16c3; sla_minutes: 240; when: immer vor dem Versand (Vier-Augen-Prinzip); zusätzlich bei Konfidenz unter 0,95 oder Abweichung über 5 Prozent |
| Zahlungszuordnungs-Agent | pilot | führt aus, umkehrbar | ERP: Zuordnung von Zahlungseingang zu offenem Posten | role: Forderungsmanager; role_id: ro_409de267032f; sla_minutes: 240; when: Konfidenz unter 0,9 oder Restdifferenz über 100 EUR |

## Vertriebsklärungs-Assistent

Bereitet Rückfragen an den Vertrieb vor: fasst die Abweichung zusammen, schlägt eine Lösung vor und entwirft die Nachricht.

**Muster:** drafting-assistant  
**Status:** planned  
**Bezug:** hybrid

| Feld | Wert |
|---|---|
| Auslöser | Sachbearbeiter markiert eine Abweichung als klärungsbedürftig |
| Eingaben | Auftragsabweichung, Historie ähnlicher Fälle, Vertragsauszug |
| Ausgaben | Lösungsvorschlag, Nachrichtenentwurf, Zusammenfassung |
| Werkzeuge | erp.read_contract, erp.read_order |
| Leserechte | ERP: Aufträge, Rahmenverträge |
| Schreibrechte | — |
| Entscheidungsreichweite | recommend |
| Rückfallebene | Kein Entwurf; der Sachbearbeiter schreibt wie bisher selbst. |
| Zeitgrenze (s) | 60 |
| Audit-Ereignisse | draft.created (Auftrag, Länge, Profilversion) |
| Gebrauchte Fähigkeiten | Deutschsprachige Zusammenfassung und Entwurfserstellung aus strukturiertem Kontext. |

**Voraussetzungen vor dem Bau**

- Lesezugriff ERP

**Aufsicht im Betrieb:** Jede Nachricht wird vom Sachbearbeiter vor dem Versand freigegeben

## Auftragserfassungs-Agent

Liest Bestellungen aus E-Mail, Portal und EDI, legt den Auftrag im ERP an, gleicht Preise und Konditionen gegen den Rahmenvertrag ab und erzeugt die Auftragsbestätigung.

**Muster:** document-extraction  
**Status:** pilot  
**Bezug:** build

| Feld | Wert |
|---|---|
| Auslöser | Neue Bestellung im Eingangskanal (E-Mail-Postfach, Portal, EDI) |
| Eingaben | Bestelldokument, Eingangskanal, Kundennummer |
| Ausgaben | Abweichungsliste, Auftragskopf, Auftragspositionen, Konfidenz |
| Werkzeuge | erp.create_order, erp.read_contract, erp.update_order, mail.send_confirmation |
| Leserechte | ERP: Kundenstammdaten, Rahmenverträge, Preislisten |
| Schreibrechte | ERP: Auftragsbestätigung, ERP: Auftragskopf und -positionen |
| Entscheidungsreichweite | execute_reversible |
| Konfidenzschwelle | 0.9 |
| Menschlicher Kontrollpunkt | role: Auftragssachbearbeiter; role_id: ro_5d42f48ee610; sla_minutes: 240; when: Konfidenz unter 0,9, kein gültiger Rahmenvertrag, oder Abweichung im Preis über 2 Prozent |
| Rückfallebene | Bestellung unverändert in die manuelle Warteschlange stellen und als 'nicht automatisch erfassbar' kennzeichnen; kein Teilauftrag im ERP. |
| Zeitgrenze (s) | 120 |
| Wiederholung | zweimal mit 10 und 60 Sekunden Abstand, danach Fallback |
| Idempotenzschlüssel | kundennummer + bestellnummer + dokument_hash |
| Audit-Ereignisse | order.created (Auftrag, Quelle, Konfidenz, Profilversion), order.escalated (Auftrag, Grund), order.failed (Quelle, Fehlerart) |
| Servicezusage | p95 unter 90 Sekunden, Verfügbarkeit 99 Prozent in der Servicezeit |
| Testmenge | cases: 320; name: auftragserfassung-eval-v1; source: Stichprobe aus 2025, von zwei Sachbearbeitern unabhängig geprüft; thresholds: Positionsgenauigkeit ≥ 0,97; keine stillen Preisabweichungen |
| Kostendeckel | amount: 1200; currency: EUR; period: monat |
| Gebrauchte Fähigkeiten | Strukturierte Extraktion aus PDF, E-Mail und EDI; Abgleich gegen tabellarische Stammdaten; kalibrierte Konfidenz je Position. |

**Voraussetzungen vor dem Bau**

- Digitalisierte Rahmenverträge
- Freigabe Betriebsrat
- Schreibzugriff ERP über Schnittstelle

**Aufsicht im Betrieb:** Stichprobe 10 Prozent durch die Auftragssachbearbeitung; alle Aufträge ohne Rahmenvertrag im Gate

## Mahnlauf-Agent

Erzeugt den Mahnvorschlag, schließt Kunden mit laufender Klärung oder Zahlungsvereinbarung aus und formuliert die Mahnschreiben.

**Muster:** standard-correspondence  
**Status:** planned  
**Bezug:** hybrid

| Feld | Wert |
|---|---|
| Auslöser | Wöchentlicher Mahnlauf, montags 06:00 |
| Eingaben | Klärfälle, Zahlungsvereinbarungen, überfällige offene Posten |
| Ausgaben | Ausschlussliste mit Begründung, Mahnschreiben-Entwurf, Mahnvorschlag je Kunde |
| Werkzeuge | erp.create_dunning_proposal, erp.read_agreements, erp.read_open_items |
| Leserechte | ERP: offene Posten, Klärfälle, Zahlungsvereinbarungen |
| Schreibrechte | ERP: Mahnvorschlagsliste (Entwurfsstatus) |
| Entscheidungsreichweite | execute_reversible |
| Konfidenzschwelle | 0.9 |
| Menschlicher Kontrollpunkt | role: Teamleitung Order-to-Cash; role_id: ro_e70a9399feff; sla_minutes: 1440; when: Mahnstufe 3 oder höher, oder Kunde mit laufender Klärung |
| Rückfallebene | Standard-Mahnvorschlag des ERP ohne Ausschlüsse erzeugen und als ungeprüft kennzeichnen. |
| Zeitgrenze (s) | 300 |
| Wiederholung | einmal nach 300 Sekunden, danach Fallback |
| Idempotenzschlüssel | mahnlauf_datum + kundennummer |
| Audit-Ereignisse | dunning.excluded (Kunde, Grund), dunning.failed (Lauf, Fehlerart), dunning.proposed (Kunde, Stufe, Betrag, Profilversion) |
| Gebrauchte Fähigkeiten | Regelbasierte Auswahl aus strukturierten Posten; deutschsprachige Korrespondenz in vorgegebener Tonalität. |

**Voraussetzungen vor dem Bau**

- Abgestimmte Ausschlussregeln mit dem Vertrieb

**Aufsicht im Betrieb:** Ab Mahnstufe 3 gibt die Teamleitung jeden Fall einzeln frei

## Analyse- und Berichtscopilot

Bereitet Durchlaufzeiten, Außenstände und Fehlerquoten auf, erklärt Abweichungen und unterstützt bei der Wirkungsabschätzung von Prozessänderungen.

**Muster:** analysis-copilot  
**Status:** proposed  
**Bezug:** buy

| Feld | Wert |
|---|---|
| Auslöser | Monatsabschluss oder Anfrage der Teamleitung |
| Eingaben | Prozesskennzahlen, Vormonatswerte, Änderungsvorhaben |
| Ausgaben | Abweichungserklärung, Berichtsentwurf, Wirkungsabschätzung |
| Werkzeuge | erp.read_metrics |
| Leserechte | ERP: aggregierte Prozesskennzahlen |
| Schreibrechte | — |
| Entscheidungsreichweite | recommend |
| Rückfallebene | Kein Entwurf; die Teamleitung berichtet wie bisher aus den Rohdaten. |
| Zeitgrenze (s) | 120 |
| Audit-Ereignisse | report.drafted (Periode, Kennzahlen, Profilversion) |
| Gebrauchte Fähigkeiten | Erklärende Analyse über Zeitreihen; deutschsprachige Berichtssprache; Wirkungsabschätzung mit ausgewiesenen Annahmen. |

**Voraussetzungen vor dem Bau**

- Lesezugriff auf das Berichtswesen

**Aufsicht im Betrieb:** Die Interpretation und jede Aussage nach außen bleibt bei der Teamleitung

## Bonitäts-Agent

Holt die externe Bonitätsauskunft, führt sie mit der internen Zahlungshistorie zusammen, schlägt ein Kreditlimit vor, kennzeichnet Limitüberschreitungen und dokumentiert die Entscheidung revisionssicher.

**Muster:** data-reconciliation  
**Status:** pilot  
**Bezug:** hybrid

| Feld | Wert |
|---|---|
| Auslöser | Geprüfter Auftrag ohne gültiges Kreditlimit oder Limit älter als 90 Tage |
| Eingaben | Auftragswert, Kundennummer, interne Zahlungshistorie |
| Ausgaben | Begründung, Bonitätsurteil, Konfidenz, Limitvorschlag |
| Werkzeuge | credit.fetch_report, erp.read_payment_history, erp.write_credit_file |
| Leserechte | Bonitätsauskunft: Unternehmensauskunft, ERP: Zahlungshistorie, offene Posten |
| Schreibrechte | ERP: Kreditakte (Vorschlag, Begründung, Quelle) |
| Entscheidungsreichweite | recommend |
| Konfidenzschwelle | 0.85 |
| Menschlicher Kontrollpunkt | role: Kreditprüfer; role_id: ro_71b3185c093f; sla_minutes: 480; when: immer vor Wirksamkeit des Limits; zusätzlich bei Konfidenz unter 0,85 |
| Rückfallebene | Bonitätsauskunft als Rohdokument anhängen, kein Limitvorschlag; der Kreditprüfer arbeitet wie bisher. |
| Zeitgrenze (s) | 180 |
| Wiederholung | dreimal mit 30, 120 und 300 Sekunden Abstand, danach Fallback |
| Idempotenzschlüssel | kundennummer + auskunftsdatum |
| Audit-Ereignisse | credit.assessed (Kunde, Vorschlag, Quelle, Profilversion), credit.escalated (Kunde, Überschreitung), credit.failed (Kunde, Fehlerart) |
| Servicezusage | p95 unter 240 Sekunden, Verfügbarkeit 98 Prozent |
| Testmenge | cases: 180; name: bonitaet-eval-v1; source: Entscheidungen 2024 und 2025 mit bekanntem Zahlungsverlauf; thresholds: Kein Vorschlag über dem später tatsächlich vergebenen Limit; Trefferquote Risikoklasse ≥ 0,85 |
| Kostendeckel | amount: 900; currency: EUR; period: monat |
| Gebrauchte Fähigkeiten | Zusammenführung strukturierter externer und interner Kennzahlen; regelbasierte Ableitung mit begründeter Ausgabe. |

**Voraussetzungen vor dem Bau**

- Schnittstelle zur Bonitätsauskunft
- Schreibzugriff ERP Kreditakte

**Aufsicht im Betrieb:** Limitvorschlag wird immer von einem Kreditprüfer bestätigt; Überschreitungen gehen an die Teamleitung

## Order-to-Cash-Orchestrator

Führt die Spezialagenten entlang des Prozesses zusammen: übergibt Ergebnisse, hält den Fallzustand, entscheidet, wann ein Mensch gebraucht wird, und stellt sicher, dass kein Fall liegen bleibt.

**Muster:** workflow-orchestration  
**Status:** proposed  
**Bezug:** hybrid

**Koordiniert:** Auftragserfassungs-Agent, Mahnlauf-Agent, Bonitäts-Agent, Fakturierungs-Agent, Zahlungszuordnungs-Agent

| Feld | Wert |
|---|---|
| Auslöser | Zustandswechsel eines Falls im Order-to-Cash-Prozess |
| Eingaben | Ergebnis des vorangegangenen Schrittes, Fallzustand |
| Ausgaben | Fristüberwachung, Zuweisung an Agent oder Mensch, nächster Schritt |
| Werkzeuge | agent.invoke, erp.read_case_state |
| Leserechte | ERP: Fallzustand aller Order-to-Cash-Vorgänge |
| Schreibrechte | — |
| Entscheidungsreichweite | execute_reversible |
| Menschlicher Kontrollpunkt | role: Teamleitung Order-to-Cash; role_id: ro_e70a9399feff; sla_minutes: 480; when: Fall ohne Fortschritt über der vereinbarten Frist, oder widersprüchliche Ergebnisse zweier Agenten |
| Rückfallebene | Fall an die zuständige Rolle übergeben und als 'manuell weiterführen' kennzeichnen. |
| Zeitgrenze (s) | 30 |
| Audit-Ereignisse | case.routed (Fall, Von, Nach, Grund), case.stalled (Fall, Dauer) |
| Gebrauchte Fähigkeiten | Zustandsbehaftete Ablaufsteuerung über mehrere Werkzeuge; Konflikterkennung zwischen Teilergebnissen. |

**Voraussetzungen vor dem Bau**

- Alle koordinierten Agenten im Pilotbetrieb
- Gemeinsamer Fallzustand im ERP

**Aufsicht im Betrieb:** Eskaliert jeden Fall, der länger als die vereinbarte Frist ohne Fortschritt ist, an die Teamleitung

## Fakturierungs-Agent

Stellt Leistungsnachweise zu einer Abrechnungsgrundlage zusammen, erzeugt den Rechnungsentwurf, prüft ihn gegen Auftrag und Vertrag und übernimmt Versand und Archivierung nach Freigabe.

**Muster:** invoice-verification  
**Status:** pilot  
**Bezug:** build

| Feld | Wert |
|---|---|
| Auslöser | Auftrag ist geliefert und abrechnungsreif |
| Eingaben | Auftrag, Lieferscheine, Stundennachweise, Vertragskonditionen |
| Ausgaben | Abrechnungsgrundlage, Konfidenz, Prüfbefund, Rechnungsentwurf |
| Werkzeuge | archive.store, erp.create_invoice_draft, erp.read_delivery, erp.read_order, erp.send_invoice |
| Leserechte | ERP: Aufträge, Lieferscheine, Verträge |
| Schreibrechte | ERP: Rechnungsentwurf, ERP: Versandvermerk nach Freigabe |
| Entscheidungsreichweite | execute_reversible |
| Konfidenzschwelle | 0.95 |
| Menschlicher Kontrollpunkt | role: Fakturierungssachbearbeiter; role_id: ro_1d3cedfc16c3; sla_minutes: 240; when: immer vor dem Versand (Vier-Augen-Prinzip); zusätzlich bei Konfidenz unter 0,95 oder Abweichung über 5 Prozent |
| Rückfallebene | Abrechnungsgrundlage als Liste anhängen, keinen Entwurf erzeugen; die Fakturierung arbeitet wie bisher. |
| Zeitgrenze (s) | 180 |
| Wiederholung | zweimal mit 30 und 120 Sekunden Abstand, danach Fallback |
| Idempotenzschlüssel | auftragsnummer + abrechnungsperiode |
| Audit-Ereignisse | invoice.drafted (Auftrag, Betrag, Konfidenz, Profilversion), invoice.failed (Auftrag, Fehlerart), invoice.sent (Rechnung, Kanal, Freigeber) |
| Servicezusage | p95 unter 120 Sekunden, Verfügbarkeit 99 Prozent in der Servicezeit |
| Testmenge | cases: 400; name: faktura-eval-v1; source: Rechnungen 2025 inklusive aller Gutschriftfälle; thresholds: Betragsgenauigkeit 100 Prozent; keine Rechnung ohne Archivbeleg |
| Kostendeckel | amount: 1500; currency: EUR; period: monat |
| Gebrauchte Fähigkeiten | Zuordnung von Belegen zu Aufträgen; regelbasierte Belegerzeugung; Abgleich gegen Konditionen mit begründetem Prüfbefund. |

**Voraussetzungen vor dem Bau**

- Abgestimmte Prüfregeln mit der Revision
- Schnittstelle zum Archiv
- Schreibzugriff ERP Faktura

**Aufsicht im Betrieb:** Die Freigabe der Rechnung bleibt beim Menschen; der Agent liefert Entwurf und Prüfbefund

## Zahlungszuordnungs-Agent

Ordnet Zahlungseingänge aus dem Kontoauszug den offenen Posten zu, teilt Teilzahlungen auf und schlägt für Differenzen eine Erklärung vor.

**Muster:** data-reconciliation  
**Status:** pilot  
**Bezug:** build

| Feld | Wert |
|---|---|
| Auslöser | Kontoauszug wurde eingelesen |
| Eingaben | Kontoauszugspositionen, Verwendungszweck, offene Posten |
| Ausgaben | Erklärungsvorschlag, Konfidenz, Restdifferenz, Zuordnung |
| Werkzeuge | erp.assign_payment, erp.read_customer, erp.read_open_items |
| Leserechte | ERP: offene Posten, Kundenstammdaten, Kontoauszüge |
| Schreibrechte | ERP: Zuordnung von Zahlungseingang zu offenem Posten |
| Entscheidungsreichweite | execute_reversible |
| Konfidenzschwelle | 0.9 |
| Menschlicher Kontrollpunkt | role: Forderungsmanager; role_id: ro_409de267032f; sla_minutes: 240; when: Konfidenz unter 0,9 oder Restdifferenz über 100 EUR |
| Rückfallebene | Position unzugeordnet lassen und als 'maschinell nicht zuordenbar' kennzeichnen; keine Teilzuordnung. |
| Zeitgrenze (s) | 60 |
| Wiederholung | zweimal mit 15 und 60 Sekunden Abstand, danach Fallback |
| Idempotenzschlüssel | kontoauszug_id + positionsnummer |
| Audit-Ereignisse | payment.failed (Auszug, Fehlerart), payment.matched (Position, Posten, Konfidenz, Profilversion), payment.unmatched (Position, Grund) |
| Servicezusage | p95 unter 30 Sekunden, Verfügbarkeit 99 Prozent |
| Testmenge | cases: 600; name: zahlungszuordnung-eval-v1; source: Kontoauszüge 2025 mit nachträglich korrigierter Zuordnung als Wahrheit; thresholds: Trefferquote ≥ 0,95; Fehlzuordnungen ≤ 0,2 Prozent |
| Kostendeckel | amount: 700; currency: EUR; period: monat |
| Gebrauchte Fähigkeiten | Fuzzy-Abgleich zwischen Freitext-Verwendungszweck und strukturierten Posten; Aufteilung von Teilbeträgen; kalibrierte Konfidenz. |

**Voraussetzungen vor dem Bau**

- Schreibzugriff ERP offene Posten
- Strukturierter Kontoauszugsimport

**Aufsicht im Betrieb:** Zuordnungen unter Konfidenz 0,9 und alle Differenzen über 100 EUR gehen an das Forderungsmanagement

