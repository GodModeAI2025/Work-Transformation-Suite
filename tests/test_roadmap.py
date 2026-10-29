"""Fahrplan-Raster und Unterlagen.

Geprüft wird vor allem, was das Raster NICHT behaupten darf: Entscheidungen ohne Person, erfundene
Zeiträume, eine Null für fehlende Angaben, doppelt gezählte Aufgaben, versandfertige Entwürfe.
"""

from __future__ import annotations

import copy
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

rl = load("transformation-roadmap", "roadmap_lib")
rv = load("transformation-roadmap", "roadmap_views")
render = load("transformation-roadmap", "render_lib")
docs = load("transformation-roadmap", "build_documents")


def graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


def cfg() -> dict:
    return rl.load_config()


def plan_of(g=None, decisions=None, config=None):
    return rl.plan(g or graph(), config or cfg(), decisions)


class TestConfig(unittest.TestCase):
    def test_default_config_is_valid(self):
        self.assertEqual(rl.check_config(cfg()), [])

    def test_rejects_broken_waves_and_weights(self):
        c = cfg()
        c["waves"] = [{"id": 2, "label": "a", "capacity": 1}, {"id": 1, "label": "b", "capacity": 1}]
        self.assertTrue(any("aufsteigend" in p for p in rl.check_config(c)))
        c = cfg()
        c["weights"] = {"value": 1}
        self.assertTrue(any("weights" in p for p in rl.check_config(c)))
        c = cfg()
        c["waves"][0]["capacity"] = 0
        self.assertTrue(any("capacity" in p for p in rl.check_config(c)))

    def test_project_config_overrides_but_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"weights": {"value": 0.5}, "max_complexity_first_wave": 2}), encoding="utf-8")
            c = rl.load_config(path)
        self.assertEqual(c["weights"]["value"], 0.5)
        self.assertEqual(c["weights"]["reach"], 0.20)
        self.assertEqual(c["max_complexity_first_wave"], 2)


class TestCandidates(unittest.TestCase):
    def test_usecase_with_agent_folds_into_the_agent(self):
        g = graph()
        agent = g["agents"][0]
        g["usecases"] = [{"id": "uc_x", "name": "Eigener Fall", "agent_ids": [agent["id"]], "task_ids": [],
                          "status": "idea", "value_eur_per_year": 1000.0}]
        cands = rl.build_candidates(g, cfg())
        self.assertEqual(len(cands), len(g["agents"]))
        mine = next(c for c in cands if c["key"] == agent["id"])
        self.assertEqual(mine["usecases"], ["Eigener Fall"])
        self.assertEqual(mine["value_declared_eur"], 1000.0)

    def test_standalone_usecase_is_its_own_candidate(self):
        cands = rl.build_candidates(graph(), cfg())
        self.assertIn("usecase", {c["kind"] for c in cands})

    def test_missing_headcount_is_not_zero(self):
        g = graph()
        for r in g["roles"]:
            r.pop("headcount", None)
            r.pop("headcount_from_positions", None)
        cands = rl.build_candidates(g, cfg())
        rl.score_candidates(cands, cfg())
        for c in cands:
            self.assertIsNone(c["fte"])
            self.assertIsNone(c["value_estimated_eur"])
        self.assertEqual(render.eur(None), "nicht bewertet")

    def test_overlapping_tasks_count_once(self):
        g = graph()
        a, b = g["agents"][0], g["agents"][1]
        shared = list(a["task_ids"])
        both = rl.reach_of_tasks(g, shared + shared + list(b["task_ids"]))
        union = rl.reach_of_tasks(g, sorted(set(shared) | set(b["task_ids"])))
        self.assertEqual(both["fte_total"], union["fte_total"])
        self.assertEqual(both["value_eur"], union["value_eur"])


class TestScore(unittest.TestCase):
    def test_score_ignores_unknown_components_instead_of_using_zero(self):
        p = plan_of()
        usecase = next(c for c in p["candidates"] if c["kind"] == "usecase" and c["complexity"] is None)
        self.assertIsNone(usecase["components"]["ease"])
        self.assertIn("es fehlt", usecase["score_basis"])
        self.assertIsNotNone(usecase["score"])

    def test_too_few_components_leaves_score_empty(self):
        c = cfg()
        c["min_components"] = 5
        p = plan_of(config=c)
        incomplete = [x for x in p["candidates"] if None in x["components"].values()]
        self.assertTrue(incomplete)
        for x in incomplete:
            self.assertIsNone(x["score"])
            self.assertIn("nicht bewertet", x["score_basis"])

    def test_scores_are_between_zero_and_ten(self):
        for c in plan_of()["candidates"]:
            if c["score"] is not None:
                self.assertGreaterEqual(c["score"], 0)
                self.assertLessEqual(c["score"], 10)


class TestWaves(unittest.TestCase):
    def test_running_candidates_start_in_wave_one(self):
        p = plan_of()
        for c in p["candidates"]:
            if c["status"] in ("pilot", "live"):
                self.assertEqual(p["placement"][c["key"]]["wave"], 1)
                self.assertEqual(p["placement"][c["key"]]["state"], "running")

    def test_every_candidate_lands_in_exactly_one_wave(self):
        p = plan_of()
        placed = [k for w in p["waves"] for k in w["items"]]
        self.assertEqual(sorted(placed), sorted(c["key"] for c in p["candidates"]))

    def test_orchestrator_follows_the_agents_it_steers(self):
        p = plan_of()
        orch = next(c for c in p["candidates"] if c["orchestrates"])
        mine = p["placement"][orch["key"]]["wave"]
        for m in orch["orchestrates"]:
            self.assertGreater(mine, p["placement"][m]["wave"])

    def test_heavy_candidate_does_not_start_in_wave_one(self):
        c = cfg()
        c["max_complexity_first_wave"] = 2
        c["running_statuses"] = []
        p = plan_of(config=c)
        for x in p["candidates"]:
            if x["complexity"] is not None and x["complexity"] > 2:
                self.assertGreater(p["placement"][x["key"]]["wave"], 1, x["name"])

    def test_decision_with_person_is_confirmed_and_without_is_ignored(self):
        g = graph()
        cands = rl.build_candidates(g, cfg())
        key = next(c["key"] for c in cands if c["name"] == "Mahnlauf-Agent")
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            (proj / "30_review").mkdir()
            (proj / "30_review" / "wellen.csv").write_text(
                "eintrag;welle;begruendung;entschieden_von;datum\n"
                "Mahnlauf-Agent;3;später;Name Person;2026-06-01\n"
                "Bonitäts-Agent;3;ohne Person;;2026-06-01\n"
                "Gibtesnicht;1;x;Name;2026-06-01\n"
                "Fakturierungs-Agent;9;falsche Welle;Name;2026-06-01\n", encoding="utf-8")
            decisions, warnings = rl.read_decisions(proj, cands, cfg())
        self.assertEqual(list(decisions), [key])
        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("ohne Verantwortlichen" in w for w in warnings))
        p = rl.plan(g, cfg(), decisions)
        self.assertEqual(p["placement"][key]["wave"], 3)
        self.assertEqual(p["placement"][key]["state"], "confirmed")
        bonitaet = next(c["key"] for c in cands if c["name"] == "Bonitäts-Agent")
        self.assertEqual(p["placement"][bonitaet]["state"], "running")

    def test_dependency_violated_by_decision_is_reported_not_changed(self):
        g = graph()
        cands = rl.build_candidates(g, cfg())
        orch = next(c for c in cands if c["orchestrates"])
        p = rl.plan(g, cfg(), {orch["key"]: {"wave": 1, "reason": "", "decided_by": "Name", "date": ""}})
        self.assertEqual(p["placement"][orch["key"]]["wave"], 1)
        self.assertTrue(any("Abhängigkeit" in n for n in p["notes"]))

    def test_wave_state_labels(self):
        self.assertEqual(rl._wave_state([]), "empty")
        self.assertEqual(rl._wave_state(["proposed", "proposed"]), "proposed")
        self.assertEqual(rl._wave_state(["proposed", "running"]), "partial")
        self.assertEqual(rl._wave_state(["confirmed", "running"]), "settled")

    def test_cumulative_reach_is_union_not_sum(self):
        p = plan_of()
        total = p["waves"][-1]["cumulative_reach"]["fte_total"]
        summed = sum(w["reach"]["fte_total"] for w in p["waves"])
        self.assertLessEqual(total, summed + 0.05)
        union = rl.reach_of_tasks(graph(), sorted({t for c in p["candidates"] for t in c["task_ids"]}))
        self.assertEqual(total, union["fte_total"])

    def test_periods_are_never_invented(self):
        p = plan_of()
        for w in p["waves"]:
            self.assertEqual(w["period"], "")
        self.assertIn("❓ offen", rv.wave_overview(p))

    def test_plan_is_deterministic(self):
        a = json.dumps(rl.plan_to_json(plan_of(), graph()), sort_keys=True, ensure_ascii=False)
        b = json.dumps(rl.plan_to_json(plan_of(), graph()), sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, b)


class TestArchitecture(unittest.TestCase):
    def test_role_without_target_is_marked_not_zero(self):
        g = graph()
        g["target_roles"] = g["target_roles"][1:]
        p = plan_of(g)
        missing = [a for a in p["architecture"] if not a["has_target"]]
        self.assertEqual(len(missing), 1)
        self.assertIsNone(missing[0]["fte_remaining"])
        self.assertIn("nicht bewertet", rv.architecture(p))

    def test_first_wave_is_set_for_touched_roles(self):
        p = plan_of()
        self.assertTrue(any(a["first_wave"] == 1 for a in p["architecture"]))


class TestRender(unittest.TestCase):
    def test_html_escapes_inserted_text(self):
        out = render.md_to_html("# T\n\n<script>alert(1)</script> **fett**\n")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<strong>fett</strong>", out)

    def test_table_and_open_quote(self):
        out = render.md_to_html("| A | B |\n|---|---:|\n| x | 1 |\n\n> ❓ offen: etwas\n")
        self.assertIn("<table>", out)
        self.assertIn('class="num"', out)
        self.assertIn('class="open"', out)

    def test_pipe_in_cell_survives(self):
        md = render.md_table(["A"], [["a|b"]])
        self.assertIn("<td>a|b</td>", render.md_to_html(md))


class TestDocuments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-docs-")
        self.proj = Path(self.tmp) / "p"
        shutil.copytree(EXAMPLE, self.proj)
        shutil.rmtree(self.proj / "expected", ignore_errors=True)
        (self.proj / "30_review" / "dokumente").mkdir(parents=True, exist_ok=True)
        wl.write_json(self.proj / "20_graph" / "work-graph_latest.json", graph())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def texts(self, data):
        (self.proj / "30_review" / "dokumente" / "texte.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return docs.load_texts(self.proj, cfg())

    def test_text_without_source_is_rejected(self):
        texts, notes, _ = self.texts({"entscheidungsvorlage": {"anlass": {"text": "Etwas ohne Beleg."}}})
        self.assertEqual(texts, {})
        self.assertTrue(any("ohne Quelle" in n for n in notes))
        texts, notes, _ = self.texts({"entscheidungsvorlage": {"anlass": {"text": "Etwas.", "quelle": " "}}})
        self.assertEqual(texts, {})
        self.assertTrue(any("ohne Quelle" in n for n in notes))
        texts, notes, _ = self.texts({"entscheidungsvorlage": {"anlass": {"text": "", "quelle": "x"}}})
        self.assertEqual((texts, notes), ({}, []))  # leeres Feld: einfach offen, keine Meldung

    def test_email_address_is_rejected(self):
        texts, notes, _ = self.texts({"hr_einseiter": {"botschaft": {"text": "Bitte an name@example.org.", "quelle": "x"}}})
        self.assertEqual(texts, {})
        self.assertTrue(any("E-Mail" in n for n in notes))

    def test_tone_flags_are_reported(self):
        texts, _, tone = self.texts({"entscheidungsvorlage": {"anlass": {"text": "Wir sind der Auftragnehmer.", "quelle": "x"}}})
        self.assertIn(("entscheidungsvorlage", "anlass"), texts)
        self.assertEqual(len(tone), 1)

    def test_open_slot_is_visible_and_document_is_a_draft(self):
        p = plan_of()
        md, ready, open_slots = docs.doc_entscheidungsvorlage(graph(), p, {}, 12, [])
        self.assertFalse(ready)
        self.assertEqual(len(open_slots), 4)
        self.assertIn("❓ offen", md)
        self.assertIn("**Stand: Entwurf**", md)

    def test_all_fields_filled_and_waves_settled_is_ready(self):
        c = cfg()
        c["running_statuses"] = ["pilot", "live", "building", "planned", "proposed", "idea"]
        p = plan_of(config=c)
        self.assertTrue(all(w["state"] in ("settled", "empty") for w in p["waves"]))
        filled = {("entscheidungsvorlage", k): {"text": "t", "quelle": "q", "von": ""}
                  for k in ("anlass", "pilot", "vorgehen", "beschluss")}
        md, ready, open_slots = docs.doc_entscheidungsvorlage(graph(), p, filled, 12, [])
        self.assertTrue(ready, open_slots)
        self.assertIn("**Stand: versandfertig**", md)

    def test_numbers_come_from_the_plan(self):
        p = plan_of()
        md, _, _ = docs.doc_entscheidungsvorlage(graph(), p, {}, 12, [])
        total = p["waves"][-1]["cumulative_reach"]
        self.assertIn(render.eur(total["value_eur"]), md)
        self.assertIn(rv.wave_overview(p), md)

    def test_hr_document_says_nothing_about_persons_and_uses_plain_words(self):
        md, _, _ = docs.doc_hr(graph(), plan_of(), {}, 12, [])
        self.assertIn("nicht einzelne Personen", md)
        self.assertNotIn("Disruption", md)
        self.assertNotIn("eliminated", md)

    def test_method_doc_lists_the_configured_weights(self):
        md = docs.doc_method(plan_of())
        for label in rl.COMPONENT_LABEL.values():
            self.assertIn(label, md)
        self.assertIn("nicht als null", md)

    def test_no_forbidden_words_in_generated_documents(self):
        p = plan_of()
        md = docs.doc_annex(graph(), p, 12) + docs.doc_method(p)
        self.assertNotIn("—", md)


class TestCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wts-roadmap-")
        cls.proj = Path(cls.tmp) / "order-to-cash"
        shutil.copytree(EXAMPLE, cls.proj)
        shutil.rmtree(cls.proj / "expected", ignore_errors=True)
        cls.pipe = subprocess.run([sys.executable, str(SKILLS / "work-transformation" / "scripts" / "run_pipeline.py"),
                                   "--project", str(cls.proj)], cwd=str(ROOT), capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_script(self, name, *extra):
        return subprocess.run([sys.executable, str(SKILLS / "transformation-roadmap" / "scripts" / name),
                               "--project", str(self.proj), *extra], cwd=str(ROOT), capture_output=True, text=True)

    def test_pipeline_runs_roadmap_stage(self):
        self.assertEqual(self.pipe.returncode, 0, self.pipe.stdout + self.pipe.stderr)
        out = self.proj / "40_output"
        for f in ("fahrplan_v012.md", "fahrplan_v012.html", "fahrplan_v012.csv", "roadmap_v012.json"):
            self.assertTrue((out / f).exists(), f)
        for d in ("entscheidungsvorlage", "hr-einseiter", "anhang-potenziale", "methodik"):
            self.assertTrue((out / "dokumente" / f"{d}.md").exists(), d)
            self.assertTrue((out / "dokumente" / f"{d}.html").exists(), d)

    def test_example_shows_partial_confirmation_and_filled_text(self):
        md = (self.proj / "40_output" / "dokumente" / "entscheidungsvorlage.md").read_text(encoding="utf-8")
        self.assertIn("gemeinsam", md)
        self.assertIn("Quelle:", md)
        self.assertIn("**Stand: Entwurf**", md)
        data = json.loads((self.proj / "40_output" / "roadmap_v012.json").read_text(encoding="utf-8"))
        confirmed = [i for i in data["items"] if i["placement"]["state"] == "confirmed"]
        self.assertEqual(sorted(i["name"] for i in confirmed), ["Mahnlauf-Agent", "Vertriebsklärungs-Assistent"])

    def test_second_run_is_byte_identical(self):
        files = sorted((self.proj / "40_output").rglob("*"))
        before = {f: f.read_bytes() for f in files if f.is_file() and ("fahrplan" in f.name or "dokumente" in f.parts or "roadmap" in f.name)}
        self.assertTrue(before)
        self.assertEqual(self.run_script("plan_waves.py").returncode, 0)
        self.assertEqual(self.run_script("build_documents.py").returncode, 0)
        for f, data in before.items():
            self.assertEqual(f.read_bytes(), data, f.name)

    def test_strict_fails_for_a_draft(self):
        self.assertEqual(self.run_script("build_documents.py", "--strict").returncode, 1)

    def test_empty_project_stops_with_code_three(self):
        empty = Path(self.tmp) / "leer"
        subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "init_project.py"),
                        "--project", str(empty), "--name", "x", "--organization", "x", "--scope", "x"],
                       cwd=str(ROOT), capture_output=True, text=True)
        wl.write_json(empty / "20_graph" / "work-graph_latest.json", wl.empty_graph() | {"meta": {"version": 1}})
        r = subprocess.run([sys.executable, str(SKILLS / "transformation-roadmap" / "scripts" / "plan_waves.py"),
                            "--project", str(empty)], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("agent-mapper", r.stdout)


if __name__ == "__main__":
    unittest.main()
