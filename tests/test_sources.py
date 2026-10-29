"""Quellenregister und Belege.

Geprüft wird, was das Register NICHT tun darf: Inhalt verändern, absolute Pfade speichern,
Zugangsdaten aufnehmen, dieselbe Quelle zweimal führen. Und was ein Beleg leisten muss:
eine registrierte Quelle und eine Fundstelle, die im Quelltext aufgeht.
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
from context import EXAMPLE, ROOT, SKILLS, load, validate_graph, wl  # noqa: E402

reg = load("work-graph-builder", "register_source")
chk = load("work-graph-builder", "check_evidence")


def example_graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


class TestLib(unittest.TestCase):
    def test_evidence_form(self):
        self.assertEqual(wl.parse_evidence("src-0123456789ab@#rolle"), ("src-0123456789ab", "#rolle"))
        self.assertIsNone(wl.parse_evidence("src-0123456789ab"))
        self.assertIsNone(wl.parse_evidence("src-xyz@#rolle"))
        self.assertIsNone(wl.parse_evidence(None))

    def test_status_is_never_null(self):
        self.assertEqual(wl.evidence_status({"evidence": ["src-0123456789ab@L1"]}), "sourced")
        self.assertEqual(wl.evidence_status({"evidence": []}, estimated=True), "estimated")
        self.assertEqual(wl.evidence_status({}), "unsourced")

    def test_locators(self):
        body = "# Rolle A\nText\n\n## Teil (1)\nmehr\n```\n# kein Anker\n```\n"
        self.assertEqual([a for *_, a in wl.source_headings(body)], ["rolle-a", "teil-1"])
        self.assertTrue(wl.resolve_locator(body, "#teil-1")[0])
        self.assertFalse(wl.resolve_locator(body, "#kein-anker")[0])
        self.assertTrue(wl.resolve_locator(body, "L2-5")[0])
        self.assertFalse(wl.resolve_locator(body, "L99")[0])
        ok, note = wl.resolve_locator(body, "Folie 3")
        self.assertTrue(ok)
        self.assertIn("Freitext", note)

    def test_credentials_and_placeholders(self):
        self.assertEqual(wl.credential_findings("sk-ant-" + "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7"), [(1, "api-key")])
        self.assertEqual(wl.credential_findings("ghp_" + "x" * 40), [])
        self.assertEqual(wl.credential_findings("https://user:password@host/pfad"), [])
        self.assertEqual(wl.credential_findings("-----BEGIN RSA PRIVATE KEY-----"), [(1, "private-key")])

    def test_portable_reference(self):
        for ok in ("00_input/x.md", "HR-Ablage/Stellen.pdf", "https://intranet/x", "sharepoint:12345"):
            self.assertTrue(wl.portable_reference(ok), ok)
        for bad in ("/home/x/y.md", "C:\\Users\\x", "~/y", "../y", "file:///x", ""):
            self.assertFalse(wl.portable_reference(bad), bad)


class TestRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-src-")
        self.proj = Path(self.tmp) / "p"
        (self.proj / "00_input").mkdir(parents=True)
        wl.save_project_meta(self.proj, {"name": "p", "graph_version": 0})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        p = self.proj / "00_input" / name
        p.write_text(text, encoding="utf-8")
        return p

    def register(self, path, title="T", **kw):
        args = dict(origin=None, kind="document", language="de", extractor="human", status="active",
                    when="2026-01-01", original=None, supersedes=None)
        args.update(kw)
        return reg.register(self.proj, path, title, **args)

    def test_content_is_kept_verbatim_and_hash_is_the_id(self):
        text = "# Titel\n\nZeile mit  zwei  Leerzeichen und Umlauten äöü.\n"
        rec = self.register(self.write("q.md", text))
        self.assertTrue(rec["source_id"].startswith("src-"))
        body = wl.split_frontmatter((self.proj / rec["file"]).read_text(encoding="utf-8"))[1]
        self.assertEqual(body, text)
        self.assertEqual(rec["origin"], "00_input/q.md")
        self.assertEqual(len(wl.load_source_register(self.proj)), 1)

    def test_same_bytes_register_once(self):
        p = self.write("q.md", "# A\n")
        a = self.register(p)
        b = self.register(p, title="anderer Titel")
        self.assertEqual(a["source_id"], b["source_id"])
        self.assertEqual(len(wl.load_source_register(self.proj)), 1)

    def test_csv_is_fenced_not_rewritten(self):
        rec = self.register(self.write("t.csv", "a;b\n1;2\n"))
        body = wl.split_frontmatter((self.proj / rec["file"]).read_text(encoding="utf-8"))[1]
        self.assertIn("```csv\na;b\n1;2\n```", body)

    def test_absolute_origin_and_credentials_are_refused(self):
        p = self.write("q.md", "# A\n")
        with self.assertRaises(SystemExit):
            self.register(p, origin="/abs/pfad.md")
        bad = self.write("k.md", "token: sk-ant-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7\n")
        with self.assertRaises(SystemExit):
            self.register(bad)
        self.assertEqual(wl.load_source_register(self.proj), {})

    def test_binary_formats_are_refused_with_instruction(self):
        p = self.proj / "00_input" / "x.pdf"
        p.write_bytes(b"%PDF-1.4")
        with self.assertRaises(SystemExit):
            self.register(p)

    def test_original_hash_is_recorded_but_file_not_copied(self):
        orig = self.proj / "00_input" / "orig.pdf"
        orig.write_bytes(b"%PDF-1.4 inhalt")
        rec = self.register(self.write("orig.md", "# Treue Fassung\n"), original=orig, extractor="claude")
        self.assertEqual(len(rec["original_sha256"]), 64)
        self.assertFalse(any(p.suffix == ".pdf" for p in wl.sources_dir(self.proj).iterdir()))


class TestValidator(unittest.TestCase):
    def test_example_is_fully_sourced(self):
        g = example_graph()
        errors, warnings = validate_graph.validate(g, strict_evidence=True)
        self.assertEqual(errors, [])
        self.assertTrue(any(r["evidence_status"] == "sourced" for r in g["roles"]))
        self.assertEqual({t["evidence_status"] for t in g["tasks"] if t["confidence"] == "inferred"}, {"estimated"})

    def test_unknown_source_and_bad_form_are_errors(self):
        g = example_graph()
        g["roles"][0]["evidence"] = ["src-ffffffffffff@#x"]
        g["tasks"][0]["evidence"] = ["irgendwas"]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("nicht registrierte Quelle" in e for e in errors))
        self.assertTrue(any("nicht die Form" in e for e in errors))

    def test_unsourced_is_warning_unless_strict(self):
        g = example_graph()
        g["roles"][0]["evidence"] = []
        g["roles"][0]["evidence_status"] = "unsourced"
        errors, warnings = validate_graph.validate(g)
        self.assertEqual(errors, [])
        self.assertTrue(any("roles: 1 von" in w for w in warnings))
        errors, _ = validate_graph.validate(g, strict_evidence=True)
        self.assertTrue(any("Belegpflicht strict" in e for e in errors))

    def test_provenance_source_ref_may_point_to_register(self):
        g = example_graph()
        g["provenance"][0]["source_ref"] = "src-ffffffffffff@L1"
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("provenance" in e and "nicht registrierte" in e for e in errors))


class TestCheckEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wts-ev-")
        cls.proj = Path(cls.tmp) / "order-to-cash"
        shutil.copytree(EXAMPLE, cls.proj)
        shutil.rmtree(cls.proj / "expected", ignore_errors=True)
        wl.write_json(cls.proj / "20_graph" / "work-graph_latest.json", example_graph())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_check(self, *extra):
        return subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "check_evidence.py"),
                               "--project", str(self.proj), *extra], cwd=str(ROOT), capture_output=True, text=True)

    def test_example_resolves_every_locator(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("unbelegt=0", r.stdout)
        self.assertTrue((self.proj / "30_review" / "belege_v012.md").exists())

    def test_bad_anchor_is_reported(self):
        g = example_graph()
        g["roles"][0]["evidence"] = ["src-2c6249b3bd2f@#gibt-es-nicht"]
        a = chk.analyse(self.proj, g)
        self.assertEqual(len(a["bad_locators"]), 1)
        self.assertIn("Anker", a["bad_locators"][0][3])

    def test_strict_stops_with_code_three(self):
        g = example_graph()
        g["roles"][0]["evidence"] = []
        g["roles"][0]["evidence_status"] = "unsourced"
        other = Path(self.tmp) / "strict"
        shutil.copytree(self.proj, other)
        wl.write_json(other / "20_graph" / "work-graph_latest.json", g)
        r = subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "check_evidence.py"),
                            "--project", str(other), "--strict"], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("STOPP", r.stdout)

    def test_locate_source_finds_quote(self):
        r = subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "locate_source.py"),
                            "--project", str(self.proj), "--source", "src-2c6249b3bd2f", "--find", "Zeitanteile geschätzt"],
                           cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("src-2c6249b3bd2f@L46", r.stdout)
        self.assertIn("#teamleitung-order-to-cash-1-stelle", r.stdout)


if __name__ == "__main__":
    unittest.main()
