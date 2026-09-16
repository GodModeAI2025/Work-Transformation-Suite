# Kanonische Skill-Taxonomie (Arbeitsversion, ESCO-orientiert)

Zweck: gleiche Fähigkeiten in allen Rollen gleich benennen, damit Skills über Rollen hinweg
vergleichbar und deduplizierbar sind. Wenn eine Fähigkeit hier steht, den Namen exakt übernehmen.
Fehlt sie, einen neuen Namen in derselben Form bilden (Substantiv, deutsch, ohne Firmenjargon)
und die Kategorie aus der Liste wählen. Neue Namen bitte am Ende der Extraktion in einem Kommentar
im Chat nennen, damit sie in diese Liste aufgenommen werden können.

Die vier Arten (`kind`): knowledge = Wissen über einen Gegenstand, skill = erlernte Tätigkeit,
competence = überfachliche Fähigkeit, tool = konkretes System oder Werkzeug.

## Energiewirtschaft (knowledge)
- Energiewirtschaftliche Marktprozesse (GPKE/GeLi Gas)
- Netzregulierung und Anreizregulierung
- Energiehandel und Portfoliomanagement
- Bilanzkreismanagement
- Messstellenbetrieb und Smart Metering
- Erneuerbare Energien und EEG-Abwicklung
- Netzanschluss und Netzbetrieb Strom
- Netzanschluss und Netzbetrieb Gas
- Wärmeversorgung und Contracting
- Elektromobilität und Ladeinfrastruktur
- Energierecht (EnWG, EEG, MsbG)
- Kritische Infrastruktur und IT-Sicherheit (KRITIS, NIS2)

## Kaufmännisch und Finanzen (knowledge/skill)
- Abrechnung und Fakturierung
- Forderungsmanagement und Mahnwesen
- Controlling und Budgetplanung
- Rechnungswesen (HGB/IFRS)
- Beschaffung und Vergaberecht
- Vertragsrecht und Vertragsgestaltung
- Datenschutz (DSGVO)
- Compliance und interne Kontrollsysteme
- Risikomanagement
- Nachhaltigkeitsberichterstattung (CSRD/ESG)

## Kundenservice und Vertrieb (skill)
- Schriftliche Kundenkommunikation
- Telefonische Kundenberatung
- Beschwerdemanagement
- Angebotserstellung und Kalkulation
- Kundenbedarfsanalyse
- Verhandlungsführung
- Key-Account-Management
- Kampagnenmanagement
- Tarif- und Produktwissen Energie

## Technik und Betrieb (skill/knowledge)
- Störungsmanagement und Entstörung
- Instandhaltungsplanung
- Anlagenbetrieb Umspannwerke
- Arbeitssicherheit und Unfallverhütung
- Technische Dokumentation
- Projektplanung Netzausbau
- Geoinformationssysteme (GIS)
- Leitstellenbetrieb und SCADA
- Elektrotechnik Mittel- und Hochspannung
- Gastechnik und Rohrnetz

## Daten und IT (skill/tool)
- Datenanalyse und Reporting
- Datenqualitätsmanagement
- SQL und Datenbankabfragen
- Python für Datenanalyse
- Machine Learning und Prognosemodelle
- Prompt Engineering und KI-Nutzung
- KI-Output-Qualitätssicherung
- Workflow-Automatisierung (RPA, Low-Code)
- Anforderungsmanagement
- Softwareentwicklung
- IT-Architektur und Integration
- Cloud-Plattformen
- Cybersecurity-Grundlagen
- Testmanagement

## Systeme (tool)
- SAP IS-U
- SAP S/4HANA
- SAP SuccessFactors
- Salesforce
- Microsoft 365 (Excel, PowerPoint, Teams)
- Power BI
- ServiceNow
- Jira und Confluence
- CRM-Systeme
- Dokumentenmanagementsysteme
- Marktkommunikationssysteme (EDIFACT)

## Personal und Organisation (skill/knowledge)
- Personalgewinnung und Recruiting
- Personalentwicklung und Weiterbildung
- Arbeitsrecht und Mitbestimmung
- Vergütungsmanagement
- Personaladministration und Entgeltabrechnung
- Organisationsentwicklung
- Change Management
- Workforce Planning

## Führung und Zusammenarbeit (competence)
- Mitarbeiterführung
- Projektmanagement
- Agile Methoden (Scrum, Kanban)
- Prozessmanagement und Prozessoptimierung
- Stakeholdermanagement
- Moderation und Präsentation
- Entscheidungsfähigkeit unter Unsicherheit
- Konfliktlösung
- Priorisierung und Selbstorganisation
- Coaching und Mentoring

## Überfachlich (competence)
- Analytisches Denken
- Kreativität und Konzeptentwicklung
- Qualitätsbewusstsein und Sorgfalt
- Kundenorientierung
- Kommunikationsfähigkeit
- Lernbereitschaft
- Ethisches Urteilsvermögen
- Interkulturelle Kompetenz
- Englisch (Fachsprache)
- Resilienz und Belastbarkeit

## Hinweis zu ESCO

Die ESCO-Klassifikation der EU (esco.ec.europa.eu, kostenlos, CSV/JSON-LD, 28 Sprachen) enthält
rund 14.000 Skills und 3.000 Berufe. Wer ein `esco_uri` je Skill hinterlegen will, kann die
ESCO-CSV in `00_input/esco/` ablegen; das Feld ist im Schema vorgesehen, wird aber von keinem
Skript verlangt. Für Pilotprojekte reicht die obige Liste.
