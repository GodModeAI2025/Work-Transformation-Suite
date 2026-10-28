# Interviewleitfaden Prozessaufnahme

Ziel: aus einem Gespräch mit jemandem, der die Arbeit macht, genug Material für `process_*.json`
zu gewinnen — Schritte, Systeme, Übergaben und Reibung. Eine Stellenbeschreibung liefert allenfalls
ein Drittel davon, weil sie nicht festhält, wie Rollen zusammenarbeiten und was informell läuft.

## Die drei Fragen

Bei jedem Schritt, in dieser Reihenfolge:

1. **Was machst du, Schritt für Schritt?** „Zeig mir, wie du es heute machst.“ Nicht: „Wie läuft
   der Prozess?“ Wer zeigt, nennt Details, die er beim Erzählen weglassen würde.
2. **Welche Systeme, welche Daten?** Woher kommen die Daten, wohin gehen sie, wer bekommt das
   Ergebnis? Was wird kopiert, abgetippt, per E-Mail verschickt?
3. **Wie fühlst du dich dabei?** Wo hakt es, wo wartest du, was nervt? Die Antwort gehört in das Feld
   `pain` des Prozessschritts. Hier steckt meist das eigentliche Problem.

## Nachfragen

- **Warum so?** Dreimal hintereinander fragen („Warum ist das dein Problem? Und warum ist das so?“),
  bis die Ursache erscheint und nicht das Symptom.
- **Wer bekommt es als Nächstes?** Das liefert die Übergaben. Jede Übergabe ist ein Kandidat für
  `eliminate` oder `merge`.
- **Was passiert, wenn es nicht klappt?** Das liefert Rückläufer (`rework_pct`) und Kontrollen.
- **Was wird nirgends dokumentiert?** Informelle Absprachen, Excel-Listen, Wissen im Kopf.

## Bevor du „KI“ sagst

Prüfe zuerst, ob das Problem ohne KI zu lösen ist. Ein Beispiel aus der Praxis: Ein Prozess sollte mit einem
Sprachmodell beschleunigt werden — das Problem war aber nur, dass jemand 84 PDFs von Hand öffnen musste. Eine
Schnittstelle, die den Stapel auf einmal liefert, löst das billiger und stabiler. Trage solche Fälle im Blueprint
mit `solution_class: "interface"` oder `"process_change"` ein; der Bericht zählt sie ausdrücklich.

Dasselbe gilt für den gelebten Ist-Prozess: Wer nur automatisiert, was heute geschieht (jeden Mittwoch kommt eine
Excel-Datei per E-Mail), festigt einen Umweg. Frage vorher, ob der Schritt überhaupt gebraucht wird.

## Rahmen klären, bevor du fragst

Wer weiß, dass seine Antworten zu seiner Ersetzung führen können, antwortet vorsichtig oder gar nicht. Vor der
ersten Frage muss feststehen und gesagt werden:

- Wozu wird erhoben, und was passiert nicht (keine Leistungsbewertung einzelner Personen)?
- Ist die Beschäftigtenvertretung beteiligt?
- Gibt es Zusagen zur Beschäftigung, und stehen sie in einem Dokument, das der Gesprächspartner kennt?

Halte das im Pilot als `frame_confirmed` und `frame_note` fest. Ohne bestätigten Rahmen warnt der Validator vor dem
Start eines Piloten.

## Auswerten

| Beobachtung | Eintrag |
|---|---|
| Wartezeit zwischen Schritten | `wait_time_min` am nachfolgenden Schritt |
| Nacharbeit, Rückläufer | `rework_pct` |
| Frust, Zeitfresser | `pain` (Freitext, in den Worten des Gesprächspartners) |
| Kopieren zwischen Systemen | eigener Prozessschritt mit beiden Systemen, Kandidat für `solution_class: "interface"` |
| Genannte Zahl | `estimated`, bis Beleg und `provenance` vorliegen |
