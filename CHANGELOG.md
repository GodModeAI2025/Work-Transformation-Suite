# Changelog

Alle nennenswerten Änderungen an der Work-Transformation-Suite. Die Versionen folgen
[Semantic Versioning](https://semver.org/lang/de/); die Version steht in
`.claude-plugin/plugin.json`.

## [0.2.0] — Vom Arbeitsgraphen zum KI-nativen Betriebsmodell

Bis 0.1 beantwortete die Suite eine Frage: **Welche heutige Arbeit kann KI übernehmen?**
Diese Version ergänzt die zweite Hälfte: **Wie sähe der Prozess aus, wenn man ihn vom
gewünschten Ergebnis aus neu bauen würde — und woran misst man, ob das besser ist?**

Der Auslöser ist eine einfache Beobachtung: Wenn fünf Rollen nacheinander dieselben Daten
prüfen, findet die Diagnose fünf automatisierbare Aufgaben und schlägt einen Agenten vor.
Ein Redesign streicht vier Prüfungen, drei Übergaben und zwei Datenumformungen — und der
Rest braucht gar keinen Agenten mehr. Wert entsteht auf der Ebene des Ablaufs, nicht der
Einzelaufgabe.

Der Diagnosemodus bleibt vollständig erhalten. Ein Projekt darf darin bleiben.

### Neu

- **Schema 1.1 mit Prozessebene.** Die Sammlungen `outcomes`, `systems`, `controls`,
  `metrics`, `processes`, `process_steps`, `process_edges`, `blueprints`, `experiments`,
  `provenance` und `decisions` ergänzen den Arbeitsgraphen additiv. Ein Prozess läuft über
  mehrere Rollen, Schleifen und bedingte Kanten sind erlaubt, eine Aufgabe kann mehreren
  Prozessen dienen.
- **Skill `process-redesigner`.** Erzeugt je Prozess drei vergleichbare Soll-Szenarien
  (konservativ, ausgewogen, agent-nativ) mit den sechs Operatoren eliminieren,
  vereinfachen, zusammenführen, parallelisieren, automatisieren und Human Gate erhalten.
  Rechnet Durchlaufzeit, Übergaben, Human Touchpoints und Nacharbeit gegen den
  Ist-Prozess.
- **Prozesswert statt FTE-Abdeckung.** Neun gewichtete Faktoren (Kundenwirkung, Finanzen,
  Durchlaufzeit, Qualität, Risiko, Lernwert, Integrations- und Veränderungsaufwand,
  Umkehrbarkeit) ergeben ein Prioritätsband statt einer Rangliste. Eine
  Sensitivitätsanalyse zeigt, ob das Band schon bei ±1 in einem einzelnen Faktor kippt.
  Gewichte stehen versioniert in `assets/value-weights.json`.
- **Capability Contracts für Agenten.** Auslöser, Ein- und Ausgaben, Werkzeuge, Lese- und
  Schreibrechte, Entscheidungsreichweite, Konfidenzschwelle, Kontrollpunkt, Rückfallebene,
  Zeitgrenze, Wiederholung, Idempotenzschlüssel, Audit-Ereignisse, Servicezusage,
  Testmenge und Kostendeckel — modellagnostisch. Export als JSON und Markdown.
- **Experiment- und Rolloutkarten.** Vier Designs (A/B-Test, Schattenbetrieb, gestaffelter
  Rollout, Vorher-Nachher) mit deterministischem Vorschlag, Guardrails, Stoppregeln und
  Rollback. Messwerte fließen als `observed` samt Provenienz in den Graphen zurück.
- **Ist/Soll-Dashboard.** Die Prozessansicht ist die neue Hauptansicht: Ist-Fluss,
  Szenarien zum Umschalten (ohne JavaScript), Delta-Kennzahlen, veränderte Kontrollen,
  offene Annahmen, Pilotkarten und ein Governance-Abschnitt. Die Rollenansicht bleibt
  vollständig, rückt aber dahinter — als Folgenansicht des Prozessredesigns.
- **Governance.** Feldprovenienz je Kennzahl (Quelle, Fundstelle, Ersteller, Reviewer,
  Konfidenz, Status), Entscheidungsrechte je automatisiertem Schritt, Datenklassifikation
  und ein Entscheidungslog in `30_review/decisions.csv`, das die Freigabestände setzt.
- **Referenzbeispiel `examples/order-to-cash/`.** Fünf Rollen, 21 Aufgaben, zwei
  End-to-End-Prozesse, acht Agenten mit Verträgen, sechs Blueprints, zwei Piloten
  (einer ausgewertet) und fünf Entscheidungen. Mit hinterlegtem Sollstand und Prüfsummen.
- **Testsuite.** 83 Tests über `python -m unittest discover`: Bibliothek, Validator,
  Redesign-Regeln, Prozesswert, vollständiger End-to-End-Lauf des Referenzbeispiels,
  Migration eines Schema-1.0-Projekts. CI läuft auf Python 3.9, 3.11 und 3.13.
- **Werkzeuge.** `tools/sync_shared.py` hält die Bibliothekskopien gleich,
  `tools/pack_skills.py` baut die `.skill`-Pakete deterministisch,
  `tools/refresh_example.py` erzeugt den Sollstand des Beispiels neu.

### Geändert

- `run_pipeline.py` kennt die Stufen `builder`, `processes`, `scorer`, `mapper`,
  `redesign`, `dashboard`. Der Redesignmodus schaltet sich ein, sobald Prozesse erfasst
  sind. Freigaben werden zuletzt angewendet, damit ein Neubau der Blueprints sie nicht
  überschreibt.
- `compute_coverage.py --shared-tasks` erlaubt mehreren Agenten dieselbe Aufgabe, weist
  Überschneidungen je Agent aus und meldet eine bereinigte Gesamtabdeckung. Ohne den
  Schalter bleibt es bei genau einem Agenten je nicht-manueller Aufgabe.
- Ein Orchestrator ohne eigene Aufgaben wird nicht mehr als Lücke gemeldet.
- `.gitignore` schließt nur noch die erzeugten Stände aus, nicht ganze Ordner — damit das
  Referenzbeispiel mit seinen Eingabedateien versioniert werden kann.

### Behoben

- `Path.write_text(newline=...)` gibt es erst ab Python 3.10. Dashboard und Bericht
  ließen sich unter Python 3.9 nicht schreiben, obwohl die Suite 3.9 zusagt. Alle
  Textausgaben laufen jetzt über `wl.write_text` mit fester Zeilenende-Konvention — das
  macht die Ausgaben zusätzlich plattformunabhängig byteidentisch.
- `save_graph_version` verglich den zu schreibenden Graphen mit einer bereits migrierten
  Fassung des gespeicherten Standes. Ein Schema-1.0-Projekt sah dadurch identisch aus und
  die Migration wurde nie auf die Platte geschrieben.
- Ein gemessener Pilotwert überschrieb den Ist-Ausgangswert derselben Kennzahl. Damit
  verglich sich der Soll-Zustand mit sich selbst. `baseline`, `target` und `observed` sind
  jetzt strikt getrennt.
- Ein erneuter Lauf verwarf im Pilot gemessene Werte und Freigabestände und legte deshalb
  jedes Mal eine neue Graph-Version an. Beides überlebt den Neubau.

### Behoben nach dem Code-Review dieses Stands

Ein Review des Schema-1.1-Stands hat sieben Fehler gefunden, ein Regressionstest dazu einen
achten. Alle waren reproduzierbar und sind behoben; für jeden gibt es jetzt einen Test in
`tests/test_regressions.py`.

- **Die Pipeline brach beim ersten Redesign-Durchgang ab.** Solange alle Entwürfe auf
  `draft` standen — dem dokumentierten Ausgangszustand — beendete sich `make_experiments.py`
  mit Code 2 und riss Szenarienvergleich, Freigaben und Dashboard mit. Pilotplanung ist
  jetzt ein Hinweis (Code 3), kein Abbruch.
- **Eine Umbenennung konnte ein Projekt dauerhaft blockieren.** IDs sind Hashes der Namen;
  der alte Provenienzeintrag zeigte danach ins Leere und der Validator lehnte jeden weiteren
  Lauf ab. `build_processes.py` sortiert verwaiste Provenienz jetzt aus und meldet es.
- **Ein Prozess ohne erfasste Zeiten ließ `build_blueprints.py` abstürzen** — nach dem
  Schreiben des Graphen, was wie ein gescheiterter Lauf aussah. Fehlende Prozentwerte
  werden jetzt als „–" dargestellt.
- **Ein namenloser Schritt verschwand still und zerriss die Schrittkette.** Er wird jetzt
  gemeldet, und die implizite Verkettung läuft über die benannten Schritte.
- **Eine zweite Prozessdatei löschte die Kennzahlverknüpfung eines Ergebnisses.** Ergebnisse
  werden zusammengeführt statt ersetzt.
- **`design: "ab_test"` ohne erfasste Jahresmenge** warf einen TypeError. Alle vier Designs
  vertragen jetzt eine fehlende Menge und benennen sie als Lücke.
- **Kennzahlen ganz ohne Ausgangswert zählten als „bestätigt oder gemessen"** und kehrten
  damit genau die Aussage um, für die der Satz existiert. Der Bericht unterscheidet jetzt
  drei Fälle.
- **Ein Eintrag ohne `id` ließ den Validator mit `KeyError` abstürzen** — ausgerechnet an
  dem Eintrag, dessen Fehler er gerade melden wollte. Der Fehler wird jetzt gemeldet, und
  `validate()` verändert den übergebenen Graphen nicht mehr.

### Geändert: Übergaben werden anders gezählt

Ist und Soll zählten Übergaben nach verschiedenen Regeln — das Ist jede Kante mit einem
Medium, das Soll jeden Wechsel des Ausführenden. Dadurch wies ein Entwurf, der **nichts**
änderte, eine Verbesserung aus. Beide Seiten verwenden jetzt dieselbe Regel: Eine Übergabe
ist ein Wechsel des Ausführenden, bei dem mindestens eine Seite ein Mensch ist. Zwei
Agenten, die innerhalb desselben Systems weiterreichen, kosten Millisekunden und zählen
nicht. Medienbrüche (E-Mail, Telefon, Papier) bleiben als eigener Ist-Befund erhalten,
gehen aber nicht in den Vergleich ein, weil ein Soll-Entwurf keine Medien modelliert.

Die Zahlen im Referenzbeispiel ändern sich dadurch, und zwar nach unten. „Auftrag bis
Rechnung" hat vier statt neun Ist-Übergaben, und das konservative Szenario weist bei dieser
Kennzahl jetzt −2 aus statt +3: Es setzt einen Agenten an beide Enden einer sonst
unveränderten Menschenkette und erzeugt damit zwei zusätzliche Wechsel. Dieses Ergebnis
bleibt so stehen — es ist der Befund, um den es geht.

### Nachgezogene Akzeptanzkriterien

Eine Gegenprobe gegen die Akzeptanzkriterien des Feedbacks hat drei Punkte gefunden, die
noch nicht erfüllt waren:

- **Freigabe setzt einen Kontrollpunkt voraus.** Ein Prozess mit hoher Fehlerfolge — unter
  Aufsicht, mit einer nicht umkehrbaren Entscheidung oder mit personenbezogenen Daten —
  lässt sich nicht mehr auf `approved` setzen, wenn kein einziger Schritt eine Kontrolle
  oder ein Human Gate trägt. Bisher galt diese Regel nur für Blueprint-Schritte, nicht für
  die Freigabe des Prozesses selbst.
- **Jede Delta-Zahl führt zu ihrer Annahme.** Begründungen und Annahmen lagen in den
  Szenario-Tafeln, also hinter einem Reiter und damit faktisch unauffindbar. Sie stehen
  jetzt in einem immer sichtbaren Block „Woher diese Zahlen kommen" mit Ausgangswerten,
  Belastbarkeit und Fundstelle; die Spaltenköpfe der Vergleichstabelle verlinken dorthin.
- **Release mit Prüfsummen und Changelog-Eintrag.** `.github/workflows/release.yml` prüft
  auf einem Tag die gesamte Suite, schneidet den Changelog-Abschnitt der Version heraus und
  hängt die `.skill`-Pakete samt `SHA256SUMS` an das Release. `tools/check_release.py`
  prüft, dass Tag, Version im Plugin-Manifest und Changelog-Abschnitt zusammenpassen — und
  läuft auch im normalen CI, damit die drei nicht auseinanderlaufen.

### Bekannte Grenzen

Ein Soll-Prozess aus Interviews und Stellenbeschreibungen ist ein Entwurf, keine Prognose.
Für belastbare Zahlen braucht die Suite Prozessbeobachtungen, Systemdaten und gemessene
Ausgangswerte. Wo sie fehlen, steht „geschätzt" — in jeder Ausgabe, sichtbar.

## [0.1.0] — Arbeitsgraph und Agentenbibliothek

Fünf Skills: Arbeitsgraph aus Stellenbeschreibungen, Aufgabenbewertung nach sechs
Kriterien, Disruptionstyp je Rolle, Agentenbibliothek mit Rollenabdeckung und ein
Offline-Dashboard. Deterministische IDs, versionierte Graphstände, Expertenkorrekturen
über Overrides, Belastbarkeits- und Stabilitätsanzeige.
