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

### Bekannte Grenzen

Ein Soll-Prozess aus Interviews und Stellenbeschreibungen ist ein Entwurf, keine Prognose.
Für belastbare Zahlen braucht die Suite Prozessbeobachtungen, Systemdaten und gemessene
Ausgangswerte. Wo sie fehlen, steht „geschätzt" — in jeder Ausgabe, sichtbar.

## [0.1.0] — Arbeitsgraph und Agentenbibliothek

Fünf Skills: Arbeitsgraph aus Stellenbeschreibungen, Aufgabenbewertung nach sechs
Kriterien, Disruptionstyp je Rolle, Agentenbibliothek mit Rollenabdeckung und ein
Offline-Dashboard. Deterministische IDs, versionierte Graphstände, Expertenkorrekturen
über Overrides, Belastbarkeits- und Stabilitätsanzeige.
