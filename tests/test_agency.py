"""Beschäftigtensicht (Skill agency-audit, Schema 1.4).

Geprüft wird die Rechenlogik (Zonen, Lücke, Jensen-Shannon-Distanz), der Datenschutz im Import
(keine Personenspalten, keine Codes im Ergebnis, Mindestgruppe je Aufgabe und Rolle), die Ableitung
im Graphen samt Validator, und dass die Pipeline die Befragung selbst aufnimmt, ohne dass ein
Projekt ohne Befragung sich verändert.
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
from context import EXAMPLE, ROOT, SKILLS, validate_graph, wl  # noqa: E402

A = SKILLS / "agency-audit" / "scripts"
COLUMNS = ["teilnehmer", "rolle", "aufgabe_id", "aufgabe", "bekannt", "wunsch", "zusammenarbeit", "sorge",
           "freude", "gruende_wunsch", "gruende_zusammenarbeit"]


def run(script, *args, skill="agency-audit"):
    return subprocess.run([sys.executable, str(SKILLS / skill / "scripts" / script), *args],
                          cwd=str(ROOT), capture_output=True, text=True)


def answers(graph, per_role=6, desire=None, has=None, skip_roles=(), small_roles=()):
    """Antworten für alle Aufgaben: desire(task) und has(task) bestimmen die Werte."""
    rows = []
    roles = {r["id"]: r for r in graph["roles"]}
    for rid, r in sorted(roles.items()):
        if r["name"] in skip_roles:
            continue
        n = 4 if r["name"] in small_roles else per_role
        for k in range(n):
            for t in sorted((t for t in graph["tasks"] if t["role_id"] == rid), key=lambda t: t["id"]):
                rows.append({"teilnehmer": f"P{rid[-4:]}{k}", "rolle": r["name"], "aufgabe_id": t["id"],
                             "aufgabe": t["name"], "bekannt": "ja",
                             "wunsch": desire(t) if desire else 4, "zusammenarbeit": has(t) if has else 2,
                             "sorge": 2, "freude": 3, "gruende_wunsch": "zeit|wiederholung",
                             "gruende_zusammenarbeit": "pruefung"})
    return rows


class TestLibrary(unittest.TestCase):
    def test_zones(self):
        self.assertEqual(wl.agency_zone(4.0, 7.0), "green")
        self.assertEqual(wl.agency_zone(3.0, 7.0), "red")
        self.assertEqual(wl.agency_zone(3.5, 5.9), "opportunity")
        self.assertEqual(wl.agency_zone(2.0, 2.0), "low")
        self.assertIsNone(wl.agency_zone(None, 7.0))

    def test_jensen_shannon(self):
        self.assertEqual(wl.jensen_shannon([0, 1, 0, 0, 0], [0, 1, 0, 0, 0]), 0.0)
        self.assertEqual(wl.jensen_shannon([1, 0, 0, 0, 0], [0, 0, 0, 0, 1]), 1.0)
        mid = wl.jensen_shannon([0.5, 0.5, 0, 0, 0], [0, 0.5, 0.5, 0, 0])
        self.assertTrue(0 < mid < 1)
        self.assertIsNone(wl.jensen_shannon([0] * 5, [1, 0, 0, 0, 0]))
        self.assertEqual(wl.friction_level(0.1), "low")
        self.assertEqual(wl.friction_level(0.3), "medium")
        self.assertEqual(wl.friction_level(0.5), "high")

    def test_distribution_is_weighted(self):
        self.assertEqual(wl.has_distribution([1, 3], [3, 1]), [0.75, 0.0, 0.25, 0.0, 0.0])
        self.assertEqual(wl.has_distribution([]), [0.0] * 5)


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-agency-")
        self.proj = Path(self.tmp) / "p"
        shutil.copytree(EXAMPLE, self.proj)
        shutil.rmtree(self.proj / "00_input" / "befragung", ignore_errors=True)
        r = run("run_pipeline.py", "--project", str(self.proj), skill="work-transformation")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr)
        self.graph = wl.load_latest_graph(self.proj)
        self.csv = self.proj / "00_input" / "befragung" / "antworten.csv"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rows, columns=COLUMNS):
        wl.write_csv(self.csv, rows, columns)

    def test_sheet_lists_every_task_of_the_role(self):
        r = run("export_audit_sheet.py", "--project", str(self.proj), "--rollen", "Kreditprüfer")
        self.assertEqual(r.returncode, 0, r.stderr)
        sheet = (self.proj / "30_review" / "befragung" / "fragebogen_kreditprufer.md").read_text(encoding="utf-8")
        role = next(x for x in self.graph["roles"] if x["name"] == "Kreditprüfer")
        for t in self.graph["tasks"]:
            if t["role_id"] == role["id"]:
                self.assertIn(t["id"], sheet)
        self.assertIn("§ 94", sheet)
        rows = wl.read_csv(self.proj / "30_review" / "befragung" / "antworten_vorlage.csv")
        self.assertTrue(rows and all(x["rolle"] == "Kreditprüfer" and not x["teilnehmer"] for x in rows))
        self.assertEqual(run("export_audit_sheet.py", "--project", str(self.proj), "--rollen", "Gibtsnicht").returncode, 2)

    def test_columns_naming_persons_are_refused(self):
        rows = answers(self.graph)
        for x in rows:
            x["email"] = "x"
        self.write(rows, COLUMNS + ["email"])
        r = run("import_audit.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 2)
        self.assertIn("benennen Personen", r.stdout + r.stderr)

    def test_code_that_looks_like_an_address_is_refused(self):
        rows = answers(self.graph)
        rows[0]["teilnehmer"] = "jemand@example.org"
        self.write(rows)
        self.assertEqual(run("import_audit.py", "--project", str(self.proj)).returncode, 2)

    def test_minimum_group_and_no_codes_in_result(self):
        self.write(answers(self.graph, small_roles=("Forderungsmanager",)))
        r = run("import_audit.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (self.proj / "20_graph" / "agency.json").read_text(encoding="utf-8")
        self.assertNotIn('"P', text)  # kein Teilnehmercode im Ergebnis
        data = wl.read_json(self.proj / "20_graph" / "agency.json")
        fm = next(x for x in self.graph["roles"] if x["name"] == "Forderungsmanager")
        self.assertNotIn(fm["id"], data["roles"])
        self.assertFalse(any(self.graph and t["role_id"] == fm["id"]
                             for t in self.graph["tasks"] if t["id"] in data["tasks"]))
        self.assertTrue(all(v["respondents"] >= wl.AUDIT_MIN_GROUP for v in data["tasks"].values()))

    def test_unfamiliar_answers_do_not_count(self):
        rows = answers(self.graph)
        target = rows[0]["aufgabe_id"]
        flagged = 0
        for x in rows:
            if x["aufgabe_id"] == target and flagged < 2:
                x["bekannt"] = "nein"
                flagged += 1
        self.write(rows)
        self.assertEqual(run("import_audit.py", "--project", str(self.proj)).returncode, 0)
        data = wl.read_json(self.proj / "20_graph" / "agency.json")
        self.assertNotIn(target, data["tasks"])  # 6 − 2 = 4 Antworten, unter der Mindestgruppe
        self.assertEqual(data["meta"]["answers_unfamiliar"], 2)

    def test_zones_gap_and_friction_in_graph(self):
        def desire(t):
            return 2 if (t.get("automation_potential") or 0) >= 6 and "prüfen" in t["name"] else 4

        def has(t):
            return min(5, (t.get("has_level") or 3) + 2)

        self.write(answers(self.graph, desire=desire, has=has))
        self.assertEqual(run("import_audit.py", "--project", str(self.proj)).returncode, 0)
        r = run("score_agency.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        g = wl.load_latest_graph(self.proj)
        self.assertEqual(g["meta"]["stage"], "agency")
        rated = [t for t in g["tasks"] if t.get("agency")]
        self.assertTrue(rated)
        for t in rated:
            a = t["agency"]
            self.assertEqual(a["zone"], wl.agency_zone(a["desire"], t["automation_potential"]))
            self.assertEqual(a["has_gap"], a["has_desired"] - t["has_level"])
        self.assertIn("red", {t["agency"]["zone"] for t in rated})
        roles = [r for r in g["roles"] if r.get("agency")]
        self.assertTrue(roles)
        for ro in roles:
            self.assertAlmostEqual(sum(ro["agency"]["zone_shares"].values()), 100.0, delta=1.0)
            self.assertIn(ro["agency"]["friction"], wl.ENUM_FRICTION)
            self.assertGreater(ro["agency"]["gap_mean"], 0)
        errors, _ = validate_graph.validate(g)
        self.assertEqual(errors, [])
        review = sorted((self.proj / "30_review").glob("beschaeftigtensicht_v*.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("Vorsichtszone", review)
        self.assertNotIn("P", "".join(x for x in review.split() if x.startswith("P") and x[1:2].isdigit()))

    def test_validator_rejects_small_groups_and_warns_on_autonomy_conflict(self):
        g = wl.load_latest_graph(self.proj)
        t = g["tasks"][0]
        t["agency"] = {"respondents": 3, "has_desired": 5, "desire": 2.0}
        errors, _ = validate_graph.validate(g)
        self.assertTrue(any("Mindestgruppe" in e for e in errors))
        t["agency"]["respondents"] = 6
        agent = {"id": "ag_test", "name": "Test", "status": "proposed", "specificity": "generic", "task_ids": [t["id"]],
                 "contract": {"trigger": "x", "inputs": ["a"], "outputs": ["b"], "decision_scope": "execute_reversible",
                              "fallback": "Mensch"}}
        g["agents"].append(agent)
        errors, warnings = validate_graph.validate(g)
        self.assertFalse(any("Mindestgruppe" in e for e in errors))
        self.assertTrue(any("laufende Beteiligung" in w for w in warnings))
        agent["contract"]["human_checkpoint"] = {"role_id": t["role_id"]}
        _, warnings = validate_graph.validate(g)
        self.assertFalse(any("laufende Beteiligung" in w for w in warnings))

    def test_pipeline_picks_up_answers_and_is_deterministic(self):
        self.write(answers(self.graph))
        r = run("run_pipeline.py", "--project", str(self.proj), skill="work-transformation")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr)
        self.assertIn("score_agency.py", r.stdout)
        first = (self.proj / "20_graph" / "agency.json").read_bytes()
        v1 = wl.load_project_meta(self.proj)["graph_version"]
        g1 = wl.load_latest_graph(self.proj)
        self.assertTrue(any(t.get("agency") for t in g1["tasks"]))
        r = run("run_pipeline.py", "--project", str(self.proj), skill="work-transformation")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(first, (self.proj / "20_graph" / "agency.json").read_bytes())
        g2 = wl.load_latest_graph(self.proj)
        strip = lambda g: {k: v for k, v in g.items() if k != "meta"}  # noqa: E731
        self.assertEqual(strip(g1), strip(g2))
        self.assertGreaterEqual(wl.load_project_meta(self.proj)["graph_version"], v1)


class TestOutputs(unittest.TestCase):
    """Welle 2: Dashboard, Berichte, Fahrplan, Verträge und Rollen.md nutzen die Beschäftigtensicht."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wts-agency-out-")
        cls.proj = Path(cls.tmp) / "p"
        shutil.copytree(EXAMPLE, cls.proj)
        shutil.rmtree(cls.proj / "00_input" / "befragung", ignore_errors=True)
        assert run("run_pipeline.py", "--project", str(cls.proj), skill="work-transformation").returncode == 0
        g = wl.load_latest_graph(cls.proj)

        def desire(t):
            return 1 if "Rahmenvertrag" in t["name"] else 4

        def has(t):
            return 5 if "Rahmenvertrag" in t["name"] else (t.get("has_level") or 3)

        wl.write_csv(cls.proj / "00_input" / "befragung" / "a.csv", answers(g, per_role=6, desire=desire, has=has), COLUMNS)
        r = run("run_pipeline.py", "--project", str(cls.proj), skill="work-transformation")
        assert r.returncode == 0, r.stdout[-2000:]
        cls.graph = wl.load_latest_graph(cls.proj)
        cls.v = int(cls.graph["meta"]["version"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def out(self, name):
        return (self.proj / "40_output" / name).read_text(encoding="utf-8")

    def test_dashboard_and_reports(self):
        html = self.out(f"dashboard_v{self.v:03d}.html")
        self.assertIn('id="beschaeftigte"', html)
        self.assertIn('href="#beschaeftigte"', html)
        self.assertIn("Vorsichtszone", html)
        hr = self.out(f"report_hr_v{self.v:03d}.md")
        self.assertIn("## Sicht der Beschäftigten", hr)
        self.assertIn("Auftragsdaten gegen Rahmenvertrag prüfen", hr)
        it = self.out(f"report_it_v{self.v:03d}.md")
        self.assertIn("## Latente Nachfrage", it)

    def test_contracts_and_rollen_md(self):
        md = self.out(f"contracts_v{self.v:03d}.md")
        self.assertIn("Sicht der Beschäftigten", md)
        r = run("build_rollen_md.py", "--project", str(self.proj), "--role", "Auftragssachbearbeiter", skill="agent-mapper")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = "".join(p.read_text(encoding="utf-8") for p in (self.proj / "40_output" / "rollen_md").glob("*.md"))
        self.assertIn("Was die Rolle selbst will (6 Teilnehmende)", text)
        self.assertIn("Lieber selbst behalten: Auftragsdaten gegen Rahmenvertrag prüfen", text)

    def test_roadmap_gate_keeps_red_work_out_of_the_first_wave(self):
        sys.path.insert(0, str(SKILLS / "transformation-roadmap" / "scripts"))
        import roadmap_lib as rl  # noqa: WPS433
        g = wl.load_latest_graph(self.proj)
        cfg = rl.load_config()
        cfg["waves"][0]["capacity"] = 99  # Platz in Welle 1, damit das Tor sichtbar wird
        cfg["max_complexity_first_wave"] = 5
        base = rl.plan(g, cfg)
        first = [k for k, v in base["placement"].items() if v["wave"] == 1 and v["state"] == "proposed"]
        self.assertTrue(first, "Beispiel braucht einen Vorschlag in Welle 1")
        key = first[0]
        cand = base["by_key"][key]
        for t in g["tasks"]:
            if t["id"] in cand["task_ids"]:
                t["agency"] = {"respondents": 6, "has_desired": 3, "desire": 1.5, "zone": "red"}
        gated = rl.plan(g, cfg)
        self.assertNotEqual(gated["placement"][key]["wave"], 1)
        self.assertIn("Vorsichtszone", gated["placement"][key]["reason"])
        self.assertTrue(any("Vorsichtszone" in n for n in gated["notes"]))
        cfg["max_red_zone_share_first_wave"] = 100
        self.assertEqual(rl.plan(g, cfg)["placement"][key]["wave"], 1)
        csv_text = self.out(f"fahrplan_v{self.v:03d}.csv")
        self.assertIn("beschaeftigte", csv_text.splitlines()[0])


class TestWithoutSurvey(unittest.TestCase):
    def test_project_without_answers_has_no_agency(self):
        tmp = tempfile.mkdtemp(prefix="wts-agency-")
        try:
            proj = Path(tmp) / "p"
            shutil.copytree(EXAMPLE, proj)
            shutil.rmtree(proj / "00_input" / "befragung", ignore_errors=True)
            r = run("run_pipeline.py", "--project", str(proj), skill="work-transformation")
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("import_audit.py", r.stdout)
            g = wl.load_latest_graph(proj)
            self.assertFalse(any(t.get("agency") for t in g["tasks"]))
            v = int(g["meta"]["version"])
            html = (proj / "40_output" / f"dashboard_v{v:03d}.html").read_text(encoding="utf-8")
            self.assertNotIn('id="beschaeftigte"', html)
            fahrplan = (proj / "40_output" / f"fahrplan_v{v:03d}.md").read_text(encoding="utf-8")
            self.assertNotIn("Sicht der Beschäftigten", fahrplan)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
