---
name: transformation-dashboard
description: "Erzeugt aus einem bewerteten work-graph (nach work-graph-builder, task-scorer, agent-mapper) deterministisch ein eigenständiges HTML-Dashboard im Corporate Design (Farben und Schriften per Theme-Datei) mit Rollenmatrix (Automatisierungspotenzial vs. menschliches Urteil), Rollenanalyse mit Disruptionsscore und nächstem Schritt, Agentenbibliothek mit Rollenabdeckung, Rollout-Plan und Tabellenansicht, dazu CSV-Exporte und einen Markdown-Kurzbericht. Vierter Schritt der Work-Transformation-Suite. IMMER verwenden bei: AI Transformation Dashboard, Rollenmatrix visualisieren, Disruptions-Dashboard, Workforce-Transformation zeigen, Ergebnis der Rollenbewertung präsentieren, Agentenlandkarte darstellen, Rollout-Plan je Rolle, Bericht aus work-graph, CSV-Export der Rollenbewertung, 'zeig mir das Ergebnis', 'mach ein Dashboard aus der Analyse', Dashboard wie bei kommerziellen Work-Architecture-Plattformen — auch wenn der Nutzer nur sagt 'jetzt bitte visualisieren' und ein Projektordner mit work-graph existiert."
---

# transformation-dashboard

Das Dashboard ist eine Ansicht auf den Graphen, nichts weiter. Es enthält keine eigene Logik,
keine neuen Bewertungen, keine Texte, die nicht aus dem Graphen kommen. Wenn im Dashboard
etwas falsch aussieht, ist der Graph falsch; dann zurück zu `task-scorer` oder `agent-mapper`,
nicht am HTML schrauben. Das ist der Grund, warum das Ergebnis reproduzierbar bleibt:
`build_dashboard.py` erzeugt aus demselben Graphen byteidentisches HTML.

## Ablauf

### 1. Bauen

```
python3 <skill>/scripts/build_dashboard.py --project ./projekte/<name> [--title "..."] [--stamp "15.09.2026"]
```

Ergebnis in `40_output/` (NNN = Graph-Version):

- `dashboard_vNNN.html`: eine Datei, ohne externe Ressourcen, offline nutzbar, Corporate-Farbwelt (per Theme-Datei anpassbar)
- `roles_vNNN.csv`, `tasks_vNNN.csv`, `agents_vNNN.csv`: alle Werte, Semikolon-getrennt, UTF-8
- `processes_vNNN.csv`, `blueprints_vNNN.csv`: nur wenn Prozesse erfasst sind
- `report_vNNN.md`: Kurzbericht mit Kennzahlen, Rollentabelle, Agententabelle, Prozessportfolio

`--stamp` schreibt ein Datum in die Kopfzeile. Ohne `--stamp` ist die Datei byteidentisch
reproduzierbar (nützlich für Diffs zwischen Versionen). Für Präsentationen ist `--stamp` sinnvoll.

Sobald der Graph Prozesse enthält, ist die **Prozessansicht die Hauptansicht**: Portfolio,
Ist/Soll je Prozess mit umschaltbaren Szenarien, Pilotkarten und ein Governance-Abschnitt. Die
Rollenansicht bleibt vollständig erhalten, rückt aber dahinter — als Folgenansicht des
Prozessredesigns. Das ist Absicht: Sobald Organisationskästchen zuerst kommen, wird das
Organigramm zum Designobjekt, und genau das verhindert ein Redesign vom Ergebnis her.

Ohne Prozesse verhält sich das Dashboard wie bisher und zeigt die Rollenansicht zuerst.

Die Szenarien schalten über verborgene Radiobuttons um, ohne JavaScript. Das Dashboard bleibt
damit auch in Dateivorschauen bedienbar, in denen kein Skript ausgeführt wird.

### 2. Ansehen und prüfen

Öffne das HTML nicht nur, sondern prüfe drei Dinge, bevor du es weitergibst:

- Rollenmatrix: Liegen Punkte so, wie es der Fachbereich erwarten würde? Eine
  Sachbearbeitungsrolle links oben („Geschützt") ist meist eine Bewertung mit zu hohem Urteil.
- Rollenanalyse: Sind die „nächsten Schritte" bei eliminierten Rollen mit Bedacht formuliert?
  Die Texte kommen aus einer festen Tabelle im Scorer; wenn der Nutzer andere Formulierungen
  will, gehören sie dort hin (`TRANSFORMATION_LOGIC` in `task-scorer/scripts/score_roles.py`).
- Agentenbibliothek: Trägt ein Agent mehr als die Hälfte aller Abdeckungspunkte? Dann zurück
  zum `agent-mapper` und teilen.
- Prozessansicht (wenn vorhanden): Steht über einem Prozess der Hinweis, dass das Modell die
  gemessene Durchlaufzeit nicht erklärt? Dann sind die Deltas darunter auf zu kleiner Grundmenge
  gerechnet — das gehört in deine Einordnung, nicht ins Kleingedruckte. Und: Kippt ein
  Prioritätsband schon bei ±1? Dann ist die Reihenfolge eine Richtung, keine Rangfolge.

Der Nutzer kann das Dashboard nicht im Chat sehen. Übergib die Datei (SendUserFile) und, wenn ein
Ordner verbunden ist, lege sie dort ab. Wenn der Nutzer das Dashboard teilen will, veröffentliche
es als Artifact; die Datei ist dafür bereits vollständig eigenständig.

### 3. Berichten

Wenn Prozesse erfasst sind, beginne mit ihnen: welcher Prozess zuerst und in welchem Band,
welches Szenario wie viel gegenüber dem konservativen bringt, wie viele Ausgangswerte gemessen
und wie viele geschätzt sind, und welche Pflichtkontrollen für das empfohlene Szenario angefasst
werden müssen. Die Rollenwirkung kommt danach — sie ist die Folge, nicht der Ausgangspunkt.

Nenne dem Nutzer außerdem: Version, Verteilung der Disruptionstypen, die drei Rollen mit dem
höchsten Score, die drei priorisierten Agenten mit FTE-Äquivalent, den Anteil ungeprüfter Rollen,
und die Belastbarkeits- und Stabilitätsverteilung (wie viele Rollen ungeprüft, wie viele grenznah
oder wackelig). Eine Rollenkarte, in der alle Rollen „ungeprüft" sind, ist ein Gesprächsangebot
an den Fachbereich, kein Ergebnis; sag das so. Weise
darauf hin, dass alle Werte KI-generiert und durch Overrides überschreibbar sind, und dass die
Rollenkarten die Begründungen je Aufgabe enthalten (aufklappbar), damit Fachexperten
widersprechen können.

## Gestaltung

Farben und Schriften kommen aus `assets/theme.json`. Für ein Corporate Design eine Kopie anlegen,
Primär- und Akzentfarbe, Schriftstacks und bei Bedarf die Typfarben ändern und mit
`--theme ./mein-theme.json` übergeben. Standard: Primärton `#0F5F57`, Akzent `#852BCA`
(Delegation, Transformiert). Disruptionstypen Eliminiert `#931F29`, Transformiert `#852BCA`,
Augmentiert `#2287A0`, Entstehend `#647B0A`, Stabil `#455663`, Ohne Bewertung `#9A9A9A`.
Geprüft mit CIEDE2000 über Normalsicht, Deuteranopie, Protanopie und Tritanopie: der kleinste
Abstand zwischen zwei Typfarben ist 8,6 (engstes Paar Augmentiert/Entstehend unter Tritanopie).
Alle fünf Typfarben liegen über 3:1 Kontrast zur Fläche, die graue Fläche für unbewertete Rollen
bei 2,7. Punkte tragen zusätzlich Textlabels, dazu gibt es die Tabellenansicht.
Wer Typfarben ändert, sollte sie erneut validieren. Schriften: System-Stack (Segoe UI/system-ui);
Corporate-Fonts müssen auf dem Zielrechner installiert sein, da keine Webfonts geladen werden.
Keine externen Skripte, keine Webfonts, kein Tracking.

Wer das Layout ändern will, ändert `CSS`, `JS` oder die Bausteinfunktionen in
`scripts/build_dashboard.py` und baut neu. Handbearbeitetes HTML geht beim nächsten Lauf verloren.

## Ab Schema 1.2

Die **Aufgabenkarte** zeigt alle bewerteten Aufgaben quer über alle Rollen: Automatisierungspotenzial gegen Urteil, Größe nach
gebundener Arbeit (FTE, sonst Prozent), Farbe nach Modus, schwarzer Rand bei teurer Fehlerfolge. Darunter die Rangliste nach
Exposition (Potenzial ÷ 10 × gebundene Arbeit). **Exposition und Fehlerfolge sind getrennte Spalten:** Was am meisten Arbeit bindet
und gut automatisierbar ist, ist nicht automatisch das, was man delegieren sollte.

Das Dashboard zeigt zusätzlich, sobald Daten vorliegen: **Kapazität** (technisch gegenüber auffangbar je Jobfamilie), **Zielbild** je
Rolle, **Nutzungsstand** je Rolle und Agent (unterdrückt unter 5 Stellen) sowie **Reichweite und Blindflecken**. Die Agentenbibliothek
zeigt den Evidenzgrad.

Neben `report_vNNN.md` entstehen zwei Berichte aus demselben Graphen: `report_hr_vNNN.md` (Kapazität, Zielbild, Rahmen — für HR) und
`report_it_vNNN.md` (Backlog nach Wert, Use Cases, Prozessbänder, Blindflecken — für IT). Die Sprache im HR-Bericht ist bewusst:
„Rolle verändert sich“, nie „Rolle entfällt“. Alle Zahlen sind Schätzungen; wo etwas nicht bewertet ist, steht „nicht bewertet“.

## Ab Schema 1.4: Sicht der Beschäftigten

Liegt eine Befragung vor (Skill `agency-audit`), zeigt der Abschnitt **Sicht der Beschäftigten** die Landschaft aus Wunsch (1–5)
und Automatisierungspotenzial (0–10) je Aufgabe mit den vier Zonen, die Matrix der Beteiligung (gewünschte gegen nötige HAS-Stufe),
Reibung und Abdeckung je Rolle und die Zonen je Cluster. Farben der Zonen stehen in `assets/theme.json` (`zone_colors`).

Der HR-Bericht nennt die Vorsichtszone und die Aufgaben, bei denen mehr Beteiligung gewünscht ist, der IT-Bericht die latente
Nachfrage (gewünscht, ohne Vorhaben), Agenten auf überwiegend ungewollter Arbeit und Nutzung gegen Wunsch. Der HR-Bericht enthält
außerdem die **Kompetenzverschiebung** je Skill (nötige Human Agency gegen heute gebundene Arbeit) aus `task-scorer`.

Ohne Befragung bleibt das Dashboard, wie es war. Berichte nie über einzelne Personen: Alle Zahlen sind Zusammenfassungen ab fünf
Antworten.

Unter der Aufgabenkarte steht, sobald Aufgabencluster vorliegen, die Tabelle **Wiederkehrende Aufgaben über Rollen**. Kandidaten sind als
solche gekennzeichnet; verworfene Cluster erscheinen nicht.
