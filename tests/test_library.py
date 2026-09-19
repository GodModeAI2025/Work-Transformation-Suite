"""Einheiten der gemeinsamen Bibliothek: IDs, Sortierung, Migration, Prozessrechnung."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import wl  # noqa: E402


class TestIdentifiers(unittest.TestCase):
    def test_normalize_name_is_stable_across_umlauts_and_spacing(self):
        self.assertEqual(wl.normalize_name("Prüfung  der   Fälle"), "prufung der falle")
        self.assertEqual(wl.normalize_name("Straße"), "strasse")
        self.assertEqual(wl.normalize_name(None), "")

    def test_same_name_gives_same_id(self):
        a = wl.make_id("role", "Finanzen", "Order-to-Cash", "Kreditprüfer")
        b = wl.make_id("role", "Finanzen", "Order-to-Cash", "Kreditprufer")
        self.assertEqual(a, b, "Die Normalisierung muss Umlautschreibweisen zusammenführen")
        self.assertTrue(a.startswith("ro_"))

    def test_every_collection_has_an_id_prefix(self):
        # Ohne Präfix könnte eine Sammlung keine deterministischen IDs bilden.
        singular = {
            "job_families": "job_family", "job_clusters": "job_cluster", "roles": "role",
            "tasks": "task", "skills": "skill", "agents": "agent", "positions": "position",
            "courses": "course", "outcomes": "outcome", "systems": "system",
            "controls": "control", "metrics": "metric", "processes": "process",
            "process_steps": "process_step", "process_edges": "process_edge",
            "blueprints": "blueprint", "experiments": "experiment",
            "provenance": "provenance", "decisions": "decision",
        }
        self.assertEqual(set(singular), set(wl.COLLECTIONS))
        for kind in singular.values():
            self.assertIn(kind, wl.ID_PREFIX)
        prefixes = [wl.ID_PREFIX[k] for k in singular.values()]
        self.assertEqual(len(prefixes), len(set(prefixes)), "Präfixe müssen eindeutig sein")


class TestMigration(unittest.TestCase):
    def test_schema_10_migrates_losslessly(self):
        old = {"meta": {"schema_version": "1.0"}}
        for c in wl.COLLECTIONS_CORE:
            old[c] = []
        old["roles"] = [{"id": "ro_x", "name": "Bestand"}]
        notes = wl.migrate_graph(old)
        self.assertEqual(old["meta"]["schema_version"], "1.1")
        self.assertEqual(old["roles"], [{"id": "ro_x", "name": "Bestand"}],
                         "Migration darf vorhandene Inhalte nicht anfassen")
        for c in wl.COLLECTIONS:
            self.assertIsInstance(old[c], list)
        self.assertTrue(any("processes" in n for n in notes))

    def test_migration_is_idempotent(self):
        g = wl.empty_graph()
        self.assertEqual(wl.migrate_graph(g), [])


class TestSorting(unittest.TestCase):
    def test_reference_lists_are_sorted_recursively(self):
        g = wl.empty_graph()
        g["blueprints"] = [{"id": "bp_b", "steps": [{"from_step_ids": ["ps_c", "ps_a", "ps_a"]}]},
                           {"id": "bp_a"}]
        wl.sort_graph(g)
        self.assertEqual([b["id"] for b in g["blueprints"]], ["bp_a", "bp_b"])
        self.assertEqual(g["blueprints"][1]["steps"][0]["from_step_ids"], ["ps_a", "ps_c"])

    def test_ordered_lists_keep_their_order(self):
        g = wl.empty_graph()
        g["processes"] = [{"id": "pr_a", "step_ids": ["ps_z", "ps_a"]}]
        wl.sort_graph(g)
        self.assertEqual(g["processes"][0]["step_ids"], ["ps_z", "ps_a"],
                         "step_ids ist die fachliche Reihenfolge und darf nicht sortiert werden")


class TestMetricStages(unittest.TestCase):
    def test_observed_does_not_overwrite_the_baseline(self):
        # Ein Pilotwert beschreibt den veränderten Prozess, nicht den heutigen.
        m = {"baseline": {"value": 42, "basis": "observed"},
             "observed": {"value": 3, "basis": "observed"}}
        self.assertEqual(wl.metric_value(m, "baseline")[0], 42)
        self.assertEqual(wl.metric_value(m, "observed")[0], 3)

    def test_missing_stage_returns_none(self):
        self.assertEqual(wl.metric_value({}, "baseline"), (None, None))

    def test_best_known_prefers_the_measurement(self):
        m = {"baseline": {"value": 42, "basis": "estimated"},
             "observed": {"value": 3, "basis": "observed"}}
        self.assertEqual(wl.metric_best_known(m), (3, "observed", "observed"))


class TestProcessArithmetic(unittest.TestCase):
    def setUp(self):
        self.g = wl.empty_graph()
        self.g["processes"] = [{"id": "pr_1", "name": "P", "step_ids": ["ps_1", "ps_2"],
                                "baseline_metric_ids": ["me_1"]}]
        self.g["process_steps"] = [
            {"id": "ps_1", "process_id": "pr_1", "name": "A", "executor": {"type": "human", "id": "ro_1"},
             "handling_time_min": 10, "wait_time_min": 50, "rework_pct": 10, "value_type": "waste"},
            {"id": "ps_2", "process_id": "pr_1", "name": "B", "executor": {"type": "agent", "id": "ag_1"},
             "handling_time_min": 2, "wait_time_min": 8, "rework_pct": 0,
             "human_gate": {"when": "x", "role_id": "ro_1"}},
        ]
        self.g["process_edges"] = [{"id": "pe_1", "process_id": "pr_1", "from_step_id": "ps_1",
                                    "to_step_id": "ps_2", "handover": "email"}]

    def test_totals(self):
        t = wl.process_totals(self.g, "pr_1")
        self.assertEqual(t["steps"], 2)
        self.assertEqual(t["handling_time_min"], 12.0)
        self.assertEqual(t["wait_time_min"], 58.0)
        self.assertEqual(t["lead_time_hours"], 1.2)
        self.assertEqual(t["handovers"], 1)
        self.assertEqual(t["waste_steps"], 1)
        self.assertEqual(t["automated_steps"], 1)
        self.assertEqual(t["human_touches"], 2,
                         "Ein Agentenschritt mit Human Gate bindet trotzdem einen Menschen")

    def test_lead_time_gap_reports_an_incomplete_model(self):
        self.g["metrics"] = [{"id": "me_1", "name": "Durchlauf", "kind": "time", "unit": "Stunden",
                              "direction": "lower_is_better",
                              "baseline": {"value": 10, "basis": "observed"}}]
        gap = wl.lead_time_gap(self.g, "pr_1")
        self.assertIsNotNone(gap, "1,2 h modelliert gegenüber 10 h gemessen muss auffallen")
        self.assertEqual(gap["measured_hours"], 10.0)
        self.assertLess(gap["deviation_pct"], -50)

    def test_lead_time_gap_silent_when_model_matches(self):
        self.g["metrics"] = [{"id": "me_1", "name": "Durchlauf", "kind": "time", "unit": "Stunden",
                              "direction": "lower_is_better",
                              "baseline": {"value": 1.2, "basis": "observed"}}]
        self.assertIsNone(wl.lead_time_gap(self.g, "pr_1"))

    def test_lead_time_gap_ignores_unknown_units(self):
        self.g["metrics"] = [{"id": "me_1", "name": "Durchlauf", "kind": "time", "unit": "Mondphasen",
                              "direction": "lower_is_better",
                              "baseline": {"value": 99, "basis": "observed"}}]
        self.assertIsNone(wl.lead_time_gap(self.g, "pr_1"),
                          "Eine unbekannte Einheit wird nicht geraten")


if __name__ == "__main__":
    unittest.main()
