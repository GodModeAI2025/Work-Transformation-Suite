---
type: "agent"
name: "Order-to-Cash-Orchestrator"
pattern: "workflow-orchestration"
specificity: "domain"
status: "proposed"
complexity: 4
existing_system: null
prerequisites:
  - "Alle koordinierten Agenten im Pilotbetrieb"
  - "Gemeinsamer Fallzustand im ERP"
orchestrates:
  - "Auftragserfassungs-Agent"
  - "Bonitäts-Agent"
  - "Fakturierungs-Agent"
  - "Zahlungszuordnungs-Agent"
  - "Mahnlauf-Agent"
tasks: []
---

## Fähigkeit

Führt die Spezialagenten entlang des Prozesses zusammen: übergibt Ergebnisse, hält den Fallzustand, entscheidet, wann ein Mensch gebraucht wird, und stellt sicher, dass kein Fall liegen bleibt.

## Aufsicht

Eskaliert jeden Fall, der länger als die vereinbarte Frist ohne Fortschritt ist, an die Teamleitung

## Vertrag

```json
{
  "audit_events": [
    "case.routed (Fall, Von, Nach, Grund)",
    "case.stalled (Fall, Dauer)"
  ],
  "capability_profile": "Zustandsbehaftete Ablaufsteuerung über mehrere Werkzeuge; Konflikterkennung zwischen Teilergebnissen.",
  "decision_scope": "execute_reversible",
  "fallback": "Fall an die zuständige Rolle übergeben und als 'manuell weiterführen' kennzeichnen.",
  "human_checkpoint": {
    "role_id": "ro_e70a9399feff",
    "sla_minutes": 480,
    "when": "Fall ohne Fortschritt über der vereinbarten Frist, oder widersprüchliche Ergebnisse zweier Agenten"
  },
  "inputs": [
    "Fallzustand",
    "Ergebnis des vorangegangenen Schrittes"
  ],
  "outputs": [
    "nächster Schritt",
    "Zuweisung an Agent oder Mensch",
    "Fristüberwachung"
  ],
  "read_permissions": [
    "ERP: Fallzustand aller Order-to-Cash-Vorgänge"
  ],
  "timeout_seconds": 30,
  "tools": [
    "erp.read_case_state",
    "agent.invoke"
  ],
  "trigger": "Zustandswechsel eines Falls im Order-to-Cash-Prozess",
  "write_permissions": []
}
```
