# Quellen dieses Beispiels

Die Rollen- und Prozessbeschreibungen sind erfunden. Sie bilden einen typischen
Order-to-Cash-Bereich eines mittelständischen Industrieunternehmens nach, enthalten aber
keine echten Personen-, Kunden- oder Unternehmensdaten.

Reale Projekte legen hier ihre Quelldokumente ab: Stellenbeschreibungen, Organigramme,
Rollenlisten aus dem HR-System, Prozessdokumentationen, Prozess-Mining-Exporte.

| Datei | Inhalt | Wofür |
|---|---|---|
| `stellenbeschreibungen.md` | Fünf Rollen des Bereichs | Grundlage für `10_extraction/extract_order-to-cash.json` |
| `prozessaufnahme.md` | Zwei End-to-End-Prozesse mit Zeiten | Grundlage für `10_extraction/process_order-to-cash.json` |
| `sources/` | Dieselben zwei Dateien, registriert: treue Fassung mit `source_id`, dazu `register.jsonl` | Belege `src-…@#anker` in den Extraktionen; `check_evidence.py` prüft sie |

Die Zahlen der Prozessaufnahme stammen im Beispiel teils aus einem ERP-Export
(`observed`), teils aus dem Workshop (`estimated`). Dieser Unterschied ist überall in der
Suite sichtbar und wird nie eingeebnet.
