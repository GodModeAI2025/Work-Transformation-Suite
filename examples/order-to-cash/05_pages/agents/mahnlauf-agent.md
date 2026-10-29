---
type: "agent"
name: "Mahnlauf-Agent"
pattern: "standard-correspondence"
specificity: "domain"
status: "planned"
complexity: 3
existing_system: null
prerequisites:
  - "Abgestimmte Ausschlussregeln mit dem Vertrieb"
orchestrates: []
tasks:
  - "Forderungsmanager > Mahnlauf vorbereiten und prüfen"
---

## Fähigkeit

Erzeugt den Mahnvorschlag, schließt Kunden mit laufender Klärung oder Zahlungsvereinbarung aus und formuliert die Mahnschreiben.

## Aufsicht

Ab Mahnstufe 3 gibt die Teamleitung jeden Fall einzeln frei

## Vertrag

```json
{
  "audit_events": [
    "dunning.proposed (Kunde, Stufe, Betrag, Profilversion)",
    "dunning.excluded (Kunde, Grund)",
    "dunning.failed (Lauf, Fehlerart)"
  ],
  "capability_profile": "Regelbasierte Auswahl aus strukturierten Posten; deutschsprachige Korrespondenz in vorgegebener Tonalität.",
  "confidence_threshold": 0.9,
  "decision_scope": "execute_reversible",
  "fallback": "Standard-Mahnvorschlag des ERP ohne Ausschlüsse erzeugen und als ungeprüft kennzeichnen.",
  "human_checkpoint": {
    "role_id": "ro_e70a9399feff",
    "sla_minutes": 1440,
    "when": "Mahnstufe 3 oder höher, oder Kunde mit laufender Klärung"
  },
  "idempotency_key": "mahnlauf_datum + kundennummer",
  "inputs": [
    "überfällige offene Posten",
    "Klärfälle",
    "Zahlungsvereinbarungen"
  ],
  "outputs": [
    "Mahnvorschlag je Kunde",
    "Ausschlussliste mit Begründung",
    "Mahnschreiben-Entwurf"
  ],
  "read_permissions": [
    "ERP: offene Posten, Klärfälle, Zahlungsvereinbarungen"
  ],
  "retry_policy": "einmal nach 300 Sekunden, danach Fallback",
  "timeout_seconds": 300,
  "tools": [
    "erp.read_open_items",
    "erp.read_agreements",
    "erp.create_dunning_proposal"
  ],
  "trigger": "Wöchentlicher Mahnlauf, montags 06:00",
  "write_permissions": [
    "ERP: Mahnvorschlagsliste (Entwurfsstatus)"
  ]
}
```
