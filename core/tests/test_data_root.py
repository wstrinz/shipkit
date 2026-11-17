#!/usr/bin/env python3
"""Data root (DATA.md): shipkit_init.py --data-root, lib/ship_data.py, and pull-upstream.sh's
refusal to write into the ship's data. Runs against scratch copies of the repo; stdlib only.

Usage: python3 core/tests/test_data_root.py"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lib"))

import shipkit_init  # noqa: E402
from ship_data import data_root  # noqa: E402

DIRS = ("inbox", "logs", "projects", "state", "docs")
FILES = ("captain.md", "queue.md", "queue-archive.md", "DECISIONS.local.md")


def copy_kit(dst):
    shutil.copytree(ROOT, dst, symlinks=True, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", "loop.config.json", "mate.local.md", "ship-data",
        "install.json", "status.json"))
    return dst


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = os.path.realpath(self._td.name)
        self.kit = copy_kit(os.path.join(self.td, "kit"))

    def tearDown(self):
        self._td.cleanup()

    def init(self, *argv):
        return subprocess.run(
            [sys.executable, os.path.join(self.kit, "shipkit_init.py"), "--defaults",
             "--agents-target", os.path.join(self.td, "agents"),
             "--skills-target", os.path.join(self.td, "skills"), *argv],
            capture_output=True, text=True, cwd=self.kit)

    def in_kit(self):
        return mock.patch.object(shipkit_init, "SHIPKIT_ROOT", Path(self.kit))

    def assert_untouched(self):
        for name in DIRS + FILES:
            self.assertFalse(os.path.islink(os.path.join(self.kit, name)), name)
        self.assertFalse(read(os.path.join(self.kit, "queue.md")).startswith(
            shipkit_init.STUB_MARKER))


class TestInitDataRoot(Base):
    def test_nested_links_dirs_and_stubs_files(self):
        queue_before = read(os.path.join(self.kit, "queue.md"))
        res = self.init("--data-root", "ship-data")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        data = os.path.join(self.kit, "ship-data")
        for name in DIRS:
            self.assertEqual(os.readlink(os.path.join(self.kit, name)), f"ship-data/{name}")
        for name in FILES:
            stub = os.path.join(self.kit, name)
            self.assertFalse(os.path.islink(stub), name)
            self.assertTrue(read(stub).startswith(shipkit_init.STUB_MARKER), name)
            self.assertIn(f"`ship-data/{name}`", read(stub))
        self.assertEqual(read(os.path.join(data, "queue.md")), queue_before)
        self.assertTrue(os.path.isfile(os.path.join(data, "inbox", "captain.md")))
        self.assertTrue(os.path.isfile(os.path.join(data, "state", "status.json")))
        self.assertTrue(os.path.isfile(os.path.join(data, "state", "install.json")))
        self.assertIn("state/status.json", read(os.path.join(data, ".gitignore")).splitlines())
        self.assertEqual(data_root(self.kit), Path(data))

        again = self.init("--data-root", "ship-data")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("queue.md: already set up", again.stdout)
        self.assertIn("logs: already set up", again.stdout)
        self.assertIn("data root: " + data, again.stdout)

    def test_outside_path_uses_absolute_targets(self):
        data = os.path.join(self.td, "elsewhere", "my-ship-data")
        res = self.init("--data-root", data)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(os.readlink(os.path.join(self.kit, "logs")), os.path.join(data, "logs"))
        self.assertTrue(os.path.isfile(os.path.join(data, "captain.md")))
        self.assertIn(f"`{os.path.join(data, 'captain.md')}`",
                      read(os.path.join(self.kit, "captain.md")))
        self.assertEqual(data_root(self.kit), Path(data))

    def test_fresh_clone_placeholders_give_way_to_existing_data(self):
        data = os.path.join(self.td, "data")
        write(os.path.join(data, "queue.md"), "my real queue\n")
        write(os.path.join(data, "logs", "p", "T-1", "log.md"), "a log\n")
        res = self.init("--data-root", data)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("drop kit placeholder + pointer stub queue.md", res.stdout)
        self.assertEqual(read(os.path.join(data, "queue.md")), "my real queue\n")
        self.assertEqual(os.listdir(os.path.join(self.kit, "logs")), ["p"])
        self.assertTrue(os.path.isfile(os.path.join(data, "captain.md")))

    def test_edited_or_committed_kit_data_conflicts(self):
        """Only byte-identical kit placeholders give way; real data on both sides never
        silently loses one copy."""
        data = os.path.join(self.td, "data")
        write(os.path.join(data, "queue.md"), "data-root queue\n")
        write(os.path.join(self.kit, "queue.md"), "the kit's real queue\n")
        write(os.path.join(data, "logs", "a.md"), "x\n")
        write(os.path.join(self.kit, "logs", "b.md"), "y\n")
        res = self.init("--data-root", data)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("queue.md exists in both", res.stderr)
        self.assertIn("logs exists in both", res.stderr)
        self.assert_untouched()
        self.assertFalse(os.path.exists(os.path.join(data, "captain.md")))

    def test_symlink_elsewhere_conflicts(self):
        other = os.path.join(self.td, "other-logs")
        os.makedirs(other)
        shutil.rmtree(os.path.join(self.kit, "logs"))
        os.symlink(other, os.path.join(self.kit, "logs"))
        res = self.init("--data-root", "ship-data")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("logs is already a symlink to " + other, res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.kit, "ship-data")))

    def test_dry_run_moves_nothing(self):
        res = self.init("--data-root", "ship-data", "--dry-run")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("would move + pointer stub queue.md -> ship-data/queue.md", res.stdout)
        self.assertIn("would move + link logs -> ship-data/logs", res.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.kit, "ship-data")))
        self.assert_untouched()

    def test_rejects_roots_that_overlap_the_kit(self):
        for bad in (".", "..", "core/data", "logs/data", "LOGS/x", "Queue.md/x", ".claude/data"):
            res = self.init("--data-root", bad, "--dry-run")
            self.assertNotEqual(res.returncode, 0, bad)
            self.assertIn("--data-root", res.stderr, bad)
        self.assert_untouched()

    def test_rejects_a_case_variant_of_the_kit(self):
        variant = os.path.join(self.td, "KIT")
        if not os.path.exists(variant):
            self.skipTest("case-sensitive filesystem")
        res = self.init("--data-root", variant, "--dry-run")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("is the ship dir or contains it", res.stderr)
        res = self.init("--data-root", os.path.join(variant, "LOGS", "x"), "--dry-run")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("is inside LOGS/", res.stderr)

    def test_failure_mid_way_reports_and_resumes(self):
        real_symlink = os.symlink

        def flaky(src, dst, *a, **kw):
            if os.path.basename(dst) == "projects":
                raise OSError("simulated")
            return real_symlink(src, dst, *a, **kw)

        data = os.path.join(self.td, "data")
        with self.in_kit():
            with mock.patch.object(shipkit_init.os, "symlink", flaky), \
                    self.assertRaises(SystemExit), redirect_stderr(io.StringIO()) as err:
                shipkit_init.link_data_root(data, dry_run=False)
            self.assertIn("failed on projects", err.getvalue())
            self.assertIn("re-run the same command to resume", err.getvalue())
            lines = shipkit_init.link_data_root(data, dry_run=False)
        self.assertIn("logs: already set up", lines)
        self.assertIn(f"link projects -> {os.path.join(data, 'projects')}", lines)
        for name in DIRS:
            self.assertTrue(os.path.islink(os.path.join(self.kit, name)), name)
        self.assertTrue(os.path.isfile(os.path.join(data, "projects", ".gitkeep")))

    def test_links_and_stubs_go_to_the_kit_clone_exclude_file(self):
        exclude = os.path.join(self.td, "git-info-exclude")
        write(exclude, "/already-there\n")
        fake = subprocess.CompletedProcess([], 0, stdout=exclude + "\n", stderr="")
        with self.in_kit(), mock.patch.object(shipkit_init.subprocess, "run", return_value=fake):
            lines = shipkit_init._exclude_from_kit_git("private", dry_run=False)
            again = shipkit_init._exclude_from_kit_git("private", dry_run=False)
        rules = read(exclude).splitlines()
        for want in ("/logs", "/state", "/queue-archive.md", "/DECISIONS.local.md", "/private/"):
            self.assertIn(want, rules)
        self.assertNotIn("/queue.md", rules)
        self.assertTrue(lines)
        self.assertEqual(again, [])

    def test_no_data_root_leaves_layout_unchanged(self):
        res = self.init()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assert_untouched()
        self.assertNotIn("data root", res.stdout)
        self.assertEqual(data_root(self.kit), Path(self.kit))

    def test_placeholder_hashes_match_the_kit(self):
        for rel, sha in shipkit_init.KIT_PLACEHOLDERS.items():
            with open(os.path.join(ROOT, rel), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), sha, rel)

    def test_rotation_prep_reads_the_queue_from_the_data_root(self):
        self.assertEqual(self.init("--data-root", "ship-data").returncode, 0)
        write(os.path.join(self.kit, "ship-data", "queue.md"), "## Active\n- live item\n")
        spec = importlib.util.spec_from_file_location(
            "rotation_prep", os.path.join(self.kit, "modules", "autonomous", "scripts",
                                          "rotation_prep.py"))
        rp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rp)
        active, _, _ = rp.gather_queue(Path(self.kit))
        self.assertEqual(active, ["- live item"])


class TestShipDataRoot(unittest.TestCase):
    """data_root() trusts a state/ link only with evidence it is a data root."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(os.path.realpath(self._td.name))
        self.ship, self.data = self.td / "ship", self.td / "data"
        (self.ship).mkdir()
        (self.data / "state").mkdir(parents=True)
        (self.ship / "queue.md").write_text("a real in-repo queue\n")

    def tearDown(self):
        self._td.cleanup()

    def test_state_link_alone_is_not_a_data_root(self):
        (self.ship / "state").symlink_to(self.data / "state")
        self.assertEqual(data_root(self.ship), self.ship)

    def test_dangling_state_link_is_not_a_data_root(self):
        (self.ship / "state").symlink_to(self.td / "gone" / "state")
        self.assertEqual(data_root(self.ship), self.ship)

    def test_queue_beside_the_link_target_makes_it_one(self):
        (self.ship / "state").symlink_to(self.data / "state")
        (self.data / "queue.md").write_text("q\n")
        self.assertEqual(data_root(self.ship), self.data)

    def test_ship_root_stub_makes_it_one(self):
        (self.ship / "state").symlink_to(self.td / "gone" / "state")
        (self.ship / "queue.md").write_text(shipkit_init.STUB_MARKER + "\n")
        self.assertEqual(data_root(self.ship), self.td / "gone")

    def test_no_link_is_the_ship(self):
        (self.data / "queue.md").write_text("q\n")
        self.assertEqual(data_root(self.ship), self.ship)


class TestPullUpstreamGuard(Base):
    def setUp(self):
        super().setUp()
        self.upstream = copy_kit(os.path.join(self.td, "upstream"))
        write(os.path.join(self.upstream, "README.md"), "changed upstream\n")

    def pull(self, *argv):
        return subprocess.run(
            ["bash", os.path.join(self.kit, "scripts", "pull-upstream.sh"), *argv, self.upstream],
            capture_output=True, text=True)

    def declare_upstream_template(self, relpath):
        """Make upstream's core/module.json ship a template at a ship-root-relative path."""
        manifest = os.path.join(self.upstream, "core", "module.json")
        meta = json.loads(read(manifest))
        meta["templates"].append(os.path.join("..", relpath))
        write(manifest, json.dumps(meta))
        write(os.path.join(self.upstream, relpath), "upstream content\n")

    def assert_refused_before_copying(self, res, relpath):
        self.assertNotEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("refusing to sync", res.stderr)
        self.assertIn(relpath, res.stderr)
        self.assertNotEqual(read(os.path.join(self.kit, "README.md")), "changed upstream\n")

    def test_clean_sync_applies(self):
        res = self.pull("--apply")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(read(os.path.join(self.kit, "README.md")), "changed upstream\n")

    def test_refuses_a_data_entry_in_repo_ship(self):
        self.declare_upstream_template("state/evil.json")
        res = self.pull("--apply")
        self.assert_refused_before_copying(res, "state/evil.json")
        self.assertFalse(os.path.exists(os.path.join(self.kit, "state", "evil.json")))

    def test_refuses_case_variants_of_data_entries(self):
        self.declare_upstream_template("Docs/x.md")
        self.declare_upstream_template("Queue.md")
        res = self.pull("--apply")
        self.assert_refused_before_copying(res, "Docs/x.md")
        self.assertIn("Queue.md", res.stderr)

    def test_dry_run_refuses_too(self):
        self.declare_upstream_template("queue.md")
        self.assert_refused_before_copying(self.pull(), "queue.md")

    def test_refuses_any_path_into_a_linked_data_root(self):
        self.assertEqual(self.init("--data-root", "ship-data").returncode, 0)
        queue = read(os.path.join(self.kit, "ship-data", "queue.md"))
        self.declare_upstream_template("ship-data/README.md")
        res = self.pull("--apply")
        self.assert_refused_before_copying(res, "ship-data/README.md")
        self.assertFalse(os.path.exists(os.path.join(self.kit, "ship-data", "README.md")))
        self.assertEqual(read(os.path.join(self.kit, "ship-data", "queue.md")), queue)

    def test_sync_with_data_root_leaves_data_alone(self):
        self.assertEqual(self.init("--data-root", "ship-data").returncode, 0)
        write(os.path.join(self.kit, "ship-data", "queue.md"), "live queue\n")
        res = self.pull("--apply")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(read(os.path.join(self.kit, "README.md")), "changed upstream\n")
        self.assertTrue(os.path.islink(os.path.join(self.kit, "logs")))
        self.assertEqual(read(os.path.join(self.kit, "ship-data", "queue.md")), "live queue\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
