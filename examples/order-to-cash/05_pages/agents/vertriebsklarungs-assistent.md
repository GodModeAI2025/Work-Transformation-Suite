---
type: "agent"
name: "Vertriebsklärungs-Assistent"
pattern: "drafting-assistant"
specificity: "domain"
status: "planned"
complexity: 2
existing_system: null
prerequisites:
  - "Lesezugriff ERP"
orchestrates: []
tasks:
  - "Auftragssachbearbeiter > Rückfragen mit Vertrieb klären"
---

## Fähigkeit

Bereitet Rückfragen an den Vertrieb vor: fasst die Abweichung zusammen, schlägt eine Lösung vor und entwirft die Nachricht.

## Aufsicht

Jede Nachricht wird vom Sachbearbeiter vor dem Versand freigegeben

## Vertrag

```json
{
  "audit_events": [
    "draft.created (Auftrag, Länge, Profilversion)"
  ],
  "capability_profile": "Deutschsprachige Zusammenfassung und Entwurfserstellung aus strukturiertem Kontext.",
  "decision_scope": "recommend",
  "fallback": "Kein Entwurf; der Sachbearbeiter schreibt wie bisher selbst.",
  "inputs": [
    "Auftragsabweichung",
    "Vertragsauszug",
    "Historie ähnlicher Fälle"
  ],
  "outputs": [
    "Zusammenfassung",
    "Lösungsvorschlag",
    "Nachrichtenentwurf"
  ],
  "read_permissions": [
    "ERP: Aufträge, Rahmenverträge"
  ],
  "timeout_seconds": 60,
  "tools": [
    "erp.read_order",
    "erp.read_contract"
  ],
  "trigger": "Sachbearbeiter markiert eine Abweichung als klärungsbedürftig",
  "write_permissions": []
}
```
