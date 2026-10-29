"""Referenzbibliothek: Branchenpakete, Rechtsraum, Plattformprofile.

Geprüft wird, dass jedes Branchenpaket fehlerfrei übersetzbar ist und zu einem gültigen Graphen führt,
dass übernommene Einträge als „reference“ und nicht als Befund gelten, dass vorhandene Seiten nie
überschrieben werden, und dass Rechtsrahmen und Plattformvorschläge nur aus der Bibliothek kommen.
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

pl = load("work-graph-builder", "pages_lib")
cp = load("work-graph-builder", "compile_pages")
B = SKILLS / "work-graph-builder" / "scripts"
LIB = SKILLS / "work-graph-builder" / "library"


def run(script, *args):
    skill = "work-transformation" if script in ("run_pipeline.py",) else "work-graph-builder"
    return subprocess.run([sys.executable, str(SKILLS / skill / "scripts" / script), *args],
                          cwd=str(ROOT), capture_output=True, text=True)


class TestLibraryContent(unittest.TestCase):
    def test_index_matches_packages(self):
        index = wl.read_json(LIB / "branchen" / "index.json")
        self.assertGreaterEqual(len(index), 5)
        for bid, b in index.items():
            d = LIB / "branchen" / bid
            self.assertTrue((d / "quelle.md").exists(), bid)
            roles = list((d / "roles").glob("*.md"))
            tasks = list((d / "tasks").glob("*.md"))
            self.assertEqual(len(roles), b["rollen"], bid)
            self.assertEqual(len(tasks), b["aufgaben"], bid)

    def test_every_package_compiles_and_builds_a_valid_graph(self):
        for bid in wl.read_json(LIB / "branchen" / "index.json"):
            with tempfile.TemporaryDirectory(prefix="wts-lib-") as tmp:
                proj = Path(tmp) / "p"
                self.assertEqual(run("init_project.py", "--project", str(proj), "--name", "t", "--branche", bid).returncode, 0, bid)
                r = run("seed_from_library.py", "--project", str(proj), "--branche", bid, "--date", "2026-01-01")
                self.assertEqual(r.returncode, 0, bid + r.stdout + r.stderr)
                r = run("run_pipeline.py", "--project", str(proj), "--until", "processes")
                self.assertEqual(r.returncode, 0, bid + r.stdout + r.stderr)
                self.assertNotIn("FEHLER", r.stdout, bid)
                g = wl.read_json(proj / "20_graph" / "work-graph_latest.json")
                errors, _ = validate_graph.validate(g, strict_evidence=True)
                self.assertEqual(errors, [], bid)
                self.assertEqual({x["evidence_status"] for x in g["roles"]}, {"reference"}, bid)
                self.assertEqual({x["evidence_status"] for x in g["tasks"]}, {"reference"}, bid)
                for role in g["roles"]:
                    total = sum(t["share_of_time"] for t in g["tasks"] if t["role_id"] == role["id"])
                    self.assertAlmostEqual(total, 100.0, delta=0.6, msg=f"{bid}/{role['name']}")

    def test_every_locator_of_every_package_resolves(self):
        for bid in wl.read_json(LIB / "branchen" / "index.json"):
            body = (LIB / "branchen" / bid / "quelle.md").read_text(encoding="utf-8")
            anchors = {a for *_, a in wl.source_headings(body)}
            for p in (LIB / "branchen" / bid / "roles").glob("*.md"):
                meta, _ = pl.parse_frontmatter(p.read_text(encoding="utf-8"), p.name)
                for ev in meta["evidence"]:
                    self.assertTrue(ev.startswith("lib@#"), ev)
                    self.assertIn(ev[len("lib@#"):], anchors, f"{bid}/{p.name}")

    def test_legal_catalog_and_platforms_are_well_formed(self):
        de = wl.read_json(LIB / "rechtsraeume" / "DE.json")
        ids = [t["id"] for t in de["themen"]]
        self.assertEqual(len(ids), len(set(ids)))
        index = wl.read_json(LIB / "branchen" / "index.json")
        for t in de["themen"]:
            for k in ("thema", "gesetz", "fundstelle", "pflicht", "stichwoerter", "branchen"):
                self.assertTrue(t.get(k), f"{t['id']}: {k}")
            for k in t["stichwoerter"]:  # nur Normalform trifft beim Abgleich (qualitat, nicht qualitaet)
                self.assertTrue(k == "*" or wl.normalize_name(k) == k, f"{t['id']}: {k}")
            for b in t["branchen"]:
                self.assertTrue(b == "*" or b in index, f"{t['id']}: {b}")
        for bid, entry in index.items():  # jedes Paket nennt nur Themen, die der Rechtsraum kennt
            for rid in entry.get("rechtsthemen", []):
                self.assertIn(rid, ids, f"{bid}: {rid}")
        patterns = set()
        for pid in wl.ENUM_PLATFORM:
            prof = wl.read_json(LIB / "plattformen" / f"{pid}.json")
            self.assertEqual(prof["id"], pid)
            self.assertTrue(prof["grundsaetze"])
            patterns.add(frozenset(prof["muster"]))
            for v in prof["muster"].values():
                self.assertTrue(v["dienste"], pid)
        self.assertEqual(len(patterns), 1)  # alle Profile kennen dieselben Muster


class TestSeeding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-seed-")
        self.proj = Path(self.tmp) / "p"
        self.assertEqual(run("init_project.py", "--project", str(self.proj), "--name", "t", "--branche", "energieversorgung",
                             "--plattform", "microsoft").returncode, 0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unknown_branch_is_refused_at_init(self):
        r = run("init_project.py", "--project", str(Path(self.tmp) / "q"), "--name", "t", "--branche", "gibtsnicht")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Bekannt", r.stdout + r.stderr)

    def test_selection_by_cluster_and_role(self):
        r = run("seed_from_library.py", "--project", str(self.proj), "--branche", "energieversorgung", "--cluster", "Netzbetrieb",
                "--date", "2026-01-01")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(list((self.proj / "05_pages" / "roles").glob("*.md"))), 4)
        r = run("seed_from_library.py", "--project", str(self.proj), "--branche", "allgemein", "--rollen", "Controller;Datenschutzbeauftragter",
                "--date", "2026-01-01")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(list((self.proj / "05_pages" / "roles").glob("*.md"))), 6)
        self.assertEqual(len(wl.load_source_register(self.proj)), 2)
        self.assertEqual({rec["kind"] for rec in wl.load_source_register(self.proj).values()}, {"reference"})

    def test_existing_page_is_never_overwritten(self):
        run("seed_from_library.py", "--project", str(self.proj), "--branche", "energieversorgung", "--rollen", "Netzplaner", "--date", "2026-01-01")
        page = self.proj / "05_pages" / "roles" / "netzplaner.md"
        edited = page.read_text(encoding="utf-8").replace("headcount: null", "headcount: 7")
        page.write_text(edited, encoding="utf-8")
        r = run("seed_from_library.py", "--project", str(self.proj), "--branche", "energieversorgung", "--rollen", "Netzplaner", "--date", "2026-01-01")
        self.assertEqual(r.returncode, 0)
        self.assertIn("unverändert", r.stdout)
        self.assertEqual(page.read_text(encoding="utf-8"), edited)

    def test_registers_without_pages_must_be_exported_first(self):
        other = Path(self.tmp) / "legacy"
        shutil.copytree(EXAMPLE, other)
        shutil.rmtree(other / "05_pages")
        r = run("seed_from_library.py", "--project", str(other), "--branche", "allgemein", "--rollen", "Controller")
        self.assertEqual(r.returncode, 2)
        self.assertIn("export_pages.py", r.stdout + r.stderr)

    def test_review_list_marks_reference_roles_once_and_names_legal_topics(self):
        run("seed_from_library.py", "--project", str(self.proj), "--branche", "energieversorgung", "--cluster", "Netzbetrieb", "--date", "2026-01-01")
        self.assertEqual(run("run_pipeline.py", "--project", str(self.proj), "--until", "builder").returncode, 0)
        review = next((self.proj / "30_review").glob("review_v*.md")).read_text(encoding="utf-8")
        self.assertEqual(review.count("Aus der Referenzbibliothek übernommen"), 4)
        self.assertIn("### Rechtsrahmen", review)
        self.assertIn("EnWG", review)
        self.assertIn("keine Rechtsberatung", review)


class TestExampleProfile(unittest.TestCase):
    def test_example_graph_carries_profile_and_contracts_name_platform(self):
        g = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        self.assertEqual(g["meta"]["profile"]["plattform"], "mischbetrieb")
        contracts = sorted((EXAMPLE / "expected").glob("contracts_v*.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("Umsetzung auf Plattformprofil", contracts)
        self.assertIn("kein Beschaffungsentscheid", contracts)

    def test_legal_topics_need_library_and_match_keywords(self):
        g = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        role = next(r for r in g["roles"] if r["name"] == "Forderungsmanager")
        topics = wl.legal_topics(g, role)
        ids = [t["id"] for t in topics]
        self.assertIn("mitbestimmung", ids)
        self.assertIn("handelsrecht", ids)
        self.assertNotIn("trinkwasser", ids)
        g2 = json.loads(json.dumps(g))
        g2["meta"]["profile"] = {"branche": "wasserversorgung", "rechtsraum": "XX"}
        self.assertEqual(wl.legal_topics(g2, role), [])


if __name__ == "__main__":
    unittest.main()
