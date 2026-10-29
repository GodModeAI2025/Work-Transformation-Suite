---
type: "agent"
name: "Analyse- und Berichtscopilot"
pattern: "analysis-copilot"
specificity: "generic"
status: "proposed"
complexity: 2
existing_system: null
prerequisites:
  - "Lesezugriff auf das Berichtswesen"
orchestrates: []
tasks:
  - "Teamleitung Order-to-Cash > Kennzahlen berichten"
  - "Teamleitung Order-to-Cash > Prozessänderungen abstimmen"
---

## Fähigkeit

Bereitet Durchlaufzeiten, Außenstände und Fehlerquoten auf, erklärt Abweichungen und unterstützt bei der Wirkungsabschätzung von Prozessänderungen.

## Aufsicht

Die Interpretation und jede Aussage nach außen bleibt bei der Teamleitung

## Vertrag

```json
{
  "audit_events": [
    "report.drafted (Periode, Kennzahlen, Profilversion)"
  ],
  "capability_profile": "Erklärende Analyse über Zeitreihen; deutschsprachige Berichtssprache; Wirkungsabschätzung mit ausgewiesenen Annahmen.",
  "decision_scope": "recommend",
  "fallback": "Kein Entwurf; die Teamleitung berichtet wie bisher aus den Rohdaten.",
  "inputs": [
    "Prozesskennzahlen",
    "Vormonatswerte",
    "Änderungsvorhaben"
  ],
  "outputs": [
    "Berichtsentwurf",
    "Abweichungserklärung",
    "Wirkungsabschätzung"
  ],
  "read_permissions": [
    "ERP: aggregierte Prozesskennzahlen"
  ],
  "timeout_seconds": 120,
  "tools": [
    "erp.read_metrics"
  ],
  "trigger": "Monatsabschluss oder Anfrage der Teamleitung",
  "write_permissions": []
}
```
