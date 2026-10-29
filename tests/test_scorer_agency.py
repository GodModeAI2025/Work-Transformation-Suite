"""Erweiterungen des task-scorer aus dem Auditrahmen (Schema 1.4).

Merkmale der Aufgabe (zwischenmenschlich, Erfahrungswissen) heben die HAS-Stufe an; zwei unabhängige
Bewertungsläufe lassen sich vergleichen; auffällige Muster werden gemeldet; je Skill entsteht die
Kompetenzverschiebung.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, ROOT, SKILLS, load, validate_graph, wl  # noqa: E402

sr = load("task-scorer", "score_roles")
cs = load("task-scorer", "compare_scores")


def run(skill, script, *args):
    return subprocess.run([sys.executable, str(SKILLS / skill / "scripts" / script), *args],
                          cwd=str(ROOT), capture_output=True, text=True)


class TestHasFloors(unittest.TestCase):
    def test_markers_raise_the_level(self):
        self.assertEqual(sr.derive_has(9, 1, {}), 1)
        self.assertEqual(sr.derive_has(9, 1, {"interpersonal": True}), sr.HAS_FLOOR_INTERPERSONAL)
        self.assertEqual(sr.derive_has(9, 1, {"tacit_expertise": True}), sr.HAS_FLOOR_TACIT)
        self.assertEqual(sr.derive_has(1, 9, {"tacit_expertise": True}), 5)  # nie abgesenkt
        self.assertEqual(sr.derive_has(9, 1, {"interpersonal": False}), 1)

    def test_alpha(self):
        self.assertEqual(cs.alpha_interval([(1, 1), (5, 5), (3, 3)]), 1.0)
        self.assertIsNone(cs.alpha_interval([(3, 3), (3, 3)]))
        self.assertLess(cs.alpha_interval([(1, 5), (5, 1), (3, 3)]), 0)


class TestProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-scorer-")
        self.proj = Path(self.tmp) / "p"
        shutil.copytree(EXAMPLE, self.proj)
        shutil.rmtree(self.proj / "00_input" / "befragung", ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pipeline(self):
        r = run("work-transformation", "run_pipeline.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr)
        return r

    def test_page_marker_flows_into_the_graph(self):
        page = next(p for p in (self.proj / "05_pages" / "tasks").glob("*.md")
                    if "name: \"Auftrag aus Bestellung erfassen\"" in p.read_text(encoding="utf-8"))
        text = page.read_text(encoding="utf-8")
        page.write_text(text.replace("score_automation_ai:", "score_interpersonal: true\nscore_automation_ai:", 1), encoding="utf-8")
        self.pipeline()
        g = wl.load_latest_graph(self.proj)
        t = next(t for t in g["tasks"] if t["name"] == "Auftrag aus Bestellung erfassen")
        self.assertIs(t["scores"].get("interpersonal"), True)
        self.assertGreaterEqual(t["has_level"], sr.HAS_FLOOR_INTERPERSONAL)

    def test_page_marker_must_be_boolean(self):
        page = next(iter(sorted((self.proj / "05_pages" / "tasks").glob("*.md"))))
        text = page.read_text(encoding="utf-8")
        page.write_text(text.replace("score_automation_ai:", "score_tacit_expertise: \"ja\"\nscore_automation_ai:", 1), encoding="utf-8")
        r = run("work-graph-builder", "compile_pages.py", "--project", str(self.proj))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("score_tacit_expertise", r.stdout + r.stderr)

    def test_skill_shift_and_plausibility(self):
        r = self.pipeline()
        g = wl.load_latest_graph(self.proj)
        analysed = [s for s in g["skills"] if s.get("analysis")]
        self.assertTrue(analysed)
        for s in analysed:
            self.assertTrue(1 <= s["analysis"]["human_agency"] <= 5)
            self.assertIn(s["analysis"]["bound_basis"], ("fte", "share_pct"))
        self.assertTrue(all("has_dominant" in r_["analysis"] for r_ in g["roles"] if r_["analysis"].get("scored")))
        self.assertIn("PLAUSIBILITÄT", r.stdout)  # das Beispiel ist überwiegend H1
        v = int(g["meta"]["version"])
        hr = (self.proj / "40_output" / f"report_hr_v{v:03d}.md").read_text(encoding="utf-8")
        self.assertIn("## Kompetenzverschiebung", hr)
        errors, _ = validate_graph.validate(g)
        self.assertEqual(errors, [])

    def test_calibrate_runs_without_overrides(self):
        self.pipeline()
        (self.proj / "30_review" / "overrides.csv").unlink(missing_ok=True)
        r = run("task-scorer", "calibrate.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = sorted((self.proj / "30_review").glob("calibration_v*.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("## Plausibilität", rep)

    def test_second_rating_is_compared(self):
        self.pipeline()
        self.assertEqual(run("task-scorer", "compare_scores.py", "--project", str(self.proj)).returncode, 3)
        first = wl.read_json(self.proj / "20_graph" / "scores.json")
        second = {k: dict(v) for k, v in first.items()}
        tid = sorted(second)[0]
        second[tid]["human_judgment"] = min(10, second[tid]["human_judgment"] + 4)
        wl.write_json(self.proj / "20_graph" / "scores_zweitbewertung.json", second)
        r = run("task-scorer", "compare_scores.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        v = int(wl.load_latest_graph(self.proj)["meta"]["version"])
        rep = (self.proj / "30_review" / f"zweitbewertung_v{v:03d}.md").read_text(encoding="utf-8")
        g = wl.load_latest_graph(self.proj)
        name = next(t["name"] for t in g["tasks"] if t["id"] == tid)
        self.assertIn(name, rep)
        self.assertIn("Urteilsbedarf +4", rep)
        self.assertIn("belastbar", rep)  # alle übrigen Felder identisch


if __name__ == "__main__":
    unittest.main()
