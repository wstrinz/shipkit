#!/usr/bin/env python3
"""Tests for modules/familiar/scripts/familiar_drop.py (send, validate, archive).

The CLI runs as a subprocess with SHIP_ROOT pointed at a temp dir; the clock-dependent naming
is tested through the module API with a pinned `now`.

    python3 modules/familiar/tests/test_familiar_drop.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "familiar_drop.py"
CLASSIFY = HERE.parents[2] / "lib" / "classify_input.py"

GOOD = """---
kind: steer
---
# Objective
Ship the thing.

## Bounds
In scope: the thing. Prepare, do not fire: no merge.

## Success condition
A draft PR exists.

## Report
A note to inbox/familiar/.
"""

RELAYED = GOOD.replace("kind: steer", "kind: steer\nauthority: relayed-explicit\n"
                       "origin: chat:12345") + "\n## Authorized action\nMerge PR 7.\n"


def load(root):
    os.environ["SHIP_ROOT"] = str(root)
    try:
        spec = importlib.util.spec_from_file_location("familiar_drop_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.environ.pop("SHIP_ROOT", None)
    return mod


def cli(root, *args, tz=None):
    env = dict(os.environ, SHIP_ROOT=str(root))
    if tz:
        env["TZ"] = tz
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          env=env, cwd=str(root))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.drafts = self.root / "state" / "familiar" / "drafts"
        self.drafts.mkdir(parents=True)
        self.drops = self.root / "inbox" / "drops"

    def tearDown(self):
        self._tmp.cleanup()

    def draft(self, name, text):
        p = self.drafts / name
        p.write_text(text, encoding="utf-8")
        return p


class TestValidate(Base):
    def setUp(self):
        super().setUp()
        self.mod = load(self.root)

    def test_defaults_make_a_minimal_draft_valid(self):
        text = self.mod.with_defaults(GOOD)
        self.assertEqual(self.mod.validate(text), [])
        self.assertIn("authority: standing", text)
        self.assertIn("origin: familiar-initiative", text)
        self.assertIn("source: familiar", text)

    def test_relayed_explicit_valid(self):
        self.assertEqual(self.mod.validate(self.mod.with_defaults(RELAYED)), [])

    def test_relayed_explicit_needs_origin_and_action(self):
        text = GOOD.replace("kind: steer", "kind: steer\nauthority: relayed-explicit")
        problems = " ".join(self.mod.validate(self.mod.with_defaults(text)))
        self.assertIn("origin", problems)
        self.assertIn("Authorized action", problems)

    def test_bad_values_and_missing_sections(self):
        text = "---\nsource: familiar\nkind: dance\nauthority: absolute\norigin: x\n" \
               "priority: whenever\nwake_class: loud\n---\n# Objective\n"
        problems = " ".join(self.mod.validate(text))
        for needle in ("kind must be", "authority must be", "priority must be",
                       "wake_class must be", "## Bounds", "## Report"):
            self.assertIn(needle, problems)

    def test_duplicate_key_smuggle_refused(self):
        text = self.mod.with_defaults(GOOD).replace("kind: steer", "kind: steer\nkind: ask")
        self.assertIn("duplicate", " ".join(self.mod.validate(text)))

    def test_role_key_refused(self):
        text = self.mod.with_defaults(GOOD.replace("kind: steer", "kind: steer\nrole: captain"))
        self.assertIn("role", " ".join(self.mod.validate(text)))

    def test_wrong_source_refused(self):
        text = self.mod.with_defaults(GOOD.replace("kind: steer", "kind: steer\nsource: mate"))
        self.assertIn("source must be", " ".join(self.mod.validate(text)))

    def test_no_frontmatter(self):
        self.assertIn("no frontmatter", " ".join(self.mod.validate("# Objective\n")))

    def test_unparseable_line_is_not_silently_dropped_by_defaults(self):
        text = GOOD.replace("kind: steer", "kind: steer\nthis is not yaml")
        self.assertIn("unparseable", " ".join(self.mod.validate(self.mod.with_defaults(text))))

    def test_filename_rule(self):
        ok = self.mod.with_defaults(GOOD)
        self.assertEqual(self.mod.validate(ok, "familiar-20261112T201500Z-ship-it.md"), [])
        self.assertEqual(self.mod.validate(ok, "familiar-20261112T201500Z.md"), [])
        for bad in ("familiar-2026-11-12-ship.md", "steer.md", "familiar-20261112T201500Z-A.md",
                    "familiar-20261112T201500Z.md\n"):
            self.assertTrue(self.mod.validate(ok, bad), bad)

    def test_quoted_values_and_inline_comments(self):
        text = '---\nkind: "steer"\nsource: familiar  # who\nauthority: standing\n' \
               "origin: 'chat:1'\n---\n" + GOOD.split("---\n", 2)[2]
        self.assertEqual(self.mod.validate(text), [])


class TestSend(Base):
    def test_send_stamps_utc_name_and_removes_draft(self):
        mod = load(self.root)
        d = self.draft("Ship The Thing.md", GOOD)
        now = datetime(2026, 11, 12, 20, 15, 0, tzinfo=timezone.utc)
        out = mod.send(str(d), now=now)
        self.assertEqual(out.name, "familiar-20261112T201500Z-ship-the-thing.md")
        self.assertFalse(d.exists())
        self.assertEqual(mod.validate(out.read_text(), out.name), [])

    def test_send_never_overwrites(self):
        mod = load(self.root)
        now = datetime(2026, 11, 12, 20, 15, 0, tzinfo=timezone.utc)
        a = mod.send(str(self.draft("x.md", GOOD)), now=now)
        b = mod.send(str(self.draft("x.md", GOOD)), now=now)
        self.assertNotEqual(a, b)
        self.assertTrue(b.name.endswith("-x-2.md"))

    def test_failed_write_leaves_no_visible_drop(self):
        from unittest import mock
        mod = load(self.root)
        d = self.draft("x.md", GOOD)
        with mock.patch.object(mod.os, "fdopen", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                mod.send(str(d))
        self.assertEqual(list(self.drops.glob("*.md")), [])
        self.assertEqual([p.name for p in self.drops.iterdir() if p.is_file()], [])
        self.assertTrue(d.exists())

    def test_cli_send_uses_the_clock_in_utc(self):
        self.draft("plan.md", GOOD)
        before = datetime.now(timezone.utc).replace(microsecond=0)
        r = cli(self.root, "send", "state/familiar/drafts/plan.md", "--topic", "Night plan",
                tz="Pacific/Kiritimati")
        after = datetime.now(timezone.utc)
        self.assertEqual(r.returncode, 0, r.stderr)
        name = Path(r.stdout.strip()).name
        self.assertTrue(name.endswith("Z-night-plan.md"), name)
        stamp = datetime.strptime(name[9:25], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        self.assertTrue(before <= stamp <= after, (before, stamp, after))

    def test_cli_refuses_invalid_draft_and_keeps_it(self):
        d = self.draft("bad.md", "---\nkind: dance\n---\nno sections\n")
        r = cli(self.root, "send", str(d))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kind must be", r.stderr)
        self.assertTrue(d.exists())
        self.assertFalse(self.drops.exists() and any(self.drops.iterdir()))

    def test_cli_refuses_a_draft_outside_drafts(self):
        outside = self.root / "queue.md"
        outside.write_text(GOOD)
        r = cli(self.root, "send", str(outside))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("drafts must live under", r.stderr)
        self.assertTrue(outside.exists())

    def test_cli_refuses_a_symlinked_draft_pointing_outside(self):
        target = self.root / "projects" / "p" / "tickets" / "T.md"
        target.parent.mkdir(parents=True)
        target.write_text(GOOD)
        link = self.drafts / "link.md"
        link.symlink_to(target)
        r = cli(self.root, "send", str(link))
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(target.exists())

    def test_sent_drop_classifies_as_wake_when_module_enabled(self):
        self.draft("c.md", GOOD)
        r = cli(self.root, "send", "state/familiar/drafts/c.md")
        drop = Path(r.stdout.strip())
        manifest = self.root / "install.json"
        manifest.write_text('{"modules": ["core", "autonomous", "wake-monitor", "familiar"]}')
        env = dict(os.environ, SHIPKIT_INSTALL_MANIFEST=str(manifest))
        c = subprocess.run([sys.executable, str(CLASSIFY), str(drop)], capture_output=True,
                           text=True, env=env)
        self.assertEqual(c.stdout.strip(), "wake", c.stderr)
        self.assertNotIn("undeclared", c.stderr)


class TestValidateCli(Base):
    def test_validate_reports_problems_with_exit_1(self):
        p = self.root / "familiar-x.md"
        p.write_text("---\nsource: familiar\n---\n")
        r = cli(self.root, "validate", str(p))
        self.assertEqual(r.returncode, 1)
        self.assertIn("filename", r.stdout)

    def test_usage(self):
        self.assertEqual(cli(self.root, "explode", "x").returncode, 2)
        self.assertEqual(cli(self.root, "send", "a", "b").returncode, 2)


class TestArchive(Base):
    def setUp(self):
        super().setUp()
        self.mail = self.root / "inbox" / "familiar"
        self.mail.mkdir(parents=True)

    def test_archive_moves_into_read(self):
        (self.mail / "note.md").write_text("x")
        r = cli(self.root, "archive", "note.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.mail / "read" / "note.md").exists())
        self.assertFalse((self.mail / "note.md").exists())

    def test_archive_refuses_paths_and_missing_mail(self):
        for name in ("../../queue.md", "read/x.md", ".hidden.md", "note.txt", "absent.md"):
            r = cli(self.root, "archive", name)
            self.assertNotEqual(r.returncode, 0, name)

    def test_archive_refuses_symlinked_mail(self):
        (self.root / "queue.md").write_text("q")
        (self.mail / "q.md").symlink_to(self.root / "queue.md")
        self.assertNotEqual(cli(self.root, "archive", "q.md").returncode, 0)

    def test_archive_never_overwrites(self):
        (self.mail / "read").mkdir()
        (self.mail / "read" / "n.md").write_text("old")
        (self.mail / "n.md").write_text("new")
        self.assertNotEqual(cli(self.root, "archive", "n.md").returncode, 0)
        self.assertEqual((self.mail / "read" / "n.md").read_text(), "old")


if __name__ == "__main__":
    unittest.main(verbosity=1)
