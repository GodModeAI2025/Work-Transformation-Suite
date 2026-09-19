# Capability Contract

Ein Agent im Graphen hat bis hierher einen Namen, ein Muster, eine Fähigkeitsbeschreibung
und die Aufgaben, die er abdeckt. Das reicht für eine Portfoliodiskussion. Es reicht
nicht, um ihn zu bauen, zu betreiben oder freizugeben.

Der Capability Contract schließt diese Lücke: Er beschreibt, **was den Agenten auslöst,
worauf er zugreifen darf, wie weit seine Entscheidung reicht, was passiert, wenn er
scheitert, und woran man merkt, dass er schlechter geworden ist.**

Er steht als `contract` im jeweiligen Eintrag von `20_graph/agents.json` und wird von
`compute_coverage.py` unverändert in den Graphen übernommen.

## Modellagnostisch

Der Vertrag nennt **keine Modellnamen**. Nicht aus Prinzipienreiterei, sondern weil
Modelle schneller wechseln als Prozesse: Ein Vertrag, der ein bestimmtes Modell festlegt,
zwingt bei jedem Wechsel zu einer Prozessänderung und zu einer neuen Freigabe.

Was gebraucht wird, steht stattdessen in `capability_profile` als Anforderung:
„deutschsprachige Klassifikation von Freitext mit mindestens 0,9 Trefferquote auf der
Testmenge", „strukturierte Extraktion aus PDF-Rechnungen", „Werkzeugaufrufe in mehreren
Schritten mit Zwischenergebnis". Der Validator meldet einen Fehler, wenn ein konkreter
Modellname im Vertrag auftaucht.

## Beispiel

```json
{
  "name": "Reklamations-Triage-Agent",
  "pattern": "classification-routing",
  "capability": "Klassifiziert eingehende Reklamationen nach Falltyp und Dringlichkeit, sammelt Vertrags- und Abrechnungsdaten zum Fall und legt einen vorbereiteten Vorgang im CRM an.",
  "specificity": "domain",
  "status": "pilot",
  "complexity": 3,
  "oversight": "Stichprobe 10 % durch Servicemitarbeiter, alle Fälle unter Konfidenz 0,85 im Gate",
  "prerequisites": ["Lesezugriff Abrechnungssystem über Schnittstelle", "Freigabe Betriebsrat"],
  "task_ids": ["ta_…", "ta_…"],
  "contract": {
    "trigger": "Neue Reklamation im CRM mit Status 'eingegangen'",
    "inputs": ["Kundennachricht (Freitext)", "Vertragsnummer", "Eingangskanal"],
    "outputs": ["Falltyp", "Dringlichkeit", "Konfidenz", "Faktenblatt zum Fall"],
    "tools": ["crm.read_case", "crm.write_case_fields", "billing.read_contract"],
    "read_permissions": ["CRM: Fälle, Kundenstammdaten", "Abrechnungssystem: Vertragsdaten (lesend)"],
    "write_permissions": ["CRM: Felder Falltyp, Dringlichkeit, Faktenblatt"],
    "system_ids": ["sy_…", "sy_…"],
    "decision_scope": "execute_reversible",
    "confidence_threshold": 0.85,
    "human_checkpoint": {
      "when": "Konfidenz unter 0,85 oder Falltyp 'Härtefall'",
      "role_id": "ro_…",
      "sla_minutes": 120
    },
    "fallback": "Fall unverändert in die allgemeine Warteschlange stellen und als 'ungeklärt' markieren; kein Teilergebnis schreiben.",
    "timeout_seconds": 60,
    "retry_policy": "zweimal mit 5 und 25 Sekunden Abstand, danach Fallback",
    "idempotency_key": "case_id + input_hash",
    "audit_events": [
      "triage.classified (Fall, Typ, Konfidenz, Version des Fähigkeitsprofils)",
      "triage.escalated (Fall, Grund)",
      "triage.failed (Fall, Fehlerart)"
    ],
    "service_level": "p95 unter 30 Sekunden, Verfügbarkeit 99 % in der Servicezeit",
    "evaluation_set": {
      "name": "reklamation-triage-eval-v1",
      "cases": 240,
      "source": "Stichprobe aus 2025, von zwei Sachbearbeitern unabhängig gelabelt",
      "thresholds": "Trefferquote ≥ 0,90; Fehlklassifikationen in Kategorie 'Härtefall' = 0"
    },
    "cost_ceiling": {"amount": 800, "currency": "EUR", "period": "monat"},
    "capability_profile": "Deutschsprachige Klassifikation von Freitext in 12 Klassen mit kalibrierter Konfidenz; strukturierte Extraktion aus Vertragsdaten; mehrstufige Werkzeugaufrufe."
  }
}
```

## Feldreferenz

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `trigger` | ja | Das Ereignis, das den Agenten startet. Ein Zeitplan ist auch ein Auslöser |
| `inputs` | ja | Was er bekommt |
| `outputs` | ja | Was er zurückgibt |
| `tools` | empfohlen | Aufrufbare Funktionen, technisch benannt |
| `read_permissions` | empfohlen | Worauf er lesend zugreift, systemgenau |
| `write_permissions` | nach Lage | Worauf er schreibend zugreift. Löst zusätzliche Pflichten aus |
| `system_ids` | empfohlen | IDs aus `systems` im Graphen |
| `decision_scope` | ja | `recommend`, `execute_reversible`, `execute_irreversible` |
| `confidence_threshold` | nach Lage | 0..1. Unterhalb greift der Kontrollpunkt |
| `human_checkpoint` | nach Lage | `{"when": …, "role_id": …, "sla_minutes": …}` |
| `fallback` | ja | Was passiert, wenn er nicht kann. Muss einen definierten Zustand hinterlassen |
| `timeout_seconds` | empfohlen | Zeitgrenze je Lauf |
| `retry_policy` | Pflicht bei Schreibrechten | Wie oft, in welchen Abständen |
| `idempotency_key` | Pflicht bei Schreibrechten | Woran ein Wiederholungslauf denselben Fall erkennt |
| `audit_events` | Pflicht bei Schreibrechten | Was protokolliert wird, mit den Feldern |
| `service_level` | Pflicht ab Status `pilot` | Latenz und Verfügbarkeit |
| `evaluation_set` | Pflicht ab Status `pilot` | Testmenge, Herkunft, Schwellen |
| `cost_ceiling` | empfohlen ab `pilot` | `{"amount": …, "currency": …, "period": …}` |
| `capability_profile` | empfohlen | Die gebrauchte Fähigkeit, anbieterneutral |

## Regeln, die der Validator durchsetzt

Alle drei stammen aus derselben Erfahrung: Agentenprojekte scheitern nicht am Modell,
sondern am Betrieb.

| Bedingung | Regel | Warum |
|---|---|---|
| `write_permissions` gesetzt | `audit_events` und `idempotency_key` Pflicht | Eine Schreibaktion ohne Spur ist nicht prüfbar; ein Wiederholungslauf ohne Schlüssel schreibt doppelt |
| `decision_scope: execute_irreversible` | `human_checkpoint` Pflicht | Was sich nicht zurücknehmen lässt, entscheidet kein Agent allein |
| `status` ist `pilot` oder `live` | `evaluation_set` Pflicht, `service_level` und `cost_ceiling` empfohlen | Ohne Testmenge merkt niemand, wenn die Qualität nachlässt |
| Vertrag nennt einen Modellnamen | Fehler | Der Vertrag beschreibt die Fähigkeit, nicht das Produkt |

`validate_contracts.py` prüft zusätzlich gegen den Prozess, in dem der Agent läuft:

- Reicht `decision_scope` für die Schritte, die er ausführt? (Ein Schritt mit
  `execute_irreversible` und ein Vertrag mit `recommend` ist ein Fehler.)
- Soll er in ein System schreiben, das als `api_available: false` erfasst ist?
- Tragen seine Schritte Kontrollen, die der Vertrag nicht abbildet?
- Verweist ein Kontrollpunkt auf eine Konfidenz, ohne dass eine Schwelle festgelegt ist?

## Orchestrierung

Ein Agent kann andere koordinieren: `"orchestrates": ["Name eines anderen Agenten", …]`.
Der Orchestrator sollte dann **keine eigenen Schreibrechte** haben — sonst ist im
Fehlerfall nicht mehr feststellbar, wer geschrieben hat. Das Schreiben gehört zu den
Spezialagenten, die Koordination zum Orchestrator.

## Ein Prozessschritt, mehrere Fähigkeiten

Im Redesignmodus kann ein Prozessschritt menschliche, regelbasierte, systemische und
agentische Fähigkeiten kombinieren, und mehrere Agenten können sich eine Aufgabe teilen.
`compute_coverage.py --shared-tasks` erlaubt das, weist die Überschneidungen je Agent aus
(`overlap_task_ids`) und meldet am Ende eine bereinigte Gesamtabdeckung. Ohne den Schalter
bleibt es bei genau einem Agenten je nicht-manueller Aufgabe — für eine Opportunity Map
die ehrlichere Darstellung, weil sich Abdeckungen dann addieren lassen.

## Export

```
python3 <skill>/scripts/validate_contracts.py --project ./projekte/<name>
python3 <skill>/scripts/export_contracts.py --project ./projekte/<name> [--status pilot,live]
```

Schreibt `40_output/contracts_vNNN.json` für Plattform- und Architekturteams und
`contracts_vNNN.md` für Freigabe, Betriebsrat und Revision.
