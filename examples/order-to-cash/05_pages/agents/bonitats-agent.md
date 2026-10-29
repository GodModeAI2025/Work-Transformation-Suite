---
type: "agent"
name: "Bonitäts-Agent"
pattern: "data-reconciliation"
specificity: "domain"
status: "pilot"
complexity: 3
existing_system: null
prerequisites:
  - "Schnittstelle zur Bonitätsauskunft"
  - "Schreibzugriff ERP Kreditakte"
orchestrates: []
tasks:
  - "Kreditprüfer > Bonitätsauskunft einholen"
  - "Kreditprüfer > Kreditakte dokumentieren"
  - "Kreditprüfer > Kreditlimit festlegen"
  - "Kreditprüfer > Limitüberschreitung eskalieren"
---

## Fähigkeit

Holt die externe Bonitätsauskunft, führt sie mit der internen Zahlungshistorie zusammen, schlägt ein Kreditlimit vor, kennzeichnet Limitüberschreitungen und dokumentiert die Entscheidung revisionssicher.

## Aufsicht

Limitvorschlag wird immer von einem Kreditprüfer bestätigt; Überschreitungen gehen an die Teamleitung

## Vertrag

```json
{
  "audit_events": [
    "credit.assessed (Kunde, Vorschlag, Quelle, Profilversion)",
    "credit.escalated (Kunde, Überschreitung)",
    "credit.failed (Kunde, Fehlerart)"
  ],
  "capability_profile": "Zusammenführung strukturierter externer und interner Kennzahlen; regelbasierte Ableitung mit begründeter Ausgabe.",
  "confidence_threshold": 0.85,
  "cost_ceiling": {
    "amount": 900,
    "currency": "EUR",
    "period": "monat"
  },
  "decision_scope": "recommend",
  "evaluation_set": {
    "cases": 180,
    "name": "bonitaet-eval-v1",
    "source": "Entscheidungen 2024 und 2025 mit bekanntem Zahlungsverlauf",
    "thresholds": "Kein Vorschlag über dem später tatsächlich vergebenen Limit; Trefferquote Risikoklasse ≥ 0,85"
  },
  "fallback": "Bonitätsauskunft als Rohdokument anhängen, kein Limitvorschlag; der Kreditprüfer arbeitet wie bisher.",
  "human_checkpoint": {
    "role_id": "ro_71b3185c093f",
    "sla_minutes": 480,
    "when": "immer vor Wirksamkeit des Limits; zusätzlich bei Konfidenz unter 0,85"
  },
  "idempotency_key": "kundennummer + auskunftsdatum",
  "inputs": [
    "Kundennummer",
    "Auftragswert",
    "interne Zahlungshistorie"
  ],
  "outputs": [
    "Bonitätsurteil",
    "Limitvorschlag",
    "Begründung",
    "Konfidenz"
  ],
  "read_permissions": [
    "Bonitätsauskunft: Unternehmensauskunft",
    "ERP: Zahlungshistorie, offene Posten"
  ],
  "retry_policy": "dreimal mit 30, 120 und 300 Sekunden Abstand, danach Fallback",
  "service_level": "p95 unter 240 Sekunden, Verfügbarkeit 98 Prozent",
  "timeout_seconds": 180,
  "tools": [
    "credit.fetch_report",
    "erp.read_payment_history",
    "erp.write_credit_file"
  ],
  "trigger": "Geprüfter Auftrag ohne gültiges Kreditlimit oder Limit älter als 90 Tage",
  "write_permissions": [
    "ERP: Kreditakte (Vorschlag, Begründung, Quelle)"
  ]
}
```
