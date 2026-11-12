#!/usr/bin/env python3
"""Test suite for queue_move.py: a live file and an archive file in a tempdir, never a real queue.

Usage: python3 modules/queue-split/tests/test_queue_move.py
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
MODULE_DIR = Path(__file__).resolve().parent.parent
SCRIPT = MODULE_DIR / "queue_move.py"
QUEUE_TEMPLATE = MODULE_DIR.parent.parent / "core" / "templates" / "queue.md"
ARCHIVE_TEMPLATE = MODULE_DIR / "templates" / "queue-archive.md"
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(MODULE_DIR.parent.parent / "lib"))
import queue_split as qs  # noqa: E402
from ship_data import STUB_MARKER  # noqa: E402

LIVE = """# Queue

## Awaiting Captain

1. [AC-ONE](projects/demo/tickets/AC-ONE.md) - **Action:** merge it
   continuation
2. [AC-TWO](projects/demo/tickets/AC-TWO.md) - second

## Ready

1. [RD-ONE](projects/demo/tickets/RD-ONE.md) - ready

## Done (recent)

- [OLD-LIVE](projects/demo/tickets/OLD-LIVE.md) - leftover
"""

ARCHIVE = """# Queue Archive

## Ready (parked)

## Backlog

1. [BL-ONE](projects/demo/tickets/BL-ONE.md) - later

## Shelved

## Done

- [OLD-ARCH](projects/demo/tickets/OLD-ARCH.md) - done
"""


def entries(text, section):
    s = qs.Doc(text).find(section)
    return [e.first() for e in s.entries] if s else []


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q, self.a = Path(self.tmp.name) / "live.md", Path(self.tmp.name) / "archive.md"
        self.q.write_text(LIVE)
        self.a.write_text(ARCHIVE)

    def tearDown(self):
        self.tmp.cleanup()

    def mv(self, *args, env=None):
        env = dict(env or os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(SCRIPT), "--queue", str(self.q), "--archive", str(self.a), *args],
                              capture_output=True, text=True, env=env)

    def ready(self):
        return self.q.read_text().split("## Ready\n")[1].split("## ")[0]


class Move(Env):
    def test_done_lands_at_the_top_of_the_live_done_recent(self):
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done", "--note", "merged 11-10")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.a.read_text(), ARCHIVE)
        done = self.q.read_text().split("## Done (recent)\n")[1]
        self.assertTrue(done.lstrip().startswith("1. [AC-ONE]"), done)
        self.assertIn("| merged 11-10\n   continuation", done)
        self.assertLess(done.index("AC-ONE"), done.index("OLD-LIVE"))
        self.assertNotIn("AC-ONE", self.q.read_text().split("## Done (recent)")[0])

    def test_done_recent_spelling_is_the_same_target(self):
        r = self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Done (recent)")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AC-TWO", entries(self.q.read_text(), "Done")[0])
        self.assertNotIn("AC-TWO", self.a.read_text())

    def test_done_goes_to_the_archive_only_when_the_live_file_has_no_done(self):
        self.q.write_text(LIVE.split("## Done (recent)")[0])
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AC-ONE", entries(self.a.read_text(), "Done")[0])

    def test_backlog_target_is_the_archive_and_a_move_out_of_the_archive_appends(self):
        self.assertEqual(self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Backlog").returncode, 0)
        backlog = self.a.read_text().split("## Backlog")[1].split("## Shelved")[0]
        self.assertLess(backlog.index("BL-ONE"), backlog.index("AC-TWO"))
        r = self.mv("--ticket", "BL-ONE", "--from", "Backlog", "--to", "Ready")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("BL-ONE", self.a.read_text())
        self.assertEqual(self.ready(), "\n1. [RD-ONE](projects/demo/tickets/RD-ONE.md) - ready\n"
                                       "1. [BL-ONE](projects/demo/tickets/BL-ONE.md) - later\n\n")

    def test_at_top_overrides_the_append_default(self):
        r = self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Ready", "--at", "top")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.ready().lstrip().startswith("2. [AC-TWO]"))

    def test_at_end_into_done_appends_instead_of_newest_first(self):
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done", "--at", "end")
        self.assertEqual(r.returncode, 0, r.stderr)
        done = self.q.read_text().split("## Done (recent)\n")[1]
        self.assertLess(done.index("OLD-LIVE"), done.index("AC-ONE"))

    def test_into_an_empty_section_keeps_blank_lines_around_the_entry(self):
        r = self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Shelved")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## Shelved\n\n2. [AC-TWO](projects/demo/tickets/AC-TWO.md) - second\n\n## Done", self.a.read_text())

    def test_from_done_finds_the_live_done_recent_heading(self):
        r = self.mv("--ticket", "OLD-LIVE", "--from", "Done", "--to", "Ready")
        self.assertEqual(r.returncode, 0, r.stderr)
        live = self.q.read_text()
        self.assertNotIn("OLD-LIVE", live.split("## Done (recent)")[1])
        self.assertIn("- [OLD-LIVE]", self.ready())

    def test_from_done_falls_back_to_the_archive(self):
        r = self.mv("--ticket", "OLD-ARCH", "--from", "Done", "--to", "Ready")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("OLD-ARCH", self.a.read_text())
        self.assertIn("- [OLD-ARCH]", self.ready())

    def test_to_done_without_an_archive_uses_the_live_done_recent(self):
        self.a.unlink()
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.a.exists())
        self.assertTrue(self.q.read_text().split("## Done (recent)\n")[1].lstrip().startswith("1. [AC-ONE]"))

    def test_file_modes_are_kept(self):
        os.chmod(self.q, 0o640)
        os.chmod(self.a, 0o664)
        self.assertEqual(self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Backlog").returncode, 0)
        self.assertEqual((os.stat(self.q).st_mode & 0o777, os.stat(self.a).st_mode & 0o777), (0o640, 0o664))

    def test_source_in_live_done_recent_is_found(self):
        r = self.mv("--ticket", "OLD-LIVE", "--from", "Done (recent)", "--to", "Backlog")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("OLD-LIVE", self.q.read_text())
        self.assertIn("OLD-LIVE", self.a.read_text())

    def test_live_to_live_move_leaves_the_archive_alone(self):
        r = self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Ready")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.a.read_text(), ARCHIVE)
        self.assertIn("2. [AC-TWO]", self.ready())

    def test_refuses_when_not_exactly_one_entry(self):
        self.assertNotEqual(self.mv("--ticket", "NOPE", "--from", "Awaiting Captain", "--to", "Done").returncode, 0)
        self.assertEqual(self.q.read_text(), LIVE)
        self.q.write_text(LIVE.replace("## Ready\n", "## Ready\n\n1. [AC-TWO](projects/demo/tickets/AC-TWO.md) - dup\n"))
        self.assertEqual(self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Ready").returncode, 0)
        before = (self.q.read_text(), self.a.read_text())
        r = self.mv("--ticket", "AC-TWO", "--from", "Ready", "--to", "Done")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSED", r.stderr)
        self.assertEqual(before, (self.q.read_text(), self.a.read_text()))

    def test_dry_run_writes_nothing(self):
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("first line: 1. [AC-ONE]", r.stdout)
        self.assertEqual((self.q.read_text(), self.a.read_text()), (LIVE, ARCHIVE))

    def test_unknown_target_section_refuses(self):
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Nowhere")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no section", r.stderr)

    def test_default_paths_resolve_under_ship_root(self):
        root = Path(self.tmp.name)
        (root / "queue.md").write_text(LIVE)
        (root / "queue-archive.md").write_text(ARCHIVE)
        env = dict(os.environ, SHIP_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, str(SCRIPT), "--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Backlog"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AC-ONE", (root / "queue-archive.md").read_text())

    def test_default_paths_follow_a_data_root_past_the_stubs(self):
        ship = Path(self.tmp.name) / "ship"
        data = ship / "ship-data"
        (data / "state").mkdir(parents=True)
        (ship / "state").symlink_to("ship-data/state")
        stub = STUB_MARKER + "\nMoved to the data root.\n"
        for name in ("queue.md", "queue-archive.md"):
            (ship / name).write_text(stub)
        (data / "queue.md").write_text(LIVE)
        (data / "queue-archive.md").write_text(ARCHIVE)
        env = dict(os.environ, SHIP_ROOT=str(ship), PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, str(SCRIPT), "--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Backlog"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AC-ONE", (data / "queue-archive.md").read_text())
        for name in ("queue.md", "queue-archive.md"):
            self.assertEqual((ship / name).read_text(), stub)


class Templates(Env):
    """The shipped templates open sections with multi-line HTML comments; nothing may land inside one."""

    def seed(self):
        live = QUEUE_TEMPLATE.read_text(encoding="utf-8").replace(
            "## Awaiting Captain\n", "## Awaiting Captain\n\n1. [AC-ONE](projects/demo/tickets/AC-ONE.md) - act\n", 1)
        self.q.write_text(live)
        self.a.write_text(ARCHIVE_TEMPLATE.read_text(encoding="utf-8"))

    def test_top_insert_skips_a_three_line_comment_in_the_live_done(self):
        self.seed()
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Done")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(entries(self.q.read_text(), "Done")), 1, self.q.read_text().split("## Done")[1])

    def test_top_insert_skips_a_three_line_comment_in_the_archive_shelved(self):
        self.seed()
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Shelved", "--at", "top")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(entries(self.a.read_text(), "Shelved")), 1, self.a.read_text().split("## Shelved")[1])


class Recognition(Env):
    """queue_move sees the same entries and sections queue_split does."""

    def test_star_plus_and_dotted_number_entries_are_found(self):
        for marker in ("*", "+", "1.2."):
            with self.subTest(marker=marker):
                self.q.write_text(LIVE.replace("2. [AC-TWO]", f"{marker} [AC-TWO]"))
                r = self.mv("--ticket", "AC-TWO", "--from", "Awaiting Captain", "--to", "Ready")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f"{marker} [AC-TWO]", self.ready())

    def test_a_heading_inside_a_comment_is_not_a_section(self):
        self.q.write_text(LIVE.replace("## Ready\n", "## Ready\n<!-- note\n## Fake\n-->\n"))
        r = self.mv("--ticket", "RD-ONE", "--from", "Ready", "--to", "Done")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.mv("--ticket", "AC-ONE", "--from", "Awaiting Captain", "--to", "Fake")
        self.assertNotEqual(r.returncode, 0)

    def test_an_entry_inside_a_comment_is_not_an_entry(self):
        self.q.write_text(LIVE.replace("## Ready\n", "## Ready\n<!--\n1. [AC-TWO](projects/demo/tickets/AC-TWO.md) - old\n-->\n"))
        r = self.mv("--ticket", "AC-TWO", "--from", "Ready", "--to", "Done")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSED: 0", r.stderr)


if __name__ == "__main__":
    unittest.main()
