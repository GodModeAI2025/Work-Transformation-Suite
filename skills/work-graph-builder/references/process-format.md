# Prozessextraktionsformat (Schema 1.1)

Eine Datei je Quelle unter `10_extraction/process_<quelle>.json`. `build_processes.py`
führt alle Dateien alphabetisch zusammen und schreibt daraus die Prozessebene des
Arbeitsgraphen.

## Abgrenzung zum Aufgabenformat

`extract_*.json` beschreibt **wer was tut** (Rollen, Aufgaben, Skills, Zeitanteile).
`process_*.json` beschreibt **wie ein Fall durch die Organisation läuft** (Auslöser,
Schritte, Übergaben, Systeme, Kontrollen, Ergebnis). Beides hängt zusammen: ein
Prozessschritt verweist über `tasks` auf Aufgaben aus dem Arbeitsgraphen.

Eine Aufgabe kann in mehreren Prozessen vorkommen, und ein Prozessschritt kann
mehrere Aufgaben bündeln. Die Beziehung ist ausdrücklich n:m, nicht 1:1.

## Woher die Zahlen kommen dürfen

Jede Zahl trägt ihre Belastbarkeit mit: `estimated` (geschätzt), `expert_confirmed`
(vom Fachexperten bestätigt), `observed` (gemessen). Wer `expert_confirmed` oder
`observed` schreibt, muss einen `provenance`-Eintrag mitliefern — sonst meldet der
Validator einen Fehler. Das ist Absicht: eine behauptete Messung ohne Fundstelle ist
schlechter als eine ehrliche Schätzung, weil sie sich nicht widerlegen lässt.

Ohne Prozessbeobachtung, Systemexport oder Interview bleibt `estimated` korrekt.
Die Suite rechnet damit weiter, markiert die Ergebnisse aber sichtbar als Schätzung.

## Minimalbeispiel

```json
{
  "source": "Interview Kundenservice, 2026-03-11",
  "outcomes": [
    {
      "name": "Fall korrekt gelöst und Kunde informiert",
      "description": "Reklamation abschließend bearbeitet, Kunde hat eine verständliche Antwort.",
      "beneficiary": "Privatkunde"
    }
  ],
  "systems": [
    {"name": "CRM", "kind": "application", "system_of_record": true, "api_available": true,
     "data_classes": ["personal"]},
    {"name": "Abrechnungssystem", "kind": "application", "system_of_record": true, "api_available": false}
  ],
  "controls": [
    {"name": "Vier-Augen-Prinzip Gutschrift", "kind": "financial", "mode": "preventive",
     "mandatory": true, "legal_basis": "Interne Richtlinie Zahlungsfreigabe 4.2",
     "evidence": "Freigabevermerk im CRM"}
  ],
  "processes": [
    {
      "name": "Kundenreklamation bis Lösung",
      "trigger": "Reklamation geht über Formular, Telefon oder E-Mail ein",
      "outcome": "Fall korrekt gelöst und Kunde informiert",
      "beneficiary": "Privatkunde",
      "owner_role": "Teamleitung Kundenservice",
      "volume_per_year": 42000,
      "variants": ["Abrechnungsfehler", "Lieferverzug", "Kulanzanfrage"],
      "regulated": false,
      "data_classes": ["personal"],
      "baseline_metrics": [
        {
          "name": "Durchlaufzeit bis Lösung",
          "kind": "time", "unit": "Stunden", "direction": "lower_is_better",
          "baseline": {"value": 72, "basis": "observed", "as_of": "2026-02", "source": "CRM-Export Q1"},
          "target": {"value": 24, "basis": "estimated", "as_of": "2026-12"},
          "provenance": [
            {"field": "baseline", "source_kind": "system_export", "source_ref": "CRM-Export Q1 2026",
             "locator": "reklamation_durchlaufzeit.csv, Spalte lead_time_h",
             "author": "Controlling", "reviewer": "Teamleitung Kundenservice",
             "confidence": 0.9, "status": "verified", "as_of": "2026-03-01"}
          ]
        },
        {
          "name": "Nacharbeitsquote", "kind": "quality", "unit": "Prozent",
          "direction": "lower_is_better",
          "baseline": {"value": 18, "basis": "estimated", "as_of": "2026-02"}
        }
      ],
      "steps": [
        {
          "name": "Anliegen klassifizieren",
          "role": "Servicemitarbeiter",
          "executor": {"type": "human"},
          "tasks": ["Reklamation aufnehmen und kategorisieren"],
          "inputs": ["Kundennachricht"],
          "outputs": ["Falltyp", "Dringlichkeit"],
          "systems": ["CRM"],
          "data_classes": ["personal"],
          "handling_time_min": 8,
          "wait_time_min": 240,
          "rework_pct": 5,
          "value_type": "business_required",
          "next": [{"to": "Sachverhalt prüfen", "handover": "system", "share_pct": 100}]
        },
        {
          "name": "Sachverhalt prüfen",
          "role": "Sachbearbeiter Abrechnung",
          "executor": {"type": "human"},
          "systems": ["Abrechnungssystem", "CRM"],
          "controls": ["Vier-Augen-Prinzip Gutschrift"],
          "handling_time_min": 25,
          "wait_time_min": 960,
          "rework_pct": 20,
          "value_type": "customer_value",
          "decision": {
            "scope": "execute_reversible",
            "accountable_role": "Teamleitung Kundenservice",
            "escalation": "Ab 250 EUR Gutschrift an Teamleitung"
          },
          "human_gate": {"when": "Gutschrift über 250 EUR", "role": "Teamleitung Kundenservice"},
          "next": [{"to": "Antwort an Kunden senden", "handover": "email", "share_pct": 100}]
        },
        {
          "name": "Antwort an Kunden senden",
          "role": "Servicemitarbeiter",
          "systems": ["CRM"],
          "handling_time_min": 10,
          "wait_time_min": 60,
          "value_type": "customer_value"
        }
      ]
    }
  ]
}
```

## Feldreferenz

### `outcomes[]`
| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Das Ergebnis aus Sicht des Empfängers, nicht der Abteilung |
| `description` | nein | Ein Satz, woran man das Ergebnis erkennt |
| `beneficiary` | empfohlen | Wer hat etwas davon (Kundengruppe, interne Rolle, Aufsicht) |

### `systems[]`
`name` (Pflicht), `kind`, `system_of_record` (führt dieses System die Wahrheit?),
`api_available` (entscheidet mit, ob ein Agent überhaupt schreiben kann),
`data_classes` aus `public | internal | confidential | personal | special_category`.

### `controls[]`
`name` (Pflicht), `kind` aus `regulatory | financial | safety | privacy | quality | contractual`,
`mode` aus `preventive | detective | corrective`, `mandatory` (Standard: `true`),
`legal_basis` (Pflicht bei `regulatory`), `evidence` (woran die Ausführung nachweisbar ist).

Kontrollen sind der Grund, warum ein Redesign nicht beliebig kürzen kann: Eine
Pflichtkontrolle darf im Blueprint nur entfallen, wenn ein dokumentierter Ersatz und
eine namentliche Freigabe vorliegen.

### `processes[]`
| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Von Auslöser bis Ergebnis benennen („Reklamation bis Lösung") |
| `trigger` | ja | Das Ereignis, das den Prozess startet |
| `outcome` | ja | Name eines Eintrags aus `outcomes` (wird sonst angelegt) |
| `owner_role` | empfohlen | Rollenname aus dem Arbeitsgraphen |
| `volume_per_year` | empfohlen | Fälle pro Jahr; ohne Menge keine Wertschätzung |
| `variants` | nein | Fachliche Spielarten, die derselbe Fluss abdeckt |
| `regulated` | nein | Steht der Prozess unter Aufsicht? |
| `data_classes` | nein | Höchste Datenklasse im Prozess |
| `baseline_metrics` | ja | Mindestens eine Ergebnis- und eine Qualitätskennzahl |
| `steps` | ja | Schritte in fachlicher Reihenfolge |

### `processes[].steps[]`
| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Verb-Objekt-Form |
| `role` | ja bei `executor.type=human` | Rollenname aus dem Arbeitsgraphen |
| `executor` | nein | `{"type": "human\|agent\|system\|rule", "id": "…"}`, Standard `human` |
| `tasks` | empfohlen | Aufgabennamen dieser Rolle aus dem Arbeitsgraphen |
| `inputs` / `outputs` | empfohlen | Was hereinkommt, was entsteht — die Grundlage für `merge` und `parallelize` |
| `systems` / `controls` | nach Lage | Namen aus den obigen Listen |
| `handling_time_min` | empfohlen | Reine Bearbeitungszeit |
| `wait_time_min` | empfohlen | Liegezeit vor dem Schritt. Meist der größere Hebel |
| `rework_pct` | empfohlen | Anteil der Fälle, die zurücklaufen |
| `value_type` | empfohlen | `customer_value`, `business_required`, `waste` |
| `human_gate` | nach Lage | `{"when": "Bedingung", "role": "Rollenname"}` |
| `decision` | bei Entscheidungen | `{"scope": …, "accountable_role": …, "escalation": …}` |
| `next` | nein | Kanten; fehlt `next` überall, wird linear verkettet |

`next[]`: `{"to": "Schrittname", "condition": "…", "handover": "none\|system\|document\|email\|ticket\|call\|meeting", "share_pct": 0..100}`.

Schleifen sind erlaubt und erwünscht — Nacharbeit ist ein Fakt des Ist-Prozesses, kein
Modellfehler. Genau diese Schleifen sind später die lohnendsten Redesign-Ziele.

## Wie du einen Prozess aufnimmst

1. **Vom Ergebnis aus.** Zuerst `outcome` und `beneficiary` festhalten, dann rückwärts
   die Schritte. Wer vorne anfängt, schreibt den Ist-Zustand fort.
2. **Übergaben mitschreiben.** Jeder Wechsel der ausführenden Rolle ist eine Kante mit
   `handover`. Übergaben per E-Mail oder Meeting sind die typischen Wartezeitquellen.
3. **Liegezeit trennen.** `handling_time_min` ist Arbeit, `wait_time_min` ist Warten.
   Wer beides vermischt, verliert den größten Hebel aus dem Blick.
4. **Kontrollen benennen, nicht bewerten.** Ob eine Kontrolle nötig bleibt, entscheidet
   das Redesign — hier wird nur festgehalten, dass es sie gibt und worauf sie beruht.
5. **Fünf bis fünfzehn Schritte.** Weniger verbirgt die Übergaben, mehr modelliert
   Klickfolgen statt Prozess.

## Grenzen

Ein Prozessmodell aus Interviews ist eine Rekonstruktion, kein Prozess-Mining-Ergebnis.
Volumen, Wartezeiten und Nacharbeitsquoten aus dem Gedächtnis sind systematisch zu
optimistisch. Schreibe sie trotzdem auf — mit `basis: "estimated"` — und ersetze sie,
sobald ein Systemexport vorliegt. Der Unterschied zwischen geschätzt und gemessen ist
in der Suite überall sichtbar und darf nicht verwischt werden.
