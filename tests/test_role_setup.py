"""Rollen-Setup: Paket je Rolle aus dem Arbeitsgraphen.

Geprüft wird vor allem, was das Paket NICHT behaupten darf: erfundenen Kontext, echte Testfälle, Freigaben, aktive Routinen,
einen überladenen Systemprompt — und dass ein erneuter Lauf bearbeitete Dateien in Ruhe lässt.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, load, wl  # noqa: E402
from test_preparation import mini_graph  # noqa: E402

brs = load("agent-mapper", "build_role_setup")
crs = load("agent-mapper", "check_role_setup")


def example_graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


def role(g, name):
    return brs.find_role(g, name)


class TestRoleLookup(unittest.TestCase):
    def test_find_by_name_id_and_spelling(self):
        g = example_graph()
        r = role(g, "Forderungsmanager")
        self.assertEqual(role(g, r["id"])["name"], "Forderungsmanager")
        self.assertEqual(role(g, "forderungsmanager")["id"], r["id"])

    def test_unknown_role_gives_suggestions_not_a_guess(self):
        g = example_graph()
        self.assertIsNone(role(g, "Forderung"))
        self.assertEqual(brs.similar_roles(g, "Forderung"), ["Forderungsmanager"])
        self.assertIsNone(role(g, "Gibtesnicht"))


class TestSkillGroups(unittest.TestCase):
    def test_same_agent_means_one_skill(self):
        g = example_graph()
        groups, _ = brs.skill_groups(g, role(g, "Auftragssachbearbeiter"), 5)
        keys = [x["key"] for x in groups]
        self.assertEqual(len(keys), len(set(keys)))
        agent_group = next(x for x in groups if x["agent"] and x["agent"]["name"] == "Auftragserfassungs-Agent")
        self.assertGreaterEqual(len(agent_group["tasks"]), 2)

    def test_highest_weight_first(self):
        g = example_graph()
        groups, _ = brs.skill_groups(g, role(g, "Auftragssachbearbeiter"), 5)
        weights = [x["weight"] for x in groups]
        self.assertEqual(weights, sorted(weights, reverse=True))

    def test_manual_core_gets_an_honest_note(self):
        g = mini_graph()
        for t in g["tasks"]:
            t["mode"] = "manual"
        groups, note = brs.skill_groups(g, g["roles"][0], 4)
        self.assertTrue(groups)
        self.assertIn("menschlich", note)

    def test_requested_count_is_clamped(self):
        g = mini_graph()
        g["tasks"] += [{"id": f"ta_x{i}", "role_id": "ro_a", "name": f"Aufgabe {i}", "description": "", "share_of_time": 5, "frequency": "weekly",
                        "nature": "cognitive", "status": "generated", "skill_ids": [], "agent_ids": []} for i in range(10)]
        groups, _ = brs.skill_groups(g, g["roles"][0], 99)
        self.assertEqual(len(groups), brs.MAX_SKILLS)


class TestContextProfile(unittest.TestCase):
    def setUp(self):
        self.g = example_graph()
        self.r = role(self.g, "Forderungsmanager")
        self.groups, _ = brs.skill_groups(self.g, self.r, 4)

    def test_unknowable_fields_stay_open(self):
        text, filled, open_n = brs.kontextprofil(self.g, self.r, self.groups)
        for label in ("Geschäftsmodell", "Produkte und Leistungen", "Tonalität", "Qualitätsverständnis", "Persönliche Prioritäten"):
            self.assertRegex(text, rf"\*\*{label}[^\n]*\*\*:? ?\*?\*? ?{brs.OPEN}|{label}[^\n]*{brs.OPEN}")
        self.assertGreater(open_n, 0)
        self.assertGreater(filled, 0)

    def test_graph_lines_carry_their_origin(self):
        text, _f, _o = brs.kontextprofil(self.g, self.r, self.groups)
        self.assertIn("Ordnet Zahlungseingänge zu", text)
        self.assertIn(brs.GRAPH, text)

    def test_decision_scope_is_readable(self):
        text, _f, _o = brs.kontextprofil(self.g, self.r, self.groups)
        self.assertNotIn("execute_reversible", text)

    def test_unknown_company_data_is_not_invented(self):
        g = example_graph()
        g["meta"]["organization"] = ""
        text, _f, _o = brs.kontextprofil(g, self.r, self.groups)
        self.assertIn(f"**Organisation:** {brs.OPEN}", text)

    def test_interview_forbids_inventing(self):
        text = brs.interview_prompt(self.r, 7)
        self.assertIn("Erfinde nichts", text)
        self.assertIn("7 Felder", text)


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.g = example_graph()
        self.r = role(self.g, "Auftragssachbearbeiter")
        self.files = brs.build_package(self.g, self.r, 4)

    def test_expected_files_exist(self):
        for rel in ("README.md", "kontext/kontextprofil.md", "kontext/interview-prompt.md", "agent/systemprompt.md", "tools/anbindungen.md",
                    "routinen/routinen.json", "routinen/routinen.md", "pflege/pflege.md"):
            self.assertIn(rel, self.files)
        self.assertTrue(any(k.endswith("/SKILL.md") for k in self.files))

    def test_system_prompt_is_lean_and_holds_no_task_detail(self):
        text = self.files["agent/systemprompt.md"]
        self.assertLessEqual(len(text.splitlines()), crs.MAX_PROMPT_LINES)
        self.assertLessEqual(len(text), crs.MAX_PROMPT_CHARS)
        for t in self.g["tasks"]:
            if t["role_id"] == self.r["id"]:
                self.assertNotIn(t["name"], text, "Aufgaben gehören in Skills, nicht in den Prompt")

    def test_every_skill_has_a_valid_frontmatter(self):
        for rel, text in self.files.items():
            if rel.endswith("/SKILL.md"):
                fm = crs.frontmatter(text)
                self.assertIsNotNone(fm, rel)
                self.assertEqual(fm["name"], rel.split("/")[1])
                self.assertLessEqual(len(fm["description"]), 1024)

    def test_cases_are_scaffolds_not_evidence(self):
        for rel, text in self.files.items():
            if rel.endswith("cases.json"):
                doc = json.loads(text)
                self.assertGreaterEqual(len(doc["cases"]), brs.MIN_CASES)
                self.assertTrue(all(c["real_data"] is False and c["last_result"] is None for c in doc["cases"]))
                self.assertEqual(crs.readiness(doc)[0], "entwurf")
                self.assertIn("fehlende_eingabe", {c["art"] for c in doc["cases"]})
                self.assertIn("eskalation", {c["art"] for c in doc["cases"]})

    def test_write_permissions_add_a_repeat_case(self):
        kinds = {c["art"] for rel, t in self.files.items() if rel.endswith("cases.json") for c in json.loads(t)["cases"]}
        self.assertIn("wiederholung", kinds, "Der Auftragserfassungs-Agent schreibt, also braucht er den Wiederholungsfall")

    def test_every_routine_is_inactive(self):
        doc = json.loads(self.files["routinen/routinen.json"])
        self.assertTrue(doc["routines"])
        self.assertTrue(all(r["active"] is False for r in doc["routines"]))

    def test_tools_table_gives_no_approval(self):
        text = self.files["tools/anbindungen.md"]
        self.assertIn(brs.OPEN, text)
        self.assertNotRegex(text, r"\|\s*freigegeben\s*\|")
        self.assertIn("Diese Tabelle gibt keine Freigabe", text)

    def test_personal_data_systems_are_flagged(self):
        g = example_graph()
        g["systems"][0]["data_classes"] = ["personal"]
        sid = g["systems"][0]["id"]
        r = role(g, "Auftragssachbearbeiter")
        for s in g["process_steps"]:
            if s.get("role_id") == r["id"]:
                s["system_ids"] = sorted(set(s.get("system_ids", [])) | {sid})
        groups, _ = brs.skill_groups(g, r, 4)
        _t, rows = brs.tool_table(g, r, groups)
        self.assertTrue(any("besonders prüfen" in x["flag"] for x in rows))

    def test_no_playbook_numbers_used_as_value(self):
        blob = "\n".join(self.files.values())
        self.assertNotIn("Arbeitstag pro Woche", blob.replace("Selbstauskünfte", ""))
        self.assertIn("keine Messung", blob)

    def test_build_is_deterministic(self):
        again = brs.build_package(example_graph(), role(example_graph(), "Auftragssachbearbeiter"), 4)
        self.assertEqual(self.files, again)

    def test_every_role_gets_a_package(self):
        g = example_graph()
        for r in g["roles"]:
            files = brs.build_package(g, r, 4)
            self.assertIn("kontext/kontextprofil.md", files, r["name"])


class TestWriteAndProtect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = Path(self.tmp) / "pkg"
        self.g = example_graph()
        self.files = brs.build_package(self.g, role(self.g, "Forderungsmanager"), 4)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_write_changes_nothing(self):
        brs.write_package(self.out, self.files)
        written, proposed, unchanged = brs.write_package(self.out, self.files)
        self.assertEqual((written, proposed), ([], []))
        self.assertTrue(unchanged)

    def test_edited_file_is_never_overwritten(self):
        brs.write_package(self.out, self.files)
        prof = self.out / "kontext" / "kontextprofil.md"
        prof.write_text(prof.read_text(encoding="utf-8").replace(brs.OPEN, "Antwort", 1), encoding="utf-8")
        edited = prof.read_text(encoding="utf-8")
        files2 = dict(self.files)
        files2["kontext/kontextprofil.md"] = self.files["kontext/kontextprofil.md"] + "\nNeue Zeile aus dem Graphen\n"
        written, proposed, _ = brs.write_package(self.out, files2)
        self.assertIn("kontext/kontextprofil.md", proposed)
        self.assertEqual(prof.read_text(encoding="utf-8"), edited)
        self.assertTrue((self.out / "kontext" / "kontextprofil.md.vorschlag").exists())

    def test_untouched_file_is_updated(self):
        brs.write_package(self.out, self.files)
        files2 = dict(self.files)
        files2["pflege/pflege.md"] = self.files["pflege/pflege.md"] + "\nNeu\n"
        written, proposed, _ = brs.write_package(self.out, files2)
        self.assertIn("pflege/pflege.md", written)
        self.assertEqual(proposed, [])

    def test_real_test_cases_survive_a_rebuild(self):
        brs.write_package(self.out, self.files)
        cp = next(self.out.glob("skills/*/evals/cases.json"))
        doc = json.loads(cp.read_text(encoding="utf-8"))
        for c in doc["cases"]:
            c["real_data"], c["last_result"] = True, "pass"
        doc["tested_loops"] = 2
        cp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        brs.write_package(self.out, self.files)
        self.assertEqual(crs.readiness(json.loads(cp.read_text(encoding="utf-8")))[0], "live-reif")


class TestReadiness(unittest.TestCase):
    def doc(self, real=5, loops=2, result="pass"):
        return {"min_cases": 5, "min_loops": 2, "tested_loops": loops,
                "cases": [{"id": f"c{i}", "real_data": i < real, "last_result": result if i < real else None} for i in range(6)]}

    def test_stages(self):
        self.assertEqual(crs.readiness(self.doc(real=4))[0], "entwurf")
        self.assertEqual(crs.readiness(self.doc(loops=1))[0], "im Test")
        self.assertEqual(crs.readiness(self.doc(result="fail"))[0], "im Test")
        self.assertEqual(crs.readiness(self.doc())[0], "live-reif")

    def test_one_failed_case_blocks_live(self):
        d = self.doc()
        d["cases"][0]["last_result"] = "fail"
        self.assertEqual(crs.readiness(d)[0], "im Test")


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = Path(self.tmp) / "pkg"
        g = example_graph()
        brs.write_package(self.out, brs.build_package(g, role(g, "Forderungsmanager"), 4))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fresh_package_is_incomplete_but_not_wrong(self):
        problems, notes, skills, summary = crs.check(self.out)
        self.assertEqual(problems, [])
        self.assertTrue(all(s["status"] == "entwurf" for s in skills))
        self.assertGreater(summary["open_fields"], 0)
        self.assertTrue(any("ohne Freigabe" in n for n in notes))

    def test_active_routine_for_an_unready_skill_is_a_problem(self):
        rj = self.out / "routinen" / "routinen.json"
        doc = json.loads(rj.read_text(encoding="utf-8"))
        doc["routines"][0]["active"] = True
        rj.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        problems, *_ = crs.check(self.out)
        self.assertTrue(any("erst erweitern, dann automatisieren" in p for p in problems))

    def test_active_routine_is_fine_once_the_skill_is_live_ready(self):
        cp = next(self.out.glob("skills/*/evals/cases.json"))
        skill = cp.parent.parent.name
        doc = json.loads(cp.read_text(encoding="utf-8"))
        for c in doc["cases"]:
            c["real_data"], c["last_result"] = True, "pass"
        doc["tested_loops"] = 2
        cp.write_text(json.dumps(doc), encoding="utf-8")
        rj = self.out / "routinen" / "routinen.json"
        rd = json.loads(rj.read_text(encoding="utf-8"))
        for r in rd["routines"]:
            if r["skill"] == skill:
                r["active"] = True
        rj.write_text(json.dumps(rd), encoding="utf-8")
        problems, *_ = crs.check(self.out)
        self.assertEqual([p for p in problems if skill in p], [])

    def test_overloaded_system_prompt_is_a_problem(self):
        sp = self.out / "agent" / "systemprompt.md"
        sp.write_text(sp.read_text(encoding="utf-8") + "\n".join(f"Aufgabe {i}: mach das so und so." for i in range(200)), encoding="utf-8")
        problems, *_ = crs.check(self.out)
        self.assertTrue(any("Systemprompt zu lang" in p for p in problems))

    def test_missing_cases_are_a_problem(self):
        next(self.out.glob("skills/*/evals/cases.json")).unlink()
        problems, *_ = crs.check(self.out)
        self.assertTrue(any("ohne Testfälle" in p for p in problems))

    def test_broken_frontmatter_is_a_problem(self):
        md = next(self.out.glob("skills/*/SKILL.md"))
        md.write_text("kein Frontmatter", encoding="utf-8")
        problems, *_ = crs.check(self.out)
        self.assertTrue(any("Frontmatter" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
