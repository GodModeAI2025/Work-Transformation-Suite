"""Regressionen aus dem Code-Review zu Schema 1.1.

Jeder Test hier steht für einen Fehler, der einmal im Repository war. Sie sind nach dem
benannt, was schiefging, nicht nach der Funktion, die es behebt — wer den Test bricht,
soll sofort sehen, welches Verhalten er zurückholt.
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

rl = load("process-redesigner", "redesign_lib")
bb = load("process-redesigner", "build_blueprints")
me = load("process-redesigner", "make_experiments")
PIPELINE = SKILLS / "work-transformation" / "scripts" / "run_pipeline.py"


class TestValidatorSurvivesBrokenInput(unittest.TestCase):
    """Ein Eintrag ohne id ließ den Validator mit KeyError abstürzen — ausgerechnet an dem
    Eintrag, dessen Fehler er gerade melden wollte."""

    def test_entry_without_id_is_reported_not_crashed(self):
        g = wl.empty_graph()
        g["roles"] = [{"name": "Ohne ID"}]
        g["skills"] = [{"name": "Auch ohne ID"}]
        g["processes"] = [{"name": "Prozess ohne ID"}]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("roles: Eintrag ohne id" in e for e in errors))
        self.assertTrue(any("processes: Eintrag ohne id" in e for e in errors))

    def test_non_dict_entry_is_reported(self):
        g = wl.empty_graph()
        g["roles"] = ["das ist ein String, kein Objekt"]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("kein Objekt" in e for e in errors))

    def test_validate_does_not_mutate_the_caller_graph(self):
        g = wl.empty_graph()
        g["roles"] = [{"name": "Ohne ID"}]
        before = json.dumps(g, sort_keys=True)
        validate_graph.validate(g)
        self.assertEqual(json.dumps(g, sort_keys=True), before)


class TestSummaryWithoutBaseline(unittest.TestCase):
    """delta() liefert keinen Prozentwert, wenn der Ist-Wert 0 ist. Die Zusammenfassung von
    build_blueprints.py stürzte daran ab — nachdem der Graph längst geschrieben war."""

    def test_delta_has_no_percentage_when_ist_is_zero(self):
        d = rl.delta({"lead_time_hours": 0.0}, {"lead_time_hours": 0.0})
        self.assertIsNone(d["lead_time_hours"]["improvement_pct"])

    def test_signed_renders_none_as_dash(self):
        self.assertEqual(bb._signed(None), "–")
        self.assertEqual(bb._signed(None, suffix=" %"), "–")
        self.assertEqual(bb._signed(-12.5, suffix=" %"), "-12.5 %")
        self.assertEqual(bb._signed(3), "+3")


class TestDesignRationaleWithoutVolume(unittest.TestCase):
    """_design_reason rechnete int(volume_per_year), ohne dass die Menge erfasst sein musste.
    Ein selbst gesetztes design: "ab_test" reichte für einen TypeError."""

    def graph(self):
        g = wl.empty_graph()
        g["processes"] = [{"id": "pr_1", "name": "P", "step_ids": []}]
        return g

    def test_every_design_survives_a_missing_volume(self):
        g = self.graph()
        proc = {"id": "pr_1", "name": "P"}
        for design in wl.ENUM_EXPERIMENT_DESIGN:
            text = me._design_reason(g, proc, {}, design)
            self.assertTrue(text, design)
            self.assertNotIn("None", text, design)

    def test_missing_volume_is_named_as_a_gap(self):
        text = me._design_reason(self.graph(), {"id": "pr_1", "name": "P"}, {}, "ab_test")
        self.assertIn("volume_per_year", text,
                      "Wenn die Menge fehlt, soll der Text sagen, was nachzutragen ist")

    def test_exposure_estimate_without_volume_is_none(self):
        self.assertIsNone(me.exposure_estimate({"name": "P"}, "ab_test", 42))


class TestEvidenceBuckets(unittest.TestCase):
    """Kennzahlen ohne Ausgangswert landeten im Eimer „bestätigt oder gemessen" und kehrten
    damit genau die Aussage um, für die der Satz existiert."""

    def bucket(self, metric):
        _value, basis = wl.metric_value(metric, "baseline")
        if basis in ("observed", "expert_confirmed"):
            return "belegt"
        return "geschätzt" if basis == "estimated" else "ohne Ausgangswert"

    def test_three_buckets_are_distinguished(self):
        self.assertEqual(self.bucket({"baseline": {"value": 1, "basis": "observed"}}), "belegt")
        self.assertEqual(self.bucket({"baseline": {"value": 1, "basis": "expert_confirmed"}}), "belegt")
        self.assertEqual(self.bucket({"baseline": {"value": 1, "basis": "estimated"}}), "geschätzt")
        self.assertEqual(self.bucket({}), "ohne Ausgangswert")
        self.assertEqual(self.bucket({"baseline": {"basis": "estimated"}}), "ohne Ausgangswert")

    def test_report_names_metrics_without_a_baseline(self):
        dash = load("transformation-dashboard", "build_dashboard")
        graph = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        graph["metrics"].append({"id": "me_leer", "name": "Ohne Ausgangswert", "kind": "quality",
                                 "unit": "Prozent", "direction": "lower_is_better",
                                 "process_id": graph["processes"][0]["id"]})
        data = dash.prepare(graph)
        text = dash.report_md(graph, data, dash.kpis(graph, data), "T")
        self.assertIn("ohne Ausgangswert", text)
        self.assertIn("4 von 7", text, "Der Zähler der belegten Werte darf nicht mitwachsen")


class TestProcessExtractionEdgeCases(unittest.TestCase):
    """Drei Fälle in build_processes.py, die still das Modell beschädigten."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-reg-")
        self.project = Path(self.tmp) / "p"
        subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "init_project.py"),
                        "--project", str(self.project), "--name", "R", "--organization", "R",
                        "--scope", "R"], cwd=str(ROOT), capture_output=True, check=True)
        wl.write_json(self.project / "10_extraction" / "extract_a.json", {
            "source": "q", "job_family": "F", "job_cluster": "C",
            "roles": [{"name": "Bearbeiter", "headcount": 2,
                       "skills": [{"name": "S", "kind": "skill", "level": 3, "importance": "core"}],
                       "tasks": [{"name": "Arbeiten", "share_of_time": 100,
                                  "frequency": "daily", "nature": "cognitive"}]}]})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self):
        for script in ("build_graph.py", "build_processes.py"):
            r = subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / script),
                                "--project", str(self.project)], cwd=str(ROOT),
                               capture_output=True, text=True)
            if r.returncode:
                self.fail(f"{script} scheiterte:\n{r.stdout}\n{r.stderr}")
        return wl.load_latest_graph(self.project), r.stdout

    def write_process(self, steps, outcomes=None, extra_file=None):
        wl.write_json(self.project / "10_extraction" / "process_a.json", {
            "source": "A",
            "outcomes": outcomes or [{"name": "Fall gelöst", "beneficiary": "Kunde"}],
            "processes": [{
                "name": "P1", "trigger": "T", "outcome": "Fall gelöst",
                "owner_role": "Bearbeiter", "volume_per_year": 100,
                "baseline_metrics": [{"name": "Durchlaufzeit", "kind": "time", "unit": "Stunden",
                                      "direction": "lower_is_better",
                                      "baseline": {"value": 1, "basis": "estimated", "as_of": "2026"}}],
                "steps": steps}]})
        if extra_file:
            wl.write_json(self.project / "10_extraction" / "process_b.json", extra_file)

    def step(self, name):
        return {"name": name, "role": "Bearbeiter", "handling_time_min": 5, "wait_time_min": 5}

    def test_unnamed_step_is_reported_and_does_not_break_the_chain(self):
        self.write_process([self.step("Erster"), self.step(""), self.step("Dritter"),
                            self.step("Vierter")])
        graph, out = self.build()
        self.assertIn("hat keinen Namen", out, "Ein namenloser Schritt darf nicht still verschwinden")
        names = [s["name"] for s in wl.steps_of(graph, graph["processes"][0]["id"])]
        self.assertEqual(names, ["Erster", "Dritter", "Vierter"])
        self.assertEqual(len(graph["process_edges"]), 2,
                         "Die implizite Kette muss über die benannten Schritte laufen")
        totals = wl.process_totals(graph, graph["processes"][0]["id"])
        self.assertEqual(totals["handovers"], 0,
                         "Alle drei Schritte macht dieselbe Rolle — das sind keine Übergaben")

    def test_outcome_from_a_second_file_keeps_its_metrics(self):
        self.write_process(
            [self.step("Erster"), self.step("Zweiter")],
            extra_file={"source": "B", "outcomes": [
                {"name": "Fall gelöst", "beneficiary": "Kunde", "description": "Ergänzt"}]})
        graph, _ = self.build()
        outcome = graph["outcomes"][0]
        self.assertTrue(outcome["metric_ids"],
                        "Eine spätere Datei darf die Kennzahlverknüpfung nicht abräumen")
        self.assertEqual(outcome["source_refs"], ["A", "B"])
        self.assertEqual(outcome["description"], "Ergänzt")

    def test_renaming_a_metric_does_not_block_the_project(self):
        self.write_process([self.step("Erster"), self.step("Zweiter")])
        self.build()
        # Provenienz von Hand setzen, wie sie aus einer Extraktion entstünde
        graph = wl.load_latest_graph(self.project)
        metric = graph["metrics"][0]
        pid = wl.make_id("provenance", "metrics", metric["id"], "baseline")
        graph["provenance"] = [{"id": pid, "entity_type": "metrics", "entity_id": metric["id"],
                                "field": "baseline", "source_kind": "system_export",
                                "locator": "x.csv", "author": "A", "reviewer": "B",
                                "confidence": 0.9, "status": "verified", "as_of": "2026"}]
        wl.save_graph_version(self.project, graph, "test")

        source = self.project / "10_extraction" / "process_a.json"
        data = wl.read_json(source)
        data["processes"][0]["baseline_metrics"][0]["name"] = "Durchlaufzeit gesamt"
        wl.write_json(source, data)

        graph, out = self.build()
        self.assertIn("Provenienz", out, "Das Entfernen einer verwaisten Zeile gehört gemeldet")
        live = {(p["entity_type"], p["entity_id"]) for p in graph["provenance"]}
        known = {("metrics", m["id"]) for m in graph["metrics"]}
        self.assertTrue(live <= known, "Nach dem Lauf darf keine Provenienz ins Leere zeigen")
        errors, _ = validate_graph.validate(graph)
        self.assertEqual(errors, [])


class TestHandoversAreComparable(unittest.TestCase):
    """Ist und Soll zählten Übergaben verschieden: das Ist jede Kante mit einem Medium, das
    Soll jeden Wechsel des Ausführenden. Ein Entwurf, der nichts ändert, wies dadurch eine
    Verbesserung aus."""

    def setUp(self):
        self.ex = {"type": "human", "id": "ro_1"}
        self.g = wl.empty_graph()
        self.g["processes"] = [{"id": "pr_1", "name": "P", "step_ids": ["ps_1", "ps_2", "ps_3"]}]
        self.g["process_steps"] = [
            {"id": f"ps_{i}", "process_id": "pr_1", "name": f"S{i}", "executor": self.ex,
             "handling_time_min": 5, "wait_time_min": 0} for i in (1, 2, 3)]
        self.g["process_edges"] = [
            {"id": "pe_1", "process_id": "pr_1", "from_step_id": "ps_1", "to_step_id": "ps_2",
             "handover": "system"},
            {"id": "pe_2", "process_id": "pr_1", "from_step_id": "ps_2", "to_step_id": "ps_3",
             "handover": "email"}]

    def test_unchanged_flow_shows_no_improvement(self):
        ist = wl.process_totals(self.g, "pr_1")
        soll = rl.blueprint_totals({"steps": [dict(s) for s in self.g["process_steps"]]})
        self.assertEqual(ist["handovers"], soll["handovers"])
        self.assertEqual(rl.delta(ist, soll)["handovers"]["improvement"], 0.0,
                         "Ein Entwurf, der nichts ändert, darf keine Verbesserung ausweisen")

    def test_a_real_role_change_counts(self):
        self.g["process_steps"][2]["executor"] = {"type": "agent", "id": "ag_1"}
        self.assertEqual(wl.process_totals(self.g, "pr_1")["handovers"], 1)

    def test_media_breaks_stay_visible_separately(self):
        totals = wl.process_totals(self.g, "pr_1")
        self.assertEqual(totals["handovers"], 0)
        self.assertEqual(totals["media_breaks"], 1,
                         "Der Medienbruch bleibt als eigener Befund erhalten")


class TestApprovalNeedsACheckpoint(unittest.TestCase):
    """Akzeptanzkriterium aus dem Feedback: Prozesse mit hoher Fehlerfolge dürfen nicht ohne
    Kontrollpunkt freigegeben werden. Das war zunächst nur für Blueprint-Schritte umgesetzt,
    nicht für die Freigabe des Prozesses selbst."""

    def graph(self, **process):
        g = wl.empty_graph()
        g["job_families"] = [{"id": "jf_1", "name": "F", "description": ""}]
        g["job_clusters"] = [{"id": "jc_1", "name": "C", "family_id": "jf_1", "description": ""}]
        g["roles"] = [{"id": "ro_1", "name": "R", "cluster_id": "jc_1", "status": "generated",
                       "skills": [], "task_ids": [], "source_refs": []}]
        g["outcomes"] = [{"id": "ou_1", "name": "Erg", "beneficiary": "K", "metric_ids": []}]
        base = {"id": "pr_1", "name": "P", "trigger": "T", "outcome_id": "ou_1",
                "owner_role_id": "ro_1", "status": "approved", "volume_per_year": 10,
                "baseline_metric_ids": [], "step_ids": ["ps_1"], "data_classes": []}
        base.update(process)
        g["processes"] = [base]
        g["process_steps"] = [{"id": "ps_1", "process_id": "pr_1", "name": "S",
                               "executor": {"type": "human", "id": "ro_1"},
                               "value_type": "business_required", "task_ids": [],
                               "handling_time_min": 5, "wait_time_min": 0, "rework_pct": 0,
                               "system_ids": [], "control_ids": [], "data_classes": []}]
        return g

    def blocked(self, g):
        return [e for e in validate_graph.validate(g)[0] if "Human Gate" in e]

    def test_regulated_process_needs_a_checkpoint(self):
        self.assertTrue(self.blocked(self.graph(regulated=True)))

    def test_personal_data_process_needs_a_checkpoint(self):
        self.assertTrue(self.blocked(self.graph(data_classes=["personal"])))

    def test_irreversible_decision_needs_a_checkpoint(self):
        g = self.graph()
        g["process_steps"][0]["decision"] = {"scope": "execute_irreversible",
                                             "accountable_role_id": "ro_1",
                                             "escalation": "an die Leitung"}
        g["process_steps"][0]["control_ids"] = []
        errors = validate_graph.validate(g)[0]
        self.assertTrue(any("Human Gate" in e or "irreversible" in e for e in errors))

    def test_a_human_gate_satisfies_the_rule(self):
        g = self.graph(regulated=True)
        g["process_steps"][0]["human_gate"] = {"when": "immer", "role_id": "ro_1"}
        self.assertEqual(self.blocked(g), [])

    def test_harmless_process_may_be_approved_without_a_control(self):
        self.assertEqual(self.blocked(self.graph()), [])

    def test_the_rule_only_bites_on_approval(self):
        self.assertEqual(self.blocked(self.graph(regulated=True, status="reviewed")), [],
                         "Vor der Freigabe ist ein fehlender Kontrollpunkt ein offener Punkt, "
                         "kein Fehler")


class TestEveryDeltaLeadsToItsAssumption(unittest.TestCase):
    """Akzeptanzkriterium: Jede Delta-Zahl muss auf Ausgangswert und Annahme führen. Die
    Begründungen lagen zunächst in den Szenario-Tafeln — also hinter einem Reiter und damit
    faktisch unauffindbar."""

    @classmethod
    def setUpClass(cls):
        dash = load("transformation-dashboard", "build_dashboard")
        dash.load_theme(None)  # Farben kommen sonst aus einem leeren Theme
        graph = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        data = dash.prepare(graph)
        cls.html = dash.build_html(graph, data, dash.kpis(graph, data), "T", "")

    def test_no_dead_anchors(self):
        import re
        targets = set(re.findall(r'id="(herkunft-[^"]+)"', self.html))
        links = set(re.findall(r'href="#(herkunft-[^"]+)"', self.html))
        self.assertTrue(links, "Die Vergleichstabelle muss auf die Herkunft verlinken")
        self.assertEqual(links - targets, set(), "Toter Anker in der Vergleichstabelle")

    def test_assumptions_are_outside_the_hidden_tabs(self):
        import re
        block = re.search(r'<details class="herkunft".*?</details>', self.html, re.S)
        self.assertIsNotNone(block, "Der Herkunftsblock fehlt")
        self.assertNotIn('class="pane"', block.group(),
                         "Der Block darf nicht in einer umschaltbaren Tafel liegen")
        self.assertIn("Annahme", block.group())
        self.assertIn("Fundstelle", block.group())


class TestPipelineWithDraftBlueprintsOnly(unittest.TestCase):
    """Beim ersten Redesign-Durchgang stehen alle Entwürfe auf "draft". Die Pipeline brach
    dann mit Code 2 ab und baute weder Szenarienvergleich noch Dashboard."""

    def test_pipeline_finishes_and_builds_the_dashboard(self):
        tmp = tempfile.mkdtemp(prefix="wts-draft-")
        try:
            project = Path(tmp) / "p"
            shutil.copytree(EXAMPLE, project)
            shutil.rmtree(project / "expected", ignore_errors=True)
            blueprints = project / "20_graph" / "blueprints.json"
            data = wl.read_json(blueprints)
            for entry in data:
                entry["status"] = "draft"
            wl.write_json(blueprints, data)
            (project / "20_graph" / "experiments.json").unlink()
            (project / "30_review" / "decisions.csv").unlink()

            run = subprocess.run([sys.executable, str(PIPELINE), "--project", str(project)],
                                 cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            produced = {p.name for p in (project / "40_output").glob("*")}
            self.assertTrue(any(n.startswith("dashboard_v") for n in produced), produced)
            self.assertTrue(any(n.startswith("scenarios_v") for n in produced), produced)
            self.assertIn("noch keine Pilotplanung", run.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestNumbersAreReadableGerman(unittest.TestCase):
    """Im Dashboard standen deutsche und englische Zahlen in derselben Zelle, und die drei
    Zeitzeilen einer Tabelle in zwei verschiedenen Einheiten. Beides machte die Tabelle
    schwerer lesbar, als die Daten es hergeben."""

    def setUp(self):
        self.dash = load("transformation-dashboard", "build_dashboard")

    def test_thousands_and_decimals_are_german(self):
        self.assertEqual(self.dash.fmt(20940.0, 1), "20.940,0")
        self.assertEqual(self.dash.fmt(667.2, 1), "667,2")
        self.assertEqual(self.dash.fmt(None), "–")

    def test_deltas_keep_the_decimals_of_their_row(self):
        """%g warf die Nachkommastelle weg, sobald sie 0 war: +298 neben +444.7."""
        self.assertEqual(self.dash.signed(298.0, 1), "+298,0")
        self.assertEqual(self.dash.signed(444.7, 1), "+444,7")
        self.assertEqual(self.dash.signed(-2.0, 0), "-2")
        self.assertEqual(self.dash.signed(0.0, 1), "0,0")
        self.assertEqual(self.dash.signed(-0.04, 1), "0,0", "Minus-Null ist keine Verschlechterung")
        self.assertEqual(self.dash.signed_pct(44.7), "+44,7 %")

    def test_time_rows_share_one_unit(self):
        """Arbeit + Warten = Durchlauf. In gemischten Einheiten ist diese Addition unsichtbar."""
        unit, per_unit, nd = self.dash.time_scale([667.2, 20940.0, 21607.2])
        self.assertEqual(unit, "h")
        self.assertEqual(per_unit, 60.0)
        self.assertEqual(self.dash.fmt(667.2 / per_unit, nd), "11,1")
        self.assertEqual(self.dash.fmt(20940.0 / per_unit, nd), "349,0")
        self.assertEqual(self.dash.fmt(21607.2 / per_unit, nd), "360,1")

    def test_short_processes_stay_in_minutes(self):
        unit, per_unit, nd = self.dash.time_scale([12.0, 45.0, 57.0])
        self.assertEqual((unit, per_unit, nd), ("min", 1.0, 0))

    def test_a_small_value_next_to_a_large_one_keeps_a_digit(self):
        """5 min Arbeit neben 200 h Warten darf nicht zu 0,0 h werden."""
        unit, per_unit, nd = self.dash.time_scale([5.0, 12000.0, 12005.0])
        self.assertEqual(unit, "h")
        self.assertNotEqual(float(self.dash.fmt(5.0 / per_unit, nd).replace(",", ".")), 0.0)

    def test_standalone_durations_pick_their_own_unit(self):
        self.assertEqual(self.dash.dur(45), "45 min")
        self.assertEqual(self.dash.dur(667.2), "11,1 h")
        self.assertEqual(self.dash.dur(20940), "14,5 Tage")
        self.assertEqual(self.dash.dur(None), "–")

    def test_rendered_dashboard_has_no_english_numbers_left(self):
        graph = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        self.dash.load_theme(None)
        html = self.dash.build_html(graph, self.dash.prepare(graph),
                                    self.dash.kpis(graph, self.dash.prepare(graph)), "T", "")
        self.assertIn("Bearbeitungszeit (h)", html)
        self.assertNotIn("Bearbeitungszeit (min)", html)
        self.assertNotIn("Durchlaufzeit (min)", html)
        import re
        # Eine Ziffer, Punkt, Ziffer außerhalb von Tags und CSS wäre ein englisches Dezimalkomma.
        body = re.sub(r"<style.*?</style>|<svg.*?</svg>", "", html, flags=re.S)
        body = re.sub(r"<[^>]+>", " ", body)
        self.assertEqual([], re.findall(r"[+-]\d+\.\d", body), "englische Dezimalpunkte im Text")

if __name__ == "__main__":
    unittest.main()
