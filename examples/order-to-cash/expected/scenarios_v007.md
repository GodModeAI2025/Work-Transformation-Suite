# Ist und Soll im Vergleich

Je Prozess: der heutige Ablauf, die entworfenen Szenarien und was sich zwischen ihnen tatsächlich ändert. Alle Soll-Zahlen sind aus den Schritten des jeweiligen Blueprints gerechnet, nicht zugesagt.

## Rechnung bis Zahlungseingang

**Ergebnis:** Forderung ausgeglichen  
**Menge:** 21000 Fälle/Jahr

| Kennzahl | Ist | Konservativ | Ausgewogen | Agent-nativ |
|---|---|---|---|---|
| Schritte | 6 | 6 (+0) | 4 (+2) | 3 (+3) |
| Human Touchpoints | 6 | 6 (+0) | 3 (+3) | 3 (+3) |
| Übergaben | 6 | 3 (+3) | 3 (+3) | 2 (+4) |
| Bearbeitungszeit (min) | 68 | 48 (+20) | 26 (+42) | 17 (+51) |
| Wartezeit (min) | 1980 | 1350 (+630) | 470 (+1510) | 205 (+1775) |
| Durchlaufzeit (h) | 34.1 | 23.3 (+10.8) | 8.3 (+25.8) | 3.5 (+30.6) |
| Nacharbeit (%) | 11 | 8 (+3) | 6 (+5) | 4.7 (+6.3) |
| automatisierte Schritte | 0 | 1 (+1) | 2 (+2) | 2 (+2) |
| Menschliche Arbeit (VZÄ) | 14.9 | 10.5 | 5.5 | 3.7 |

Der Wert in Klammern ist die Verbesserung gegenüber dem Ist (positiv heißt immer besser, unabhängig von der Richtung der Kennzahl).

### Konservativ: Rechnung bis Zahlungseingang — Zuordnung automatisiert, Rest unverändert

Nur die Zuordnung der Zahlungseingänge übernimmt ein Agent. Klärung, Mahnwesen und Zahlungsvereinbarungen bleiben menschlich und werden lediglich besser vorbereitet. Alle Kontrollen bleiben unverändert.

**Angewandte Operatoren:** Automatisieren 1×, Human Gate 1×, Vereinfachen 4×  
**Status:** reviewed

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Zahlungseingang zuordnen | Automatisieren | agent (Zahlungszuordnungs-Agent) | Zahlungseingang zuordnen | Der Abgleich zwischen Verwendungszweck und offenen Posten ist ein Datenabgleich mit sehr guter Datenlage. · Human Gate: Konfidenz unter 0,9 oder Restdifferenz über 100 EUR |
| 2 | Differenz klären | Vereinfachen | human (Forderungsmanager) | Differenz klären | Der Agent liefert eine Erklärungshypothese mit; recherchiert werden muss nur noch, was sie nicht erklärt. |
| 3 | Mahnstufe bestimmen | Vereinfachen | human (Forderungsmanager) | Mahnstufe bestimmen | Die Vorschlagsliste ist vorgefiltert um Kunden mit laufender Klärung; durchgesehen wird nur der Rest. |
| 4 | Mahnung freigeben | Human Gate | human (Teamleitung Order-to-Cash) | Mahnung freigeben | Eine Mahnung an einen zahlenden Kunden kostet Vertrauen. Die Freigabe bleibt unverändert bei der Teamleitung. · Human Gate: Mahnstufe 3 oder höher |
| 5 | Mahnung versenden | Vereinfachen | human (Forderungsmanager) | Mahnung versenden | Der Versand erfolgt gesammelt aus der freigegebenen Liste statt einzeln. |
| 6 | Zahlungsvereinbarung abstimmen | Vereinfachen | human (Forderungsmanager) | Zahlungsvereinbarung abstimmen | Ratenpläne werden aus Vorlagen vorgerechnet; verhandelt wird wie bisher. |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Mahnungen an zahlende Kunden | 2.5 (geschätzt) | 2 | geschätzt |
| Quote unklarer Zahlungseingänge | 14 (gemessen) | 8 | geschätzt |
| Durchlaufzeit bis geklärte Zuordnung | 36 (gemessen) | 24 | geschätzt |

**Offene Annahmen**

- Ob Klärfälle im ERP zuverlässig gekennzeichnet sind, ist nicht geprüft.

**Risiken**

- Eine falsche automatische Zuordnung ist schlechter als keine, weil sie den offenen Posten schließt. Gegenmaßnahme: Konfidenzschwelle 0,9 und tägliche Ausreißerprüfung.

### Ausgewogen: Rechnung bis Zahlungseingang — Zuordnung und Vorklärung zusammen

Zuordnung und Vorklärung werden ein Schritt, der Mahnvorschlag entsteht agentengestützt, Freigabe und Versand fallen zusammen. Die Freigabe ab Stufe 3 bleibt unverändert bei der Teamleitung. Aus sechs Schritten werden vier. Die Annahme, dass Klärfälle im ERP maschinell erkennbar sind, hat der Pilot bestätigt.

**Angewandte Operatoren:** Automatisieren 1×, Zusammenführen 2×, Vereinfachen 1×  
**Status:** reviewed

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Zahlung zuordnen und Differenz vorklären | Zusammenführen | agent (Zahlungszuordnungs-Agent) | Differenz klären, Zahlungseingang zuordnen | Zuordnung und Vorklärung arbeiten auf denselben Daten. Die Trennung kostet heute zwölf Stunden Liegezeit für eine Übergabe innerhalb derselben Rolle. · Human Gate: Konfidenz unter 0,9 oder Restdifferenz über 100 EUR |
| 2 | Mahnvorschlag erzeugen | Automatisieren | agent (Mahnlauf-Agent) | Mahnstufe bestimmen | Die Stufenlogik ist ein Regelwerk. Der Agent wendet es an und begründet jeden Ausschluss. |
| 3 | Mahnung freigeben und versenden | Zusammenführen | human (Teamleitung Order-to-Cash) | Mahnung freigeben, Mahnung versenden | Freigabe und Versand sind heute zwei Schritte mit fünf Stunden Liegezeit dazwischen. Mit der Freigabe geht die Mahnung raus. · Human Gate: Mahnstufe 3 oder höher |
| 4 | Zahlungsvereinbarung abstimmen | Vereinfachen | human (Forderungsmanager) | Zahlungsvereinbarung abstimmen | Die Verhandlung bleibt menschlich; vorbereitet wird sie mit gerechneten Ratenvarianten und der Zahlungshistorie. |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Mahnungen an zahlende Kunden | 2.5 (geschätzt) | 1 | geschätzt |
| Quote unklarer Zahlungseingänge | 14 (gemessen) | 6 | geschätzt |
| Durchlaufzeit bis geklärte Zuordnung | 36 (gemessen) | 9 | geschätzt |

**Risiken**

- Die Vorklärung durch den Agenten kann eine falsche Erklärung plausibel aussehen lassen. Gegenmaßnahme: Erklärung immer mit Beleg, sonst kein Vorschlag.

### Agent-nativ: Rechnung bis Zahlungseingang — Klärung und Mahnung gleichzeitig

Zuordnung, Klärung und Mahnvorbereitung laufen gleichzeitig statt nacheinander; das Mahnwesen wird ein Schritt. Menschen entscheiden bei der Mahnfreigabe ab Stufe 3 und bei jeder Zahlungsvereinbarung. Aus sechs Schritten werden drei.

**Angewandte Operatoren:** Human Gate 1×, Zusammenführen 1×, Parallelisieren 1×  
**Status:** draft

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Zahlungseingang zuordnen und klären | Zusammenführen | agent (Zahlungszuordnungs-Agent) | Differenz klären, Zahlungseingang zuordnen | Zuordnung und Klärung sind derselbe Vorgang, sobald die Erklärung belegt werden kann. Übrig bleibt der Fall, in dem der Kunde widerspricht — und genau der gehört zu einem Menschen. · Human Gate: Restdifferenz über 500 EUR oder Kunde widerspricht |
| 2 | Mahnung erzeugen, freigeben und versenden | Parallelisieren | agent (Mahnlauf-Agent) | Mahnstufe bestimmen, Mahnung freigeben, Mahnung versenden | Das Mahnwesen wartet heute auf die Klärung, obwohl es nur die unstrittigen Posten betrifft. Beides kann gleichzeitig laufen; die Freigabe ab Stufe 3 bleibt als Kontrolle unverändert bestehen. · Human Gate: Mahnstufe 3 oder höher |
| 3 | Zahlungsvereinbarung abstimmen | Human Gate | human (Forderungsmanager) | Zahlungsvereinbarung abstimmen | Eine Zahlungsvereinbarung ist eine Zusage mit rechtlicher Wirkung und Ermessensspielraum. Sie bleibt vollständig beim Menschen, auch in einem agent-nativen Prozess. · Human Gate: immer; Stundung über 90 Tage zusätzlich durch die Teamleitung |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Mahnungen an zahlende Kunden | 2.5 (geschätzt) | 0.5 | geschätzt |
| Quote unklarer Zahlungseingänge | 14 (gemessen) | 4 | geschätzt |
| Durchlaufzeit bis geklärte Zuordnung | 36 (gemessen) | 4 | geschätzt |

**Offene Annahmen**

- Parallele Mahnung und Klärung setzt voraus, dass strittige Posten sofort markiert werden. Heute geschieht das erst bei der Klärung.

**Risiken**

- Wenn ein strittiger Posten nicht rechtzeitig markiert ist, geht eine Mahnung an einen Kunden, der zu Recht nicht gezahlt hat. Gegenmaßnahme: Mahnlauf schließt jeden Posten aus, der in den letzten 14 Tagen berührt wurde.

## Auftrag bis Rechnung

**Ergebnis:** Auftrag korrekt abgerechnet  
**Menge:** 18000 Fälle/Jahr

| Kennzahl | Ist | Konservativ | Ausgewogen | Agent-nativ |
|---|---|---|---|---|
| Schritte | 10 | 10 (+0) | 6 (+4) | 4 (+6) |
| Human Touchpoints | 10 | 9 (+1) | 3 (+7) | 3 (+7) |
| Übergaben | 9 | 6 (+3) | 5 (+4) | 3 (+6) |
| Bearbeitungszeit (min) | 121 | 75 (+46) | 20 (+101) | 10 (+111) |
| Wartezeit (min) | 2430 | 1720 (+710) | 325 (+2105) | 90 (+2340) |
| Durchlaufzeit (h) | 42.5 | 29.9 (+12.6) | 5.8 (+36.7) | 1.5 (+41) |
| Nacharbeit (%) | 8.9 | 6.3 (+2.6) | 4.3 (+4.6) | 3.3 (+5.6) |
| automatisierte Schritte | 0 | 2 (+2) | 4 (+4) | 3 (+3) |
| Menschliche Arbeit (VZÄ) | 22.7 | 13.9 | 2.4 | 1.5 |

Der Wert in Klammern ist die Verbesserung gegenüber dem Ist (positiv heißt immer besser, unabhängig von der Richtung der Kennzahl).

### Konservativ: Auftrag bis Rechnung — KI assistiert, Kontrollen unverändert

Der Ablauf bleibt wie er ist. Erfassung und Versand übernimmt ein Agent, alle übrigen Schritte werden durch bessere Vorbereitung kürzer. Jede heutige Kontrolle bleibt unverändert bestehen. Das ist die Untergrenze und der Vergleichsmaßstab für die beiden anderen Szenarien.

**Angewandte Operatoren:** Automatisieren 2×, Human Gate 2×, Vereinfachen 6×  
**Status:** reviewed

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Auftrag erfassen | Automatisieren | agent (Auftragserfassungs-Agent) | Auftrag erfassen | Die Übernahme aus Bestelldokumenten ist strukturiert und gut belegt; Fehler fallen in der anschließenden Prüfung ohnehin auf. · Human Gate: Konfidenz unter 0,9 oder kein gültiger Rahmenvertrag |
| 2 | Auftragsdaten prüfen | Vereinfachen | human (Auftragssachbearbeiter) | Auftragsdaten prüfen | Der Agent liefert eine Abweichungsliste mit; geprüft wird nur noch, was abweicht, statt jede Position. |
| 3 | Auftrag in Nachverfolgungsliste eintragen | Vereinfachen | human (Auftragssachbearbeiter) | Auftrag in Nachverfolgungsliste eintragen | Die Liste bleibt in diesem Szenario bestehen, wird aber aus dem ERP vorbefüllt statt von Hand geführt. |
| 4 | Bonität prüfen | Vereinfachen | human (Kreditprüfer) | Bonität prüfen | Die Auskunft wird automatisch angefragt und mit der internen Historie zusammengeführt; der Kreditprüfer bewertet nur noch. |
| 5 | Limit freigeben | Human Gate | human (Teamleitung Order-to-Cash) | Limit freigeben | Die Freigabe über dem Limit bleibt unverändert bei der Teamleitung. In diesem Szenario wird an den Kontrollen nichts geändert. · Human Gate: Auftragswert über dem Kreditlimit |
| 6 | Auftragsbestätigung senden | Vereinfachen | human (Auftragssachbearbeiter) | Auftragsbestätigung senden | Die Bestätigung wird aus dem freigegebenen Auftrag vorbefüllt; der Sachbearbeiter prüft und sendet. |
| 7 | Leistungsnachweis zusammenstellen | Vereinfachen | human (Fakturierungssachbearbeiter) | Leistungsnachweis zusammenstellen | Lieferscheine und Stundennachweise werden vorgeschlagen zugeordnet; offen bleibt nur, was nicht eindeutig ist. |
| 8 | Rechnung erstellen | Vereinfachen | human (Fakturierungssachbearbeiter) | Rechnung erstellen | Positionen und Steuerkennzeichen werden aus der Abrechnungsgrundlage vorgeschlagen. |
| 9 | Rechnung freigeben | Human Gate | human (Fakturierungssachbearbeiter) | Rechnung freigeben | Die Rechnung ist der Moment, in dem sich das Unternehmen festlegt. Das Vier-Augen-Prinzip bleibt unverändert. · Human Gate: immer, durch eine zweite Person |
| 10 | Rechnung versenden und archivieren | Automatisieren | agent (Fakturierungs-Agent) | Rechnung versenden und archivieren | Versand und Archivierung sind technische Schritte mit klaren Regeln; die Archivierungspflicht bleibt als Kontrolle bestehen. |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Rechnungskorrekturquote | 9 (gemessen) | 7 | geschätzt |
| Aufträge über Kreditlimit ohne Freigabe | 1.5 (geschätzt) | 1.5 | geschätzt |
| Durchlaufzeit Auftrag bis Rechnung | 42 (gemessen) | 30 | geschätzt |

**Offene Annahmen**

- Der Archivzugang über eine Schnittstelle ist heute nicht vorhanden und muss geschaffen werden.

**Risiken**

- Die Zeitgewinne entstehen überwiegend aus kürzerer Bearbeitung, nicht aus kürzerer Liegezeit. Wenn die Liegezeiten bleiben, bleibt auch die Durchlaufzeit weitgehend.

### Ausgewogen: Auftrag bis Rechnung — Übergaben entfallen, Menschen entscheiden Ausnahmen

Erfassung und Prüfung werden zu einem Schritt, die Nachverfolgungsliste entfällt, Bonität und Bestätigung laufen agentengestützt. Die Kreditfreigabe wandert in der Regelarbeit vom Teamleiter zum Kreditprüfer, die Rechnungsfreigabe bleibt im Vier-Augen-Prinzip. Aus zehn Schritten werden sechs, aus neun Übergaben fünf.

**Angewandte Operatoren:** Automatisieren 2×, Eliminieren 1×, Human Gate 1×, Zusammenführen 3×  
**Status:** reviewed

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Auftrag erfassen und prüfen | Zusammenführen | agent (Auftragserfassungs-Agent) | Auftrag erfassen, Auftragsdaten prüfen | Erfassung und Vertragsabgleich arbeiten auf denselben Daten. Getrennt gehalten kosten sie vier Stunden Liegezeit für eine Übergabe an dieselbe Rolle. · Human Gate: Konfidenz unter 0,9, kein gültiger Rahmenvertrag oder Preisabweichung über 2 Prozent |
| 2 | Bonität bewerten | Automatisieren | agent (Bonitäts-Agent) | Bonität prüfen | Auskunft einholen und mit der Zahlungshistorie verrechnen ist eine Datenzusammenführung. Der Agent schlägt vor, er entscheidet nicht. |
| 3 | Limit bestätigen | Human Gate | human (Kreditprüfer) | Limit freigeben | Die Kontrolle bleibt vollständig erhalten, rückt aber näher an die Fachkenntnis. Die Teamleitung entscheidet nur noch die großen Fälle statt jeden. · Human Gate: immer; Auftragswert über 50.000 EUR zusätzlich durch die Teamleitung |
| 4 | Auftragsbestätigung senden | Automatisieren | agent (Auftragserfassungs-Agent) | Auftragsbestätigung senden | Aus einem freigegebenen Auftrag entsteht die Bestätigung regelbasiert; ein menschlicher Zwischenschritt fügt nichts hinzu. |
| 5 | Rechnung vorbereiten | Zusammenführen | agent (Fakturierungs-Agent) | Rechnung erstellen, Leistungsnachweis zusammenstellen | Nachweise zusammenstellen und daraus die Rechnung erzeugen ist ein Arbeitsgang, der heute nur getrennt ist, weil er in zwei Postkörben liegt. Hier entsteht die meiste Nacharbeit. |
| 6 | Rechnung freigeben und versenden | Zusammenführen | human (Fakturierungssachbearbeiter) | Rechnung versenden und archivieren, Rechnung freigeben | Freigabe und Versand sind heute zwei Schritte mit vier Stunden Liegezeit dazwischen. Mit der Freigabe löst derselbe Klick Versand und Archivierung aus; das Vier-Augen-Prinzip bleibt unverändert. · Human Gate: immer, durch eine zweite Person |

**Gestrichene Schritte**

| Ist-Schritt | Begründung | Ersatz |
|---|---|---|
| Auftrag in Nachverfolgungsliste eintragen | Die Liste existiert nur, weil das ERP den Bearbeitungsstand über Bereichsgrenzen hinweg nicht ausweist. Der Fallzustand liegt künftig im ERP; die Liste bildet ihn doppelt und veraltet zwischen zwei Pflegeläufen. | Statusauswertung im ERP, täglich automatisch an die Teamleitung |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Rechnungskorrekturquote | 9 (gemessen) | 5 | geschätzt |
| Aufträge über Kreditlimit ohne Freigabe | 1.5 (geschätzt) | 0.5 | geschätzt |
| Durchlaufzeit Auftrag bis Rechnung | 42 (gemessen) | 6 | geschätzt |

**Offene Annahmen**

- Die Kreditvollmacht bis 50.000 EUR für Kreditprüfer ist heute nicht geregelt.
- Der Archivzugang über eine Schnittstelle muss geschaffen werden.

**Risiken**

- Wenn der Agent Abweichungen übersieht, fehlt die getrennte Prüfung als zweites Netz. Gegenmaßnahme: Konfidenzschwelle 0,9 und Stichprobe 10 Prozent in den ersten drei Monaten.

### Agent-nativ: Auftrag bis Rechnung — vom Ergebnis her gebaut

Der Prozess wird vom gewünschten Ergebnis aus neu geschnitten: Auftragsannahme und Bonitätsbewertung laufen gleichzeitig statt nacheinander, die Rechnung entsteht aus demselben Datenbestand, und Menschen greifen an genau zwei Stellen ein — beim Kreditlimit über der Vollmachtsgrenze und bei der Rechnungsfreigabe. Aus zehn Schritten werden vier.

**Angewandte Operatoren:** Eliminieren 1×, Zusammenführen 3×, Parallelisieren 1×  
**Status:** draft

| # | Soll-Schritt | Operator | Wer | Aus Ist-Schritt | Begründung |
|---|---|---|---|---|---|
| 1 | Auftrag aufnehmen, prüfen und bestätigen | Zusammenführen | agent (Auftragserfassungs-Agent) | Auftrag erfassen, Auftragsdaten prüfen, Auftragsbestätigung senden | Erfassen, prüfen und bestätigen arbeiten auf demselben Datensatz und trennen sich heute nur durch Postkörbe. Zusammengelegt entfallen zwei Übergaben und drei Wartestrecken. · Human Gate: kein gültiger Rahmenvertrag oder Preisabweichung über 2 Prozent |
| 2 | Bonität und Limit bestimmen | Parallelisieren | agent (Bonitäts-Agent) | Bonität prüfen, Limit freigeben | Die Bonität hängt am Kunden, nicht am Auftragsinhalt. Sie kann gleichzeitig mit der Auftragsaufnahme laufen statt danach — das spart die gesamte Wartestrecke von acht Stunden. · Human Gate: Limitvorschlag über 50.000 EUR oder Konfidenz unter 0,85 |
| 3 | Rechnung erzeugen und prüfen | Zusammenführen | agent (Fakturierungs-Agent) | Rechnung erstellen, Leistungsnachweis zusammenstellen | Nachweise, Rechnung und Prüfbefund entstehen aus demselben Datenbestand in einem Lauf. Getrennt gehalten kosten sie dreizehn Stunden Liegezeit. |
| 4 | Rechnung freigeben und versenden | Zusammenführen | human (Fakturierungssachbearbeiter) | Rechnung versenden und archivieren, Rechnung freigeben | Hier legt sich das Unternehmen gegenüber dem Kunden fest, und der Schritt ist nicht umkehrbar. Diese Verantwortungsgrenze bleibt auch in einem agent-nativen Prozess beim Menschen. · Human Gate: immer, durch eine zweite Person |

**Gestrichene Schritte**

| Ist-Schritt | Begründung | Ersatz |
|---|---|---|
| Auftrag in Nachverfolgungsliste eintragen | Die Liste bildet einen Zustand ab, den der Prozess künftig selbst führt. Sie hat keinen Empfänger außerhalb des Teams. | Fallzustand im ERP, Auswertung auf Abruf |

**Zugesagte Kennzahlen**

| Kennzahl | Ausgangswert | Zielwert | Belastbarkeit |
|---|---|---|---|
| Rechnungskorrekturquote | 9 (gemessen) | 4 | geschätzt |
| Aufträge über Kreditlimit ohne Freigabe | 1.5 (geschätzt) | 0.3 | geschätzt |
| Durchlaufzeit Auftrag bis Rechnung | 42 (gemessen) | 3 | geschätzt |

**Offene Annahmen**

- Bonitätsanfrage vor abgeschlossener Auftragsprüfung ist vertraglich mit der Auskunftei zu klären.
- Die Kreditvollmacht bis 50.000 EUR für Kreditprüfer ist heute nicht geregelt.
- Der Fallzustand muss im ERP über Bereichsgrenzen hinweg sichtbar sein; heute ist er es nicht.

**Risiken**

- Parallelität erzeugt Fälle, in denen die Bonität negativ ausfällt, nachdem der Auftrag bereits bestätigt wurde. Gegenmaßnahme: Bestätigung mit Vorbehalt bei Neukunden ohne Limit.
- Vier von zehn Schritten fallen weg — der Wissensaufbau der Sachbearbeitung über diese Schritte fällt mit weg. Gegenmaßnahme: Ausnahmebearbeitung bewusst rotieren.

