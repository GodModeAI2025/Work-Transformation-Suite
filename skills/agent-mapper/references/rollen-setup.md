# Rollen-Setup: ein persönlicher Arbeitsagent je Rolle

Der Arbeitsgraph beschreibt eine Rolle von oben: Aufgaben, Zeitanteile, Systeme, Entscheidungen. Ein persönlicher Arbeitsagent braucht dieselben
Informationen von unten: Wer bin ich, wie arbeite ich, was darf der Agent, woran erkennt er ein gutes Ergebnis. `build_role_setup.py` übersetzt das
eine ins andere. Es ist das Bindeglied zwischen der Analyse („welche Aufgaben lohnen sich“) und dem, was eine Person am Montagmorgen tatsächlich
öffnet.

## Anfragen

```
python3 <skill>/scripts/build_role_setup.py --project ./mein-projekt --list
python3 <skill>/scripts/build_role_setup.py --project ./mein-projekt --role "Forderungsmanager"
python3 <skill>/scripts/check_role_setup.py --package 40_output/rollen_setup/forderungsmanager
```

Auf Zuruf („Baue das Setup für die Rolle X“) wird das Paket für genau diese Rolle erzeugt.

## Prinzipien und wie die Suite sie umsetzt

Die Grundstruktur stammt aus einem öffentlichen Playbook zum persönlichen KI-Setup (Stand Herbst 2026):
Rollen.md (Kontext), ein zentraler Agent, Skills, Tool-Anbindungen, Routinen. Die Vorlagen und Texte in diesem Paket sind eigene Formulierungen
nach dieser Struktur; die verlinkten Originalvorlagen des Autors wurden nicht übernommen.

| Prinzip | Umsetzung |
|---|---|
| Kontext zuerst | `kontext/Rollen.md` mit den fünf Abschnitten Firmenprofil, Rollenprofil, Team-Kontext, Prioritäten & Ziele, Arbeits- & Kommunikationsstil. Vorbelegt aus dem Graphen, Rest „offen“. Dieselbe Datei erzeugt `build_rollen_md.py` für eine oder mehrere Rollen |
| Die KI als Interviewer | `kontext/interview-prompt.md` füllt die offenen Felder; er verbietet Erfinden und lässt Graph-Zeilen nur mit Bestätigung ändern |
| Ein zentraler Agent, schlanker Prompt | `agent/systemprompt.md`: steuert nur die Zusammenarbeit (Kontext laden, einordnen, Skill wählen, prüfen, bei Lücke fragen). `check_role_setup.py` begrenzt die Länge |
| Wiederkehrende Aufgaben als Skills | Drei bis fünf Skills je Rolle, gewählt nach Zeitanteil × Automatisierbarkeit; gleicher Agent heißt ein Skill. Mit Capability Contract entsteht das Gerüst aus dem Vertrag (wie `export_skill.py`), sonst aus den Aufgabendaten |
| Jeder Skill mit echten Testfällen | `evals/cases.json` mit mindestens fünf Fällen (Standard, Variante, Randfall, fehlende Eingabe, Eskalation, bei Schreibrechten Wiederholung). Die Fälle sind Gerüste; `real_data` bleibt `false`, bis echte eingetragen sind |
| Erst zwei bis drei Schleifen, dann live | `evals/protokoll.md`; Reifegrade `entwurf` → `im Test` → `live-reif` in `check_role_setup.py` |
| Werkzeuge anbinden — mit Leitplanken | `tools/anbindungen.md` aus den Systemen der Rolle. Datenklassen `personal` und `special_category` sind markiert, die Freigabe steht auf „offen“ |
| Routinen statt Vorsätze | `routinen/routinen.md` und `.json`: zeit- und ereignisbasierte Vorschläge, alle inaktiv; Sichtbarkeit des Agenten im Alltag |
| Erweitern vor Automatisieren | Eine Routine darf nur aktiv sein, wenn ihr Skill live-reif ist. `check_role_setup.py --strict` meldet jede Verletzung |
| Lebendes System | `pflege/pflege.md`; erneutes Erzeugen überschreibt keine bearbeitete Datei, der neue Stand liegt als `.vorschlag` daneben |

## Was aus dem Graphen kommt und was nicht

| Kommt aus dem Graphen | Weiß der Graph nicht (bleibt „offen“) |
|---|---|
| Organisation, Bereich, Sprache | Geschäftsmodell, Produkte, Sprachgebrauch im Haus |
| Rolle, Zweck, Beschreibung, Level, Aufgaben mit Zeitanteil | persönliche Prioritäten, woran „gut“ erkannt wird |
| Entscheidungsräume und Human Gates aus den Prozessen | wie viel Rückfrage gewünscht ist, was nie ohne Rückfrage geschehen darf |
| Zusammenarbeit (Übergaben, Stellen, Einheiten) | Namen von Führungskraft und Ansprechpersonen |
| Prozessergebnisse, Kennzahlen, Empfänger | Format, Tonalität, Detailgrad |
| Systeme, Datenklassen, Vertragsrechte | ob eine Anbindung freigegeben ist |

## Grenzen

- **Kein getesteter Agent.** Das Paket ist ein Startpunkt. Ein Skill aus Rollendaten kennt weder den echten Ablauf noch die Ausnahmen des Hauses.
- **Keine Zeitersparnis.** Die im Playbook genannten Spannen (etwa ein halber bis ein Arbeitstag pro Woche) sind Selbstauskünfte des Autors, keine Messung.
  Die Suite verwendet sie nirgends als Wert; belastbar ist nur, was in einem Pilot mit Ausgangswert gemessen wurde.
- **Kein Ersatz für Freigaben.** Die Tool-Tabelle gibt nichts frei. Datenschutz und Informationssicherheit entscheiden, nicht die Technik.
- **Personenbezogene Rollen.** Das Paket beschreibt eine Rolle, keine Person. Persönliche Angaben (Namen, Prioritäten) kommen erst im Interview dazu und gehören nicht in
  den Arbeitsgraphen.
