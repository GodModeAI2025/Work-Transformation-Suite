"""Seiten als Wahrheit: Frontmatter-Vertrag, Export, Übersetzung, Pipeline.

Geprüft wird, dass die Seiten des Beispiels denselben Graphen ergeben wie der hinterlegte Stand,
dass der Vertrag Fehler mit Datei und Zeile meldet statt zu raten, und dass eine kaputte Seite die
Pipeline anhält, ohne ein Register zu verändern.
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
from context import EXAMPLE, ROOT, SKILLS, load, wl  # noqa: E402

pl = load("work-graph-builder", "pages_lib")
cp = load("work-graph-builder", "compile_pages")
B = SKILLS / "work-graph-builder" / "scripts"


def run(name, *args):
    return subprocess.run([sys.executable, str(B / name), *args], cwd=str(ROOT), capture_output=True, text=True)


class TestFrontmatter(unittest.TestCase):
    def test_scalars_lists_and_comments(self):
        m, body = pl.parse_frontmatter('---\n# k\nname: "A"\nn: 3\nf: 1.5\nb: true\nx: null\nbare: Text mit Leerzeichen\n'
                                       'l:\n  - "a"\n  - 2\ninl: ["x", "y"]\nempty: []\n---\n\nRumpf\n', "s.md")
        self.assertEqual(m, {"name": "A", "n": 3, "f": 1.5, "b": True, "x": None, "bare": "Text mit Leerzeichen",
                             "l": ["a", 2], "inl": ["x", "y"], "empty": []})
        self.assertEqual(body, "Rumpf\n")

    def test_errors_name_file_and_line(self):
        cases = {"---\na: {x: 1}\n---\n": "s.md:2", "---\na: 1\nb: 2\na: 3\n---\n": "s.md:4: Schlüssel 'a' doppelt",
                 "---\n  a: 1\n---\n": "s.md:2", "---\nA-b: 1\n---\n": "nicht erlaubt",
                 "---\na: 1\n\tb: 2\n---\n": "Tabulator", "---\na: [1, [2]]\n---\n": "nur Zeichenketten",
                 "---\na: 1\n# spät\nb: 2\n---\n": "Kommentare nur am Anfang", "---\na: 'x'\n---\n": "nicht erlaubt",
                 "---\n__proto__: 1\n---\n": "nicht erlaubt", "ohne\n": "kein Frontmatter"}
        for text, expect in cases.items():
            with self.assertRaises(pl.PageError) as ctx:
                pl.parse_frontmatter(text, "s.md")
            self.assertIn(expect, str(ctx.exception), text)

    def test_dump_and_parse_round_trip(self):
        data = {"type": "role", "name": "Ä \"zitat\" | pipe", "n": 2, "ok": False, "none": None, "l": ["a", "b"], "e": []}
        m, _ = pl.parse_frontmatter(pl.dump_frontmatter(data) + "\nx\n", "s.md")
        self.assertEqual(m, data)
        with self.assertRaises(pl.PageError):
            pl.dump_frontmatter({"a": {"b": 1}})

    def test_body_helpers(self):
        body = "vorher\n\n## Skills\n\n| Skill | Art |\n|---|---|\n| a \\| b | tool |\n\n## Schritte\n\n1. eins\n2) zwei\n\n## Vertrag\n\n```json\n{\"k\": 1}\n```\n"
        s = pl.sections(body)
        self.assertEqual(s[""], "vorher")
        self.assertEqual(pl.table_rows(s["Skills"]), [{"Skill": "a | b", "Art": "tool"}])
        self.assertEqual(pl.ordered_list(s["Schritte"]), ["eins", "zwei"])
        self.assertEqual(pl.json_block(s["Vertrag"], "s"), {"k": 1})
        with self.assertRaises(pl.PageError):
            pl.json_block("```json\n{kaputt}\n```", "s")


class TestExampleRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wts-pages-")
        cls.proj = Path(cls.tmp) / "p"
        shutil.copytree(EXAMPLE, cls.proj)
        shutil.rmtree(cls.proj / "expected", ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_example_has_pages_and_compile_is_deterministic(self):
        self.assertTrue(pl.has_pages(self.proj))
        r = run("compile_pages.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = {p: (self.proj / p).read_bytes() for p in ("10_extraction/extract_order-to-cash.json", "20_graph/scores.json", "20_graph/agents.json")}
        self.assertEqual(run("compile_pages.py", "--project", str(self.proj)).returncode, 0)
        for p, data in first.items():
            self.assertEqual((self.proj / p).read_bytes(), data, p)

    def test_compiled_registers_equal_committed_ones(self):
        out, problems = cp.compile_pages(self.proj)
        self.assertEqual(problems, [])
        committed = wl.read_json(EXAMPLE / "10_extraction" / "extract_order-to-cash.json")
        self.assertEqual(json.dumps(out["extractions"]["extract_order-to-cash.json"], sort_keys=True),
                         json.dumps(committed, sort_keys=True))
        self.assertEqual(out["scores"], wl.read_json(EXAMPLE / "20_graph" / "scores.json"))
        self.assertEqual(json.dumps(out["agents"], sort_keys=True),
                         json.dumps(wl.read_json(EXAMPLE / "20_graph" / "agents.json"), sort_keys=True))

    def test_export_refuses_to_overwrite_pages_and_is_idempotent_with_force(self):
        r = run("export_pages.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 2)
        before = {p: p.read_bytes() for p in (self.proj / "05_pages").rglob("*.md")}
        self.assertEqual(run("export_pages.py", "--project", str(self.proj), "--force").returncode, 0)
        for p, data in before.items():
            self.assertEqual(p.read_bytes(), data, p.name)


class TestCompileErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-pages-")
        self.proj = Path(self.tmp) / "p"
        shutil.copytree(EXAMPLE, self.proj)
        shutil.rmtree(self.proj / "expected", ignore_errors=True)
        self.pages = self.proj / "05_pages"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_broken_page_stops_pipeline_and_leaves_registers_untouched(self):
        page = self.pages / "tasks" / "forderungsmanager--zahlungseingange-zuordnen.md"
        page.write_text(page.read_text(encoding="utf-8").replace("score_data_readiness: 8\n", ""), encoding="utf-8")
        before = (self.proj / "20_graph" / "scores.json").read_bytes()
        r = run("compile_pages.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Bewertung unvollständig", r.stdout)
        self.assertIn("score_data_readiness", r.stdout)
        self.assertEqual((self.proj / "20_graph" / "scores.json").read_bytes(), before)
        p = subprocess.run([sys.executable, str(SKILLS / "work-transformation" / "scripts" / "run_pipeline.py"),
                            "--project", str(self.proj)], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(p.returncode, 3)
        self.assertIn("05_pages", p.stdout)

    def test_unknown_role_and_cluster_are_reported(self):
        (self.pages / "tasks" / "neu.md").write_text('---\ntype: "task"\nname: "X"\nrole: "Gibtesnicht"\nshare_of_time: 5\n---\n', encoding="utf-8")
        (self.pages / "roles" / "neu.md").write_text('---\ntype: "role"\nname: "Y"\ncluster: "Kein Cluster"\n---\n', encoding="utf-8")
        _, problems = cp.compile_pages(self.proj)
        self.assertTrue(any("roles/neu.md" in p and "clusters/" in p for p in problems))
        self.assertTrue(any("tasks/neu.md" in p and "Gibtesnicht" in p for p in problems))

    def test_duplicate_names_and_line_numbers(self):
        shutil.copy(self.pages / "roles" / "kreditprufer.md", self.pages / "roles" / "kopie.md")
        bad = self.pages / "agents" / "kaputt.md"
        bad.write_text('---\ntype: "agent"\nname: "K"\npattern: "x"\nk: {a: 1}\n---\n', encoding="utf-8")
        _, problems = cp.compile_pages(self.proj)
        self.assertTrue(any("doppelt" in p for p in problems))
        self.assertTrue(any("05_pages/agents/kaputt.md:5" in p for p in problems))

    def test_removed_cluster_page_removes_its_register(self):
        clu = self.pages / "clusters" / "zweiter.md"
        clu.write_text('---\ntype: "cluster"\njob_family: "F"\njob_cluster: "Zweiter"\n---\n\n## Jobfamilie\n\nx\n\n## Jobcluster\n\ny\n', encoding="utf-8")
        (self.pages / "roles" / "z.md").write_text('---\ntype: "role"\nname: "Z"\ncluster: "Zweiter"\n---\n\n## Zweck\n\nz\n', encoding="utf-8")
        self.assertEqual(run("compile_pages.py", "--project", str(self.proj)).returncode, 0)
        self.assertTrue((self.proj / "10_extraction" / "extract_zweiter.json").exists())
        clu.unlink()
        (self.pages / "roles" / "z.md").unlink()
        r = run("compile_pages.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse((self.proj / "10_extraction" / "extract_zweiter.json").exists())
        self.assertIn("Entfernt", r.stdout)

    def test_agent_tasks_by_name_resolve_to_ids(self):
        out, problems = cp.compile_pages(self.proj)
        self.assertEqual(problems, [])
        agent = next(a for a in out["agents"] if a["name"] == "Zahlungszuordnungs-Agent")
        self.assertIn(wl.make_id("task", "Forderungsmanager", "Zahlungseingänge zuordnen"), agent["task_ids"])


if __name__ == "__main__":
    unittest.main()
