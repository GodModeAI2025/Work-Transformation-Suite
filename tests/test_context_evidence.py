"""Kontext aus Dokumenten: Vorschläge mit Quelle statt Fragen — und was sie nie sein dürfen.

Geprüft wird: Messung statt Raten (zu wenig Material, Anrede je Text), Zitat und Quelle als Pflicht, Maskierung von Personendaten,
Kennzeichnung als Vorschlag in der Rollen.md, und dass bearbeitete Dateien in Ruhe bleiben.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, ROOT, load, script  # noqa: E402

xe = load("agent-mapper", "extract_context_evidence")
rm = load("agent-mapper", "rollen_md")
inv = load("work-graph-builder", "inventory_sources")
PIPELINE = ROOT / "skills" / "work-transformation" / "scripts" / "run_pipeline.py"


def sample(n_words: int, **kw):
    base = ("Hallo Team, bitte kurz bestätigen, dass die Zuordnung so passt. Ich habe die offenen Posten gesichtet und drei Fälle herausgenommen. "
            "Der Mahnlauf wird erst danach freigegeben. Viele Grüße")
    words = base.split()
    reps = max(1, n_words // len(words))
    return " ".join([base] * reps)


class TestMasking(unittest.TestCase):
    def test_addresses_numbers_and_salutations_are_masked(self):
        t = xe.mask("Hallo Anna, schreib an anna.meier@firma.de oder ruf +49 170 1234567 an. Danke Herr Müller. @kollege", False)
        self.assertNotIn("anna.meier", t)
        self.assertNotIn("1234567", t)
        self.assertNotIn("Anna", t)
        self.assertNotIn("Müller", t)
        self.assertNotIn("@kollege", t)
        self.assertIn("[E-Mail]", t)

    def test_keep_names_leaves_salutations_but_never_addresses(self):
        t = xe.mask("Hallo Anna, anna@firma.de", True)
        self.assertIn("Anna", t)
        self.assertNotIn("anna@firma.de", t)

    def test_quotes_are_short(self):
        self.assertLessEqual(len(xe.quote("x " * 500)), xe.QUOTE_MAX)


class TestStyle(unittest.TestCase):
    def test_too_little_material_gives_no_profile(self):
        out = xe.style_entries([("a", sample(100)), ("b", sample(100))], False)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["confidence"], "none")
        self.assertIn("Zu wenig Material", out[0]["text"])

    def test_enough_material_is_measured(self):
        out = xe.style_entries([(f"t{i}", sample(300)) for i in range(4)], False)
        fields = {e["field"] for e in out}
        self.assertTrue({"stil.ton", "stil.format"} <= fields)
        ton = next(e for e in out if e["field"] == "stil.ton")
        self.assertIn("Sätze", ton["text"])
        self.assertTrue(all(e["quote"] and e["source"] for e in out))

    def test_address_form_is_decided_per_text(self):
        informal = "Hallo Team, könnt ihr das bitte prüfen? Ich schicke euch die Liste und eure Rückmeldung reicht mir. " * 12
        formal = "Guten Tag, vielen Dank für Ihre Rückmeldung. Ich schicke Ihnen die Übersicht, damit Sie sie prüfen können. " * 12
        out = xe.style_entries([("a", informal), ("b", informal), ("c", formal)], False)
        ton = next(e for e in out if e["field"] == "stil.ton")["text"]
        self.assertIn("je nach Adressat", ton)

    def test_donts_need_a_finding(self):
        clean = [(f"t{i}", sample(300)) for i in range(4)]
        out = xe.style_entries(clean, False)
        self.assertIn("stil.donts", {e["field"] for e in out})
        dirty = [("t0", sample(300) + " Es ist wichtig zu beachten, dass wir nahtlos ganzheitlich arbeiten. In der heutigen schnelllebigen Welt.")] + clean[1:]
        out = xe.style_entries(dirty, False)
        text = next(e for e in out if e["field"] == "stil.donts")["text"] if any(e["field"] == "stil.donts" for e in out) else ""
        self.assertIn("Kommen vor", text, "Floskeln, die vorkommen, dürfen kein Don't sein")


class TestTalk(unittest.TestCase):
    def test_goals_priorities_friction_and_channels_are_found_with_line_numbers(self):
        raw = ("00:00:01 Sprecher 1\nUnser Ziel für das vierte Quartal ist eine Quote unter zehn Prozent.\n"
               "00:00:20 Sprecher 2\nDas Zusammenstellen dauert jedes Mal einen halben Tag, das ist ein Medienbruch.\n"
               "00:00:40 Sprecher 1\nDringende Fälle laufen bei uns per Telefon, alles andere über das Ticket.\n"
               "00:01:00 Sprecher 3\nPriorität hat der Großkunde mit den offenen Rechnungen bis Ende Q4.\n")
        out = xe.talk_entries(Path("x.md"), raw, "x.md", "transkript", False)
        fields = {e["field"] for e in out}
        self.assertTrue({"prio.ziele", "rolle.zeitfresser", "team.kanaele", "prio.aktuell"} <= fields, fields)
        self.assertTrue(all(e["locator"].startswith("Zeile") for e in out))

    def test_speaker_labels_never_become_names(self):
        raw = "00:00:01 Sprecher 1\nUnser Ziel für das vierte Quartal ist eine Quote unter zehn Prozent.\n" * 3
        for e in xe.talk_entries(Path("x.md"), raw, "x.md", "transkript", False):
            self.assertNotIn("Sprecher", e["text"])

    def test_transcript_is_recognised(self):
        raw = "\n".join(f"00:0{i}:00 Sprecher 1\nText" for i in range(6))
        self.assertEqual(xe.classify(Path("notiz.md"), raw, None), "transkript")
        self.assertEqual(xe.classify(Path("x.md"), "irgendwas", "text"), "text")


class TestValidation(unittest.TestCase):
    def test_entry_without_quote_or_source_is_rejected(self):
        ok, problems = xe.validate_entries([
            {"field": "prio.aktuell", "text": "x", "quote": "", "source": "a.md"},
            {"field": "prio.aktuell", "text": "x", "quote": "q", "source": ""},
            {"field": "gibtesnicht", "text": "x", "quote": "q", "source": "a"},
            {"field": "prio.aktuell", "text": "ok", "quote": "wörtlich", "source": "a.md", "locator": "Zeile 1", "by": "claude"}])
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(problems), 3)


class TestRollenMdWithEvidence(unittest.TestCase):
    def graph(self):
        return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))

    def test_graph_value_beats_a_proposal(self):
        ev = [{"field": "firma.kunden", "text": "Privatkunden", "quote": "q", "source": "s", "locator": "Zeile 1"}]
        self.assertIn("Geschäftskunde", rm.fld("Für wen", "firma.kunden", ev, "Geschäftskunde"))
        self.assertNotIn("Privatkunden", rm.fld("Für wen", "firma.kunden", ev, "Geschäftskunde"))

    def test_proposal_is_marked_and_cites_the_source(self):
        ev = [{"field": "prio.aktuell", "text": "Fokus: Großkunden", "quote": "Fokus: Großkunden", "source": "status.md", "locator": "Zeile 4"}]
        ln = rm.fld("Woran du gerade arbeitest", "prio.aktuell", ev)
        self.assertIn(rm.PROPOSED, ln)
        self.assertIn("status.md (Zeile 4)", ln)
        self.assertNotIn(rm.OPEN, ln)

    def test_no_evidence_stays_open(self):
        self.assertIn(rm.OPEN, rm.fld("Woran du gerade arbeitest", "prio.aktuell", []))

    def test_too_little_material_stays_open_with_the_reason(self):
        ev = [{"field": "stil.ton", "text": "Zu wenig Material (2 Texte)", "quote": "2 Texte", "source": "texte/", "locator": "Zählung", "confidence": "none"}]
        ln = rm.fld("Tonalität", "stil.ton", ev)
        self.assertIn(rm.OPEN, ln)
        self.assertIn("Zu wenig Material", ln)
        self.assertNotIn(rm.PROPOSED, ln)

    def test_dos_from_regulation_and_from_texts_both_appear(self):
        g = self.graph()
        r = next(x for x in g["roles"] if x["name"] == "Kreditprüfer")
        r["regulated"] = True
        ev = {"firma": [], "roles": {r["name"]: [{"field": "stil.dos", "text": "Schlussformel „Viele Grüße“", "quote": "q", "source": "s", "locator": "Zählung"}]}}
        text, *_ = rm.compose(g, [r], evidence=ev)
        self.assertIn("Quelle jeder Aussage", text)
        self.assertIn("Do's aus deinen eigenen Texten", text)

    def test_compose_without_evidence_is_unchanged(self):
        g = self.graph()
        r = next(x for x in g["roles"] if x["name"] == "Kreditprüfer")
        a, *_ = rm.compose(g, [r])
        b, *_ = rm.compose(g, [r], evidence={"firma": [], "roles": {}})
        self.assertEqual(a, b)
        self.assertNotIn(rm.PROPOSED, a)


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.project = Path(cls.tmp) / "o2c"
        shutil.copytree(EXAMPLE, cls.project)
        shutil.rmtree(cls.project / "expected")
        r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(cls.project)], cwd=str(ROOT), capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(script("agent-mapper", name)), "--project", str(self.project), *args], cwd=str(ROOT), capture_output=True, text=True)

    def test_extraction_writes_documents_and_a_readable_summary(self):
        r = self.run_script("extract_context_evidence")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = self.project / "30_review" / "kontext_evidenz"
        self.assertTrue((d / "firma.json").exists() and (d / "forderungsmanager.json").exists() and (d / "kontext_evidenz.md").exists())
        doc = json.loads((d / "forderungsmanager.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["role"], "Forderungsmanager")
        self.assertTrue(all(e["quote"] and e["source"] for e in doc["entries"]))
        self.assertNotIn("@", json.dumps(doc))

    def test_extraction_is_deterministic(self):
        self.run_script("extract_context_evidence")
        a = (self.project / "30_review" / "kontext_evidenz" / "forderungsmanager.json").read_bytes()
        self.run_script("extract_context_evidence")
        self.assertEqual(a, (self.project / "30_review" / "kontext_evidenz" / "forderungsmanager.json").read_bytes())

    def test_rollen_md_shows_proposals_and_fewer_open_fields(self):
        self.run_script("extract_context_evidence")
        with_ev = self.run_script("build_rollen_md", "--role", "Forderungsmanager")
        self.assertEqual(with_ev.returncode, 0, with_ev.stdout + with_ev.stderr)
        text = (self.project / "40_output" / "rollen_md" / "Rollen.md").read_text(encoding="utf-8")
        self.assertIn(rm.PROPOSED, text)
        n_with = text.count(rm.OPEN)
        # Ohne Vorschläge desselben Projekts: mehr offene Felder
        no_ev = self.run_script("build_rollen_md", "--role", "Forderungsmanager", "--no-evidence", "--split")
        self.assertEqual(no_ev.returncode, 0, no_ev.stdout + no_ev.stderr)
        plain = (self.project / "40_output" / "rollen_md" / "Rollen_forderungsmanager.md").read_text(encoding="utf-8")
        self.assertGreater(plain.count(rm.OPEN), n_with)
        self.assertNotIn(rm.PROPOSED, plain)

    def test_claude_entries_are_loaded_and_bad_ones_reported(self):
        d = self.project / "30_review" / "kontext_evidenz"
        d.mkdir(parents=True, exist_ok=True)
        (d / "forderungsmanager.claude.json").write_text(json.dumps({"schema": xe.SCHEMA, "scope": "rolle", "role": "Forderungsmanager", "entries": [
            {"field": "prio.aktuell", "text": "Umstellung der Mahnstufen", "quote": "wir stellen die Mahnstufen um", "source": "Mail.eml", "locator": "Absatz 2", "by": "claude"},
            {"field": "prio.ziele", "text": "ohne Zitat", "quote": "", "source": "Mail.eml"}]}), encoding="utf-8")
        r = self.run_script("build_rollen_md", "--role", "Forderungsmanager", "--split")
        self.assertIn("ohne Zitat, Quelle oder Text", r.stdout)
        text = (self.project / "40_output" / "rollen_md" / "Rollen_forderungsmanager.md").read_text(encoding="utf-8")
        self.assertIn("Umstellung der Mahnstufen", text)
        self.assertNotIn("ohne Zitat", text.replace("ohne Zitat, Quelle", ""))
        (d / "forderungsmanager.claude.json").unlink()

    def test_setup_package_counts_proposals_and_adds_helpers(self):
        self.run_script("extract_context_evidence")
        r = self.run_script("build_role_setup", "--role", "Forderungsmanager;Kreditprüfer")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Vorschläge aus Dokumenten=", r.stdout)
        root = self.project / "40_output" / "rollen_setup"
        self.assertTrue((root / "forderungsmanager" / "skills" / "skill-ideen-prompt.md").exists())
        team = (root / "_team" / "Teamstart.md").read_text(encoding="utf-8")
        self.assertIn("Forderungsmanager", team)
        self.assertIn("Einverständnis", team)
        self.assertIn("keine Messung", team)

    def test_unknown_role_folder_is_reported_not_guessed(self):
        (self.project / "00_input" / "kontext" / "gibtesnicht" / "texte").mkdir(parents=True, exist_ok=True)
        (self.project / "00_input" / "kontext" / "gibtesnicht" / "texte" / "a.md").write_text("Text", encoding="utf-8")
        r = self.run_script("extract_context_evidence")
        self.assertIn("passt zu keiner Rolle", r.stdout)
        shutil.rmtree(self.project / "00_input" / "kontext" / "gibtesnicht")


class TestInventoryKnowsTheMaterial(unittest.TestCase):
    def test_material_under_kontext_is_recognised(self):
        self.assertEqual(inv.classify(Path("/p/00_input/kontext/forderungsmanager/texte/mail.md"), "")[0], "kontextmaterial")

    def test_other_files_are_not_swallowed(self):
        self.assertEqual(inv.classify(Path("/p/00_input/stellenbeschreibungen.md"), "")[0], "stellenbeschreibung")

    def test_offer_without_material_and_proposal_with_it(self):
        st = {"kinds": {"stellenbeschreibung"}, "have_graph": True, "roles": 3, "positions": 0, "edges": 0}
        self.assertIn("context_offer", inv.render([], st)[1]["picked"])
        st["kinds"].add("kontextmaterial")
        picked = inv.render([], st)[1]["picked"]
        self.assertIn("context_material", picked)
        self.assertNotIn("context_offer", picked)


if __name__ == "__main__":
    unittest.main()
