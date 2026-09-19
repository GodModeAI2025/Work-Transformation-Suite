"""Der Validator ist die Stelle, an der die Suite unbequem wird.

Diese Tests prüfen nicht, dass er gültige Graphen durchlässt — das zeigt der
End-to-End-Test am Beispielprojekt. Sie prüfen, dass er die Fälle ablehnt, die eine
Transformationsanalyse unbrauchbar machen: Schreibrechte ohne Spur, irreversible
Entscheidungen ohne Kontrollpunkt, gestrichene Pflichtkontrollen, behauptete Messungen
ohne Fundstelle, Freigaben ohne Entscheidungslog.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import validate_graph, wl  # noqa: E402


def base_graph() -> dict:
    """Kleinster gültiger Graph mit einem Prozess über zwei Schritte."""
    g = wl.empty_graph()
    g["job_families"] = [{"id": "jf_1", "name": "F", "description": ""}]
    g["job_clusters"] = [{"id": "jc_1", "name": "C", "family_id": "jf_1", "description": ""}]
    g["roles"] = [{"id": "ro_1", "name": "Sachbearbeiter", "cluster_id": "jc_1", "status": "generated",
                   "skills": [], "task_ids": ["ta_1"], "source_refs": []}]
    g["tasks"] = [{"id": "ta_1", "role_id": "ro_1", "name": "Belege prüfen", "share_of_time": 100,
                   "frequency": "daily", "nature": "cognitive", "status": "generated",
                   "skill_ids": [], "agent_ids": []}]
    g["outcomes"] = [{"id": "ou_1", "name": "Beleg korrekt gebucht", "beneficiary": "Buchhaltung",
                      "metric_ids": ["me_1"]}]
    g["systems"] = [{"id": "sy_1", "name": "ERP", "api_available": True, "data_classes": []}]
    g["metrics"] = [{"id": "me_1", "name": "Durchlaufzeit", "kind": "time", "unit": "Stunden",
                     "direction": "lower_is_better", "process_id": "pr_1",
                     "baseline": {"value": 4, "basis": "estimated", "as_of": "2026-01"}}]
    g["processes"] = [{"id": "pr_1", "name": "Beleg bis Buchung", "trigger": "Beleg geht ein",
                       "outcome_id": "ou_1", "owner_role_id": "ro_1", "status": "generated",
                       "volume_per_year": 1000, "baseline_metric_ids": ["me_1"],
                       "step_ids": ["ps_1", "ps_2"], "data_classes": []}]
    g["process_steps"] = [
        {"id": "ps_1", "process_id": "pr_1", "name": "Beleg erfassen",
         "executor": {"type": "human", "id": "ro_1"}, "value_type": "business_required",
         "task_ids": ["ta_1"], "handling_time_min": 10, "wait_time_min": 20, "rework_pct": 0,
         "system_ids": [], "control_ids": [], "data_classes": []},
        {"id": "ps_2", "process_id": "pr_1", "name": "Beleg buchen",
         "executor": {"type": "human", "id": "ro_1"}, "value_type": "customer_value",
         "task_ids": [], "handling_time_min": 5, "wait_time_min": 5, "rework_pct": 0,
         "system_ids": [], "control_ids": [], "data_classes": []},
    ]
    g["process_edges"] = [{"id": "pe_1", "process_id": "pr_1", "from_step_id": "ps_1",
                           "to_step_id": "ps_2", "handover": "system", "condition": ""}]
    return g


class TestBaseline(unittest.TestCase):
    def test_minimal_graph_is_valid(self):
        errors, _ = validate_graph.validate(base_graph())
        self.assertEqual(errors, [], "Der Ausgangsgraph der übrigen Tests muss fehlerfrei sein")


class TestReferentialIntegrity(unittest.TestCase):
    def test_step_from_a_foreign_process_is_rejected(self):
        g = base_graph()
        g["process_steps"][1]["process_id"] = "pr_2"
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("process_id unbekannt" in e for e in errors))

    def test_unlisted_step_is_rejected(self):
        g = base_graph()
        g["processes"][0]["step_ids"] = ["ps_1"]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("nicht in step_ids gelistet" in e for e in errors))

    def test_executor_must_resolve(self):
        g = base_graph()
        g["process_steps"][0]["executor"] = {"type": "agent", "id": "ag_gibtsnicht"}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("bekannte agent_id" in e for e in errors))


class TestEvidence(unittest.TestCase):
    def test_claimed_measurement_without_provenance_is_an_error(self):
        g = base_graph()
        g["metrics"][0]["baseline"]["basis"] = "observed"
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("provenance" in e for e in errors),
                        "Eine behauptete Messung ohne Fundstelle ist schlechter als eine Schätzung")

    def test_estimate_without_provenance_is_only_a_warning(self):
        errors, warnings = validate_graph.validate(base_graph())
        self.assertEqual(errors, [])
        self.assertTrue(any("ohne Provenienz" in w for w in warnings))

    def test_provenance_makes_the_claim_acceptable(self):
        g = base_graph()
        g["metrics"][0]["baseline"]["basis"] = "observed"
        g["provenance"] = [{"id": "pv_1", "entity_type": "metrics", "entity_id": "me_1",
                            "field": "baseline", "source_kind": "system_export",
                            "locator": "export.csv", "author": "Controlling",
                            "reviewer": "Leitung", "confidence": 0.9, "status": "verified",
                            "as_of": "2026-01"}]
        errors, _ = validate_graph.validate(g)
        self.assertEqual(errors, [])

    def test_observed_value_needs_its_own_provenance(self):
        g = base_graph()
        g["metrics"][0]["observed"] = {"value": 1, "basis": "observed", "as_of": "2026-05"}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("observed" in e for e in errors))


class TestAccountability(unittest.TestCase):
    def test_automated_decision_needs_an_accountable_person(self):
        g = base_graph()
        g["agents"] = [{"id": "ag_1", "name": "A", "status": "proposed", "specificity": "domain",
                        "task_ids": ["ta_1"]}]
        g["process_steps"][0]["executor"] = {"type": "agent", "id": "ag_1"}
        g["process_steps"][0]["decision"] = {"scope": "execute_reversible"}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("accountable_role_id" in e for e in errors))
        self.assertTrue(any("escalation" in e for e in errors))

    def test_irreversible_decision_needs_a_gate_or_control(self):
        g = base_graph()
        g["agents"] = [{"id": "ag_1", "name": "A", "status": "proposed", "specificity": "domain",
                        "task_ids": ["ta_1"]}]
        g["process_steps"][0]["executor"] = {"type": "agent", "id": "ag_1"}
        g["process_steps"][0]["decision"] = {"scope": "execute_irreversible",
                                             "accountable_role_id": "ro_1",
                                             "escalation": "an die Leitung"}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("irreversible" in e for e in errors))


class TestContracts(unittest.TestCase):
    def agent(self, **contract):
        base = {"trigger": "t", "inputs": ["i"], "outputs": ["o"],
                "decision_scope": "execute_reversible", "fallback": "zurück in die Warteschlange"}
        base.update(contract)
        return {"id": "ag_1", "name": "A", "status": "planned", "specificity": "domain",
                "task_ids": ["ta_1"], "contract": base}

    def errors_for(self, agent):
        g = base_graph()
        g["agents"] = [agent]
        g["tasks"][0]["agent_ids"] = ["ag_1"]
        return validate_graph.validate(g)[0]

    def test_minimal_contract_is_accepted(self):
        self.assertEqual(self.errors_for(self.agent()), [])

    def test_write_permissions_need_audit_and_idempotency(self):
        errors = self.errors_for(self.agent(write_permissions=["ERP: Buchungen"]))
        self.assertTrue(any("audit_events" in e for e in errors))
        self.assertTrue(any("idempotency_key" in e for e in errors))

    def test_irreversible_scope_needs_a_human_checkpoint(self):
        errors = self.errors_for(self.agent(decision_scope="execute_irreversible"))
        self.assertTrue(any("human_checkpoint" in e for e in errors))

    def test_model_names_are_rejected(self):
        errors = self.errors_for(self.agent(capability_profile="braucht GPT-6 mit langem Kontext"))
        self.assertTrue(any("konkretes Modell" in e for e in errors),
                        "Ein Vertrag beschreibt die Fähigkeit, nicht das Produkt")

    def test_pilot_without_evaluation_set_is_rejected(self):
        a = self.agent()
        a["status"] = "pilot"
        errors = self.errors_for(a)
        self.assertTrue(any("evaluation_set" in e for e in errors))

    def test_orchestrator_without_own_tasks_is_not_flagged(self):
        g = base_graph()
        g["agents"] = [
            {"id": "ag_1", "name": "Spezialist", "status": "proposed", "specificity": "domain",
             "task_ids": ["ta_1"]},
            {"id": "ag_2", "name": "Orchestrator", "status": "proposed", "specificity": "domain",
             "task_ids": [], "orchestrates": ["ag_1"]},
        ]
        g["tasks"][0]["agent_ids"] = ["ag_1"]
        _, warnings = validate_graph.validate(g)
        self.assertFalse(any("Orchestrator" in w and "deckt keine Aufgabe" in w for w in warnings))


class TestBlueprintRules(unittest.TestCase):
    def blueprint(self, **over):
        bp = {
            "id": "bp_1", "process_id": "pr_1", "scenario": "balanced", "name": "B",
            "status": "draft", "outcome_id": "ou_1",
            "steps": [
                {"name": "Erfassen und buchen", "operator": "merge",
                 "from_step_ids": ["ps_1", "ps_2"], "executor": {"type": "agent", "id": None},
                 "rationale": "Beides arbeitet auf demselben Beleg.", "metric_id": "me_1",
                 "handling_time_min": 3, "wait_time_min": 2},
            ],
            "removed_step_ids": [], "agent_ids": [],
            "control_coverage": {"retained_control_ids": [], "replaced": [], "dropped_control_ids": []},
            "projected_metrics": [], "open_assumptions": [],
        }
        bp.update(over)
        return bp

    def graph_with(self, bp, controls=None):
        g = base_graph()
        if controls:
            g["controls"] = controls
            g["process_steps"][0]["control_ids"] = [c["id"] for c in controls]
        g["blueprints"] = [bp]
        return g

    def test_valid_blueprint_passes(self):
        errors, _ = validate_graph.validate(self.graph_with(self.blueprint()))
        self.assertEqual(errors, [])

    def test_pure_automation_is_rejected(self):
        bp = self.blueprint(steps=[
            {"name": "A", "operator": "automate", "from_step_ids": ["ps_1"],
             "executor": {"type": "agent", "id": None}, "rationale": "r", "metric_id": "me_1"},
            {"name": "B", "operator": "automate", "from_step_ids": ["ps_2"],
             "executor": {"type": "agent", "id": None}, "rationale": "r", "metric_id": "me_1"},
        ])
        errors, _ = validate_graph.validate(self.graph_with(bp))
        self.assertTrue(any("kein Redesign" in e for e in errors),
                        "KI auf den Altprozess zu setzen ist genau der Fehler, den die Suite verhindern soll")

    def test_change_without_rationale_is_rejected(self):
        bp = self.blueprint()
        bp["steps"][0]["rationale"] = ""
        errors, _ = validate_graph.validate(self.graph_with(bp))
        self.assertTrue(any("rationale fehlt" in e for e in errors))

    def test_mandatory_control_cannot_be_dropped(self):
        control = {"id": "ct_1", "name": "Vier-Augen", "kind": "financial", "mode": "preventive",
                   "mandatory": True, "evidence": "Vermerk"}
        bp = self.blueprint(control_coverage={"retained_control_ids": [], "replaced": [],
                                              "dropped_control_ids": ["ct_1"]})
        errors, _ = validate_graph.validate(self.graph_with(bp, [control]))
        self.assertTrue(any("ersatzlos" in e for e in errors))

    def test_replacing_a_mandatory_control_needs_a_named_approver(self):
        control = {"id": "ct_1", "name": "Vier-Augen", "kind": "financial", "mode": "preventive",
                   "mandatory": True, "evidence": "Vermerk"}
        bp = self.blueprint(control_coverage={
            "retained_control_ids": [], "dropped_control_ids": [],
            "replaced": [{"control_id": "ct_1", "replacement": "Automatischer Abgleich",
                          "rationale": "findet dieselben Fehler"}]})
        errors, _ = validate_graph.validate(self.graph_with(bp, [control]))
        self.assertTrue(any("approved_by" in e for e in errors))

    def test_unaddressed_control_is_rejected(self):
        control = {"id": "ct_1", "name": "Vier-Augen", "kind": "financial", "mode": "preventive",
                   "mandatory": True, "evidence": "Vermerk"}
        errors, _ = validate_graph.validate(self.graph_with(self.blueprint(), [control]))
        self.assertTrue(any("weder behalten" in e for e in errors))

    def test_agent_native_needs_a_human_gate(self):
        bp = self.blueprint(scenario="agent_native")
        errors, _ = validate_graph.validate(self.graph_with(bp))
        self.assertTrue(any("Human Gate" in e for e in errors))

    def test_approved_blueprint_needs_a_decision(self):
        bp = self.blueprint(status="approved")
        errors, _ = validate_graph.validate(self.graph_with(bp))
        self.assertTrue(any("Entscheidungslog" in e for e in errors))

    def test_duplicate_scenario_is_rejected(self):
        g = self.graph_with(self.blueprint())
        second = self.blueprint()
        second["id"] = "bp_2"
        g["blueprints"].append(second)
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("gibt es für diesen Prozess schon" in e for e in errors))


class TestExperimentRules(unittest.TestCase):
    def graph_with_experiment(self, **over):
        g = base_graph()
        g["metrics"].append({"id": "me_q", "name": "Fehlerquote", "kind": "quality",
                             "unit": "Prozent", "direction": "lower_is_better", "process_id": "pr_1",
                             "baseline": {"value": 5, "basis": "estimated", "as_of": "2026-01"}})
        g["metrics"].append({"id": "me_r", "name": "Fehlbuchungen", "kind": "risk",
                             "unit": "Prozent", "direction": "lower_is_better", "process_id": "pr_1",
                             "baseline": {"value": 1, "basis": "estimated", "as_of": "2026-01"}})
        x = {"id": "xp_1", "process_id": "pr_1", "name": "Pilot", "hypothesis": "H",
             "design": "ab_test", "control_group": "halbe Menge", "status": "draft",
             "primary_metric_id": "me_1", "guardrail_metric_ids": ["me_q", "me_r"],
             "stop_rules": ["Guardrail verletzt"], "rollback": "zurückschalten",
             "owner_role_id": "ro_1", "duration_days": 42, "sample_size": 100}
        x.update(over)
        g["experiments"] = [x]
        return g

    def test_valid_experiment_passes(self):
        errors, _ = validate_graph.validate(self.graph_with_experiment())
        self.assertEqual(errors, [])

    def test_missing_quality_and_risk_guardrails_are_rejected(self):
        errors, _ = validate_graph.validate(self.graph_with_experiment(guardrail_metric_ids=[]))
        self.assertTrue(any("'quality'" in e for e in errors))
        self.assertTrue(any("'risk'" in e for e in errors))

    def test_missing_stop_rule_is_rejected(self):
        errors, _ = validate_graph.validate(self.graph_with_experiment(stop_rules=[]))
        self.assertTrue(any("stop_rules" in e for e in errors))

    def test_ab_test_needs_a_control_group(self):
        errors, _ = validate_graph.validate(self.graph_with_experiment(control_group=""))
        self.assertTrue(any("control_group" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
