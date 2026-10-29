"""Stände: Pflege-Lock, Snapshots, Freigabestände.

Geprüft wird, was ein Stand garantieren muss: Ein fremder Anspruch hält die Pipeline an, ein
abgelaufener wird nie still übernommen, ein Snapshot stellt byteidentisch wieder her, ein
Freigabestand bemerkt jede spätere Änderung, und die Kette der Freigaben ist geschlossen.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context import EXAMPLE, ROOT, SKILLS, load, wl  # noqa: E402

pl = load("work-transformation", "project_lock")
sp = load("work-transformation", "snapshot_project")
rp = load("work-transformation", "release_project")
S = SKILLS / "work-transformation" / "scripts"


def run(name, *args):
    return subprocess.run([sys.executable, str(S / name), *args], cwd=str(ROOT), capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wts-st-")
        self.proj = Path(self.tmp) / "p"
        shutil.copytree(EXAMPLE, self.proj)
        shutil.rmtree(self.proj / "expected", ignore_errors=True)
        self.tok = Path(self.tmp) / "tokens"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestLock(Base):
    def test_foreign_claim_blocks_and_own_token_passes(self):
        r = run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Anna", "--operation", "Scoring",
                "--token-file", str(self.tok / "a.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn(json.loads((self.tok / "a.json").read_text())["token"], r.stdout)
        self.assertEqual(oct((self.tok / "a.json").stat().st_mode)[-3:], "600")
        r = run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Ben", "--token-file", str(self.tok / "b.json"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("GEHALTEN", r.stdout)
        r = run("run_pipeline.py", "--project", str(self.proj), "--until", "builder")
        self.assertEqual(r.returncode, 3)
        self.assertIn("gepflegt von", r.stdout)
        r = run("run_pipeline.py", "--project", str(self.proj), "--until", "builder", "--token-file", str(self.tok / "a.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        r = run("project_lock.py", "release", "--project", str(self.proj), "--token-file", str(self.tok / "a.json"), "--remove-token-file")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.tok / "a.json").exists())
        self.assertEqual(pl.read_claims(self.proj), [])

    def test_token_file_inside_project_is_refused(self):
        r = run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Anna",
                "--token-file", str(self.proj / "t.json"))
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.proj / "t.json").exists())

    def test_expired_claim_needs_recorded_takeover(self):
        run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Anna", "--token-file", str(self.tok / "a.json"))
        claim = pl.claim_path(self.proj, "Anna")
        rec = wl.read_json(claim)
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        rec["heartbeat"] = pl.iso(old.replace(microsecond=0))
        wl.write_json(claim, rec)
        r = run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Ben", "--token-file", str(self.tok / "b.json"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("ABGELAUFEN", r.stdout)
        r = run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Ben", "--token-file", str(self.tok / "b.json"),
                "--take-over", "--reason", "Anna im Urlaub")
        self.assertEqual(r.returncode, 0, r.stdout)
        log = (self.proj / ".wts-lock" / "handovers.jsonl").read_text(encoding="utf-8")
        self.assertIn("Anna im Urlaub", log)
        self.assertIn('"kind": "take_over"', log)
        r = run("project_lock.py", "verify", "--project", str(self.proj), "--token-file", str(self.tok / "a.json"))
        self.assertEqual(r.returncode, 3)
        self.assertEqual(run("run_pipeline.py", "--project", str(self.proj), "--until", "builder").returncode, 3)


class TestSnapshot(Base):
    def test_round_trip_is_byte_identical(self):
        target, rec = sp.create(self.proj, "vor Review", "20260301-120000")
        self.assertEqual(target.name, "20260301-120000-vor-review")
        self.assertIn("project.json", rec["files"])
        self.assertFalse(any(f.startswith("40_output/") for f in rec["files"]))
        before = {rel: (self.proj / rel).read_bytes() for rel in rec["files"]}
        (self.proj / "30_review" / "overrides.csv").write_text("kaputt\n", encoding="utf-8")
        (self.proj / "00_input" / "levels.csv").unlink()
        (self.proj / "00_input" / "neu.csv").write_text("a;b\n", encoding="utf-8")
        r = run("restore_project.py", "--project", str(self.proj), "--snapshot", target.name, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("entfernen  00_input/neu.csv", r.stdout)
        self.assertEqual(sorted(wl.controlled_files(self.proj)) != sorted(rec["files"]), True)
        r = run("restore_project.py", "--project", str(self.proj), "--snapshot", target.name)
        self.assertEqual(r.returncode, 0, r.stdout)
        for rel, data in before.items():
            self.assertEqual((self.proj / rel).read_bytes(), data, rel)
        self.assertFalse((self.proj / "00_input" / "neu.csv").exists())
        self.assertEqual(len(sp.list_snapshots(self.proj)), 2)  # Sicherung vor dem Restore

    def test_damaged_snapshot_is_refused(self):
        target, _ = sp.create(self.proj, "", "20260301-120000")
        (target / "project.json").write_text("{}", encoding="utf-8")
        r = run("restore_project.py", "--project", str(self.proj), "--snapshot", target.name)
        self.assertEqual(r.returncode, 2)
        self.assertIn("beschädigt", r.stdout + r.stderr)


class TestRelease(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(run("run_pipeline.py", "--project", str(self.proj)).returncode, 0)

    def test_release_then_verify_detects_every_change(self):
        r = run("release_project.py", "--project", str(self.proj), "--version", "1.0.0", "--date", "2026-03-01", "--note", "erster Stand")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(wl.load_project_meta(self.proj)["release_version"], "1.0.0")
        r = run("verify_release.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stdout)
        v = int(wl.load_latest_graph(self.proj)["meta"]["version"])
        (self.proj / "40_output" / f"report_v{v:03d}.md").write_text("geändert", encoding="utf-8")
        (self.proj / "00_input" / "levels.csv").unlink()
        (self.proj / "10_extraction" / "extract_neu.json").write_text("{}", encoding="utf-8")
        r = run("verify_release.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"VERÄNDERT 40_output/report_v{v:03d}.md", r.stdout)
        self.assertIn("FEHLT     00_input/levels.csv", r.stdout)
        self.assertIn("NEU       10_extraction/extract_neu.json", r.stdout)

    def test_versions_must_increase_and_chain_is_linked(self):
        self.assertEqual(run("release_project.py", "--project", str(self.proj), "--version", "1.0.0").returncode, 0)
        self.assertEqual(run("release_project.py", "--project", str(self.proj), "--version", "0.9.0").returncode, 2)
        self.assertEqual(run("release_project.py", "--project", str(self.proj), "--version", "1.1.0").returncode, 0)
        log = rp.read_log(self.proj)
        self.assertEqual([e["version"] for e in log], ["1.0.0", "1.1.0"])
        self.assertEqual(log[1]["previous_manifest_sha256"], log[0]["manifest_sha256"])
        self.assertIsNone(log[0]["previous_manifest_sha256"])
        m = self.proj / "60_releases" / "1.0.0" / "manifest.json"
        data = wl.read_json(m)
        data["files"]["project.json"] = "0" * 64
        wl.write_json(m, data)
        r = run("verify_release.py", "--project", str(self.proj))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Kette", r.stdout)

    def test_no_release_while_someone_else_holds_the_project(self):
        run("project_lock.py", "acquire", "--project", str(self.proj), "--owner", "Anna", "--token-file", str(self.tok / "a.json"))
        r = run("release_project.py", "--project", str(self.proj), "--version", "1.0.0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Pflegeanspruch", r.stdout)

    def test_no_release_with_validator_errors(self):
        g = wl.read_json(self.proj / "20_graph" / "work-graph_latest.json")
        g["roles"][0]["cluster_id"] = "jc_gibtsnicht"
        wl.write_json(self.proj / "20_graph" / "work-graph_latest.json", g)
        r = run("release_project.py", "--project", str(self.proj), "--version", "1.0.0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Validator", r.stdout)


if __name__ == "__main__":
    unittest.main()
