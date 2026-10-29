---
type: "agent"
name: "Fakturierungs-Agent"
pattern: "invoice-verification"
specificity: "proprietary"
status: "pilot"
complexity: 4
existing_system: null
prerequisites:
  - "Schreibzugriff ERP Faktura"
  - "Schnittstelle zum Archiv"
  - "Abgestimmte Prüfregeln mit der Revision"
orchestrates: []
tasks:
  - "Fakturierungssachbearbeiter > Leistungsnachweise zusammenstellen"
  - "Fakturierungssachbearbeiter > Rechnung erstellen"
  - "Fakturierungssachbearbeiter > Rechnung prüfen und freigeben"
  - "Fakturierungssachbearbeiter > Rechnung versenden und archivieren"
---

## Fähigkeit

Stellt Leistungsnachweise zu einer Abrechnungsgrundlage zusammen, erzeugt den Rechnungsentwurf, prüft ihn gegen Auftrag und Vertrag und übernimmt Versand und Archivierung nach Freigabe.

## Aufsicht

Die Freigabe der Rechnung bleibt beim Menschen; der Agent liefert Entwurf und Prüfbefund

## Vertrag

```json
{
  "audit_events": [
    "invoice.drafted (Auftrag, Betrag, Konfidenz, Profilversion)",
    "invoice.sent (Rechnung, Kanal, Freigeber)",
    "invoice.failed (Auftrag, Fehlerart)"
  ],
  "capability_profile": "Zuordnung von Belegen zu Aufträgen; regelbasierte Belegerzeugung; Abgleich gegen Konditionen mit begründetem Prüfbefund.",
  "confidence_threshold": 0.95,
  "cost_ceiling": {
    "amount": 1500,
    "currency": "EUR",
    "period": "monat"
  },
  "decision_scope": "execute_reversible",
  "evaluation_set": {
    "cases": 400,
    "name": "faktura-eval-v1",
    "source": "Rechnungen 2025 inklusive aller Gutschriftfälle",
    "thresholds": "Betragsgenauigkeit 100 Prozent; keine Rechnung ohne Archivbeleg"
  },
  "fallback": "Abrechnungsgrundlage als Liste anhängen, keinen Entwurf erzeugen; die Fakturierung arbeitet wie bisher.",
  "human_checkpoint": {
    "role_id": "ro_1d3cedfc16c3",
    "sla_minutes": 240,
    "when": "immer vor dem Versand (Vier-Augen-Prinzip); zusätzlich bei Konfidenz unter 0,95 oder Abweichung über 5 Prozent"
  },
  "idempotency_key": "auftragsnummer + abrechnungsperiode",
  "inputs": [
    "Auftrag",
    "Lieferscheine",
    "Stundennachweise",
    "Vertragskonditionen"
  ],
  "outputs": [
    "Abrechnungsgrundlage",
    "Rechnungsentwurf",
    "Prüfbefund",
    "Konfidenz"
  ],
  "read_permissions": [
    "ERP: Aufträge, Lieferscheine, Verträge"
  ],
  "retry_policy": "zweimal mit 30 und 120 Sekunden Abstand, danach Fallback",
  "service_level": "p95 unter 120 Sekunden, Verfügbarkeit 99 Prozent in der Servicezeit",
  "timeout_seconds": 180,
  "tools": [
    "erp.read_order",
    "erp.read_delivery",
    "erp.create_invoice_draft",
    "erp.send_invoice",
    "archive.store"
  ],
  "trigger": "Auftrag ist geliefert und abrechnungsreif",
  "write_permissions": [
    "ERP: Rechnungsentwurf",
    "ERP: Versandvermerk nach Freigabe"
  ]
}
```
