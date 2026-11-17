#!/usr/bin/env python3
"""Tests for modules/familiar/scripts/familiar_orient.py.

The screen is built through the module API with a pinned clock and a temp ship root; one CLI
run checks --open-log end to end.

    python3 modules/familiar/tests/test_familiar_orient.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "familiar_orient.py"
NOW = datetime(2026, 11, 12, 20, 0, 0, tzinfo=timezone.utc)
TODAY = "2026-11-12"


def load():
    spec = importlib.util.spec_from_file_location("familiar_orient_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestOrient(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.mod = load()

    def tearDown(self):
        self._tmp.cleanup()

    def put(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def text(self):
        return "\n".join(self.mod.screen(self.root, NOW, TODAY))

    def test_empty_ship_names_every_absent_source(self):
        out = self.text()
        self.assertIn("mate-lock  absent", out)
        self.assertIn("status     absent", out)
        self.assertIn("no heartbeat log", out)
        self.assertIn("0 unread", out)
        self.assertIn("0 of yours", out)
        self.assertIn("mate log   none for 2026-11-12", out)
        self.assertIn("today not started; last = none", out)

    def test_deck_reads_lock_status_and_bosun(self):
        self.put("state/mate-lock.json", json.dumps(
            {"session_id": "abc123def456xyz", "heartbeat_at": "2026-11-12T19:30:00Z"}))
        self.put("state/status.json", json.dumps(
            {"tick": 41, "generated_at": "2026-11-12T19:55:00+00:00",
             "now": {"doing": "reviewing a crew log"}}))
        self.put("state/bosun-heartbeat.log",
                 "2026-11-12T13:00:00-06:00\tolder\n2026-11-12T13:50:00-06:00\tquiet tick\n")
        out = self.text()
        self.assertIn("held by abc123def456, heartbeat 30m ago", out)
        self.assertIn("written 5m ago, tick 41, doing: reviewing a crew log", out)
        self.assertIn("last beat 10m ago: quiet tick", out)

    def test_unreadable_state_is_said_not_skipped(self):
        self.put("state/status.json", "{not json")
        self.assertIn("status     unreadable", self.text())

    def test_mail_subjects_and_pending_commands(self):
        self.put("inbox/familiar/20261112T190000Z-result.md",
                 "---\ncommand: familiar-x.md\nstatus: done\nsummary: PR opened as draft\n---\n")
        self.put("inbox/familiar/20261112T180000Z-proposal.md", "# Reorder the backlog\n")
        self.put("inbox/familiar/read/old.md", "summary: archived\n")
        self.put("inbox/drops/familiar-20261112T174500Z-ship-it.md", "x")
        self.put("inbox/drops/processed/familiar-20261111T000000Z-old.md", "x")
        self.put("inbox/drops/bosun-20261112T190000Z.md", "x")
        out = self.text()
        self.assertIn("2 unread", out)
        self.assertIn("PR opened as draft", out)
        self.assertIn("Reorder the backlog", out)
        self.assertNotIn("archived", out)
        self.assertIn("1 of yours not yet processed", out)
        self.assertIn("2h15m ago  familiar-20261112T174500Z-ship-it.md", out)

    def test_note_to_tomorrow_comes_from_the_last_earlier_log(self):
        self.put("logs/familiar/2026-11-10.md", "## Note to tomorrow\nstale note\n")
        self.put("logs/familiar/2026-11-11.md",
                 "# Familiar log\n\n## Note to tomorrow\nRe-measure the weekly first.\n"
                 "Two commands in flight.\n\n## Afterword\nnot part of it\n")
        out = self.text()
        self.assertIn("last = 2026-11-11", out)
        self.assertIn("Re-measure the weekly first. Two commands in flight.", out)
        self.assertNotIn("stale note", out)
        self.assertNotIn("not part of it", out)

    def test_missing_note_is_flagged(self):
        self.put("logs/familiar/2026-11-11.md", "# Familiar log\nno close\n")
        self.assertIn("none in 2026-11-11 (the last close skipped it)", self.text())

    def test_mate_log_sections(self):
        self.put("logs/mate/2026-11-12.md", "# Session 1 — opened 08:00\n\n# Session 2 — opened 13:00\n")
        self.assertIn("2 section(s), last: Session 2 — opened 13:00", self.text())

    def test_open_log_creates_once(self):
        p = self.mod.open_log(self.root, TODAY, NOW)
        self.assertEqual(p.read_text(), "# Familiar log — 2026-11-12\n\n## Seat opened 20:00Z\n\n")
        p.write_text("kept")
        self.assertIsNone(self.mod.open_log(self.root, TODAY, NOW))
        self.assertEqual(p.read_text(), "kept")
        self.assertIn("today started", self.text())

    def test_cli_open_log(self):
        env = dict(os.environ, SHIP_ROOT=str(self.root))
        r = subprocess.run([sys.executable, str(SCRIPT), "--open-log"], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("familiar orient", r.stdout)
        self.assertEqual(len(list((self.root / "logs" / "familiar").glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
