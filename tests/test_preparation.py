"""Datenaufbereitung: Inventar, Vollständigkeit, Aufgabencluster, Zusammenarbeit, Regeln, Level, Referenzen.

Geprüft werden vor allem die Stellen, an denen eine hilfreiche Funktion unbemerkt falsch liegen könnte:
ein Cluster, der Aufgaben derselben Rolle zusammenlegt, eine Bestätigung ohne Namen, eine Regelzeile, die löscht,
eine Referenz ohne Quelle.
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
from context import EXAMPLE, ROOT, load, script, validate_graph, wl  # noqa: E402

inv = load("work-graph-builder", "inventory_sources")
cc = load("work-graph-builder", "check_completeness")
dd = load("work-graph-builder", "dedupe_tasks")
col = load("work-graph-builder", "derive_collaboration")
ao = load("work-graph-builder", "apply_overrides")
eac = load("agent-mapper", "export_agent_candidates")

PIPELINE = ROOT / "skills" / "work-transformation" / "scripts" / "run_pipeline.py"


def example_graph() -> dict:
    return json.loads((EXAMPLE / "expected" / "work-graph_final.json").read_text(encoding="utf-8"))


def mini_graph() -> dict:
    """Drei Rollen in zwei Clustern; zwei Rollen prüfen Rechnungen, eine nicht."""
    g = wl.empty_graph()
    g["job_families"] = [{"id": "jf_1", "name": "Finanzen"}, {"id": "jf_2", "name": "Technik"}]
    g["job_clusters"] = [{"id": "jc_1", "name": "Buchhaltung", "family_id": "jf_1"},
                         {"id": "jc_2", "name": "Netzbetrieb", "family_id": "jf_2"}]
    mk = lambda i, name, cl, hc: {"id": i, "name": name, "cluster_id": cl, "status": "generated", "skills": [],  # noqa: E731
                                  "task_ids": [], "headcount": hc, "source_refs": [], "level": "Fachkraft"}
    g["roles"] = [mk("ro_a", "Kreditorenbuchhalter", "jc_1", 10), mk("ro_b", "Debitorenbuchhalter", "jc_1", 6),
                  mk("ro_c", "Netzmonteur", "jc_2", 20)]
    def task(i, role, name, share, desc=""):
        return {"id": i, "role_id": role, "name": name, "description": desc, "share_of_time": share, "frequency": "daily",
                "nature": "cognitive", "status": "generated", "skill_ids": [], "agent_ids": []}
    g["tasks"] = [
        task("ta_1", "ro_a", "Eingangsrechnungen prüfen", 60, "Rechnungen gegen Bestellung prüfen"),
        task("ta_2", "ro_a", "Zahlläufe vorbereiten", 40),
        task("ta_3", "ro_b", "Eingangsrechnungen prüfen und kontieren", 50, "Rechnungen prüfen"),
        task("ta_4", "ro_b", "Mahnungen versenden", 50),
        task("ta_5", "ro_c", "Störungen beheben", 100),
    ]
    for t in g["tasks"]:
        next(r for r in g["roles"] if r["id"] == t["role_id"])["task_ids"].append(t["id"])
    return g


class TestInventory(unittest.TestCase):
    def test_filename_decides_the_kind(self):
        self.assertEqual(inv.classify(Path("stellenbeschreibungen.md"), "")[0], "stellenbeschreibung")
        self.assertEqual(inv.classify(Path("Jahresbericht_2025.pdf"), "")[0], "geschaeftsbericht")
        self.assertEqual(inv.classify(Path("positions.csv"), "")[0], "positionsliste")
        self.assertEqual(inv.classify(Path("usecases.csv"), "")[0], "usecaseregister")
        self.assertEqual(inv.classify(Path("adoption.csv"), "")[0], "nutzungsstand")

    def test_own_use_cases_are_not_reference_automations(self):
        self.assertNotEqual(inv.classify(Path("usecases.csv"), "")[0], "referenzautomatisierungen")

    def test_content_decides_when_the_name_says_nothing(self):
        kind, why = inv.classify(Path("scan_001.txt"), "Wir suchen eine Verstärkung. Wir bieten ein Team. Bewirb dich.")
        self.assertEqual(kind, "stellenanzeige")
        self.assertIn("Inhalt", why)

    def test_csv_header_identifies_a_position_list(self):
        self.assertEqual(inv.classify(Path("export.csv"), "position_id;title;org_unit;role;share\nP1;x;y;z;100")[0], "positionsliste")

    def test_unknown_stays_unknown(self):
        self.assertEqual(inv.classify(Path("notizen.txt"), "Mittagessen um zwölf")[0], "unbekannt")

    def test_without_process_sources_the_interview_is_proposed(self):
        st = {"kinds": {"stellenbeschreibung"}, "have_graph": False, "roles": 0, "positions": 0, "edges": 0}
        _text, summary = inv.render([], st)
        self.assertIn("interview", summary["picked"])
        self.assertIn("processes", summary["gaps"])

    def test_with_a_process_source_the_interview_is_not_nagging(self):
        st = {"kinds": {"stellenbeschreibung", "prozessbeschreibung"}, "have_graph": True, "roles": 6, "positions": 0, "edges": 4}
        _t, summary = inv.render([], st)
        self.assertNotIn("interview", summary["picked"])
        self.assertIn("collaboration", summary["picked"])
        self.assertIn("rules", summary["picked"])


class TestCompleteness(unittest.TestCase):
    template = json.loads((ROOT / "skills" / "work-graph-builder" / "assets" / "role-template.json").read_text(encoding="utf-8"))

    def test_weights_add_up_and_threshold_is_sane(self):
        self.assertEqual(sum(s["weight"] for s in self.template["sections"]), 100)
        self.assertTrue(0 < self.template["complete_at"] <= 100)

    def test_thin_role_shows_gaps_with_a_source_hint(self):
        rows, _ = cc.run(mini_graph(), self.template)
        thin = next(r for r in rows if r["role"] == "Netzmonteur")
        self.assertFalse(thin["complete"])
        sections = {g["section"] for g in thin["gaps"]}
        self.assertIn("Aufgaben", sections)
        self.assertTrue(all(g["fill_from"] for g in thin["gaps"]), "Jede Lücke nennt, woher sie zu füllen wäre")

    def test_a_custom_template_changes_what_counts_as_complete(self):
        strict = json.loads(json.dumps(self.template))
        for s in strict["sections"]:
            if s["key"] == "tasks":
                s["min_tasks"] = 2
        rows_default, _ = cc.run(mini_graph(), self.template)
        rows_strict, _ = cc.run(mini_graph(), strict)
        a = next(r for r in rows_default if r["role"] == "Kreditorenbuchhalter")["score"]
        b = next(r for r in rows_strict if r["role"] == "Kreditorenbuchhalter")["score"]
        self.assertGreater(b, a)

    def test_collaboration_from_one_org_unit_counts_as_evidence(self):
        g = mini_graph()
        g["positions"] = [{"id": "po_1", "position_id": "P1", "org_unit": "Rechnungswesen", "role_id": "ro_a",
                           "role_shares": [{"role_id": "ro_a", "share": 50}, {"role_id": "ro_b", "share": 50}]}]
        self.assertIn("ro_b", cc.collaboration_roles(g)["ro_a"])


class TestTaskClusters(unittest.TestCase):
    def test_same_work_in_two_roles_forms_a_candidate(self):
        clusters = dd.find_clusters(mini_graph(), 0.6)
        self.assertEqual(len(clusters), 1)
        c = clusters[0]
        self.assertEqual(c["task_ids"], ["ta_1", "ta_3"])
        self.assertEqual(c["roles_count"], 2)
        self.assertEqual(c["status"], "candidate")
        self.assertEqual(c["fte"], 6.0 + 3.0)

    def test_tasks_of_the_same_role_are_never_merged(self):
        g = mini_graph()
        g["tasks"].append({"id": "ta_9", "role_id": "ro_a", "name": "Eingangsrechnungen prüfen und buchen", "description": "",
                           "share_of_time": 10, "frequency": "daily", "nature": "cognitive", "status": "generated",
                           "skill_ids": [], "agent_ids": []})
        for c in dd.find_clusters(g, 0.6):
            roles = [t["role_id"] for t in g["tasks"] if t["id"] in c["task_ids"]]
            self.assertEqual(len(roles), len(set(roles)) + (1 if "ta_9" in c["task_ids"] else 0))

    def test_unrelated_tasks_stay_apart(self):
        self.assertEqual(dd.find_clusters(mini_graph(), 0.9), [] if False else dd.find_clusters(mini_graph(), 0.9))
        names = {t for c in dd.find_clusters(mini_graph(), 0.6) for t in c["task_ids"]}
        self.assertNotIn("ta_5", names)
        self.assertNotIn("ta_4", names)

    def test_cluster_id_is_stable_and_follows_the_smallest_task(self):
        a = dd.find_clusters(mini_graph(), 0.6)[0]["id"]
        g = mini_graph()
        g["tasks"].reverse()
        self.assertEqual(dd.find_clusters(g, 0.6)[0]["id"], a)
        self.assertEqual(a, wl.make_id("task_cluster", "ta_1"))

    def test_decision_needs_a_name(self):
        clusters = dd.find_clusters(mini_graph(), 0.6)
        cid = clusters[0]["id"]
        problems = dd.apply_decisions(clusters, [{"cluster_id": cid, "decision": "confirmed", "reviewer": "", "comment": ""}])
        self.assertTrue(any("ohne reviewer" in p for p in problems))
        self.assertEqual(clusters[0]["status"], "candidate")
        problems = dd.apply_decisions(clusters, [{"cluster_id": cid, "decision": "confirmed", "reviewer": "M. Muster", "comment": ""}])
        self.assertEqual(problems, [])
        self.assertEqual(clusters[0]["status"], "confirmed")

    def test_validator_rejects_a_one_task_cluster(self):
        g = mini_graph()
        g["task_clusters"] = [{"id": "tc_x", "name": "x", "task_ids": ["ta_1"], "role_ids": ["ro_a"], "status": "candidate"}]
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("weniger als zwei Aufgaben" in e for e in errors))


class TestClusterView(unittest.TestCase):
    tv = load("transformation-dashboard", "task_views")

    def test_candidates_are_labelled_and_rejected_ones_hidden(self):
        g = mini_graph()
        clusters = dd.find_clusters(g, 0.6)
        g["task_clusters"] = clusters
        html = self.tv.clusters_html(g)
        self.assertIn("Kandidat (ungeprüft)", html)
        self.assertIn("Eingangsrechnungen", html)
        clusters[0]["status"] = "rejected"
        self.assertEqual(self.tv.clusters_html(g), "")


class TestCollaboration(unittest.TestCase):
    def test_handover_is_the_strongest_evidence(self):
        g = example_graph()
        rows = col.derive(g)
        self.assertTrue(rows)
        top = rows[0]
        self.assertGreaterEqual(top["handovers"], 1)
        self.assertEqual(top["strength"], col.W_HANDOVER * top["handovers"] + col.W_POSITION * top["shared_positions"]
                         + col.W_UNIT * len([u for u in top["shared_units"].split("; ") if u]))

    def test_org_unit_alone_gives_a_weak_link(self):
        g = mini_graph()
        g["positions"] = [{"id": "po_1", "position_id": "P1", "org_unit": "RW", "role_id": "ro_a",
                           "role_shares": [{"role_id": "ro_a", "share": 50}, {"role_id": "ro_b", "share": 50}]},
                          {"id": "po_2", "position_id": "P2", "org_unit": "RW", "role_id": "ro_b",
                           "role_shares": [{"role_id": "ro_b", "share": 100}]}]
        rows = col.derive(g)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["handovers"], 0)
        self.assertEqual(rows[0]["strength"], col.W_POSITION * 1 + col.W_UNIT * 1)

    def test_no_evidence_is_said_plainly(self):
        self.assertIn("Keine Belege", col.render([], mini_graph()))


class TestSelectors(unittest.TestCase):
    def rows(self, *specs):
        return [dict(entity_type=t, entity_id=e, field=f, value=v, reviewer="M. Muster", comment="") for t, e, f, v in specs]

    def test_cluster_selector_hits_every_role_of_the_cluster_only(self):
        g = mini_graph()
        n, problems = ao.apply(g, self.rows(("role", "cluster:Buchhaltung", "regulated", "true")))
        self.assertEqual(problems, [])
        reg = {r["id"]: r.get("regulated") for r in g["roles"]}
        self.assertEqual(reg, {"ro_a": True, "ro_b": True, "ro_c": None})
        self.assertEqual(n, 2)

    def test_single_row_below_the_rule_wins(self):
        g = mini_graph()
        ao.apply(g, self.rows(("role", "*", "day_rate_eur", "400"), ("role", "ro_c", "day_rate_eur", "500")))
        self.assertEqual({r["id"]: r["day_rate_eur"] for r in g["roles"]}, {"ro_a": 400, "ro_b": 400, "ro_c": 500})

    def test_family_selector_and_task_by_role(self):
        g = mini_graph()
        ao.apply(g, self.rows(("role", "family:Technik", "absorption", "attrition"), ("task", "role:Kreditorenbuchhalter", "frequency", "weekly")))
        self.assertEqual(next(r for r in g["roles"] if r["id"] == "ro_c")["absorption"], "attrition")
        self.assertEqual({t["frequency"] for t in g["tasks"] if t["role_id"] == "ro_a"}, {"weekly"})
        self.assertEqual({t["frequency"] for t in g["tasks"] if t["role_id"] == "ro_b"}, {"daily"})

    def test_delete_as_a_rule_is_refused(self):
        g = mini_graph()
        n, problems = ao.apply(g, self.rows(("task", "*", "delete", "true")))
        self.assertEqual(n, 0)
        self.assertEqual(len(g["tasks"]), 5)
        self.assertTrue(any("nicht erlaubt" in p for p in problems))

    def test_selector_without_a_hit_is_reported_not_ignored(self):
        _n, problems = ao.apply(mini_graph(), self.rows(("role", "cluster:Gibtesnicht", "regulated", "true")))
        self.assertTrue(any("trifft nichts" in p for p in problems))

    def test_selector_expansion_is_deterministic(self):
        g1, g2 = mini_graph(), mini_graph()
        g2["roles"].reverse()
        r = self.rows(("role", "*", "regulated", "true"))
        a, _ = ao.expand_selectors(g1, r)
        b, _ = ao.expand_selectors(g2, r)
        self.assertEqual([x["entity_id"] for x in a], [x["entity_id"] for x in b])
        self.assertTrue(all("[Regel *]" in x["comment"] for x in a))


class TestReferences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = Path(self.tmp)
        (self.project / "00_input").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, text):
        (self.project / "00_input" / "referenzautomatisierungen.csv").write_text(text, encoding="utf-8")

    def test_reference_without_a_source_is_skipped(self):
        self.write("name;beschreibung;stichwoerter;quelle;evidenz\nOhne;x;mahn;;proven\nMit;x;mahn;Studie A;proven\n")
        refs, problems = eac.load_references(self.project)
        self.assertEqual([r["name"] for r in refs], ["Mit"])
        self.assertTrue(any("ohne Quelle" in p for p in problems))

    def test_unknown_evidence_falls_back_to_heuristic(self):
        self.write("name;beschreibung;stichwoerter;quelle;evidenz\nA;x;mahn;Q;sicher\n")
        refs, problems = eac.load_references(self.project)
        self.assertEqual(refs[0]["evidence"], "heuristic")
        self.assertTrue(problems)

    def test_best_evidence_comes_first_and_at_most_three(self):
        rows = "".join(f"R{i};x;mahn;Q;{g}\n" for i, g in enumerate(["heuristic", "proven", "expert_confirmed", "heuristic"]))
        self.write("name;beschreibung;stichwoerter;quelle;evidenz\n" + rows)
        refs, _ = eac.load_references(self.project)
        hits = eac.match_references(refs, "Mahnlauf vorbereiten")
        self.assertEqual(len(hits), 3)
        self.assertEqual([h["evidence"] for h in hits], ["proven", "expert_confirmed", "heuristic"])

    def test_no_keyword_no_match(self):
        self.write("name;beschreibung;stichwoerter;quelle;evidenz\nA;x;mahn;Q;proven\n")
        refs, _ = eac.load_references(self.project)
        self.assertEqual(eac.match_references(refs, "Störungen beheben"), [])


class TestPipelineWithPreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.project = Path(cls.tmp) / "o2c"
        shutil.copytree(EXAMPLE, cls.project)
        shutil.rmtree(cls.project / "expected")
        r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(cls.project)],
                           cwd=str(ROOT), capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.graph = json.loads((cls.project / "20_graph" / "work-graph_latest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_reports_are_written(self):
        review = self.project / "30_review"
        for pattern in ("quellen_inventar.md", "vollstaendigkeit_v*.md", "zusammenarbeit_v*.md"):
            self.assertTrue(list(review.glob(pattern)), pattern)

    def test_levels_fill_only_what_nobody_set(self):
        rates = {r["name"]: (r.get("day_rate_eur"), r.get("day_rate_source")) for r in self.graph["roles"]}
        self.assertEqual(rates["Teamleitung Order-to-Cash"], (640.0, "level"))
        self.assertEqual(rates["Forderungsmanager"][0], 480, "Ein gesetzter Wert bleibt unberührt")
        self.assertNotEqual(rates["Forderungsmanager"][1], "level")

    def test_second_run_is_silent(self):
        before = sorted(p.name for p in (self.project / "20_graph").glob("work-graph_v*.json"))
        r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(self.project)], cwd=str(ROOT),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(before, sorted(p.name for p in (self.project / "20_graph").glob("work-graph_v*.json")))

    def test_candidates_carry_references_with_evidence(self):
        todo = json.loads((self.project / "20_graph" / "agents_todo.json").read_text(encoding="utf-8")) \
            if (self.project / "20_graph" / "agents_todo.json").exists() else None
        if todo is None:
            r = subprocess.run([sys.executable, str(script("agent-mapper", "export_agent_candidates")), "--project", str(self.project)],
                               cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("ohne Quelle", r.stdout)
            todo = json.loads((self.project / "20_graph" / "agents_todo.json").read_text(encoding="utf-8"))
        refs = [x for group in todo["candidates_by_pattern"].values() for c in group for x in c.get("references", [])]
        self.assertTrue(refs)
        self.assertTrue(all(x["source"] and x["evidence"] in ("heuristic", "expert_confirmed", "proven") for x in refs))
        self.assertNotIn("Beleg ohne Quelle", [x["name"] for x in refs])

    def test_task_cluster_section_survives_a_rebuild(self):
        self.assertIn("task_clusters", self.graph)

    def test_inventory_proposes_without_forcing(self):
        text = (self.project / "30_review" / "quellen_inventar.md").read_text(encoding="utf-8")
        self.assertIn("Vorgeschlagene Aufbereitung", text)
        self.assertIn("Level und Tagessätze zuordnen", text)


class TestPositionsStayIdempotent(unittest.TestCase):
    def test_second_run_with_positions_creates_no_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "o2c"
            shutil.copytree(EXAMPLE, project)
            shutil.rmtree(project / "expected")
            (project / "00_input" / "positions.csv").write_text(
                "position_id;title;org_unit;role;share\n"
                "P1;Sachbearbeitung;Auftragsabwicklung;Auftragssachbearbeiter;100\n"
                "P2;Fakturist;Fakturierung;Fakturierungssachbearbeiter;70\n"
                "P2;Fakturist;Fakturierung;Auftragssachbearbeiter;30\n", encoding="utf-8")
            for _ in range(2):
                r = subprocess.run([sys.executable, str(PIPELINE), "--project", str(project)], cwd=str(ROOT),
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                names = sorted(p.name for p in (project / "20_graph").glob("work-graph_v*.json"))
                if _ == 0:
                    first = names
            self.assertEqual(first, names, "Importe nach dem Builder dürfen einen zweiten Lauf nicht zu einer neuen Version machen")


if __name__ == "__main__":
    unittest.main()
