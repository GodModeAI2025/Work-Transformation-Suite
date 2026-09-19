# Redesign-Regeln

Die sechs Operatoren, ihre Vorbedingungen und die Regeln, die der Validator prüft.

## Woher die Operatoren kommen

Die Reihenfolge **eliminieren → vereinfachen → zusammenführen → automatisieren** stammt
aus der ESIA-Schule der Prozessneugestaltung (Eliminate, Simplify, Integrate, Automate).
Ihr Kern ist eine Warnung: Wer zuerst automatisiert, zementiert die Schritte, die es gar
nicht mehr bräuchte. Ergänzt sind zwei Operatoren, die im KI-Kontext den Unterschied
machen: **parallelisieren** (weil Wartezeit fast immer der größere Hebel ist als
Bearbeitungszeit) und **Human Gate erhalten** (weil ein Redesign benennen muss, wo
Menschen entscheiden, statt es implizit zu lassen).

Arbeite die Operatoren in dieser Reihenfolge durch. Wenn dein Entwurf am Ende
überwiegend aus `automate` besteht, bist du zu früh eingestiegen.

## Die sechs Operatoren

### 1. eliminieren (`eliminate`)

Der Schritt entfällt ersatzlos. Wird über `removed_steps` ausgedrückt, nicht als
Soll-Schritt.

| | |
|---|---|
| Wann | Der Schritt schafft weder Kundenwert noch erfüllt er eine betriebliche Pflicht. Typisch: Statusabfragen, Zwischenablagen, Berichte, die niemand liest, Prüfungen, die nie etwas finden. |
| Pflichtfelder | `rationale` |
| Zusätzlich bei `value_type: customer_value` | `replacement` (wodurch entsteht der Kundennutzen künftig?) und `assumption` |
| Zusätzlich bei Kontrollen am Schritt | Eintrag in `control_coverage` |
| Prüfung | Streichung ohne Begründung ist ein Fehler. Eine Pflichtkontrolle ersatzlos zu streichen ist ein Fehler. |

Die ehrlichste Frage zu einem Streichungskandidaten: *Wer merkt es, wenn dieser Schritt
morgen ausfällt — und wann?* Wenn die Antwort „niemand" lautet, streiche ihn. Wenn sie
„die Revision, in elf Monaten" lautet, brauchst du einen Ersatz.

### 2. vereinfachen (`simplify`)

Ein Schritt bleibt, kostet aber weniger Arbeit oder erzeugt weniger Nacharbeit.

| | |
|---|---|
| Wann | Der Schritt ist nötig, aber umständlich: Daten werden von Hand übertragen, Vorlagen fehlen, Regeln sind unklar und erzeugen Rückläufer. |
| Pflichtfelder | genau ein Eintrag in `from_steps`, `rationale`, `metric` |
| Prüfung | Die Soll-Bearbeitungszeit muss unter der Ist-Bearbeitungszeit liegen, sonst hat der Operator keine Wirkung. |

### 3. zusammenführen (`merge`)

Mehrere Ist-Schritte werden zu einem. Der eigentliche Gewinn ist selten die Arbeitszeit,
sondern die Übergabe dazwischen.

| | |
|---|---|
| Wann | Aufeinanderfolgende Schritte arbeiten auf denselben Eingaben, oder derselbe Ausführende macht sie ohnehin hintereinander, oder mehrere Rollen prüfen nacheinander dieselben Daten. |
| Pflichtfelder | mindestens zwei Einträge in `from_steps`, `rationale`, `metric` |
| Prüfung | Die Soll-Bearbeitungszeit darf die Summe der zusammengelegten Ist-Zeiten nicht überschreiten. |

### 4. parallelisieren (`parallelize`)

Schritte laufen gleichzeitig statt nacheinander. Die Arbeitsminuten bleiben, die
Durchlaufzeit sinkt.

| | |
|---|---|
| Wann | Zwei Schritte brauchen einander nicht: Der eine wartet nur, weil er in der Reihenfolge hinten steht. Erkennbar an hoher Liegezeit gegenüber kurzer Arbeitszeit. |
| Pflichtfelder | `parallel_group` (gleicher Wert bei allen Schritten der Gruppe), `rationale`, `metric` |
| Prüfung | Eine Gruppe mit nur einem Schritt ist keine Parallelisierung. Für die Durchlaufzeit zählt der längste Schritt der Gruppe, nicht ihre Summe. |

### 5. automatisieren (`automate`)

Ein Schritt wird von einem Agenten, einem System oder einem Regelwerk ausgeführt.

| | |
|---|---|
| Wann | Erst wenn der Schritt nach den vier Operatoren davor noch steht. |
| Pflichtfelder | `executor.type` aus `agent`, `system`, `rule`, `rationale`, `metric` |
| Prüfung | `executor.type: human` widerspricht dem Operator. Trug der Ist-Schritt eine Kontrolle, muss `control_coverage` sie adressieren. |

Wähle den Ausführenden bewusst. `rule` (deterministisches Regelwerk) und `system`
(bestehende Systemfunktion) sind billiger, schneller und prüfbarer als ein Agent. Ein
Agent lohnt sich dort, wo Sprache, Uneindeutigkeit oder Kontext im Spiel sind — nicht bei
einer Schwellwertprüfung.

### 6. Human Gate erhalten (`human_gate`)

Ein Mensch entscheidet, unter einer benannten Bedingung.

| | |
|---|---|
| Wann | An Verantwortungsgrenzen: irreversible Folgen, Ermessen, Kulanz, rechtliche Wirkung, Fälle unterhalb der Konfidenzschwelle. |
| Pflichtfelder | `human_gate.when` und `human_gate.role`, oder `executor.type: human`; `rationale` |
| Prüfung | Ein Gate ohne Bedingung ist kein Gate, sondern ein manueller Schritt. |

Formuliere die Bedingung überprüfbar: „Gutschrift über 250 EUR" statt „in
Zweifelsfällen". Eine Bedingung, die niemand messen kann, wird im Betrieb entweder
immer oder nie ausgelöst.

## Regeln über den einzelnen Schritt hinaus

### Vollständigkeit

Jeder Ist-Schritt muss im Blueprint vorkommen: als Vorläufer eines Soll-Schrittes
(`from_steps`) oder unter `removed_steps`. Ein Schritt, der einfach verschwindet, ist der
häufigste Weg, ein Redesign schönzurechnen — und der am schwersten zu bemerkende.

### Ergebniserhalt

Jeder Soll-Prozess endet im selben oder einem besseren Geschäftsergebnis. Ein anderes
`outcome` braucht `outcome_change_rationale`. Sonst wird aus dem Redesign unbemerkt ein
anderer Prozess, und der Vergleich mit dem Ist ist wertlos.

### Kontrollen

Jede Kontrolle des Ist-Prozesses gehört in `control_coverage` — behalten, ersetzt oder
bewusst gestrichen. Für Pflichtkontrollen (`mandatory: true`) gilt zusätzlich:

- Ersatz braucht `replacement`, `rationale` **und** `approved_by` (eine Person, nicht eine Abteilung).
- Ersatzloses Streichen ist unzulässig.

### Die Szenarioleiter

Die drei Szenarien müssen sich unterscheiden und eine Richtung zeigen:

| Szenario | Kontrollen | Menschliche Beteiligung | Frage, die es beantwortet |
|---|---|---|---|
| Konservativ | unverändert | hoch | Was bringt KI, ohne dass wir etwas riskieren? |
| Ausgewogen | angepasst, dokumentiert | Ausnahmen | Was bringt es, wenn wir den Ablauf anfassen dürfen? |
| Agent-nativ | vom Ziel aus neu begründet | an Verantwortungsgrenzen | Was wäre möglich, wenn wir heute neu anfingen? |

Der Validator meldet einen Fehler, wenn zwei Szenarien in Operatoren und Kennzahlen
identisch sind, wenn „konservativ" Kontrollen verändert, oder wenn „agent-nativ" bei
irreversiblen Entscheidungen keinen einzigen Human Touchpoint behält. Er warnt, wenn ein
späteres Szenario weniger automatisiert als ein früheres.

Konservativ ist kein Strohmann. Es kommt vor, dass es gewinnt — und dann ist es das
wertvollste Ergebnis der ganzen Analyse, weil es eine teure Umstellung verhindert.

### Belastbarkeit

Jede zugesagte Kennzahl trägt ihre Belastbarkeit: `estimated`, `expert_confirmed`,
`observed`. Ein Durchlaufzeitgewinn über 90 %, der ausschließlich geschätzt ist, löst eine
Warnung aus. Nicht, weil er falsch wäre — sondern weil eine solche Zahl ohne Pilot in
jeder Diskussion zu Recht zerlegt wird und dann den ganzen Entwurf mitnimmt.

## Selbstprüfung vor dem Lauf

1. Habe ich zuerst nach Streichungen gesucht, oder gleich automatisiert?
2. Welcher Schritt hat die größte Liegezeit — und warum steht er noch da, wo er steht?
3. Wer prüft in meinem Soll-Prozess noch etwas, das schon jemand geprüft hat?
4. An welchen drei Stellen entscheidet ein Mensch, und warum genau dort?
5. Welche einzelne Annahme würde, wenn sie falsch ist, den ganzen Entwurf kippen —
   und steht sie unter `open_assumptions`?
