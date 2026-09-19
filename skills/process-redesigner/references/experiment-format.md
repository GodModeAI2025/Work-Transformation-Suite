# Experiment-Format

Datei: `20_graph/experiments.json`, eine Liste. Eine Karte je Pilot.
`make_experiments.py` erzeugt beim ersten Lauf eine Vorlage aus jedem geprüften oder
freigegebenen Blueprint.

## Warum nicht überall A/B

Ein A/B-Test braucht drei Dinge: gleichartige Fälle, genug Menge und die Freiheit, einen
Teil der Fälle anders zu behandeln. In Personal- und Finanzprozessen fehlt oft mindestens
eines davon — und bei Entscheidungen mit rechtlicher Wirkung ist Ungleichbehandlung nicht
nur unpraktisch, sondern unzulässig.

Deshalb kennt die Suite vier Designs und schlägt deterministisch eines vor:

| Design | Wann | Was man bekommt | Was man nicht bekommt |
|---|---|---|---|
| `ab_test` | ≥ 2000 Fälle/Jahr, nicht reguliert, keine irreversiblen Entscheidungen | sauberer Vergleich, Störeinflüsse neutralisiert | nichts über seltene Fälle |
| `shadow` | reguliert, irreversible Entscheidungen, oder Szenario agent-nativ | Qualität der Vorschläge ohne jedes Risiko | keine Aussage über Durchlaufzeit im Echtbetrieb |
| `stepped_rollout` | 200–2000 Fälle/Jahr | Wirkung je Stufe, Abbruch jederzeit möglich | Zeit- und Gruppeneffekte sind vermischt |
| `pre_post` | wenig Menge, keine Gruppenbildung möglich | eine Richtung | saubere Kausalität; Saisonalität bleibt drin |

Schattenbetrieb ist der unterschätzte Fall: Der Agent rechnet mit und entscheidet nichts,
seine Vorschläge werden gegen die menschliche Entscheidung gehalten. Das kostet keine
Freigabe, kein Risiko und liefert trotzdem eine belastbare Trefferquote.

## Beispiel

```json
[
  {
    "process": "Kundenreklamation bis Lösung",
    "blueprint_scenario": "balanced",
    "name": "Pilot Triage-Agent Reklamation",
    "hypothesis": "Wenn ein Agent Klassifikation und Faktensammlung übernimmt, sinkt die Durchlaufzeit bis Lösung von 72 auf unter 24 Stunden, ohne dass die Nacharbeitsquote über 20 Prozent steigt.",
    "design": "ab_test",
    "population": "Alle Reklamationen der Sparte Privatkunden, ohne Härtefälle und Inkassofälle",
    "control_group": "Zufällige Hälfte der eingehenden Fälle, Zuteilung über die Fallnummer",
    "duration_days": 42,
    "sample_size": 2400,
    "primary_metric": "Durchlaufzeit bis Lösung",
    "target_value": 24,
    "guardrail_metrics": [
      {"metric": "Nacharbeitsquote", "limit": 20, "direction": "max"},
      {"metric": "Fehlklassifikationsquote", "limit": 5, "direction": "max"},
      {"metric": "Kundenzufriedenheit Reklamation", "limit": 4.0, "direction": "min"}
    ],
    "stop_rules": [
      "Nacharbeitsquote über zwei aufeinanderfolgende Wochen über 20 Prozent: anhalten",
      "Eine Fehlklassifikation mit Kundenschaden: sofort anhalten, Ursache klären",
      "Mehr als 5 Prozent der Fälle brauchen manuelle Nachsteuerung außerhalb des Gates"
    ],
    "rollback": "Zuteilung auf 100 Prozent Ist-Prozess stellen; laufende Pilotfälle werden vom Team manuell zu Ende geführt. Wirkt innerhalb einer Stunde.",
    "owner_role": "Teamleitung Kundenservice",
    "status": "draft",
    "results": []
  }
]
```

## Feldreferenz

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `process` | ja | Name oder ID eines Prozesses |
| `blueprint_scenario` | empfohlen | Welches Szenario pilotiert wird |
| `name` | empfohlen | Sprechender Titel |
| `hypothesis` | ja | Ein Satz der Form „Wenn wir X tun, dann ändert sich Y von A auf B, ohne dass Z leidet" |
| `design` | ja | `ab_test`, `shadow`, `stepped_rollout`, `pre_post` |
| `population` | empfohlen | Welche Fälle dabei sind — und welche ausdrücklich nicht |
| `control_group` | Pflicht bei `ab_test` | Wie die Vergleichsgruppe entsteht |
| `comparison_period` | Pflicht bei `pre_post` | Gegen welchen Zeitraum verglichen wird |
| `duration_days` | ja | Laufzeit. Mindestens vier Wochen, sonst dominieren Wocheneffekte |
| `sample_size` | ja | Fälle, die das Design berührt |
| `primary_metric` | ja | Genau eine. Mehrere Primärmetriken heißt: keine |
| `target_value` | empfohlen | Zielwert der Primärmetrik |
| `guardrail_metrics` | ja | Mindestens eine Qualitäts- und eine Risikokennzahl |
| `stop_rules` | ja | Überprüfbare Abbruchkriterien |
| `rollback` | ja | Wie man zurückkommt, und wie schnell |
| `owner_role` | ja | Rolle, die den Pilot verantwortet |
| `status` | nein | `draft`, `ready`, `running`, `stopped`, `completed` |
| `results` | nach Lauf | Gemessene Werte |

`guardrail_metrics[]`: `{"metric": "…", "limit": Zahl, "direction": "max"|"min"}`.
`max` heißt „darf nicht darüber", `min` heißt „darf nicht darunter".

`results[]`: `{"metric": "…", "value": Zahl, "as_of": "2026-05-31", "note": "…"}`.

## Zur Fallzahl

Die vorgeschlagene `sample_size` ist eine **Mengenabschätzung**: Volumen × Laufzeit ×
Anteil der berührten Fälle. Sie sagt, ob überhaupt genug Fälle zusammenkommen — sie ist
keine Fallzahlplanung. Eine echte Power-Rechnung bräuchte die Streuung der
Ausgangskennzahl, und die liegt in der Suite nicht vor. Wenn der Pilot eine
Entscheidung über eine größere Investition tragen soll, hol dafür jemanden dazu, der
die Streuung aus den Rohdaten rechnet.

## Was eine Karte brauchbar macht

1. **Eine Primärmetrik.** Wer drei gleichzeitig optimiert, optimiert keine.
2. **Guardrails, die weh tun.** Ein Guardrail, der nie auslösen kann, ist Dekoration.
   Setze die Schwelle dorthin, wo du tatsächlich abbrechen würdest.
3. **Abbruch vor dem Start vereinbaren.** Während ein Pilot läuft, findet sich für jede
   Zahl eine Erklärung. Die Regel muss vorher stehen.
4. **Rollback mit Zeitangabe.** „Zurückschalten" ist keine Zusage. „Innerhalb einer
   Stunde, laufende Fälle manuell" ist eine.
5. **Ergebnis zurückführen.** `results` eintragen und `make_experiments.py` laufen
   lassen: Die Werte landen als `observed` samt Provenienz im Graphen, und aus einer
   Schätzung wird eine Messung.

Der Validator lehnt eine Karte ohne Qualitäts- und Risikokennzahl, ohne Stoppregel oder
ohne Rollback ab. Das ist Absicht: Ein Pilot ohne diese drei Dinge ist kein Pilot,
sondern ein unbeaufsichtigter Rollout.
