# Blueprint-Format

Datei: `20_graph/blueprints.json`, eine Liste. Ein Eintrag je Prozess und Szenario.
`build_blueprints.py` löst die Namen auf IDs auf und rechnet alle Kennzahlen aus.

**Du schreibst keine Deltas.** Du beschreibst den Soll-Ablauf; Durchlaufzeit, Übergaben,
Human Touchpoints, Nacharbeit und die Veränderung gegenüber dem Ist fallen daraus an.
Das ist der Grund, warum das Format Zeiten je Schritt verlangt und keine
Gesamtversprechen: Eine Zusage lässt sich schönschreiben, eine Summe über Schritte nicht.

## Vollständiges Beispiel

```json
[
  {
    "process": "Kundenreklamation bis Lösung",
    "scenario": "balanced",
    "name": "Reklamation mit Triage-Agent und Ausnahmebearbeitung",
    "summary": "Klassifikation und Faktensammlung übernimmt ein Agent. Die Sachprüfung bleibt menschlich, läuft aber parallel zur Vorbereitung der Antwort. Die Gutschriftfreigabe bleibt unverändert.",
    "steps": [
      {
        "name": "Anliegen klassifizieren und Fakten sammeln",
        "operator": "merge",
        "from_steps": ["Anliegen klassifizieren", "Vertragsdaten zusammenstellen"],
        "executor": {"type": "agent", "name": "Reklamations-Triage-Agent"},
        "systems": ["CRM", "Abrechnungssystem"],
        "handling_time_min": 1,
        "wait_time_min": 0,
        "rework_pct": 3,
        "human_gate": {"when": "Klassifikationskonfidenz unter 0,85", "role": "Servicemitarbeiter"},
        "rationale": "Beide Schritte arbeiten auf derselben Kundennachricht und denselben Vertragsdaten; die Übergabe dazwischen kostet einen halben Arbeitstag Liegezeit.",
        "metric": "Durchlaufzeit bis Lösung",
        "assumption": "Die Falltypen sind aus dem Freitext zuverlässig trennbar; unter 0,85 Konfidenz übernimmt ein Mensch."
      },
      {
        "name": "Sachverhalt prüfen",
        "operator": "simplify",
        "from_steps": ["Sachverhalt prüfen"],
        "executor": {"type": "human", "name": "Sachbearbeiter Abrechnung"},
        "systems": ["Abrechnungssystem"],
        "controls": ["Vier-Augen-Prinzip Gutschrift"],
        "parallel_group": "pruefung-und-entwurf",
        "handling_time_min": 12,
        "wait_time_min": 120,
        "rework_pct": 8,
        "rationale": "Der Agent liefert die Fakten vorbereitet an; die Prüfung entfällt nicht, wird aber kürzer und erzeugt weniger Rückfragen.",
        "metric": "Nacharbeitsquote",
        "assumption": "Die vorbereiteten Fakten sind vollständig genug, dass keine erneute Recherche nötig wird."
      },
      {
        "name": "Antwortentwurf erstellen",
        "operator": "parallelize",
        "from_steps": ["Antwort an Kunden senden"],
        "executor": {"type": "agent", "name": "Reklamations-Triage-Agent"},
        "systems": ["CRM"],
        "parallel_group": "pruefung-und-entwurf",
        "handling_time_min": 1,
        "wait_time_min": 0,
        "rationale": "Der Entwurf braucht das Prüfergebnis nicht, nur den Falltyp. Er kann währenddessen entstehen statt danach.",
        "metric": "Durchlaufzeit bis Lösung",
        "assumption": "Bei abweichendem Prüfergebnis ist der Entwurf in unter zwei Minuten anzupassen."
      },
      {
        "name": "Antwort freigeben und senden",
        "operator": "human_gate",
        "from_steps": ["Antwort an Kunden senden"],
        "executor": {"type": "human", "name": "Servicemitarbeiter"},
        "systems": ["CRM"],
        "handling_time_min": 3,
        "wait_time_min": 30,
        "human_gate": {"when": "immer bei Gutschrift, sonst Stichprobe 10 %", "role": "Servicemitarbeiter"},
        "rationale": "Die Antwort an den Kunden ist der Moment, in dem das Unternehmen sich festlegt. Diese Grenze bleibt beim Menschen.",
        "metric": "Nacharbeitsquote"
      }
    ],
    "removed_steps": [
      {
        "step": "Fall in Übersichtsliste eintragen",
        "rationale": "Die Liste wurde geführt, weil das CRM den Fallstatus nicht auswies. Der Triage-Agent setzt den Status direkt.",
        "metric": "Durchlaufzeit bis Lösung",
        "assumption": "Die Teamsteuerung akzeptiert die CRM-Auswertung als Ersatz für die Liste."
      }
    ],
    "control_coverage": {
      "retained": ["Vier-Augen-Prinzip Gutschrift"],
      "replaced": [],
      "dropped": []
    },
    "agents": ["Reklamations-Triage-Agent"],
    "projected_metrics": [
      {"metric": "Durchlaufzeit bis Lösung", "value": 3, "basis": "estimated"},
      {"metric": "Nacharbeitsquote", "value": 8, "basis": "estimated"}
    ],
    "open_assumptions": [
      "Der Agent bekommt Lesezugriff auf das Abrechnungssystem; heute ist dort keine Schnittstelle erfasst."
    ],
    "risks": [
      "Bei einer Fehlklassifikation läuft der Fall an der zuständigen Rolle vorbei. Gegenmaßnahme: Konfidenzschwelle und Stichprobe."
    ],
    "status": "draft"
  }
]
```

## Feldreferenz

### Blueprint

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `process` | ja | Name oder ID eines Prozesses im Graphen |
| `scenario` | ja | `conservative`, `balanced` oder `agent_native` — je Prozess höchstens einmal |
| `name` | nein | Sprechender Titel; sonst aus Prozess und Szenario gebildet |
| `summary` | empfohlen | Zwei bis drei Sätze: was sich ändert und warum |
| `steps` | ja | Soll-Schritte in fachlicher Reihenfolge |
| `removed_steps` | nach Lage | Gestrichene Ist-Schritte mit Begründung |
| `control_coverage` | ja, sobald der Ist-Prozess Kontrollen hat | Was mit jeder Kontrolle passiert |
| `agents` | nein | Wird aus den Ausführenden abgeleitet; hier nur ergänzend |
| `projected_metrics` | empfohlen | Zielwerte je Kennzahl, mit Belastbarkeit |
| `open_assumptions` | empfohlen | Was noch offen ist. Leere Liste heißt: nichts mehr offen |
| `risks` | empfohlen | Was schiefgehen kann, und die Gegenmaßnahme |
| `status` | nein | `draft` (Standard), `reviewed`, `approved`, `rejected` |
| `outcome_change_rationale` | nur bei geändertem Ergebnis | Warum der Soll-Prozess ein anderes Ergebnis liefert |

`status: "approved"` setzt du nicht selbst — Freigaben laufen über
`30_review/decisions.csv` und `apply_governance.py`.

### `steps[]`

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Verb-Objekt-Form |
| `operator` | ja | `simplify`, `merge`, `parallelize`, `automate` oder `human_gate` (`eliminate` gehört nach `removed_steps`) |
| `from_steps` | fast immer | Namen der Ist-Schritte, aus denen dieser entsteht. Leer nur bei einem wirklich neuen Schritt |
| `executor` | ja | `{"type": "human\|agent\|system\|rule", "name": "…"}` |
| `systems`, `controls` | nach Lage | Namen aus dem Graphen |
| `handling_time_min` | ja | Reine Arbeitszeit im Soll |
| `wait_time_min` | ja | Liegezeit im Soll. Hier steckt meist der Gewinn |
| `rework_pct` | empfohlen | Anteil Rückläufer im Soll |
| `parallel_group` | bei `parallelize` | Gleicher Wert bei allen gleichzeitig laufenden Schritten |
| `human_gate` | nach Lage | `{"when": "überprüfbare Bedingung", "role": "Rollenname"}` |
| `rationale` | ja | Warum diese Änderung. Ein Satz, der einem Fachexperten reicht |
| `metric` | bei `simplify`, `merge`, `parallelize`, `automate` | Name einer Kennzahl des Prozesses |
| `assumption` | empfohlen | Woran die Änderung scheitern würde |

### `removed_steps[]`

`{"step": "…", "rationale": "…", "metric": "…", "assumption": "…", "replacement": "…"}`.
Ein blanker String wird akzeptiert, gilt aber als Streichung ohne Begründung und ist
damit ein Fehler. `replacement` ist Pflicht, wenn der Schritt Kundenwert trug.

### `control_coverage`

```json
{
  "retained": ["Kontrolle, die unverändert bleibt"],
  "replaced": [
    {
      "control": "Manuelle Zweitprüfung Stammdaten",
      "replacement": "Automatischer Abgleich gegen das führende System plus tägliche Ausreißerprüfung",
      "rationale": "Die Zweitprüfung fand im letzten Jahr drei Fehler, alle davon Formatfehler, die der Abgleich sicher findet.",
      "approved_by": "Name der Person, die den Ersatz freigegeben hat"
    }
  ],
  "dropped": ["Kontrolle ohne Pflichtcharakter, die ersatzlos entfällt"]
}
```

## Vorgehen

1. **Ist-Briefing lesen.** `30_review/redesign_briefing_vNNN.md`. Vor allem die erkannten
   Ansatzpunkte und die Pflichtkontrollen.
2. **Konservativ zuerst.** Es ist der Vergleichsmaßstab. Wer mit agent-nativ anfängt,
   baut die beiden anderen als Karikatur.
3. **Zeiten realistisch schätzen.** Ein Agentenschritt kostet selten null Minuten
   Wartezeit, wenn er auf ein System wartet, das nachts läuft.
4. **Annahmen mitschreiben, während du entwirfst.** Hinterher fallen sie einem nicht mehr ein.
5. **`build_blueprints.py`, dann `validate_blueprints.py`.** Die Meldungen sind die
   Arbeitsliste, nicht der Feind.
