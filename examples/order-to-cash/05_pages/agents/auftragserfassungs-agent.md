---
type: "agent"
name: "Auftragserfassungs-Agent"
pattern: "document-extraction"
specificity: "proprietary"
status: "pilot"
complexity: 4
existing_system: null
prerequisites:
  - "Schreibzugriff ERP über Schnittstelle"
  - "Freigabe Betriebsrat"
  - "Digitalisierte Rahmenverträge"
orchestrates: []
tasks:
  - "Auftragssachbearbeiter > Auftrag aus Bestellung erfassen"
  - "Auftragssachbearbeiter > Auftragsbestätigung versenden"
  - "Auftragssachbearbeiter > Auftragsdaten gegen Rahmenvertrag prüfen"
  - "Auftragssachbearbeiter > Auftragsänderungen einpflegen"
---

## Fähigkeit

Liest Bestellungen aus E-Mail, Portal und EDI, legt den Auftrag im ERP an, gleicht Preise und Konditionen gegen den Rahmenvertrag ab und erzeugt die Auftragsbestätigung.

## Aufsicht

Stichprobe 10 Prozent durch die Auftragssachbearbeitung; alle Aufträge ohne Rahmenvertrag im Gate

## Vertrag

```json
{
  "audit_events": [
    "order.created (Auftrag, Quelle, Konfidenz, Profilversion)",
    "order.escalated (Auftrag, Grund)",
    "order.failed (Quelle, Fehlerart)"
  ],
  "capability_profile": "Strukturierte Extraktion aus PDF, E-Mail und EDI; Abgleich gegen tabellarische Stammdaten; kalibrierte Konfidenz je Position.",
  "confidence_threshold": 0.9,
  "cost_ceiling": {
    "amount": 1200,
    "currency": "EUR",
    "period": "monat"
  },
  "decision_scope": "execute_reversible",
  "evaluation_set": {
    "cases": 320,
    "name": "auftragserfassung-eval-v1",
    "source": "Stichprobe aus 2025, von zwei Sachbearbeitern unabhängig geprüft",
    "thresholds": "Positionsgenauigkeit ≥ 0,97; keine stillen Preisabweichungen"
  },
  "fallback": "Bestellung unverändert in die manuelle Warteschlange stellen und als 'nicht automatisch erfassbar' kennzeichnen; kein Teilauftrag im ERP.",
  "human_checkpoint": {
    "role_id": "ro_5d42f48ee610",
    "sla_minutes": 240,
    "when": "Konfidenz unter 0,9, kein gültiger Rahmenvertrag, oder Abweichung im Preis über 2 Prozent"
  },
  "idempotency_key": "kundennummer + bestellnummer + dokument_hash",
  "inputs": [
    "Bestelldokument",
    "Kundennummer",
    "Eingangskanal"
  ],
  "outputs": [
    "Auftragskopf",
    "Auftragspositionen",
    "Abweichungsliste",
    "Konfidenz"
  ],
  "read_permissions": [
    "ERP: Kundenstammdaten, Rahmenverträge, Preislisten"
  ],
  "retry_policy": "zweimal mit 10 und 60 Sekunden Abstand, danach Fallback",
  "service_level": "p95 unter 90 Sekunden, Verfügbarkeit 99 Prozent in der Servicezeit",
  "timeout_seconds": 120,
  "tools": [
    "erp.create_order",
    "erp.read_contract",
    "erp.update_order",
    "mail.send_confirmation"
  ],
  "trigger": "Neue Bestellung im Eingangskanal (E-Mail-Postfach, Portal, EDI)",
  "write_permissions": [
    "ERP: Auftragskopf und -positionen",
    "ERP: Auftragsbestätigung"
  ]
}
```
