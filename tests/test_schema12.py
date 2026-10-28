"""Schema 1.2: Realisierbarkeit, Zielbild, Reichweite, Nutzungsstand, Rahmen, Export.

Wie die übrigen Tests prüfen diese die unbequemen Fälle: ein unterdrückter Satz mit Zahlen,
eine Telemetrie mit Personenbezug, ein Pilot ohne Rahmen, eine Auffangbarkeit, die es nicht
gibt und trotzdem als null erscheint.
"""

from __future__ import annotations

import copy
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, ROOT, load, script, validate_graph, wl  # noqa: E402

sr = load("task-scorer", "score_roles")
btr = load("task-scorer", "build_target_roles")
mrl = load("work-graph-builder", "make_review_list")
cv = load("transformation-dashboard", "capacity_views")
es = load("agent-mapper", "export_skill")
cs = load("work-transformation", "check_suite")

PIPELINE = ROOT / "skills" / "work-transformation" / "scripts" / "run_pipeline.py"


def example_graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


class TestCapacity(unittest.TestCase):
    def test_technical_counts_delegated_fully_and_assisted_by_a_fifth(self):
        c = sr.capacity({"headcount": 10}, 50.0, 50.0)
        self.assertEqual(c["fte_released_technical"], 6.0)

    def test_unassessed_absorption_is_not_zero(self):
        c = sr.capacity({"headcount": 10}, 50.0, 0.0)
        self.assertIsNone(c["fte_realisable"], "Nicht bewertet darf nicht als 0 erscheinen")

    def test_none_means_zero_and_percentage_scales(self):
        self.assertEqual(sr.capacity({"headcount": 10, "absorption": "none"}, 50.0, 0.0)["fte_realisable"], 0.0)
        c = sr.capacity({"headcount": 10, "absorption": "growth", "absorption_pct": 40}, 50.0, 0.0)
        self.assertEqual(c["fte_realisable"], 2.0)

    def test_without_headcount_there_is_no_fte(self):
        c = sr.capacity({"absorption": "growth"}, 50.0, 50.0)
        self.assertIsNone(c["fte_released_technical"])
        self.assertIsNone(c["fte_realisable"])

    def test_positions_win_over_the_set_headcount(self):
        c = sr.capacity({"headcount": 10, "headcount_from_positions": 5.0}, 100.0, 0.0)
        self.assertEqual(c["fte_released_technical"], 5.0)

    def test_realisable_never_exceeds_technical_in_the_example(self):
        for t in example_graph()["target_roles"]:
            if t["fte_realisable"] is not None:
                self.assertLessEqual(t["fte_realisable"], t["fte_released_technical"] + 0.051)


class TestTargetRoles(unittest.TestCase):
    def test_every_scored_role_gets_a_draft(self):
        g = example_graph()
        rows = btr.build(g)
        self.assertEqual(len(rows), len([r for r in g["roles"] if r["analysis"].get("scored")]))
        self.assertTrue(all(r["basis"] == "estimated" and r["status"] == "draft" for r in rows))

    def test_roles_with_little_left_in_one_cluster_are_merge_candidates(self):
        g = example_graph()
        for r in g["roles"]:
            r["analysis"]["fte_released_technical"] = float(r["analysis"]["headcount_basis"]) - 0.4
        rows = {r["name"]: r for r in btr.build(g)}
        self.assertTrue(all(r["merge_with_role_ids"] for r in rows.values()))
        self.assertNotIn(rows["Kreditprüfer"]["role_id"], rows["Kreditprüfer"]["merge_with_role_ids"])

    def test_merge_needs_a_partner(self):
        g = example_graph()
        for r in g["roles"]:
            r["analysis"]["fte_released_technical"] = 0.0
            r["analysis"]["disruption_type"] = "stable"
        g["roles"][0]["analysis"]["fte_released_technical"] = float(g["roles"][0]["analysis"]["headcount_basis"]) - 0.2
        rows = btr.build(g)
        self.assertTrue(all(not r["merge_with_role_ids"] for r in rows), "Eine kleine Rolle allein ist kein Paar")


class TestValidatorSchema12(unittest.TestCase):
    def test_example_graph_is_clean(self):
        errors, _ = validate_graph.validate(example_graph())
        self.assertEqual(errors, [])

    def test_unknown_absorption_is_rejected(self):
        g = example_graph()
        g["roles"][0]["absorption"] = "magie"
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("absorption" in e for e in errors))

    def test_pilot_without_frame_warns(self):
        g = example_graph()
        ready = next(x for x in g["experiments"] if x["status"] == "ready")
        ready["frame_confirmed"] = False
        _, warnings = validate_graph.validate(g)
        self.assertTrue(any("Rahmen nicht bestätigt" in w for w in warnings))
        ready["frame_confirmed"] = True
        ready["frame_note"] = "Dienstvereinbarung"
        _, warnings = validate_graph.validate(g)
        self.assertFalse(any("Rahmen nicht bestätigt" in w and ready["id"] in w for w in warnings))

    def test_telemetry_must_be_aggregate_and_impersonal(self):
        g = example_graph()
        c = g["agents"][0]["contract"]
        c["telemetry"] = {"level": "user", "fields": ["user_id"]}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("telemetry.level" in e for e in errors))
        self.assertTrue(any("'user_id'" in e for e in errors))
        c["telemetry"] = {"level": "aggregate", "fields": ["outcome"]}
        errors, _ = validate_graph.validate(g)
        self.assertEqual(errors, [])

    def test_small_adoption_group_must_be_suppressed(self):
        g = example_graph()
        row = next(a for a in g["adoption"] if not a.get("suppressed"))
        row["group_size"] = 3
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("Mindestgruppengröße" in e for e in errors))

    def test_suppressed_adoption_must_not_carry_numbers(self):
        g = example_graph()
        row = next(a for a in g["adoption"] if a.get("suppressed"))
        row["in_use"] = 1
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("unterdrückter Satz" in e for e in errors))

    def test_solution_class_is_checked(self):
        g = example_graph()
        g["blueprints"][0]["steps"][0]["solution_class"] = "zauber"
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("solution_class" in e for e in errors))

    def test_non_ai_class_with_an_agent_executor_warns(self):
        g = example_graph()
        bp = g["blueprints"][0]
        st = next(s for s in bp["steps"] if (s.get("executor") or {}).get("type") == "agent")
        st["solution_class"] = "interface"
        _, warnings = validate_graph.validate(g)
        self.assertTrue(any("keine KI-Lösung" in w for w in warnings))

    def test_usecase_with_unknown_task_is_rejected(self):
        g = example_graph()
        g["usecases"][0]["task_ids"] = ["ta_gibtesnicht"]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("ta_gibtesnicht" in e for e in errors))


class TestReach(unittest.TestCase):
    def test_reach_lists_roles_with_fte(self):
        reach = {r["name"]: r for r in wl.agent_reach(example_graph())}
        uc = reach["Zahlungseingang automatisch zuordnen"]
        self.assertEqual(uc["kind"], "usecase")
        self.assertEqual(uc["value_eur_declared"], 48000.0)
        self.assertEqual(len(uc["roles"]), 1)
        self.assertGreater(uc["fte_total"], 0)

    def test_value_needs_a_day_rate(self):
        g = example_graph()
        for r in g["roles"]:
            r.pop("day_rate_eur", None)
        self.assertTrue(all(r["value_eur_estimated"] is None for r in wl.agent_reach(g)))

    def test_blind_spots_appear_when_nobody_asks(self):
        g = example_graph()
        self.assertEqual(wl.blind_spots(g), [])
        g["agents"], g["usecases"] = [], []
        spots = wl.blind_spots(g)
        self.assertEqual(len(spots), len([p for p in g["processes"] if p["value"]["band"] in ("now", "next")]))
        self.assertTrue(all(s["band"] in ("now", "next") for s in spots))

    def test_family_capacity_separates_technical_and_realisable(self):
        fam = wl.family_capacity(example_graph())[0]
        self.assertGreater(fam["fte_technical"], fam["fte_realisable"])
        self.assertEqual(fam["roles_unassessed"], 1)


class TestReports(unittest.TestCase):
    def test_hr_report_never_says_a_role_is_dropped(self):
        text = cv.hr_report(example_graph(), "Titel")
        self.assertNotIn("entfällt", text)
        self.assertIn("nicht bewertet", text, "Fehlende Auffangbarkeit muss sichtbar bleiben")
        self.assertIn("Entwurf", text)

    def test_it_backlog_names_evidence_and_blind_spots(self):
        g = example_graph()
        text = cv.it_backlog(g, "Titel", g["agents"])
        self.assertIn("Heuristik", text)
        self.assertIn("Blindflecken", text)

    def test_dashboard_sections_only_with_data(self):
        g = example_graph()
        html, nav = cv.sections(g)
        self.assertEqual([h for h, _ in nav], ["#kapazitaet", "#zielbild", "#nutzung", "#reichweite"])
        self.assertIn("unterdrückt", html)
        empty = wl.empty_graph()
        self.assertEqual(cv.sections(empty), ("", []))


class TestReviewList(unittest.TestCase):
    def tasks(self, n, skills=None):
        return [{"id": f"ta_{i}", "skill_ids": (skills[i] if skills else [])} for i in range(n)]

    def test_many_tasks_flag_a_split(self):
        self.assertIsNotNone(mrl.split_hint(self.tasks(10)))
        self.assertIsNone(mrl.split_hint(self.tasks(9)))

    def test_disjoint_skills_flag_a_split(self):
        disjoint = [[f"sk_{i}"] for i in range(6)]
        self.assertIn("Skill", mrl.split_hint(self.tasks(6, disjoint)))
        shared = [["sk_a", f"sk_{i}"] for i in range(6)]
        self.assertIsNone(mrl.split_hint(self.tasks(6, shared)))


class TestSkillExport(unittest.TestCase):
    def test_slug_never_contains_reserved_words(self):
        for name in ("Claude-Assistent", "Anthropic Helfer", "Über-Agent"):
            s = es.slug(name)
            self.assertFalse(any(w in s for w in es.RESERVED), s)
            self.assertRegex(s, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_generated_skeleton_is_a_valid_skill(self):
        g = example_graph()
        entries = list(es.collect(g, {"pilot"}, ""))
        self.assertTrue(entries)
        a, c, steps, tasks = entries[0]
        name = es.slug(a["name"])
        md = es.skill_md(a, c, steps, tasks, name)
        meta = cs.frontmatter(md)
        self.assertEqual(meta["name"], name)
        self.assertLessEqual(len(meta["description"]), 1024)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "run.py"
            p.write_text(es.run_py(a, c, name), encoding="utf-8")
            py_compile.compile(str(p), doraise=True)
            r = Path(tmp) / "report_usage.py"
            r.write_text(es.REPORT_PY, encoding="utf-8")
            py_compile.compile(str(r), doraise=True)

    def test_skeleton_does_not_mention_models(self):
        g = example_graph()
        a, c, steps, tasks = next(iter(es.collect(g, {"pilot"}, "")))
        text = es.skill_md(a, c, steps, tasks, "x") + es.run_py(a, c, "x")
        for hint in validate_graph.MODEL_NAME_HINTS:
            self.assertNotIn(hint, text.lower())


class TestImports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.project = Path(cls.tmp) / "o2c"
        shutil.copytree(EXAMPLE, cls.project)
        shutil.rmtree(cls.project / "expected")
        r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(cls.project)],
                           cwd=str(ROOT), capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_script(self, skill, name, *args):
        return subprocess.run([sys.executable, str(script(skill, name)), "--project", str(self.project), *args],
                              cwd=str(ROOT), capture_output=True, text=True)

    def test_second_run_creates_no_version(self):
        before = sorted(p.name for p in (self.project / "20_graph").glob("work-graph_v*.json"))
        r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(self.project)],
                           cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = sorted(p.name for p in (self.project / "20_graph").glob("work-graph_v*.json"))
        self.assertEqual(before, after, "Auch mit Schema-1.2-Eingaben muss ein zweiter Lauf folgenlos bleiben")

    def test_min_group_cannot_be_lowered_below_the_rule(self):
        r = self.run_script("agent-mapper", "import_adoption", "--min-group", "2")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nicht unterschreiten", r.stdout + r.stderr)

    def test_small_role_is_suppressed_on_import(self):
        g = json.loads((self.project / "20_graph" / "work-graph_latest.json").read_text(encoding="utf-8"))
        small = [a for a in g["adoption"] if a.get("suppressed")]
        self.assertEqual(len(small), 1)
        self.assertNotIn("in_use", small[0])

    def test_more_reported_than_existing_is_suppressed_not_trusted(self):
        (self.project / "00_input" / "adoption.csv").write_text(
            "agent;role;prioritized;building;in_use\nAuftragserfassungs-Agent;Auftragssachbearbeiter;9;9;9\n",
            encoding="utf-8")
        r = self.run_script("agent-mapper", "import_adoption")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        g = json.loads((self.project / "20_graph" / "work-graph_latest.json").read_text(encoding="utf-8"))
        self.assertTrue(all(a.get("suppressed") for a in g["adoption"]))

    def test_unknown_usecase_task_is_reported_not_guessed(self):
        (self.project / "00_input" / "usecases.csv").write_text(
            "name;description;owner;status;value_eur_per_year;tasks\nGeist;;;idea;;Niemand > Nichts\n",
            encoding="utf-8")
        r = self.run_script("agent-mapper", "import_usecases")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nicht im Graphen", r.stdout)

    def test_process_house_import_writes_an_extraction(self):
        csv = self.project / "00_input" / "prozesshaus.csv"
        csv.write_text("process;step;role;aufgabe;handling_time_min;wait_time_min;system\n"
                       "Mahnwesen;Mahnung prüfen;Forderungsmanager;Mahnlauf vorbereiten und prüfen;10;60;ERP\n"
                       "Mahnwesen;Mahnung senden;Unbekannte Rolle;;5;0;\n", encoding="utf-8")
        r = self.run_script("work-graph-builder", "import_process_house", "--source", "Prozesshaus Test")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nicht im Graphen", r.stdout)
        out = json.loads((self.project / "10_extraction" / "process_prozesshaus-test.json").read_text(encoding="utf-8"))
        self.assertEqual(len(out["processes"][0]["steps"]), 1)
        self.assertEqual(out["processes"][0]["steps"][0]["tasks"], ["Mahnlauf vorbereiten und prüfen"])
        (self.project / "10_extraction" / "process_prozesshaus-test.json").unlink()

    def test_reach_report_is_written(self):
        r = self.run_script("agent-mapper", "export_reach")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(list((self.project / "40_output").glob("reach_v*.md")))


class TestMigration12(unittest.TestCase):
    def test_schema_11_gains_the_new_collections(self):
        old = {"meta": {"schema_version": "1.1"}}
        for c in wl.COLLECTIONS_CORE + wl.COLLECTIONS_PROCESS + wl.COLLECTIONS_REDESIGN + wl.COLLECTIONS_GOVERNANCE:
            old[c] = []
        old["roles"] = [{"id": "ro_x", "name": "Bestand"}]
        notes = wl.migrate_graph(old)
        self.assertEqual(old["meta"]["schema_version"], "1.2")
        for c in wl.COLLECTIONS_ADOPTION:
            self.assertEqual(old[c], [])
        self.assertEqual(old["roles"], [{"id": "ro_x", "name": "Bestand"}])
        self.assertTrue(any("target_roles" in n for n in notes))

    def test_minimum_group_is_a_constant_of_the_library(self):
        self.assertGreaterEqual(wl.ADOPTION_MIN_GROUP, 5)


if __name__ == "__main__":
    unittest.main()
