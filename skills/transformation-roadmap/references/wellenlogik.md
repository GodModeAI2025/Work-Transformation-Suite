# Wellenlogik

Wie `plan_waves.py` aus Agenten und Use Cases ein Raster macht, und wo es bewusst nicht entscheidet.

## Vorhaben

Ein Vorhaben ist ein Agent oder ein Use Case ohne Agent. Verweist ein Use Case auf Agenten
(`agent_ids`), geht er im Vorhaben des Agenten auf; so erscheint dieselbe Arbeit nicht zweimal.

## Score (0 bis 10)

Fünf Größen, gewichtet (`weights` in `assets/wave-config.json`, Summe frei):

| Größe | Herkunft |
|---|---|
| Wert | Team-Angabe (`value_eur_per_year`), sonst gebundene Arbeit mal Tagessatz. Relativ zum höchsten Wert. |
| Reichweite | Betroffene FTE, relativ zum höchsten Wert |
| Umsetzbarkeit | Komplexität des Agenten: 1 ergibt 10, 5 ergibt 0. Bei Use Cases ohne Agent unbekannt |
| Reifegrad | Status: im Betrieb 10, Pilot 8, im Bau 7, geplant 5, Vorschlag 3, Idee 2 |
| Prozessrang | Bestes Prioritätsband der Prozesse, in denen die Aufgaben vorkommen: Jetzt 10, Als Nächstes 7, Später 3, Halten 0 |

**Fehlt eine Größe, rechnet der Score ohne sie.** Das Vorhaben verliert dadurch nichts, es wird nur nicht
mit einer Null bestraft. Wie viele Größen eingingen, steht im Anhang („3 von 5 Größen, es fehlt: …“).
Mit weniger als `min_components` Größen (Standard 2) bleibt der Score leer; das Vorhaben heißt dann
„nicht bewertet“ und kommt in der Rangfolge zuletzt.

Der Score ordnet. Er sagt nicht, dass 7,8 doppelt so gut ist wie 3,9. Bei dichten Werten entscheidet die
Runde, nicht die Nachkommastelle.

## Wellen

Reihenfolge der Zuordnung:

1. **Entscheidungen** aus `30_review/wellen.csv`, mit benannter Person.
2. **Laufende Vorhaben** (Status `pilot`, `live`): Welle 1. Sie sind bereits Referenz. Sie zählen in die
   Kapazität, auch wenn sie sie überschreiten; das Raster meldet das.
3. **Der Rest nach Score**, in die früheste Welle mit freier Kapazität. Vorhaben mit Komplexität über
   `max_complexity_first_wave` (Standard 3) beginnen nicht in Welle 1.
4. **Orchestratoren** frühestens eine Welle nach den Agenten, die sie steuern (`orchestrates`).

Eine bestätigte Entscheidung, die eine Abhängigkeit verletzt, wird nicht geändert, sondern gemeldet.

## Betroffene Rollen je Welle

Je Welle die Vereinigung der Aufgaben aller Vorhaben. Eine Aufgabe, die mehrere Vorhaben berührt,
zählt einmal. Daraus folgen Rollen, Zeitanteil, FTE und Wert. Die Zeile „Alle Wellen zusammen“ ist die
Vereinigung über alle Wellen, nicht die Summe der Zeilen.

## Was betroffen bedeutet

Wert und FTE sind die **heute gebundene Arbeit** der berührten Aufgaben. Wie viel davon frei wird, hängt
von Gestaltung, Akzeptanz und Aufsicht ab. Das Zielbild der Rollen (`target_roles`) trägt dazu eine
eigene, als Entwurf markierte Schätzung; die Unterlagen zeigen beides getrennt.

## Lücken

Prozesse im Band „Jetzt“ oder „Als Nächstes“, für die weder Agent noch Use Case besteht, stehen als
Lücken im Raster. Wer nur verteilt, was angefragt wird, sieht sie nicht.

## Grenzen

- Abhängigkeiten außer „Orchestrator vor Agenten“ kennt das Raster nicht. Voraussetzungen aus der
  Agentenbibliothek stehen als Text daneben, damit Menschen sie lesen.
- Zeiträume, Budgets und Teamkapazität kennt es nicht. `capacity` begrenzt die Zahl der Vorhaben je Welle,
  nicht Aufwand.
- Es optimiert nichts. Es macht einen nachvollziehbaren ersten Vorschlag, an dem sich eine Runde reiben kann.
