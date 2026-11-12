#!/usr/bin/env python3
"""Test suite for queue_split.py: fixtures in a tempdir, pinned clock, never a real queue.

Usage: python3 modules/queue-split/tests/test_queue_split.py
"""
import io
import os
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(MODULE_DIR.parent.parent / "lib"))
import queue_split as qs  # noqa: E402
from ship_data import STUB_MARKER  # noqa: E402

TODAY = "2026-11-10"

QUEUE = """# Queue

> **Owned by First Mate.** Crew: read only.

## Active

- **Live one.** [A-ONE](projects/demo/tickets/A-ONE.md) multi-line
  - nested bullet
  - another | dispatched: 2026-11-09

<!-- a note about the next entry -->
1. [A-TWO](projects/demo/tickets/A-TWO.md) - second | since: 2026-11-01
   continuation line

## Ready

0a. [R-ONE](projects/demo/tickets/R-ONE.md) - stays | since: 2026-11-05
1. [R-TWO](projects/demo/tickets/R-TWO.md) - parked later
   | last: 2026-10-01

## Blocked

- [D-ONE](projects/demo/tickets/D-ONE.md) - waiting

## Awaiting Captain

1. [W-ONE](projects/demo/tickets/W-ONE.md) - **Action:** merge it

## In Review

1. [I-ONE](projects/demo/tickets/I-ONE.md) - ci

## Backlog

1. [B-ONE](projects/demo/tickets/B-ONE.md) - backlog one | filed: 2026-09-01
2. [B-TWO](projects/demo/tickets/B-TWO.md) - backlog two
   still two

## Shelved
<!-- answered, deliberately not built
     multi-line note with a "## " lookalike below
## not a heading -->
1. [S-ONE](projects/demo/tickets/S-ONE.md) - shelved | shelved: 2026-10-20

## Done (recent)

- done recent stamped [DN-RECENT](projects/demo/tickets/DN-RECENT.md) | done: 2026-11-09
- done old stamped [DN-OLD](projects/demo/tickets/DN-OLD.md) | done: 2026-10-01
  with a continuation

<!-- note before the mmdd entry -->
- [DN-MMDD](projects/demo/tickets/DN-MMDD.md) - 10-03: merged, no stamp
- [DN-MMDD-RECENT](projects/demo/tickets/DN-MMDD-RECENT.md) - 11-08: merged, no stamp
- [DN-NODATE](projects/demo/tickets/DN-NODATE.md) - merged at some point
- mixed stamps [DN-MIXED](projects/demo/tickets/DN-MIXED.md) | since: 2026-09-01 | done: 2026-11-07
"""


def lines(text):
    return Counter(l for l in text.splitlines() if l.strip())


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q = os.path.join(self.tmp.name, "live.md")
        self.a = os.path.join(self.tmp.name, "archive.md")
        Path(self.q).write_text(QUEUE)

    def tearDown(self):
        self.tmp.cleanup()

    def run_split(self, *extra, apply=False):
        argv = ["--queue", self.q, "--archive", self.a, "--today", TODAY, *extra] + (["--apply"] if apply else [])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = qs.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def sections(self, path):
        return {s.canon: s for s in qs.Doc(Path(path).read_text()).sections}


class DryRun(Env):
    def test_dry_run_writes_nothing_and_reports(self):
        rc, out, _ = self.run_split()
        self.assertEqual(rc, 0)
        self.assertEqual(Path(self.q).read_text(), QUEUE)
        self.assertFalse(os.path.exists(self.a))
        for needle in ("dry run", "Backlog", "Shelved", "Done", "nothing written", "(new)"):
            self.assertIn(needle, out)
        self.assertIn("UNDATED", out)

    def test_parse_serialize_round_trip(self):
        self.assertEqual(qs.Doc(QUEUE).text(), QUEUE)
        self.assertEqual(qs.Doc("no trailing newline\n- a\n- b").text(), "no trailing newline\n- a\n- b")


class Config(Env):
    def test_a_first_split_seeds_the_archive_from_the_shipped_template(self):
        template = (MODULE_DIR / "templates" / "queue-archive.md").read_text(encoding="utf-8")
        self.assertEqual([s.canon for s in qs.Doc(template).sections], qs.ARCHIVE_SECTIONS)
        self.run_split(apply=True)
        a = self.sections(self.a)
        self.assertIn("Entry needs ALL THREE", "".join(a["Shelved"].lines()))
        self.assertIn("S-ONE", "".join(a["Shelved"].lines()))

    def test_without_the_template_the_built_in_seed_is_used(self):
        with mock.patch.object(qs, "ARCHIVE_TEMPLATE", Path(self.tmp.name) / "missing.md"):
            rc, _, err = self.run_split(apply=True)
        self.assertEqual(rc, 0, err)
        self.assertTrue(Path(self.a).read_text().startswith(qs.ARCHIVE_NOTE))
        self.assertEqual(list(self.sections(self.a)), qs.ARCHIVE_SECTIONS)

    def test_a_section_that_received_entries_is_separated_from_the_next_heading(self):
        self.run_split("--park-ready", "R-TWO", apply=True)
        arch = Path(self.a).read_text()
        for name in qs.ARCHIVE_SECTIONS[1:]:
            self.assertIn(f"\n\n## {name}\n", arch)
        self.assertIn("- stays | since: 2026-11-05\n\n## Blocked\n", Path(self.q).read_text())

    def test_done_days_default_comes_from_the_environment(self):
        with mock.patch.dict(os.environ, {"SHIP_QUEUE_DONE_DAYS": "400"}):
            _, out, _ = self.run_split()
        self.assertIn("done-days 400", out)
        self.assertIn("Done (recent) -> Done: 1 entries", out)
        with mock.patch.dict(os.environ, {"SHIP_QUEUE_DONE_DAYS": "400"}):
            _, out, _ = self.run_split("--done-days", "0")
        self.assertIn("done-days 0", out)

    def test_unset_done_days_is_the_documented_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHIP_QUEUE_DONE_DAYS", None)
            _, out, _ = self.run_split()
        self.assertIn(f"done-days {qs.DEFAULT_DONE_DAYS}", out)

    def test_bad_done_days_is_a_usage_error(self):
        with mock.patch.dict(os.environ, {"SHIP_QUEUE_DONE_DAYS": "two weeks"}), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            qs.main(["--queue", self.q, "--archive", self.a])
        self.assertEqual(cm.exception.code, 2)
        rc, _, err = self.run_split("--done-days", "-1")
        self.assertEqual(rc, 2)
        self.assertIn(">= 0", err)

    def test_default_paths_resolve_under_ship_root(self):
        root = Path(self.tmp.name)
        (root / "queue.md").write_text(QUEUE)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"SHIP_ROOT": str(root)}), redirect_stdout(out):
            rc = qs.main(["--today", TODAY, "--apply"])
        self.assertEqual(rc, 0)
        self.assertTrue((root / "queue-archive.md").exists())
        self.assertIn("S-ONE", (root / "queue-archive.md").read_text())

    def test_default_paths_follow_a_data_root_past_the_stubs(self):
        ship, data = Path(self.tmp.name) / "ship", Path(self.tmp.name) / "ship" / "ship-data"
        (data / "state").mkdir(parents=True)
        (ship / "state").symlink_to("ship-data/state")
        stub = STUB_MARKER + "\nMoved to the data root.\n"
        for name in ("queue.md", "queue-archive.md"):
            (ship / name).write_text(stub)
        (data / "queue.md").write_text(QUEUE)
        with mock.patch.dict(os.environ, {"SHIP_ROOT": str(ship)}), redirect_stdout(io.StringIO()):
            rc = qs.main(["--today", TODAY, "--apply"])
        self.assertEqual(rc, 0)
        self.assertIn("S-ONE", (data / "queue-archive.md").read_text())
        self.assertNotIn("S-ONE", (data / "queue.md").read_text())
        for name in ("queue.md", "queue-archive.md"):
            self.assertEqual((ship / name).read_text(), stub)


class Apply(Env):
    def test_moves_wholesale_and_done_by_age(self):
        rc, out, err = self.run_split("--park-ready", "R-TWO", apply=True)
        self.assertEqual(rc, 0, err)
        q, a = self.sections(self.q), self.sections(self.a)
        self.assertEqual([s for s in q], ["Active", "Ready", "Blocked", "Awaiting Captain", "In Review", "Done"])
        self.assertEqual(list(a), ["Ready (parked)", "Backlog", "Shelved", "Done"])
        self.assertEqual(len(a["Backlog"].entries), 2)
        self.assertEqual(len(a["Shelved"].entries), 1)
        self.assertEqual(len(a["Ready (parked)"].entries), 1)
        self.assertEqual(len(q["Ready"].entries), 1)
        done_live = "".join(q["Done"].lines())
        for keep in ("DN-RECENT", "DN-MMDD-RECENT", "DN-MIXED"):
            self.assertIn(keep, done_live)
        done_arch = "".join(a["Done"].lines())
        for gone in ("DN-OLD", "DN-MMDD", "DN-NODATE"):
            self.assertIn(gone, done_arch)
            self.assertNotIn(gone + "]", done_live)

    def test_multiline_entries_and_comments_travel_intact(self):
        self.run_split("--park-ready", "R-TWO", apply=True)
        a = self.sections(self.a)
        b2 = [e for e in a["Backlog"].entries if "B-TWO" in e.first()][0]
        self.assertEqual("".join(b2.body), "2. [B-TWO](projects/demo/tickets/B-TWO.md) - backlog two\n   still two\n")
        old = [e for e in a["Done"].entries if "DN-OLD" in e.first()][0]
        self.assertIn("  with a continuation\n", old.body)
        mm = [e for e in a["Done"].entries if "DN-MMDD]" in e.first()][0]
        self.assertTrue(any("note before the mmdd entry" in l for l in mm.head))
        parked = a["Ready (parked)"].entries[0]
        self.assertEqual(parked.body[1], "   | last: 2026-10-01\n")

    def test_shelved_heading_note_moves_and_lookalike_heading_is_not_a_section(self):
        self.run_split(apply=True)
        arch = Path(self.a).read_text()
        self.assertIn("answered, deliberately not built", arch)
        self.assertIn("## not a heading -->", arch)
        self.assertEqual(list(self.sections(self.a)), ["Ready (parked)", "Backlog", "Shelved", "Done"])
        self.assertNotIn("deliberately not built", Path(self.q).read_text())

    def test_no_line_is_lost(self):
        self.run_split("--park-ready", "R-TWO", apply=True)
        before = lines(QUEUE)
        after = lines(Path(self.q).read_text()) + lines(Path(self.a).read_text())
        self.assertEqual(before - after, Counter())

    def test_archive_header_and_live_header_notes(self):
        self.run_split(apply=True)
        arch = Path(self.a).read_text()
        self.assertTrue(arch.startswith("# Queue Archive"))
        self.assertIn("Not read at boot", arch)
        self.assertIn("Owned by First Mate", Path(self.q).read_text())

    def test_idempotent_rerun_moves_nothing_new(self):
        self.run_split("--park-ready", "R-TWO", apply=True)
        q1, a1 = Path(self.q).read_text(), Path(self.a).read_text()
        rc, out, err = self.run_split("--park-ready", "R-TWO", apply=True)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(self.q).read_text(), q1)
        self.assertEqual(Path(self.a).read_text(), a1)
        self.assertIn("none", out)

    def test_appends_to_an_existing_archive(self):
        self.run_split(apply=True)
        live = Path(self.q).read_text()
        Path(self.q).write_text(
            live.replace("## In Review", "## Backlog\n\n- [B-NEW](projects/demo/tickets/B-NEW.md) - later\n\n## In Review")
        )
        a0 = Path(self.a).read_text()
        rc, _, err = self.run_split(apply=True)
        self.assertEqual(rc, 0, err)
        a = self.sections(self.a)
        self.assertEqual([e.first()[:12] for e in a["Backlog"].entries], ["1. [B-ONE](p", "2. [B-TWO](p", "- [B-NEW](pr"])
        self.assertEqual(lines(a0) - lines(Path(self.a).read_text()), Counter())

    def test_done_cutoff_boundary_and_done_days(self):
        rc, out, _ = self.run_split("--done-days", "0")
        self.assertIn("Done (recent) -> Done: 6 entries", out)
        rc, out, _ = self.run_split("--done-days", "400")
        self.assertIn("1 Done entries are UNDATED", out)

    def test_undated_done_entry_is_called_out(self):
        _, out, _ = self.run_split()
        self.assertIn("[undated]", out)
        self.assertIn("DN-NODATE", out)
        self.assertIn("[MM-DD 10-03 of 1 -> 2026-10-03]", out)
        self.assertIn("[stamp -> 2026-10-01]", out)

    def test_non_leading_mmdd_uses_the_newest_date_on_the_line(self):
        live = QUEUE.replace(
            "## Done (recent)\n",
            "## Done (recent)\n\n- [DN-MAXLIVE](projects/demo/tickets/DN-MAXLIVE.md) - draft since 06-22; merged 11-05\n"
            "- [DN-FUTURE](projects/demo/tickets/DN-FUTURE.md) - lanes 11-14 only\n",
        )
        Path(self.q).write_text(live)
        _, out, _ = self.run_split()
        self.assertNotIn("DN-MAXLIVE", out.split("Moves:")[1])
        self.assertIn("[MM-DD 11-14 of 1 -> 2025-11-14]", out)
        self.assertIn("DN-FUTURE", out.split("Moves:")[1])

    def test_duplicated_entry_is_caught_by_the_self_check(self):
        real_plan = qs.plan

        def dup(queue, archive, *a):
            res = real_plan(queue, archive, *a)
            sec = archive.find("Backlog")
            sec.entries.append(sec.entries[0])
            return res

        with mock.patch.object(qs, "plan", dup):
            rc, _, err = self.run_split(apply=True)
        self.assertEqual(rc, 2)
        self.assertIn("duplicated or added", err)
        self.assertEqual(Path(self.q).read_text(), QUEUE)
        self.assertFalse(os.path.exists(self.a))

    def test_post_write_mismatch_restores_the_originals(self):
        real_write, seen = qs.atomic_write, []

        def bad(path, text):
            real_write(path, text + ("stray line\n" if path == self.q and not seen else ""))
            if path == self.q:
                seen.append(path)

        with mock.patch.object(qs, "atomic_write", bad):
            rc, _, err = self.run_split(apply=True)
        self.assertEqual(rc, 3)
        self.assertIn("changed after write", err)
        self.assertEqual(Path(self.q).read_text(), QUEUE)
        self.assertFalse(os.path.exists(self.a))

    def test_column0_group_header_after_a_parked_entry_is_flagged(self):
        live = QUEUE.replace("   | last: 2026-10-01\n", "   | last: 2026-10-01\n**GROUP - header**\n")
        Path(self.q).write_text(live)
        _, out, _ = self.run_split("--park-ready", "R-TWO")
        self.assertIn("COL0=1", out)
        self.assertIn("1 with column-0 non-list lines", out)
        self.assertIn("lines", out.split("COL0=1")[0].splitlines()[-1])
        self.run_split("--park-ready", "R-TWO", apply=True)
        parked = self.sections(self.a)["Ready (parked)"].entries[0]
        self.assertIn("**GROUP - header**\n", parked.body)

    def test_every_moved_entry_reports_its_line_count(self):
        _, out, _ = self.run_split()
        self.assertIn("[stamp -> 2026-10-01] 3 lines", out)

    def test_file_modes_are_kept_and_a_new_archive_is_0644(self):
        os.chmod(self.q, 0o640)
        self.run_split(apply=True)
        self.assertEqual(os.stat(self.q).st_mode & 0o777, 0o640)
        self.assertEqual(os.stat(self.a).st_mode & 0o777, 0o644)

    def test_unicode_line_separators_do_not_split_an_entry(self):
        text = QUEUE.replace("backlog one", "backlog one\x0cmore")
        Path(self.q).write_text(text, encoding="utf-8", newline="")
        self.run_split(apply=True)
        b1 = [e for e in self.sections(self.a)["Backlog"].entries if "B-ONE" in e.first()][0]
        self.assertEqual(len(b1.body), 1)
        self.assertIn("backlog one\x0cmore", b1.body[0])

    def test_done_newest_first_across_runs(self):
        self.run_split(apply=True)
        live = Path(self.q).read_text()
        Path(self.q).write_text(live.replace("## Done (recent)\n", "## Done (recent)\n\n- done 09-20 [DN-LATER](projects/demo/tickets/DN-LATER.md)\n"))
        self.run_split(apply=True)
        done = self.sections(self.a)["Done"].entries
        self.assertIn("DN-LATER", done[0].first())

    def test_park_ready_unknown_id_refuses_and_writes_nothing(self):
        rc, _, err = self.run_split("--park-ready", "R-TWO,NOPE", apply=True)
        self.assertEqual(rc, 2)
        self.assertIn("NOPE", err)
        self.assertEqual(Path(self.q).read_text(), QUEUE)
        self.assertFalse(os.path.exists(self.a))

    def test_missing_queue_is_an_error(self):
        os.unlink(self.q)
        rc, _, err = self.run_split()
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)

    def test_no_trailing_newline_does_not_glue_entries(self):
        Path(self.q).write_text(QUEUE.rstrip("\n"))
        self.run_split(apply=True)
        for text in (Path(self.q).read_text(), Path(self.a).read_text()):
            self.assertTrue(all(len(l) < 200 for l in text.splitlines()))
        a = self.sections(self.a)
        self.assertTrue(all(e.lines()[-1].endswith("\n") for e in a["Done"].entries))


if __name__ == "__main__":
    unittest.main()
