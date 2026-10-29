# Referenzbibliothek: Branchen, Rechtsraum, Plattformprofile

Die Bibliothek unter `library/` ist ein Vorrat, kein Befund. Sie liefert, was sich branchenweit sagen lässt,
damit ein Projekt nicht bei null beginnt; was am Haus gilt, bestätigt das Haus. Drei Teile:

| Teil | Ort | Inhalt | Wirkung im Projekt |
|---|---|---|---|
| Branchenpakete | `library/branchen/<id>/` | Seiten (Cluster, Rollen, Aufgaben) im Format von `05_pages/` plus `quelle.md` mit Rollenprofilen und Rechtsgrundlagen | `seed_from_library.py` kopiert Seiten ins Projekt; Belege zeigen auf `quelle.md`, Belegstand „reference“ |
| Rechtsraum | `library/rechtsraeume/DE.json` | Themen mit Gesetz, Fundstelle, Pflicht und Stichwörtern | Review-Liste und Rollen.md nennen je Rolle die Themen, die sie berühren: Prüfaufträge, keine Rechtsberatung |
| Plattformprofile | `library/plattformen/<id>.json` | je Agentenmuster die Dienste eines Profils; Zuordnung abstrakter Werkzeuge (`mail.*`, `document.*`) | Capability Contracts und `tools/anbindungen.md` nennen die Umsetzung auf dem Profil des Hauses |

## Branchen

`library_catalog.py` zeigt den Bestand. Ausgeliefert werden dreizehn Pakete:

| Paket | Inhalt |
|---|---|
| `allgemein` | Querschnitt: Finanzen, Personal, Einkauf, IT, Recht und Compliance |
| `bauwirtschaft` | Kalkulation, Bauleitung, Planung, Abrechnung |
| `energieversorgung` | Netzbetrieb, Marktkommunikation, Messwesen, Handel, Regulierung |
| `wasserversorgung` | Wasserwerk, Rohrnetz, Labor, Abwasser |
| `automobilindustrie` | Entwicklung, Fertigungsplanung, Qualität, Lieferkette |
| `maschinenbau` | Vertrieb und Kalkulation, Konstruktion, Steuerungstechnik, Fertigung, Service, Exportkontrolle |
| `chemie_pharma` | Produktion, Qualitätskontrolle, Validierung, Sachkundige Person, Regulatory Affairs, Pharmakovigilanz |
| `gesundheitswesen` | Station, Patientenaufnahme, Medizincontrolling, Abrechnung, Hygiene, Medizintechnik, Apotheke |
| `oeffentliche_verwaltung` | Bürgerbüro, Ordnungsamt, Sozialleistungen, Bauaufsicht, Kämmerei, Personal, Digitalisierung |
| `handel` | Category Management, Disposition, Filiale, E-Commerce, Kundenservice, Retouren |
| `logistik` | Disposition, Fuhrpark, Lager, Gefahrgut, Zoll, Kundenbetreuung |
| `banken` | Privat- und Firmenkunden, Kredit, Zahlungsverkehr, Risikocontrolling, Meldewesen, Geldwäscheprävention |
| `versicherungen` | Underwriting, Bestand, Schaden, Leistung, Aktuariat, Vermittlerbetreuung, Compliance |

Jede Rolle hat einen Zweck,
eine Beschreibung, einen Archetyp, die Einstufung „reguliert“, fünf typische Aufgaben mit Zeitanteilen und Skills, und in
`quelle.md` die Rechtsgrundlagen (Deutschland) und typischen Systeme.

Die Zeitanteile sind typische Verteilungen (`time_shares_source: estimated`). Stellenzahlen sind leer. Beides füllt das Haus.

### Einspielen

```
python3 <skill>/scripts/init_project.py --project ./projekte/<name> --name "…" --branche energieversorgung --plattform microsoft --rechtsraum DE
python3 <skill>/scripts/seed_from_library.py --project ./projekte/<name> --branche energieversorgung [--cluster "Netzbetrieb"] [--rollen "Netzführer;Netzplaner"]
python3 <skill>/scripts/seed_from_library.py --project ./projekte/<name> --branche allgemein --rollen "Datenschutzbeauftragter;Controller"
```

`seed_from_library.py` registriert `quelle.md` als Quelle der Art „reference“ und kopiert die ausgewählten Seiten nach
`05_pages/`. Eine Seite, die dort schon existiert, bleibt unverändert; so überschreibt die Bibliothek nie, was jemand am
Haus angepasst hat. Ein Projekt mit Extraktionsdateien, aber ohne Seiten, geht zuerst durch `export_pages.py`.

### Kundenspezifisch machen

Die Seiten im Projekt sind nach dem Einspielen die Wahrheit. Was das Haus anders macht, wird dort geändert: Rollen
umbenennen oder streichen, Aufgaben ergänzen, Zeitanteile aus Interview oder Zeiterfassung eintragen
(`time_shares_source: source`, `confidence: source` mit eigenem Beleg), Stellenzahlen setzen, Skills anpassen. Ein Eintrag,
der einen Beleg aus eigenem Material bekommt, wechselt von „reference“ zu „belegt“; eine Rolle, die der Fachexperte
bestätigt, bekommt `status;reviewed` über `overrides.csv`.

Am Ende beschreibt der Graph das Haus, und der Belegbericht sagt, welche Aussagen noch aus dem Vorrat stammen.

## Rechtsraum

`DE.json` enthält Themen wie Mitbestimmung (§ 87 Abs. 1 Nr. 6 BetrVG), Datenschutz, KI-Verordnung, Buchführung,
Arbeitsschutz, Vergabe, Hinweisgeberschutz, Lieferkette sowie branchenspezifische Themen (EnWG und Marktkommunikation,
TrinkwV und WHG, VOB/B und BaustellV, Typgenehmigung, ISO 26262, IATF 16949). Jedes Thema hat Stichwörter; ein Thema mit
`"*"` gilt für jede Rolle, Branchenlisten begrenzen die Treffer.

`legal_topics()` in der Bibliothek gleicht Stichwörter gegen Rolle, Cluster, Familie, Aufgaben und Skills ab. Das Ergebnis
steht in der Review-Liste (Abschnitt „Rechtsrahmen“) und in der Rollen.md (Rollenprofil). Es ist ein Prüfauftrag: Ob ein
Thema greift und was es konkret verlangt, klärt das Haus mit Fachexperten oder Rechtsabteilung. Der Stand der Gesetze ist
der der Erstellung; Änderungen sind nachzuhalten.

Weitere Rechtsräume kommen als `library/rechtsraeume/<KÜRZEL>.json` dazu; das Projekt wählt mit `--rechtsraum`.

## Plattformprofile

Vier Profile: `microsoft` (Microsoft 365 und Azure), `google` (Google Workspace und Google Cloud), `mischbetrieb` (beides,
mit Regeln, wo was liegt) und `unabhaengig` (offene Schnittstellen, eigener Betrieb). Je Agentenmuster aus
`agent-mapper/references/agent-patterns.md` nennt ein Profil die Dienste, mit denen das Muster typischerweise umgesetzt wird,
und ordnet abstrakte Werkzeuge der Verträge (`mail.*`, `calendar.*`, `files.*`, `document.*`, `search.*`, `llm.*`,
`workflow.*`, `identity.*`) Diensten zu. Fachsysteme (`erp.*`, `crm.*`, `ticket.*`) bleiben Schnittstellen des jeweiligen
Systems, unabhängig vom Profil.

Die Vorschläge erscheinen in `40_output/contracts_vNNN.md` je Agent und in `tools/anbindungen.md` des Setup-Pakets. Sie sind
Vorschläge aus der Bibliothek, kein Beschaffungsentscheid: Dienstnamen und Verfügbarkeit ändern sich, Datenklassen und
Auftragsverarbeitung sind je Dienst zu prüfen. Die Verträge selbst bleiben anbieterneutral.

## Grenzen

- Die Bibliothek kennt typische Rollen, nicht die des Hauses. Was sie liefert, ist „reference“, bis es bestätigt ist.
- Rechtsgrundlagen sind Hinweise mit Fundstelle, keine Rechtsberatung, und sie veralten.
- Plattformvorschläge nennen Dienste, keine Architektur. Ob ein Dienst für eine Datenklasse zulässig ist, entscheidet das Haus.
- Prozesse enthält die Bibliothek nicht; Abläufe sind zu hausspezifisch, um sie als Vorrat zu halten.
