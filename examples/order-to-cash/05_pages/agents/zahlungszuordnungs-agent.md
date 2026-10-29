---
type: "agent"
name: "Zahlungszuordnungs-Agent"
pattern: "data-reconciliation"
specificity: "proprietary"
status: "pilot"
complexity: 3
existing_system: null
prerequisites:
  - "Schreibzugriff ERP offene Posten"
  - "Strukturierter Kontoauszugsimport"
orchestrates: []
tasks:
  - "Forderungsmanager > Offene Posten klären"
  - "Forderungsmanager > Zahlungseingänge zuordnen"
---

## Fähigkeit

Ordnet Zahlungseingänge aus dem Kontoauszug den offenen Posten zu, teilt Teilzahlungen auf und schlägt für Differenzen eine Erklärung vor.

## Aufsicht

Zuordnungen unter Konfidenz 0,9 und alle Differenzen über 100 EUR gehen an das Forderungsmanagement

## Vertrag

```json
{
  "audit_events": [
    "payment.matched (Position, Posten, Konfidenz, Profilversion)",
    "payment.unmatched (Position, Grund)",
    "payment.failed (Auszug, Fehlerart)"
  ],
  "capability_profile": "Fuzzy-Abgleich zwischen Freitext-Verwendungszweck und strukturierten Posten; Aufteilung von Teilbeträgen; kalibrierte Konfidenz.",
  "confidence_threshold": 0.9,
  "cost_ceiling": {
    "amount": 700,
    "currency": "EUR",
    "period": "monat"
  },
  "decision_scope": "execute_reversible",
  "evaluation_set": {
    "cases": 600,
    "name": "zahlungszuordnung-eval-v1",
    "source": "Kontoauszüge 2025 mit nachträglich korrigierter Zuordnung als Wahrheit",
    "thresholds": "Trefferquote ≥ 0,95; Fehlzuordnungen ≤ 0,2 Prozent"
  },
  "fallback": "Position unzugeordnet lassen und als 'maschinell nicht zuordenbar' kennzeichnen; keine Teilzuordnung.",
  "human_checkpoint": {
    "role_id": "ro_409de267032f",
    "sla_minutes": 240,
    "when": "Konfidenz unter 0,9 oder Restdifferenz über 100 EUR"
  },
  "idempotency_key": "kontoauszug_id + positionsnummer",
  "inputs": [
    "Kontoauszugspositionen",
    "offene Posten",
    "Verwendungszweck"
  ],
  "outputs": [
    "Zuordnung",
    "Restdifferenz",
    "Erklärungsvorschlag",
    "Konfidenz"
  ],
  "read_permissions": [
    "ERP: offene Posten, Kundenstammdaten, Kontoauszüge"
  ],
  "retry_policy": "zweimal mit 15 und 60 Sekunden Abstand, danach Fallback",
  "service_level": "p95 unter 30 Sekunden, Verfügbarkeit 99 Prozent",
  "timeout_seconds": 60,
  "tools": [
    "erp.read_open_items",
    "erp.assign_payment",
    "erp.read_customer"
  ],
  "trigger": "Kontoauszug wurde eingelesen",
  "write_permissions": [
    "ERP: Zuordnung von Zahlungseingang zu offenem Posten"
  ]
}
```
