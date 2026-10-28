# Kontext aus Dokumenten statt aus Fragen

Der Arbeitsgraph kennt Rollen, Aufgaben, Prozesse und Systeme. Er kennt keine Person: nicht ihre Prioritäten, nicht ihren Ton, nicht, was sie nervt. Das lässt sich
erfragen (Interview-Prompt im Setup-Paket) — oder aus Material holen, das ohnehin existiert. Dieses Dokument beschreibt den zweiten Weg.

Beides ergänzt sich. Das Material liefert **Vorschläge mit Quelle**; die Person bestätigt oder verwirft sie. Das Interview schließt, was das Material nicht hergibt.

## Wohin mit dem Material

```
00_input/kontext/
├── firma/                   Texte über das Unternehmen: Über-uns, Leitbild, Produktseiten, Geschäftsbericht als Text
└── <rolle>/                 Ordnername = Rollenname in Kleinbuchstaben, Umlaute aufgelöst (Forderungsmanager → forderungsmanager)
    ├── texte/               eigene Texte: Mails, Beiträge, Notizen — daraus wird der Stil gemessen
    ├── transkripte/         Meeting-Transkripte
    └── projekte/            Projektdokumente, Protokolle, Statusberichte
```

`extract_context_evidence.py --project <projekt>` liest Textdateien (.md, .txt, .csv, .json, .srt, .vtt) und schreibt `30_review/kontext_evidenz/firma.json`,
`<rolle>.json` und eine lesbare `kontext_evidenz.md`. Danach erzeugt `build_rollen_md.py` oder `build_role_setup.py` die Rollen.md mit den Vorschlägen.

## Was woher kommt

| Feld der Rollen.md | Material | Wie es gewonnen wird |
|---|---|---|
| Geschäftsmodell, Kunden, Produkte | `firma/` | Sätze mit Mustern wie „wir sind“, „unsere Kunden“, „Portfolio“, ganze Sätze mit Zeile |
| Markt und Branche | `firma/` | Zählung von Branchenbegriffen (Treffer stehen im Zitat) |
| Sprachgebrauch im Haus | `firma/` | häufige Fachbegriffe, gezählt |
| Zeitfresser aus deiner Sicht | Transkripte, Projektdokumente | Zeilen mit Reibungswörtern („dauert“, „manuell“, „Medienbruch“, „doppelt“, „Excel“ …) |
| Bevorzugter Kanal je Anlass | Transkripte | Zeilen, in denen ein Kanal (E-Mail, Chat, Telefon, Ticket …) mit einem Vorgang genannt wird |
| Woran du gerade arbeitest | Transkripte, Projektdokumente | Zeilen mit „Priorität“, „Fokus“, „Deadline“, „Action Item“ |
| Ziele dieses Quartals | Transkripte, Projektdokumente | Zeilen mit „Ziel“, „OKR“, „Meilenstein“, „KPI“ |
| Tonalität, Formate | `texte/` | **Messung:** Anrede je Text (informell oder Sie), Satzlänge, Listenanteil, Absatzlänge, Ausrufezeichen, Emojis |
| Do's für KI-Texte | `texte/` | wiederkehrende Wendungen und Schlussformel, gezählt |
| Don'ts für KI-Texte | `texte/` | typische KI-Floskeln, die in den eigenen Texten **nie** vorkommen — ein Befund, keine Vermutung |

Nicht aus Material gewonnen werden: Qualitätsverständnis, gewünschte Rückfrage, „was der Agent nie ohne Rückfrage tun soll“. Das sind Entscheidungen; sie bleiben offen.

## Regeln

1. **Vorschlag, nie Tatsache.** In der Rollen.md steht jeder Eintrag als „✎ Vorschlag aus Dokument — bitte bestätigen“ mit Quelle und Fundstelle. Erst wenn die Person die
   Datei bearbeitet (Markierung entfernt, Text angepasst), gilt er. Das Skript überschreibt bearbeitete Dateien nicht.
2. **Zitat und Quelle sind Pflicht.** Ein Eintrag ohne Zitat, Quelle oder Text wird beim Laden abgelehnt und gemeldet. So bleibt jede Aussage zum Originaltext zurückverfolgbar.
3. **Messen, nicht raten.** Ein Stilprofil entsteht erst ab drei Texten und 600 Wörtern; darunter steht „zu wenig Material“ mit der Zählung. Die Anrede wird je Text bestimmt:
   Wer intern „ihr“ und Kunden „Sie“ schreibt, bekommt „je nach Adressat“, nicht ein einziges Etikett.
4. **Don'ts nur mit Befund.** „Nie vorgekommen“ in den eigenen Texten ist ein Befund. Es bleibt ein Vorschlag, denn ein kleiner Textkorpus beweist nichts.
5. **Personendaten.** E-Mail-Adressen, Telefonnummern und Anreden mit Namen („Hallo Anna“, „Herr Meier“) werden maskiert; Personennamen werden **nicht** automatisch
   gesucht oder gespeichert. Die Maskierung ist eine Heuristik, kein Anonymisierungsverfahren. Transkripte enthalten Daten Dritter: nur mit Einverständnis aller
   Beteiligten ablegen, am besten vorher kürzen. Es werden nur kurze Zitate (höchstens 220 Zeichen) gespeichert, nie ganze Dokumente.
6. **Freiwillig.** Niemand muss Material abgeben. Eigene Texte und Transkripte einer Person gehören ihr; sie entscheidet, was in den Ordner kommt.

## Was Claude ergänzt

Das Skript liest nur Textdateien. PDF, Word, Mails, Kalender und Chat-Verläufe liest Claude (bei verbundenen Werkzeugen auch direkt), und trägt die Funde im selben Format
in `30_review/kontext_evidenz/<rolle>.claude.json` ein:

```json
{
  "schema": "kontext-evidenz-1",
  "scope": "rolle",
  "role": "Forderungsmanager",
  "entries": [
    {"field": "prio.aktuell", "text": "Umstellung der Mahnstufen bis Jahresende",
     "quote": "…wir stellen die Mahnstufen bis Jahresende um…", "source": "Statusmail 2026-10-12.eml",
     "locator": "Absatz 2", "by": "claude", "confidence": "medium"}
  ]
}
```

Zulässige Felder: `firma.geschaeftsmodell`, `firma.kunden`, `firma.markt`, `firma.produkte`, `firma.sprachgebrauch`, `rolle.zeitfresser`, `team.kanaele`, `prio.aktuell`,
`prio.ziele`, `stil.ton`, `stil.format`, `stil.dos`, `stil.donts`. Für Firmenangaben gilt derselbe Aufbau mit `scope: "firma"` in `firma.claude.json`.
Claude erfindet nichts: Was nicht im Material steht, wird nicht eingetragen. Ein wörtliches Zitat ist Pflicht.

## Grenzen

- Die Muster sind Heuristiken. Ein Satz mit „Ziel“ ist nicht immer ein Ziel, und „Excel“ in einer Zeile nicht immer ein Zeitfresser. Deshalb Vorschlag und Bestätigung.
- Ein Stilprofil aus acht Mails beschreibt diese acht Mails, nicht die ganze Person. Andere Textsorten (Vortrag, Bericht) klingen anders.
- Transkripte unterscheiden Sprechende nur als „Sprecher 1“. Die Suite ordnet keine Aussage einer Person zu.
