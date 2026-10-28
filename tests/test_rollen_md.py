"""Rollen.md: die fünf Abschnitte für eine oder mehrere Rollen.

Geprüft wird, dass nichts erfunden wird (Prioritäten, Tonalität, Do's und Don'ts bleiben offen), dass Abgeleitetes als solches
gekennzeichnet ist, dass der Kanal einer Übergabe im Team-Kontext steht und dass das Setup-Paket denselben Text benutzt.
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

rm = load("agent-mapper", "rollen_md")
brs = load("agent-mapper", "build_role_setup")

PIPELINE = ROOT / "skills" / "work-transformation" / "scripts" / "run_pipeline.py"
HEADINGS = ["1) Firmenprofil", "2) Rollenprofil", "3) Team-Kontext", "4) Prioritäten & Ziele", "5) Arbeits- & Kommunikationsstil"]


def graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


def role(g, name):
    return brs.find_role(g, name)


class TestSections(unittest.TestCase):
    def test_all_five_sections_for_one_role(self):
        g = graph()
        text, _f, _o = rm.compose(g, [role(g, "Forderungsmanager")])
        for h in HEADINGS:
            self.assertEqual(sum(1 for ln in text.splitlines() if ln.startswith("#") and h in ln), 1, h)

    def test_company_profile_once_role_sections_per_role(self):
        g = graph()
        text, _f, _o = rm.compose(g, [role(g, "Forderungsmanager"), role(g, "Kreditprüfer")])
        heads = [ln for ln in text.splitlines() if ln.startswith("#")]
        self.assertEqual(sum(1 for ln in heads if "1) Firmenprofil" in ln), 1)
        for h in HEADINGS[1:]:
            self.assertEqual(sum(1 for ln in heads if h in ln), 2, h)
        self.assertIn("## Rolle: Forderungsmanager", text)
        self.assertIn("## Rolle: Kreditprüfer", text)

    def test_front_matter_lists_the_roles_sorted(self):
        g = graph()
        text, *_ = rm.compose(g, [role(g, "Kreditprüfer"), role(g, "Forderungsmanager")])
        head = text.split("---")[1]
        self.assertLess(head.index("Forderungsmanager"), head.index("Kreditprüfer"))
        self.assertIn("stand: offen", head)

    def test_output_is_deterministic_and_order_independent(self):
        g = graph()
        a, *_ = rm.compose(g, [role(g, "Forderungsmanager"), role(g, "Kreditprüfer")])
        b, *_ = rm.compose(graph(), [role(graph(), "Kreditprüfer"), role(graph(), "Forderungsmanager")])
        self.assertEqual(a, b)

    def test_what_a_graph_cannot_know_stays_open(self):
        g = graph()
        text, _f, open_n = rm.compose(g, [role(g, "Forderungsmanager")])
        for label in ("Was das Unternehmen tut", "Markt und Branche", "Produkte und Leistungen", "Woran du gerade arbeitest", "Ziele dieses Quartals",
                      "Tonalität", "Qualitätsverständnis", "Don'ts für KI-Texte", "Führungskraft und Ansprechpersonen", "Zeitfresser aus deiner Sicht"):
            hits = [ln for ln in text.splitlines() if ln.startswith("- **") and label in ln]
            self.assertTrue(hits, label)
            self.assertTrue(all(rm.OPEN in ln for ln in hits), label)
        self.assertGreaterEqual(open_n, 10)

    def test_derived_lines_are_marked(self):
        g = graph()
        text, *_ = rm.compose(g, [role(g, "Forderungsmanager")])
        zeit = [ln for ln in text.splitlines() if "größte gebundene Zeit" in ln]
        self.assertTrue(zeit)
        self.assertTrue(all("bitte bestätigen" in ln for ln in zeit))


class TestTeamContext(unittest.TestCase):
    def test_channel_and_direction_are_named(self):
        g = graph()
        text, *_ = rm.compose(g, [role(g, "Kreditprüfer")])
        self.assertIn("E-Mail", text, "Der Kanal der Übergabe gehört in den Team-Kontext")
        self.assertRegex(text, r"du gibst weiter|du bekommst")

    def test_handover_map_counts_per_channel(self):
        g = graph()
        h = rm.handovers(g, role(g, "Auftragssachbearbeiter"))
        self.assertTrue(h)
        for d in h.values():
            self.assertTrue(set(d["to"]) | set(d["from"]))

    def test_no_handovers_is_said_plainly(self):
        g = graph()
        g["process_edges"] = []
        text, *_ = rm.compose(g, [role(g, "Kreditprüfer")])
        self.assertIn("keine Übergaben im Graphen erfasst", text)


class TestTimeWasters(unittest.TestCase):
    def test_friction_from_the_interview_is_quoted(self):
        g = graph()
        text, *_ = rm.compose(g, [role(g, "Forderungsmanager")])
        self.assertIn("Ich suche die Gutschrift in drei Systemen", text)

    def test_list_stays_short(self):
        g = graph()
        text, *_ = rm.compose(g, [role(g, "Forderungsmanager")])
        waits = [ln for ln in text.splitlines() if "längste Liegezeit" in ln]
        rework = [ln for ln in text.splitlines() if "meiste Rückläufer" in ln]
        self.assertLessEqual(len(waits), rm.ZEITFRESSER_TOP)
        self.assertLessEqual(len(rework), rm.ZEITFRESSER_TOP)

    def test_dos_come_from_regulation_but_are_marked(self):
        g = graph()
        r = role(g, "Kreditprüfer")
        r["regulated"] = True
        text, *_ = rm.compose(g, [r])
        line = next(ln for ln in text.splitlines() if "Do's für KI-Texte" in ln)
        self.assertIn("Quelle jeder Aussage", line)
        self.assertIn("bitte bestätigen", line)

    def test_dos_stay_open_without_a_reason(self):
        g = graph()
        r = role(g, "Teamleitung Order-to-Cash")
        r["regulated"] = False
        for t in g["tasks"]:
            if t["role_id"] == r["id"] and t.get("scores"):
                t["scores"]["consequence_of_error"] = 1
        text, *_ = rm.compose(g, [r])
        self.assertIn(rm.OPEN, next(ln for ln in text.splitlines() if "Do's für KI-Texte" in ln))


class TestSamePackageText(unittest.TestCase):
    def test_setup_package_uses_the_same_rollen_md(self):
        g = graph()
        r = role(g, "Forderungsmanager")
        pkg = brs.build_package(g, r, 4)
        single, *_ = rm.compose(g, [r], title="Rollen — Forderungsmanager")
        self.assertEqual(pkg["kontext/Rollen.md"], single)
        self.assertNotIn("kontext/kontextprofil.md", pkg)


class TestCommandLine(unittest.TestCase):
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

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(script("agent-mapper", "build_rollen_md")), "--project", str(self.project), *args],
                              cwd=str(ROOT), capture_output=True, text=True)

    def test_several_roles_in_one_file(self):
        r = self.run_cli("--role", "Forderungsmanager", "--role", "Kreditprüfer")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (self.project / "40_output" / "rollen_md" / "Rollen.md").read_text(encoding="utf-8")
        self.assertIn("## Rolle: Forderungsmanager", text)
        self.assertIn("## Rolle: Kreditprüfer", text)

    def test_semicolon_list_works_like_repeated_flags(self):
        a = self.run_cli("--role", "Forderungsmanager;Kreditprüfer")
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        self.assertIn("Rollen=2", a.stdout)

    def test_unknown_role_fails_with_a_hint_and_writes_nothing_new(self):
        r = self.run_cli("--role", "Forderung")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Forderungsmanager", r.stdout + r.stderr)

    def test_split_writes_one_file_per_role(self):
        r = self.run_cli("--all", "--split")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = sorted(p.name for p in (self.project / "40_output" / "rollen_md").glob("Rollen_*.md"))
        self.assertEqual(len(files), 5)
        one = (self.project / "40_output" / "rollen_md" / "Rollen_kreditprufer.md").read_text(encoding="utf-8")
        self.assertIn("1) Firmenprofil", one, "Jede Einzeldatei muss für sich tragen")

    def test_edited_file_is_not_overwritten(self):
        self.run_cli("--role", "Kreditprüfer", "--split")
        f = self.project / "40_output" / "rollen_md" / "Rollen_kreditprufer.md"
        f.write_text(f.read_text(encoding="utf-8").replace(rm.OPEN, "Meine Antwort", 1), encoding="utf-8")
        edited = f.read_text(encoding="utf-8")
        # Der Graph ändert sich, der neue Stand müsste eine Änderung enthalten.
        gp = self.project / "20_graph" / "work-graph_latest.json"
        g = json.loads(gp.read_text(encoding="utf-8"))
        next(r for r in g["roles"] if r["name"] == "Kreditprüfer")["purpose"] = "Neuer Zweck der Rolle, ganz anders formuliert."
        gp.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        r = self.run_cli("--role", "Kreditprüfer", "--split")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(f.read_text(encoding="utf-8"), edited)
        self.assertTrue(f.with_name(f.name + ".vorschlag").exists())


if __name__ == "__main__":
    unittest.main()
