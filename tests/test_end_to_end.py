"""Vollständiger Lauf des Referenzprojekts examples/order-to-cash.

Das ist der Test, der zählt: Er belegt nicht Strukturkonsistenz, sondern dass aus echten
Eingaben ein vollständiges, gültiges Ergebnis entsteht — und zwar jedes Mal dasselbe.

Er prüft drei Dinge:
1. Die Pipeline läuft ohne Eingriff durch und endet mit Exit-Code 0.
2. Das Ergebnis stimmt mit dem hinterlegten Stand überein (examples/…/expected/).
3. Ein zweiter Lauf erzeugt byteidentische Dateien und keine neue Graph-Version.

Der Test ist langsamer als die übrigen (er startet Unterprozesse). Das ist der Preis
dafür, dass er die Suite so benutzt, wie ein Anwender sie benutzt.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, ROOT, SKILLS, wl  # noqa: E402

PIPELINE = SKILLS / "work-transformation" / "scripts" / "run_pipeline.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestExampleProject(unittest.TestCase):
    """Ein Lauf für alle Prüfungen: das Kopieren und Rechnen lohnt sich nur einmal."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wts-e2e-")
        cls.project = Path(cls.tmp) / "order-to-cash"
        shutil.copytree(EXAMPLE, cls.project)
        shutil.rmtree(cls.project / "expected", ignore_errors=True)
        cls.first = cls.run_pipeline()
        cls.second = cls.run_pipeline()
        cls.graph = wl.read_json(cls.project / "20_graph" / "work-graph_latest.json")
        cls.expected = wl.read_json(EXAMPLE / "expected" / "work-graph_final.json")
        cls.manifest = wl.read_json(EXAMPLE / "expected" / "manifest.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def run_pipeline(cls):
        return subprocess.run(
            [sys.executable, str(PIPELINE), "--project", str(cls.project)],
            cwd=str(ROOT), capture_output=True, text=True,
        )

    # --- 1: läuft durch ---------------------------------------------------
    def test_pipeline_completes(self):
        self.assertEqual(self.first.returncode, 0,
                         f"Pipeline abgebrochen:\n{self.first.stdout}\n{self.first.stderr}")
        self.assertNotIn("FEHLER", self.first.stdout)
        self.assertNotIn("STOPP", self.first.stdout)

    def test_no_unresolved_references(self):
        sys.path.insert(0, str(SKILLS / "work-graph-builder" / "scripts"))
        import validate_graph
        errors, _ = validate_graph.validate(self.graph)
        self.assertEqual(errors, [])

    # --- 2: Ergebnis stimmt -----------------------------------------------
    def test_collection_counts_match_the_snapshot(self):
        actual = {c: len(self.graph.get(c, [])) for c in wl.COLLECTIONS if self.graph.get(c)}
        self.assertEqual(actual, self.manifest["counts"])

    def test_graph_matches_the_snapshot(self):
        self.assertEqual(self.graph, self.expected,
                         "Der erzeugte Graph weicht vom hinterlegten Stand ab. Wenn die Änderung "
                         "gewollt ist: examples/order-to-cash/expected/ neu erzeugen und im "
                         "Commit begründen.")

    def test_output_files_match_their_checksums(self):
        mismatched = []
        for rel, digest in sorted(self.manifest["files"].items()):
            path = self.project / rel
            self.assertTrue(path.exists(), f"Ausgabedatei fehlt: {rel}")
            if sha(path) != digest:
                mismatched.append(rel)
        self.assertEqual(mismatched, [],
                         "Nicht byteidentisch zum hinterlegten Stand — die Suite verspricht "
                         "gleiche Eingaben, gleiche Bytes.")

    # --- 3: zweiter Lauf ändert nichts ------------------------------------
    def test_second_run_creates_no_new_version(self):
        self.assertEqual(self.second.returncode, 0)
        self.assertEqual(self.graph["meta"]["version"], self.manifest["graph_version"],
                         "Ein Lauf ohne neue Eingaben darf keine neue Graph-Version anlegen")
        self.assertIn("Unverändert", self.second.stdout)

    def test_second_run_is_byte_identical(self):
        for rel in sorted(self.manifest["files"]):
            self.assertEqual(sha(self.project / rel), self.manifest["files"][rel], rel)

    # --- fachliche Stichproben --------------------------------------------
    def test_both_processes_have_all_three_scenarios(self):
        for pr in self.graph["processes"]:
            scenarios = {b["scenario"] for b in self.graph["blueprints"]
                         if b["process_id"] == pr["id"]}
            self.assertEqual(scenarios, {"conservative", "balanced", "agent_native"}, pr["name"])

    def test_scenarios_form_a_ladder(self):
        order = ["conservative", "balanced", "agent_native"]
        for pr in self.graph["processes"]:
            bps = {b["scenario"]: b for b in self.graph["blueprints"] if b["process_id"] == pr["id"]}
            shares = [bps[s]["soll_totals"]["automated_steps"] / bps[s]["soll_totals"]["steps"]
                      for s in order]
            self.assertEqual(shares, sorted(shares), f"{pr['name']}: Ambition muss steigen")

    def test_no_blueprint_is_pure_automation(self):
        for bp in self.graph["blueprints"]:
            ops = {s["operator"] for s in bp["steps"]}
            self.assertNotEqual(ops, {"automate"}, bp["name"])

    def test_every_mandatory_control_survives_every_blueprint(self):
        controls = wl.index_by_id(self.graph["controls"])
        for bp in self.graph["blueprints"]:
            ist = {c for s in self.graph["process_steps"]
                   if s["process_id"] == bp["process_id"] for c in s.get("control_ids", [])}
            cov = bp["control_coverage"]
            handled = set(cov["retained_control_ids"]) | {r["control_id"] for r in cov["replaced"]}
            for cid in ist:
                if controls[cid].get("mandatory", True):
                    self.assertIn(cid, handled,
                                  f"{bp['name']}: Pflichtkontrolle {controls[cid]['name']} verloren")

    def test_measured_values_carry_their_provenance(self):
        measured = [m for m in self.graph["metrics"] if (m.get("observed") or {}).get("value") is not None]
        self.assertTrue(measured, "Das Beispiel soll einen abgeschlossenen Pilot enthalten")
        prov = {(p["entity_type"], p["entity_id"], p["field"]) for p in self.graph["provenance"]}
        for m in measured:
            self.assertIn(("metrics", m["id"], "observed"), prov, m["name"])

    def test_baselines_are_not_overwritten_by_pilot_results(self):
        for m in self.graph["metrics"]:
            if (m.get("observed") or {}).get("value") is None:
                continue
            baseline, _ = wl.metric_value(m, "baseline")
            observed, _ = wl.metric_value(m, "observed")
            self.assertNotEqual(baseline, observed,
                                f"{m['name']}: Der Ist-Wert wurde vom Pilotwert überschrieben")

    def test_approved_blueprints_have_a_decision(self):
        decided = {d["subject_id"] for d in self.graph["decisions"]
                   if d["subject_type"] == "blueprints"}
        approved = [b for b in self.graph["blueprints"] if b["status"] == "approved"]
        self.assertTrue(approved, "Das Beispiel soll eine Freigabe enthalten")
        for b in approved:
            self.assertIn(b["id"], decided, b["name"])

    def test_dashboard_is_a_single_offline_file(self):
        v = self.graph["meta"]["version"]
        html = (self.project / "40_output" / f"dashboard_v{v:03d}.html").read_text(encoding="utf-8")
        for forbidden in ("<script src=", "<link rel=\"stylesheet\"", "http://", "https://"):
            self.assertNotIn(forbidden, html,
                             "Das Dashboard darf nichts nachladen — es soll offline funktionieren")
        for section in ('id="prozesse"', 'id="szenarien"', 'id="piloten"', 'id="governance"'):
            self.assertIn(section, html)


class TestMigrationOfAnOlderProject(unittest.TestCase):
    """Ein Projekt nach Schema 1.0 muss sich verlustfrei weiterbetreiben lassen."""

    def test_schema_10_project_migrates_and_still_runs(self):
        tmp = tempfile.mkdtemp(prefix="wts-mig-")
        try:
            project = Path(tmp) / "alt"
            shutil.copytree(EXAMPLE, project)
            shutil.rmtree(project / "expected", ignore_errors=True)
            # Prozessebene entfernen: so sieht ein Projekt nach Schema 1.0 aus.
            (project / "10_extraction" / "process_order-to-cash.json").unlink()
            for leftover in ("blueprints.json", "process_value.json", "experiments.json"):
                (project / "20_graph" / leftover).unlink()
            (project / "30_review" / "decisions.csv").unlink()

            subprocess.run([sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "build_graph.py"),
                            "--project", str(project)], cwd=str(ROOT), capture_output=True, check=True)
            graph = wl.read_json(project / "20_graph" / "work-graph_latest.json")
            # Auf Schema 1.0 zurückschreiben, wie es ein Altprojekt auf der Platte hätte
            for c in wl.COLLECTIONS_PROCESS + wl.COLLECTIONS_REDESIGN + wl.COLLECTIONS_GOVERNANCE:
                graph.pop(c, None)
            graph["meta"]["schema_version"] = "1.0"
            wl.write_json(project / "20_graph" / "work-graph_latest.json", graph)

            migrate = subprocess.run(
                [sys.executable, str(SKILLS / "work-graph-builder" / "scripts" / "migrate_graph.py"),
                 "--project", str(project)], cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(migrate.returncode, 0, migrate.stdout + migrate.stderr)

            migrated = wl.read_json(project / "20_graph" / "work-graph_latest.json")
            self.assertEqual(migrated["meta"]["schema_version"], wl.SCHEMA_VERSION)
            self.assertEqual(len(migrated["roles"]), len(graph["roles"]), "Migration verliert nichts")
            self.assertEqual(len(migrated["tasks"]), len(graph["tasks"]))
            for c in wl.COLLECTIONS_PROCESS:
                self.assertEqual(migrated[c], [], f"{c} entsteht leer, nicht geraten")

            run = subprocess.run([sys.executable, str(PIPELINE), "--project", str(project)],
                                 cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("Diagnosemodus", run.stdout,
                          "Ohne Prozesse muss die Pipeline sagen, dass sie in der Diagnose bleibt")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
