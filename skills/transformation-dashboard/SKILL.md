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
- `report_vNNN.md`: Kurzbericht mit Kennzahlen, Rollentabelle, Agententabelle

`--stamp` schreibt ein Datum in die Kopfzeile. Ohne `--stamp` ist die Datei byteidentisch
reproduzierbar (nützlich für Diffs zwischen Versionen). Für Präsentationen ist `--stamp` sinnvoll.

### 2. Ansehen und prüfen

Öffne das HTML nicht nur, sondern prüfe drei Dinge, bevor du es weitergibst:

- Rollenmatrix: Liegen Punkte so, wie es der Fachbereich erwarten würde? Eine
  Sachbearbeitungsrolle links oben („Geschützt") ist meist eine Bewertung mit zu hohem Urteil.
- Rollenanalyse: Sind die „nächsten Schritte" bei eliminierten Rollen mit Bedacht formuliert?
  Die Texte kommen aus einer festen Tabelle im Scorer; wenn der Nutzer andere Formulierungen
  will, gehören sie dort hin (`TRANSFORMATION_LOGIC` in `task-scorer/scripts/score_roles.py`).
- Agentenbibliothek: Trägt ein Agent mehr als die Hälfte aller Abdeckungspunkte? Dann zurück
  zum `agent-mapper` und teilen.

Der Nutzer kann das Dashboard nicht im Chat sehen. Übergib die Datei (SendUserFile) und, wenn ein
Ordner verbunden ist, lege sie dort ab. Wenn der Nutzer das Dashboard teilen will, veröffentliche
es als Artifact; die Datei ist dafür bereits vollständig eigenständig.

### 3. Berichten

Nenne dem Nutzer: Version, Verteilung der Disruptionstypen, die drei Rollen mit dem höchsten
Score, die drei priorisierten Agenten mit FTE-Äquivalent, den Anteil ungeprüfter Rollen, und
die Belastbarkeits- und Stabilitätsverteilung (wie viele Rollen ungeprüft, wie viele grenznah
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
