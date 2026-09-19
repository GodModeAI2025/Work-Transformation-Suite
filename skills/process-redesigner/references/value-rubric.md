# Prozesswert-Rubrik

Neun Faktoren, Skala 0..10, ganze Zahlen. Gewichte und Bänder stehen in
`../assets/value-weights.json` und sind versioniert; die verwendete Version wird mit
jeder Bewertung in den Graphen geschrieben.

## Warum nicht nach FTE

Der `agent-mapper` sortiert Agenten nach FTE-Äquivalent. Für eine Opportunity Map ist das
richtig: Sie soll zeigen, wo Arbeitszeit gebunden ist. Als alleiniger Wertmaßstab führt
es zuverlässig zu Vorhaben, die viel Arbeit einsparen, ohne dass Kunden, Qualität oder
Durchlaufzeit sich messbar ändern — und die deshalb nach dem Pilot niemanden überzeugen.

Das FTE-Äquivalent bleibt sichtbar und wird bei Gleichstand als Tiebreaker verwendet. Es
entscheidet die Rangfolge nicht mehr allein.

## Die Faktoren

### Nutzen

| Faktor | 0 | 5 | 10 |
|---|---|---|---|
| `customer_impact` | Kunde merkt nichts | Kunde wartet spürbar kürzer oder bekommt klarere Antworten | Kunde erlebt einen anderen Service; wäre ein Argument im Wettbewerb |
| `financial_impact` | kein messbarer Effekt | fünfstellige Wirkung im Jahr | Effekt in der Größenordnung eines Budgetpostens |
| `cycle_time_reduction` | Durchlaufzeit bleibt | Halbierung | Tage werden zu Minuten |
| `quality_impact` | Fehlerquote unverändert | Nacharbeit etwa halbiert | Nacharbeit und Fehler weitgehend weg |
| `risk_reduction` | Risikolage unverändert | bekannte Schwachstelle wird kleiner | bekannte Compliance- oder Ausfallrisiken entfallen |
| `learning_value` | Einzelfall ohne Übertragbarkeit | Muster für zwei, drei ähnliche Prozesse | Muster, das viele weitere Prozesse trägt |

### Aufwand (hoher Wert heißt: teuer)

| Faktor | 0 | 5 | 10 |
|---|---|---|---|
| `integration_effort` | vorhandene Schnittstellen reichen | eine neue Schnittstelle, Standardtechnik | neue Anbindung an ein führendes System, Altsystem ohne API |
| `change_effort` | eine Rolle, eine Schulung | ein Team, neue Arbeitsweise, Kommunikation nötig | mehrere Bereiche, Mitbestimmung, veränderte Zuständigkeiten |

### Modifikator

| Faktor | 0 | 5 | 10 |
|---|---|---|---|
| `reversibility` | einmal umgestellt, kein Weg zurück | Rückbau möglich, aber teuer | jederzeit per Schalter zurückdrehbar |

Umkehrbarkeit ist bewusst ein eigener Faktor und nicht Teil des Aufwands. Ein umkehrbares
Vorhaben darf schlechter geschätzt sein, weil man es ausprobieren und beenden kann. Ein
unumkehrbares muss vorher stimmen.

## Rechnung

```
benefit = gewichteter Mittelwert der sechs Nutzenfaktoren           (0..10)
effort  = gewichteter Mittelwert der zwei Aufwandsfaktoren          (0..10)
ease    = 10 − effort                                               (0..10)
score   = 0,60 · benefit + 0,30 · ease + 0,10 · reversibility       (0..10)
```

Linear und ohne Schwellen. Jede Nichtlinearität würde die Sensitivitätsanalyse unlesbar
machen — und genau die ist hier das wichtigste Ergebnis.

## Prioritätsbänder

| Band | Score | Bedeutung |
|---|---|---|
| Jetzt | ≥ 7,0 | Pilot starten |
| Als Nächstes | 5,5 – 7,0 | vorbereiten, Daten schärfen, Voraussetzungen klären |
| Später | 4,0 – 5,5 | beobachten, Abhängigkeiten auflösen |
| Zurückstellen | < 4,0 | Aufwand steht nicht im Verhältnis |

**Bänder, keine Rangliste.** Ein Score von 6,8 gegenüber 6,9 bedeutet nichts, solange die
Eingaben Schätzungen auf einer Zehnerskala sind. Die Rangnummer im Graphen ist eine
Lesehilfe innerhalb eines Bandes, keine Aussage.

## Sensitivität

Für jeden Faktor wird ±1 durchgerechnet. Wechselt das Band dabei, gilt es als kippelig;
`sensitivity.flips` nennt die Faktoren, an denen es hängt.

Ein kippeliges Band ist kein Mangel der Methode, sondern ein Befund: Die Entscheidung
hängt an einer Schätzung, die man schärfen kann. Meist lohnt es sich mehr, den einen
Faktor mit einem Fachexperten zu klären, als die Rangfolge zu diskutieren.

## Bewerten

1. **Prozessweise, nicht faktorweise.** Ein Prozess vollständig, dann der nächste. Sonst
   entstehen Skalen, die je Faktor eine andere Bedeutung haben.
2. **Kontext lesen.** `process_value_todo.json` bringt Ist-Kennzahlen, Menge und
   FTE-Äquivalent mit. `customer_impact` lässt sich ohne die Durchlaufzeit nicht schätzen.
3. **Anker benutzen.** Die 5 ist der wichtigste Anker: „spürbar, aber nicht umwälzend".
4. **Begründen.** `rationale` je Prozess, zwei bis drei Sätze. Wer in vier Wochen die
   Rangfolge hinterfragt, liest genau das.
5. **Nicht optimieren.** Wer einen Lieblingsprozess nach oben schreibt, merkt es spätestens
   im Pilot — dann aber teuer.

## Eigene Gewichte

`--weights ./eigene-gewichte.json` ersetzt die Datei. Sinnvoll, wenn ein Haus
ausdrücklich anders priorisiert (etwa Risikominderung vor Kundenwirkung). Die
`composite`-Gewichte müssen auf 1,0 summieren, sonst bricht das Skript ab. Vergib eine
neue `config_version`: Bewertungen aus einer anderen Version werden beim nächsten Lauf
neu gerechnet, statt stillschweigend gemischt zu werden.
