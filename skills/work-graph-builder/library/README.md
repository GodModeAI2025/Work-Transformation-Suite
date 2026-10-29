# Referenzbibliothek

Vorrat für neue Projekte: dreizehn Branchenpakete als Seiten, der Rechtsrahmen Deutschland und vier Plattformprofile.
Was hier steht, ist typisch, nicht gemessen; im Projekt gilt es als „reference“, bis das Haus es bestätigt.

- `branchen/<id>/`: Seiten im Format von `05_pages/` (clusters, roles, tasks) und `quelle.md`, auf die die Seiten mit
  `lib@#<rolle>` verweisen. `seed_from_library.py` ersetzt `lib@` durch die `source_id` der registrierten `quelle.md`.
- `rechtsraeume/DE.json`: Themen mit Gesetz, Fundstelle, Pflicht, Stichwörtern und Branchen. Stichwörter stehen in der
  Normalform von `normalize_name` (Kleinbuchstaben, Umlaute als einfache Vokale: `qualitat`, nicht `qualitaet`), weil nur
  so der Abgleich gegen Rollen, Aufgaben und Skills trifft; der Test prüft das.
- `plattformen/<id>.json`: je Agentenmuster die Dienste eines Profils, Zuordnung abstrakter Werkzeuge, Grundsätze.

Pflege: Seiten sind die Wahrheit eines Pakets. Eine neue Rolle braucht eine Rollenseite, ihre Aufgabenseiten und einen
Abschnitt `## <Rollenname>` in `quelle.md`; `tests/test_library.py` prüft, dass jedes Paket übersetzbar ist, jeder Anker
aufgeht und die Zeitanteile je Rolle 100 ergeben. Beschreibung in `references/referenzbibliothek.md`.
