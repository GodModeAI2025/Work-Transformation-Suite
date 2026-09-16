# Extraktionsformat `10_extraction/extract_<quelle>.json`

Eine Datei je Quelldokument (oder je Jobcluster, wenn eine Quelle mehrere Cluster enthält).
Dateiname: `extract_` + Kleinbuchstaben-Slug der Quelle, z. B. `extract_stellenbeschreibung_sachbearbeiter_vertrag.json`.
Die Dateien werden von `build_graph.py` alphabetisch gelesen; bei gleichen Rollen in mehreren Dateien
gewinnt die alphabetisch erste Datei für Texte, Aufgaben und Skills werden vereinigt.

```json
{
  "source": "00_input/Stellenbeschreibung_Sachbearbeiter_Vertrag.pdf",
  "job_family": "Kundenservice",
  "job_family_description": "Alle Rollen mit direktem oder indirektem Kundenkontakt im Vertriebsgeschäft.",
  "job_cluster": "Vertragsmanagement",
  "job_cluster_description": "Anlage, Änderung und Beendigung von Energielieferverträgen.",
  "roles": [
    {
      "name": "Sachbearbeiter Vertragsmanagement",
      "level": "Sachbearbeitung",
      "purpose": "Stellt sicher, dass Vertragsänderungen korrekt, fristgerecht und regelkonform im Abrechnungssystem umgesetzt werden.",
      "description": "Bearbeitet Ein- und Auszüge, Tarifwechsel und Stammdatenänderungen; klärt Rückfragen mit Kunden und Netzbetreibern; prüft Plausibilität der Abrechnungsdaten.",
      "headcount": 24,
      "archetype": "process-heavy",
      "regulated": true,
      "is_new": false,
      "time_shares_source": "estimated",
      "skills": [
        {"name": "Energiewirtschaftliche Marktprozesse (GPKE/GeLi Gas)", "kind": "knowledge", "category": "Energiewirtschaft", "level": 4, "importance": "core"},
        {"name": "SAP IS-U", "kind": "tool", "category": "IT-Systeme", "level": 3, "importance": "core"},
        {"name": "Schriftliche Kundenkommunikation", "kind": "skill", "category": "Kommunikation", "level": 3, "importance": "supporting"}
      ],
      "tasks": [
        {
          "name": "Ein- und Auszüge im Abrechnungssystem verarbeiten",
          "description": "Eingehende Meldungen (Portal, Brief, Marktkommunikation) prüfen, im System anlegen und Bestätigung auslösen.",
          "workflow_steps": [
            "Meldung im Eingangskorb sichten und Vollständigkeit prüfen",
            "Kundendaten und Zählpunkt gegen Stammdaten abgleichen",
            "Vorgang in SAP IS-U anlegen und Marktkommunikation auslösen",
            "Bestätigung an Kunden versenden"
          ],
          "share_of_time": 35,
          "frequency": "daily",
          "nature": "cognitive",
          "confidence": "source",
          "skills": ["SAP IS-U", "Energiewirtschaftliche Marktprozesse (GPKE/GeLi Gas)"]
        }
      ]
    }
  ]
}
```

## Felder

| Feld | Pflicht | Erlaubte Werte / Hinweis |
|---|---|---|
| source | ja | Pfad relativ zum Projektordner |
| job_family, job_cluster | ja | Freitext, konsistent über alle Dateien (gleiche Schreibweise!) |
| roles[].name | ja | Offizieller Rollentitel ohne Level-Zusatz, Singular, männliche oder neutrale Form konsistent |
| roles[].level | nein | z. B. Sachbearbeitung, Spezialist, Teamleitung, Referent, Experte |
| roles[].purpose | ja | Ein Satz: Wozu gibt es die Rolle? |
| roles[].description | ja | 2–4 Sätze |
| roles[].headcount | nein | Ganzzahl, nur wenn in der Quelle oder vom Nutzer genannt |
| roles[].archetype | ja | control-heavy, knowledge-heavy, process-heavy, relationship-heavy, creative-heavy, physical-heavy |
| roles[].regulated | ja | true, wenn gesetzliche/aufsichtliche Anforderungen die Ausführung binden |
| roles[].is_new | ja | true nur für Rollen, die es heute noch nicht gibt (z. B. vorgeschlagene Agent-Manager-Rolle) |
| roles[].time_shares_source | ja | source, wenn die Zeitanteile aus der Quelle oder vom Nutzer stammen; estimated, wenn du sie aus dem Berufsbild geschätzt hast. Bestimmt die Belastbarkeitsstufe der Rolle. |
| roles[].skills[] | ja | 5–12 Einträge; name aus references/skill-taxonomy.md, wenn dort vorhanden |
| skills[].kind | ja | knowledge, skill, competence, tool |
| skills[].level | ja | 1 Grundkenntnisse … 5 Experte |
| skills[].importance | ja | core (max. 5 je Rolle) oder supporting |
| roles[].tasks[] | ja | 5–12 Aufgaben, die zusammen die Arbeitszeit vollständig abdecken |
| tasks[].name | ja | Verb-Objekt-Form: „Rechnungen prüfen", nicht „Rechnungsprüfung" |
| tasks[].workflow_steps | ja | 3–6 Schritte in Ausführungsreihenfolge |
| tasks[].share_of_time | ja | Prozent der Arbeitszeit, Summe je Rolle ≈ 100 (das Skript normalisiert) |
| tasks[].frequency | ja | daily, weekly, monthly, quarterly, adhoc |
| tasks[].nature | ja | cognitive (Bildschirmarbeit, Kommunikation), physical (vor Ort, Handarbeit), mixed |
| tasks[].confidence | ja | source (steht so in der Quelle) oder inferred (aus Berufsbild ergänzt) |
| tasks[].skills | ja | 1–4 Skillnamen, exakt wie in roles[].skills geschrieben |

## Was das Skript daraus macht

- IDs: `ro_` + Hash(Familie|Cluster|Rolle), `ta_` + Hash(Rolle|Aufgabe), `sk_` + Hash(Skillname).
  Gleiche Namen ergeben in jedem Lauf dieselben IDs; ein umbenannter Task bekommt eine neue ID
  und verliert Bewertungen und Overrides. Deshalb Namen nur ändern, wenn nötig.
- Zeitanteile werden je Rolle auf 100 normalisiert, der Rohwert bleibt in `share_of_time_raw`.
- Skills werden über den normalisierten Namen dedupliziert („SAP IS-U" und „sap is u" sind ein Skill).
- Bewertungen (scores), Status und Agentenzuordnung bereits vorhandener Tasks bleiben erhalten.
