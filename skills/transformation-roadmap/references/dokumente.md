# Dokumente und Textfelder

## Aufbau

Jedes Dokument besteht aus zwei Arten von Inhalt:

- **Bausteine aus dem Graphen:** Tabellen und Kennzahlen. Sie entstehen durch `build_documents.py`,
  werden nie von Hand geändert und gelten für genau eine Graph-Version.
- **Textfelder:** Anlass, Pilot und Referenz, Vorgehen, Beschluss, Kernbotschaft, Beteiligung. Sie
  stehen in `30_review/dokumente/texte.json`.

## texte.json

```json
{
  "entscheidungsvorlage": {
    "anlass":   {"text": "…", "quelle": "Gesprächsnotiz Lenkungskreis, Juni 2026", "verfasst_von": "Name oder Rolle"},
    "pilot":    {"text": "…", "quelle": "…"},
    "vorgehen": {"text": "…", "quelle": "…"},
    "beschluss":{"text": "…", "quelle": "…"}
  },
  "hr_einseiter": {
    "botschaft":     {"text": "…", "quelle": "…"},
    "mitbestimmung": {"text": "…", "quelle": "…"}
  }
}
```

Ein Feld gilt als gefüllt, wenn `text` und `quelle` gesetzt sind. Fehlt die Quelle, wird der Text nicht
übernommen und das Skript meldet es. Enthält ein Text eine E-Mail-Adresse, wird er ebenfalls nicht
übernommen.

## Wie Claude die Felder füllt

1. Das Material lesen, das die Person bereitstellt: Transkripte, Gesprächsnotizen, Mails, Projektstände.
2. Je Feld nur schreiben, was das Material hergibt. Eine Aussage ohne Beleg gehört nicht hinein.
3. In der Quelle das Material und die Fundstelle nennen (Dokument, Datum, bei Transkripten die Zeit).
4. Wo das Material schweigt, das Feld leer lassen. „❓ offen“ ist ein gültiges Ergebnis und besser
   als ein plausibler Satz.
5. Der Person zeigen, was gefüllt wurde und was offen blieb.

Das Skript prüft die Quelle, nicht die Wahrheit. Ob ein Text stimmt, entscheidet, wer ihn freigibt.

## Ton

Die Unterlagen sind für ein gemeinsames Vorhaben geschrieben: „wir klären“, „wir einigen uns“, nicht
„wir liefern“. Wo eine Runde ausdrücklich keine Auftragsbeziehung will, sollte weder
„Auftraggeber“ noch „Auftragnehmer“ vorkommen. `tone_flags` in der Konfiguration listet Wörter, die das
Skript meldet; die Liste ist anpassbar und ersetzt kein Lesen.

Für HR: einfache Sprache, keine Fachbegriffe wie FTE oder Disruption im Fließtext. Die Tabelle trägt die
Zahlen; der Text sagt, was sie für die Rollen bedeuten.

## Personen und Namen

- Die Unterlagen beschreiben Rollen, nie einzelne Personen.
- Namen Dritter, Kunden und Referenzen nur mit deren Einverständnis; das Feld „Pilot und Referenz“
  verlangt deshalb die Freigabe als Teil der Quelle.
- Gesprächstranskripte enthalten Daten Dritter. Aus ihnen zitiert nur, was für das Feld nötig ist.

## Stand

Der Kopf jedes Dokuments nennt den Stand. *Versandfertig* heißt: alle Textfelder des Dokuments haben eine
Quelle, und jede Welle ist entschieden oder läuft bereits. Es heißt nicht, dass der Inhalt freigegeben ist.
Das bleibt eine menschliche Entscheidung.

## Ausgabeformate

Markdown (weiterverarbeitbar) und HTML (druckt als PDF, hell und dunkel). Ein Word-Dokument entsteht
nicht; Markdown lässt sich in Word oder Pandoc übernehmen.
