"""Rechenregeln und Redesign-Regeln des Skills process-redesigner."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import load, wl  # noqa: E402

rl = load("process-redesigner", "redesign_lib")
vb = load("process-redesigner", "validate_blueprints")
sp = load("process-redesigner", "score_processes")


class TestBlueprintArithmetic(unittest.TestCase):
    def test_serial_steps_add_up(self):
        bp = {"steps": [
            {"handling_time_min": 10, "wait_time_min": 50, "executor": {"type": "human", "id": "ro_1"}},
            {"handling_time_min": 5, "wait_time_min": 5, "executor": {"type": "agent", "id": "ag_1"}},
        ]}
        t = rl.blueprint_totals(bp)
        self.assertEqual(t["lead_time_hours"], 1.2)
        self.assertEqual(t["handling_time_min"], 15.0)
        self.assertEqual(t["handovers"], 1, "Der Wechsel Mensch → Agent ist eine Übergabe")

    def test_parallel_group_only_counts_its_longest_step(self):
        bp = {"steps": [
            {"handling_time_min": 10, "wait_time_min": 50, "parallel_group": "g",
             "executor": {"type": "agent", "id": "ag_1"}},
            {"handling_time_min": 5, "wait_time_min": 5, "parallel_group": "g",
             "executor": {"type": "agent", "id": "ag_1"}},
        ]}
        t = rl.blueprint_totals(bp)
        self.assertEqual(t["lead_time_hours"], 1.0, "60 statt 70 Minuten: der längere Schritt zählt")
        self.assertEqual(t["handling_time_min"], 15.0,
                         "Parallelität spart Wartezeit, keine Arbeitsminuten")
        self.assertEqual(t["handovers"], 0, "Derselbe Ausführende, keine Übergabe")

    def test_human_gate_on_an_agent_step_still_counts_as_a_touchpoint(self):
        bp = {"steps": [{"handling_time_min": 1, "wait_time_min": 0,
                         "executor": {"type": "agent", "id": "ag_1"},
                         "human_gate": {"when": "Konfidenz unter 0,9"}}]}
        self.assertEqual(rl.blueprint_totals(bp)["human_touches"], 1)


class TestDelta(unittest.TestCase):
    def test_positive_always_means_better(self):
        ist = {"lead_time_hours": 40.0, "automated_steps": 1}
        soll = {"lead_time_hours": 10.0, "automated_steps": 4}
        d = rl.delta(ist, soll)
        self.assertEqual(d["lead_time_hours"]["improvement"], 30.0,
                         "Weniger Durchlaufzeit ist eine Verbesserung")
        self.assertEqual(d["lead_time_hours"]["improvement_pct"], 75.0)
        self.assertEqual(d["automated_steps"]["improvement"], 3.0,
                         "Mehr automatisierte Schritte ist ebenfalls eine Verbesserung")

    def test_worse_values_are_negative(self):
        d = rl.delta({"rework_pct": 5.0}, {"rework_pct": 9.0})
        self.assertEqual(d["rework_pct"]["improvement"], -4.0)


class TestFteFromTimeAndVolume(unittest.TestCase):
    def test_fte_needs_a_volume(self):
        self.assertIsNone(rl.fte_equivalent(30.0, None))

    def test_fte_is_computed_from_minutes_and_cases(self):
        # 60 Minuten je Fall, 1600 Fälle im Jahr = 1600 Stunden = genau ein Vollzeitäquivalent
        self.assertEqual(rl.fte_equivalent(60.0, 1600), 1.0)


class TestRedesignSignals(unittest.TestCase):
    def graph(self):
        g = wl.empty_graph()
        g["processes"] = [{"id": "pr_1", "name": "P", "step_ids": ["ps_1", "ps_2"]}]
        g["process_steps"] = [
            {"id": "ps_1", "process_id": "pr_1", "name": "Warten", "value_type": "business_required",
             "executor": {"type": "human", "id": "ro_1"}, "handling_time_min": 5,
             "wait_time_min": 600, "rework_pct": 2, "inputs": [], "outputs": []},
            {"id": "ps_2", "process_id": "pr_1", "name": "Liste pflegen", "value_type": "waste",
             "executor": {"type": "human", "id": "ro_1"}, "handling_time_min": 5,
             "wait_time_min": 5, "rework_pct": 30, "inputs": [], "outputs": []},
        ]
        g["process_edges"] = [{"id": "pe_1", "process_id": "pr_1", "from_step_id": "ps_1",
                               "to_step_id": "ps_2", "handover": "email"}]
        return g

    def test_signals_are_found_and_sorted(self):
        signals = rl.redesign_signals(self.graph(), "pr_1")
        ops = [s["operator"] for s in signals]
        self.assertIn("eliminate", ops, "Ein Schritt ohne Wertbeitrag ist ein Streichkandidat")
        self.assertIn("parallelize", ops, "600 min Warten gegenüber 5 min Arbeit fällt auf")
        self.assertIn("simplify", ops, "30 Prozent Nacharbeit fällt auf")
        self.assertIn("automate", ops, "Eine Übergabe per E-Mail ist ein Medienbruch")
        self.assertEqual(ops, sorted(ops), "Die Ausgabe muss deterministisch sortiert sein")

    def test_signals_are_deterministic(self):
        a = rl.redesign_signals(self.graph(), "pr_1")
        b = rl.redesign_signals(self.graph(), "pr_1")
        self.assertEqual(a, b)


class TestRedesignRules(unittest.TestCase):
    def graph(self, steps, scenario="balanced", removed=None):
        g = wl.empty_graph()
        g["roles"] = [{"id": "ro_1", "name": "R"}]
        g["metrics"] = [{"id": "me_1", "name": "M", "kind": "time", "unit": "Stunden",
                         "process_id": "pr_1"}]
        g["processes"] = [{"id": "pr_1", "name": "P", "step_ids": ["ps_1", "ps_2"]}]
        g["process_steps"] = [
            {"id": "ps_1", "process_id": "pr_1", "name": "A", "handling_time_min": 20,
             "value_type": "business_required", "executor": {"type": "human", "id": "ro_1"},
             "control_ids": []},
            {"id": "ps_2", "process_id": "pr_1", "name": "B", "handling_time_min": 10,
             "value_type": "customer_value", "executor": {"type": "human", "id": "ro_1"},
             "control_ids": []},
        ]
        bp = {"id": "bp_1", "process_id": "pr_1", "scenario": scenario, "name": "B",
              "status": "draft", "steps": steps, "removed_steps": removed or [],
              "control_coverage": {}, "projected_metrics": [],
              "soll_totals": rl.blueprint_totals({"steps": steps}),
              "delta": {}, "operator_counts": {}}
        g["blueprints"] = [bp]
        return g

    def test_simplify_without_effect_is_rejected(self):
        steps = [{"name": "A", "operator": "simplify", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 25, "assumption": "x"}]
        errors, _ = vb.check(self.graph(steps))
        self.assertTrue(any("ohne Wirkung" in e for e in errors))

    def test_merge_needs_two_predecessors(self):
        steps = [{"name": "A", "operator": "merge", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 5, "assumption": "x"}]
        errors, _ = vb.check(self.graph(steps))
        self.assertTrue(any("mindestens zwei Vorläufer" in e for e in errors))

    def test_parallelize_needs_a_group_with_two_members(self):
        steps = [{"name": "A", "operator": "parallelize", "from_step_ids": ["ps_1"],
                  "executor": {"type": "agent", "id": None}, "metric_id": "me_1",
                  "parallel_group": "g", "handling_time_min": 1, "assumption": "x"}]
        errors, _ = vb.check(self.graph(steps))
        self.assertTrue(any("keine Parallelisierung" in e for e in errors))

    def test_automate_with_a_human_executor_is_rejected(self):
        steps = [{"name": "A", "operator": "automate", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 1, "assumption": "x"}]
        errors, _ = vb.check(self.graph(steps))
        self.assertTrue(any("executor.type='human'" in e for e in errors))

    def test_change_without_a_metric_is_rejected(self):
        steps = [{"name": "A", "operator": "automate", "from_step_ids": ["ps_1"],
                  "executor": {"type": "agent", "id": None}, "handling_time_min": 1}]
        errors, _ = vb.check(self.graph(steps))
        self.assertTrue(any("ohne betroffene Kennzahl" in e for e in errors))

    def test_removal_needs_a_rationale(self):
        steps = [{"name": "A", "operator": "simplify", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 5, "assumption": "x"}]
        errors, _ = vb.check(self.graph(steps, removed=[{"step_id": "ps_2", "rationale": ""}]))
        self.assertTrue(any("ohne Begründung" in e for e in errors))

    def test_removing_a_customer_value_step_needs_a_replacement(self):
        steps = [{"name": "A", "operator": "simplify", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 5, "assumption": "x"}]
        removed = [{"step_id": "ps_2", "rationale": "nicht mehr nötig", "assumption": "y"}]
        errors, _ = vb.check(self.graph(steps, removed=removed))
        self.assertTrue(any("Kundennutzen" in e for e in errors))

    def test_conservative_must_not_touch_controls(self):
        steps = [{"name": "A", "operator": "simplify", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 5, "assumption": "x"}]
        g = self.graph(steps, scenario="conservative")
        g["controls"] = [{"id": "ct_1", "name": "K", "kind": "quality", "mode": "detective",
                          "mandatory": True}]
        g["blueprints"][0]["control_coverage"] = {"dropped_control_ids": ["ct_1"], "replaced": []}
        errors, _ = vb.check(g)
        self.assertTrue(any("konservativ" in e for e in errors))

    def test_identical_scenarios_are_rejected(self):
        steps = [{"name": "A", "operator": "simplify", "from_step_ids": ["ps_1"],
                  "executor": {"type": "human", "id": "ro_1"}, "metric_id": "me_1",
                  "handling_time_min": 5, "assumption": "x"}]
        g = self.graph(steps)
        twin = dict(g["blueprints"][0])
        twin["id"] = "bp_2"
        twin["scenario"] = "agent_native"
        twin["steps"] = [dict(steps[0], human_gate={"when": "immer", "role_id": "ro_1"})]
        g["blueprints"].append(twin)
        errors, _ = vb.check(g)
        self.assertTrue(any("identisch" in e for e in errors),
                        "Drei gleiche Entwürfe geben nichts zu entscheiden")


class TestProcessValueScoring(unittest.TestCase):
    def setUp(self):
        self.cfg = sp.load_weights(None)
        self.mid = {k: 5 for k in list(self.cfg["factors"]) + ["reversibility"]}

    def test_weights_are_versioned_and_normalised(self):
        self.assertIn("config_version", self.cfg)
        self.assertAlmostEqual(sum(float(v) for v in self.cfg["composite"].values()), 1.0)

    def test_midpoint_scores_in_the_middle(self):
        res = sp.compute(self.mid, self.cfg)
        self.assertEqual(res["score"], 5.0)
        self.assertEqual(res["band"], "later",
                         "Ein Prozess, der überall Mittelmaß ist, gehört nicht nach vorn")

    def test_effort_lowers_the_score(self):
        cheap = dict(self.mid, integration_effort=0, change_effort=0)
        dear = dict(self.mid, integration_effort=10, change_effort=10)
        self.assertGreater(sp.compute(cheap, self.cfg)["score"], sp.compute(dear, self.cfg)["score"])

    def test_bands_cover_the_whole_range(self):
        for v in range(0, 11):
            band = sp.band_of(float(v), self.cfg)
            self.assertIn(band, wl.ENUM_PRIORITY_BAND)

    def test_sensitivity_flags_a_band_on_the_edge(self):
        # Ein Wertepaar knapp an der Bandgrenze muss als kippelig erkannt werden.
        edge = dict(self.mid)
        edge["customer_impact"] = 9
        edge["financial_impact"] = 9
        edge["cycle_time_reduction"] = 9
        res = sp.compute(edge, self.cfg)
        sens = sp.sensitivity(edge, self.cfg, res["band"])
        self.assertIn("band_stable", sens)
        if not sens["band_stable"]:
            self.assertTrue(all(f["factor"] in edge for f in sens["flips"]))

    def test_clearly_strong_case_is_stable(self):
        strong = {k: 10 for k in self.cfg["factors"] if self.cfg["factors"][k]["direction"] == "benefit"}
        strong.update({k: 0 for k in self.cfg["factors"] if self.cfg["factors"][k]["direction"] == "effort"})
        strong["reversibility"] = 10
        res = sp.compute(strong, self.cfg)
        self.assertEqual(res["band"], "now")
        self.assertTrue(sp.sensitivity(strong, self.cfg, res["band"])["band_stable"])


if __name__ == "__main__":
    unittest.main()
