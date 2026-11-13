#!/usr/bin/env python3
"""Tests for modules/console/console_state.py: fixture ships in a tempdir, a pinned clock, every document checked
against console.schema.json.

    python3 modules/console/tests/test_console_state.py
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
MODULE_DIR = Path(__file__).resolve().parent.parent
SCRIPT = MODULE_DIR / "console_state.py"
NOW = datetime(2026, 11, 12, 20, 0, 0, tzinfo=timezone.utc)
STAMP = NOW.timestamp()

QUEUE = """# Queue

## Ready
<!-- Format: 1. [x](path) - not an entry
- [IN-COMMENT](projects/demo/tickets/IN-COMMENT.md) - inside a comment, not counted
-->
1. [RD-ONE](projects/demo/tickets/RD-ONE.md) - first
   continuation line, not an entry
2. [RD-TWO](projects/demo/tickets/RD-TWO.md) - second

## Active
1. [AC-ONE](projects/demo/tickets/AC-ONE.md) - crew on it

## Awaiting Captain
1. [AW-ONE](projects/demo/tickets/AW-ONE.md) - **Action:** merge the draft PR
```
1. fenced, not an entry
```

## Done (recent)
- [DN-ONE](projects/demo/tickets/DN-ONE.md) - shipped | done: 2026-11-10
"""


def load():
    spec = importlib.util.spec_from_file_location("console_state_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CS = load()
SCHEMA = json.loads((MODULE_DIR / "console.schema.json").read_text(encoding="utf-8"))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "ship"
        self.root.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def put(self, rel, text, age_s=0, base=None):
        p = (base or self.root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf-8")
        os.utime(p, (STAMP - age_s, STAMP - age_s))
        return p

    def build(self, **kw):
        doc = CS.build(self.root, NOW, **kw)
        self.assertEqual(CS.validate(doc, SCHEMA), [])
        return doc

    def val(self, doc, *path):
        node = doc
        for k in path:
            node = node[k]
        return node["value"]


class TestEmptyShip(Base):
    def test_every_section_present_and_nothing_green(self):
        doc = self.build()
        self.assertEqual(doc["schema"], "shipkit-console/1")
        self.assertEqual(doc["generated_at"], "2026-11-12T20:00:00Z")
        for seat in ("mate", "bosun"):
            self.assertEqual(doc["seats"][seat]["verdict"]["value"], "unknown", seat)
            self.assertIn("state/ absent", doc["seats"][seat]["verdict"]["by"])
        self.assertEqual(doc["crew"]["claims"]["count"]["confidence"], "unknown")
        self.assertEqual(doc["queue"]["claims"]["counts"]["confidence"], "unknown")
        self.assertIn("queue.md absent", doc["queue"]["claims"]["counts"]["resolved_by"])
        states = {s["name"]: s["state"] for s in doc["sources"]}
        for name in ("status", "install", "mate-lock", "bosun-heartbeat", "queue", "captain-inbox", "drops",
                     "drops-processed", "inbox", "tickets"):
            self.assertEqual(states[name], "absent", name)

    def test_a_missing_directory_is_unknown_not_zero(self):
        doc = self.build()
        for section, field, why in (("tickets", "total", "projects/ absent"),
                                    ("tickets", "by_status", "projects/ absent"),
                                    ("mail", "boxes", "inbox/ absent"),
                                    ("drops", "pending", "inbox/drops/ absent"),
                                    ("drops", "ledger", "inbox/drops/ absent"),
                                    ("drops", "processed", "inbox/drops/processed/ absent")):
            c = doc[section]["claims"][field]
            self.assertEqual((c["value"], c["confidence"]), (None, "unknown"), field)
            self.assertIn(why, c["resolved_by"])

    def test_present_but_empty_directories_are_zero(self):
        for d in ("state", "projects", "inbox/drops/processed"):
            (self.root / d).mkdir(parents=True)
        doc = self.build()
        for seat in ("mate", "bosun"):
            self.assertEqual(doc["seats"][seat]["verdict"]["value"], "absent", seat)
        self.assertEqual(self.val(doc, "tickets", "claims", "total"), 0)
        self.assertEqual(self.val(doc, "drops", "claims", "pending"), 0)
        self.assertEqual(self.val(doc, "drops", "claims", "processed"), 0)
        self.assertEqual(self.val(doc, "mail", "claims", "boxes"), {})

    def test_unreadable_inbox_is_unknown(self):
        (self.root / "inbox" / "drops").mkdir(parents=True)
        os.chmod(self.root / "inbox", 0)
        try:
            doc = self.build()
        finally:
            os.chmod(self.root / "inbox", 0o755)
        c = doc["mail"]["claims"]["boxes"]
        self.assertEqual(c["confidence"], "unknown")
        self.assertIn("unreadable", c["resolved_by"])
        self.assertEqual(doc["drops"]["claims"]["pending"]["confidence"], "unknown")

    def test_unreadable_tickets_dir_is_unknown(self):
        self.put("projects/a/tickets/A-1.md", "**Status:** ready\n")
        self.put("projects/b/tickets/B-1.md", "**Status:** ready\n")
        os.chmod(self.root / "projects" / "b" / "tickets", 0)
        try:
            doc = self.build()
        finally:
            os.chmod(self.root / "projects" / "b" / "tickets", 0o755)
        for field in ("total", "by_status"):
            c = doc["tickets"]["claims"][field]
            self.assertEqual((c["value"], c["confidence"]), (None, "unknown"), field)
            self.assertIn("projects/b/tickets/ unreadable", c["resolved_by"])
        states = {s["path"]: s["state"] for s in doc["sources"]}
        self.assertEqual(states["projects/b/tickets"], "unreadable")

    def test_extreme_offset_stamp_is_unknown(self):
        self.put("state/mate-lock.json", {"session_id": "s", "heartbeat_at": "0001-01-01T00:00:00+05:00"})
        self.put("state/status.json", {"tick": 1, "generated_at": "0001-01-01T00:00:00+05:00"})
        doc = self.build()
        self.assertEqual(doc["seats"]["mate"]["verdict"]["value"], "unknown")
        self.assertEqual(doc["seats"]["mate"]["claims"]["heartbeat_at"]["confidence"], "unknown")
        self.assertEqual(doc["status"]["claims"]["written_at"]["confidence"], "unknown")


class TestFixtureShip(Base):
    def setUp(self):
        super().setUp()
        self.put("state/install.json", {"schema": 1, "preset": "autonomous", "modules": ["core", "console"],
                                        "updated_at": "2026-11-01T00:00:00Z"})
        self.put("state/mate-lock.json", {"session_id": "bg-mate-1", "acquired_at": "2026-11-12T18:00:00Z",
                                          "heartbeat_at": "2026-11-12T19:50:00Z"})
        self.put("state/status.json", {
            "tick": 41, "wake_reason": "drop", "validator": "CLEAN", "next_wake": "14:30 CST (fallback)",
            "generated_at": "2026-11-12T19:55:00+00:00",
            "now": {"doing": "reviewing a crew log", "since": "2026-11-12T19:40:00Z", "wake": "drop"},
            "crew": [{"name": "crew:RD-ONE", "ticket": "RD-ONE", "task": "build it",
                      "dispatched": "2026-11-12T19:00:00Z"}, "not-a-dict"]})
        self.put("state/bosun-heartbeat.log",
                 "2026-11-12T13:00:00-06:00\tolder\n2026-11-12T13:50:00-06:00\tquiet tick\n")
        self.put("state/bosun-last-sweep.json", {"pace_secs": 900, "_updated": "2026-11-12T19:45:00Z"})
        self.put("queue.md", QUEUE, age_s=120)
        self.put("projects/demo/tickets/RD-ONE.md", "# RD-ONE: x\n\n**Status:** ready\n")
        self.put("projects/demo/tickets/AC-ONE.md", "---\nstatus: active\n---\n# AC-ONE\n")
        self.put("projects/demo/tickets/NO-STATUS.md", "# nothing\n")
        self.put("inbox/captain.md", "# Captain's Inbox\n\n> Append here.\n\n---\nship the thing\n"
                 "<!-- a note -->\nand this\n")
        self.put("inbox/familiar/b.md", "x", age_s=60)
        self.put("inbox/familiar/a.md", "x", age_s=600)
        self.put("inbox/familiar/read/old.md", "x")
        self.put("inbox/navigator/.hidden.md", "x")
        self.put("inbox/drops/bosun-20261112T190000Z.md",
                 "---\nshipkit_input: v1\nsource: bosun\nwake_class: wake\n---\n# x\n", age_s=3600)
        self.put("inbox/drops/familiar-20261112T195000Z-go.md",
                 "---\nsource: familiar\nauthority: standing\n---\n", age_s=600)
        self.put("inbox/drops/ui-steer.json", {"source": "ui", "wake_class": "batch"}, age_s=30)
        self.put("inbox/drops/notes.txt", "ignored")
        self.put("inbox/drops/processed/old.md", "x")
        self.doc = self.build()

    def test_seats(self):
        mate, bosun = self.doc["seats"]["mate"], self.doc["seats"]["bosun"]
        self.assertEqual(mate["verdict"]["value"], "fresh")
        self.assertIn("600s old; the threshold is 2700s", mate["verdict"]["by"])
        self.assertEqual(self.val(mate, "claims", "lock_holder"), "bg-mate-1")
        self.assertEqual(self.val(mate, "claims", "heartbeat_age_s"), 600)
        self.assertEqual(bosun["verdict"]["value"], "fresh")
        self.assertEqual(self.val(bosun, "claims", "last_beat_at"), "2026-11-12T19:50:00Z")
        self.assertEqual(self.val(bosun, "claims", "last_note"), "quiet tick")
        self.assertEqual(self.val(bosun, "claims", "last_sweep_at"), "2026-11-12T19:45:00Z")

    def test_status_and_crew(self):
        c = self.doc["status"]["claims"]
        self.assertEqual((c["doing"]["value"], c["tick"]["value"], c["validator"]["value"]),
                         ("reviewing a crew log", 41, "CLEAN"))
        self.assertEqual(c["written_at"]["value"], "2026-11-12T19:55:00Z")
        self.assertEqual(c["doing"]["observed_at"], "2026-11-12T19:55:00Z")
        self.assertEqual(self.val(self.doc, "crew", "claims", "count"), 1)
        self.assertEqual(self.val(self.doc, "crew", "claims", "active")[0]["ticket"], "RD-ONE")

    def test_queue_counts_skip_comments_fences_and_continuations(self):
        self.assertEqual(self.val(self.doc, "queue", "claims", "counts"),
                         {"Ready": 2, "Active": 1, "Awaiting Captain": 1, "Done": 1})
        self.assertEqual(self.val(self.doc, "queue", "claims", "awaiting_captain"),
                         ["[AW-ONE](projects/demo/tickets/AW-ONE.md) - **Action:** merge the draft PR"])
        self.assertEqual(self.doc["queue"]["claims"]["counts"]["observed_at"], "2026-11-12T19:58:00Z")

    def test_tickets_mail_and_drops(self):
        self.assertEqual(self.val(self.doc, "tickets", "claims", "total"), 3)
        self.assertEqual(self.val(self.doc, "tickets", "claims", "by_status"),
                         {"ready": 1, "active": 1, "unset": 1})
        self.assertEqual(self.val(self.doc, "mail", "claims", "boxes"), {
            "familiar": {"unread": 2, "newest": "b.md", "oldest_unread_at": "2026-11-12T19:50:00Z"},
            "navigator": {"unread": 0, "newest": None, "oldest_unread_at": None}})
        self.assertEqual(self.val(self.doc, "mail", "claims", "captain_inbox_lines"), 2)
        d = self.doc["drops"]["claims"]
        self.assertEqual((d["pending"]["value"], d["processed"]["value"]), (3, 1))
        self.assertEqual(d["oldest_pending_at"]["value"], "2026-11-12T19:00:00Z")
        self.assertEqual([e["name"] for e in d["ledger"]["value"]],
                         ["ui-steer.json", "familiar-20261112T195000Z-go.md", "bosun-20261112T190000Z.md"])
        self.assertEqual(d["ledger"]["value"][0]["wake_class"], "batch")
        self.assertEqual(d["ledger"]["value"][1]["authority"], "standing")
        self.assertEqual(d["ledger"]["value"][2]["source"], "bosun")

    def test_install_and_no_absolute_paths(self):
        self.assertEqual(self.val(self.doc, "install", "claims", "modules"), ["core", "console"])
        text = json.dumps(self.doc)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn(os.path.realpath(self.root), text)


class TestVerdicts(Base):
    def lock(self, hb):
        self.put("state/mate-lock.json", {"session_id": "s", "heartbeat_at": hb})
        return self.build()["seats"]["mate"]["verdict"]

    def test_stale_lock(self):
        v = self.lock("2026-11-12T19:00:00Z")
        self.assertEqual(v["value"], "stale")
        self.assertIn("3600s old; the threshold is 2700s", v["by"])

    def test_threshold_comes_from_mate_locks_env_var(self):
        os.environ["STALE_MINUTES"] = "90"
        try:
            self.assertEqual(self.lock("2026-11-12T19:00:00Z")["value"], "fresh")
        finally:
            del os.environ["STALE_MINUTES"]

    def test_boundaries_match_each_consumer(self):
        self.assertEqual(self.lock("2026-11-12T19:15:00Z")["value"], "fresh")
        self.put("state/bosun-heartbeat.log", "2026-11-12T19:15:00Z\tbeat\n", age_s=2700)
        self.assertEqual(self.build()["seats"]["bosun"]["verdict"]["value"], "stale")
        self.put("state/bosun-heartbeat.log", "2026-11-12T19:15:00Z\tbeat\n", age_s=2699)
        self.assertEqual(self.build()["seats"]["bosun"]["verdict"]["value"], "fresh")

    def test_lock_falls_back_to_acquired_at_like_mate_lock(self):
        self.put("state/mate-lock.json", {"session_id": "s", "acquired_at": "2026-11-12T19:59:00Z"})
        v = self.build()["seats"]["mate"]["verdict"]
        self.assertEqual(v["value"], "fresh")
        self.assertIn("acquired_at", v["by"])

    def test_unknown_never_reads_fresh(self):
        for bad, why in (("2026-11-12T21:00:00Z", "in the future"), ("garbage", "unparseable"),
                         (None, "unparseable")):
            v = self.lock(bad)
            self.assertEqual(v["value"], "unknown", bad)
            self.assertIn(why, v["by"])
        self.lock("2026-11-12T21:00:00Z")
        age = self.build()["seats"]["mate"]["claims"]["heartbeat_age_s"]
        self.assertEqual((age["value"], age["confidence"]), (None, "unknown"))
        self.put("state/mate-lock.json", "{not json")
        doc = self.build()
        self.assertEqual(doc["seats"]["mate"]["verdict"]["value"], "unknown")
        self.assertEqual(doc["seats"]["mate"]["claims"]["lock_holder"]["confidence"], "unknown")
        self.put("state/mate-lock.json", "[1, 2]")
        self.assertEqual(self.build()["seats"]["mate"]["verdict"]["value"], "unknown")

    def test_bosun_pace_widens_threshold(self):
        self.put("state/bosun-heartbeat.log", "2026-11-12T19:10:00Z\tbeat\n", age_s=3000)
        self.assertEqual(self.build()["seats"]["bosun"]["verdict"]["value"], "stale")
        self.put("state/bosun-last-sweep.json", {"pace_secs": 1800})
        doc = self.build()
        self.assertEqual(doc["seats"]["bosun"]["verdict"]["value"], "fresh")
        self.assertEqual(self.val(doc, "seats", "bosun", "claims", "stale_after_s"), 3600)

    def test_bosun_age_is_the_logs_mtime_like_launch_bosun(self):
        self.put("state/bosun-heartbeat.log", "2026-11-12T10:00:00Z\told stamp, fresh write\n", age_s=60)
        doc = self.build()
        self.assertEqual(doc["seats"]["bosun"]["verdict"]["value"], "fresh")
        self.assertEqual(self.val(doc, "seats", "bosun", "claims", "heartbeat_age_s"), 60)
        self.assertEqual(self.val(doc, "seats", "bosun", "claims", "last_beat_at"), "2026-11-12T10:00:00Z")

    def test_empty_heartbeat_is_unknown_and_unstamped_line_has_no_beat_time(self):
        self.put("state/bosun-heartbeat.log", "\n\n")
        self.assertEqual(self.build()["seats"]["bosun"]["verdict"]["value"], "unknown")
        self.put("state/bosun-heartbeat.log", "no tab, no stamp\n")
        beat = self.build()["seats"]["bosun"]["claims"]["last_beat_at"]
        self.assertEqual((beat["value"], beat["confidence"]), (None, "unknown"))

    def test_missing_preset_is_unknown(self):
        self.put("state/install.json", {"modules": ["core"]})
        c = self.build()["install"]["claims"]["preset"]
        self.assertEqual((c["value"], c["confidence"]), (None, "unknown"))

    def test_status_without_crew_is_unknown_not_zero(self):
        self.put("state/status.json", {"tick": 0, "generated_at": "2026-11-12T19:00:00Z"})
        doc = self.build()
        self.assertEqual(doc["crew"]["claims"]["count"]["value"], None)
        self.assertIn("no crew[]", doc["crew"]["claims"]["count"]["resolved_by"])
        self.assertEqual(doc["status"]["claims"]["tick"]["value"], 0)
        self.assertEqual(doc["status"]["claims"]["doing"]["confidence"], "unknown")


class TestDataRoot(Base):
    def test_queue_resolves_through_the_data_root(self):
        data = Path(self._tmp.name) / "data"
        (data / "state").mkdir(parents=True)
        self.put("queue.md", "## Ready\n1. [X](projects/d/tickets/X.md) - x\n", base=data)
        (self.root / "state").symlink_to(data / "state")
        self.put("queue.md", CS.STUB_MARKER + "\nmoved to the data root\n")
        self.put("state/mate-lock.json", {"session_id": "s", "heartbeat_at": "2026-11-12T19:59:00Z"})
        doc = self.build()
        self.assertEqual(self.val(doc, "queue", "claims", "counts"), {"Ready": 1})
        self.assertIn("<data-root>/queue.md", doc["queue"]["claims"]["counts"]["resolved_by"])
        self.assertEqual(doc["seats"]["mate"]["verdict"]["value"], "fresh")
        self.assertNotIn(os.path.realpath(data), json.dumps(doc))

    def test_dangling_state_link_is_unknown_and_the_write_refuses(self):
        (self.root / "state").symlink_to(Path(self._tmp.name) / "gone" / "state")
        doc = self.build()
        for seat in ("mate", "bosun"):
            self.assertEqual(doc["seats"][seat]["verdict"]["value"], "unknown", seat)
        env = dict(os.environ, SHIP_ROOT=str(self.root))
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("refused", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_unresolved_stub_is_unknown(self):
        self.put("queue.md", CS.STUB_MARKER + "\nmoved\n")
        c = self.build()["queue"]["claims"]["counts"]
        self.assertEqual(c["confidence"], "unknown")
        self.assertIn("pointer stub", c["resolved_by"])


class TestHardening(Base):
    def run_cli(self, *args):
        env = dict(os.environ, SHIP_ROOT=str(self.root))
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env,
                              timeout=20)

    def test_fifos_and_devices_are_not_read(self):
        for rel in ("projects/demo/tickets/FIFO.md", "inbox/drops/fifo.md", "inbox/familiar/fifo.md"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            os.mkfifo(self.root / rel)
        os.mkfifo(self.root / "queue.md")
        (self.root / "state").mkdir()
        (self.root / "state" / "status.json").symlink_to("/dev/zero")
        self.put("projects/demo/tickets/OK.md", "**Status:** ready\n")
        r = self.run_cli("--stdout")
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(doc["tickets"]["claims"]["total"]["value"], 1)
        self.assertEqual(doc["drops"]["claims"]["pending"]["value"], 0)
        self.assertEqual(doc["queue"]["claims"]["counts"]["confidence"], "unknown")
        self.assertIn("not a regular file", doc["status"]["claims"]["doing"]["resolved_by"])

    def test_oversized_and_deeply_nested_sources_are_unreadable(self):
        self.put("state/status.json", "[" * 100000 + "]" * 100000)
        doc = self.build()
        self.assertIn("unreadable", doc["status"]["claims"]["doing"]["resolved_by"])
        self.put("state/status.json", {"tick": 1, "pad": "x" * (CS.MAX_BYTES + 1)})
        self.assertIn("larger than", self.build()["status"]["claims"]["tick"]["resolved_by"])
        deep = self.put("deep.json", "[" * 100000 + "]" * 100000)
        r = self.run_cli("--validate", str(deep))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_content_strings_are_capped(self):
        long = "y" * 5000
        self.put("state/mate-lock.json", {"session_id": long, "heartbeat_at": "2026-11-12T19:59:00Z"})
        self.put("state/status.json", {"tick": 1, "now": {"doing": long}, "wake_reason": {"nested": long},
                                       "crew": [{"name": long, "task": long}]})
        self.put("inbox/drops/d.md", "---\nsource: %s\nauthority: %s\n---\n" % (long, long))
        doc = self.build()
        for v in (self.val(doc, "seats", "mate", "claims", "lock_holder"),
                  self.val(doc, "status", "claims", "doing"), self.val(doc, "status", "claims", "wake_reason"),
                  self.val(doc, "crew", "claims", "active")[0]["task"],
                  self.val(doc, "drops", "claims", "ledger")[0]["source"]):
            self.assertLessEqual(len(v), CS.STR_CAP)


class TestSchemaGuards(Base):
    def test_claim_refuses_without_provenance(self):
        with self.assertRaises(ValueError):
            CS.claim(1, "observed", "")
        with self.assertRaises(ValueError):
            CS.claim(1, "certain", "x")

    def test_validator_catches_each_violation(self):
        good = self.build()
        cases = {
            "missing resolved_by": lambda d: d["queue"]["claims"]["counts"].pop("resolved_by"),
            "bad confidence": lambda d: d["queue"]["claims"]["counts"].update(confidence="sure"),
            "bad verdict": lambda d: d["seats"]["mate"]["verdict"].update(value="alive"),
            "missing section": lambda d: d.pop("drops"),
            "missing required claim": lambda d: d["seats"]["mate"]["claims"].pop("heartbeat_at"),
            "stray key in a claim": lambda d: d["tickets"]["claims"]["total"].update(note="x"),
            "bad stamp": lambda d: d.update(generated_at="2026-11-12 20:00"),
            "wrong schema id": lambda d: d.update(schema="shipkit-console/2"),
            "bool is not an integer": lambda d: d.update(stale_after_s=True),
            "extension must be a section": lambda d: d.update(fuel={"pct": 3}),
        }
        for name, mutate in cases.items():
            doc = copy.deepcopy(good)
            mutate(doc)
            self.assertNotEqual(CS.validate(doc, SCHEMA), [], name)
        ext = copy.deepcopy(good)
        ext["fuel"] = {"claims": {"pct": CS.claim(3, "observed", "a module's own file")}}
        self.assertEqual(CS.validate(ext, SCHEMA), [])


class TestCli(Base):
    def run_cli(self, *args):
        env = dict(os.environ, SHIP_ROOT=str(self.root))
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def test_missing_state_dir_refuses_and_is_not_created(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 2)
        self.assertIn("refused: state/ absent", r.stderr)
        self.assertFalse((self.root / "state").exists())

    def test_unwritable_state_dir_refuses_cleanly(self):
        (self.root / "state").mkdir()
        os.chmod(self.root / "state", 0o555)
        try:
            r = self.run_cli()
        finally:
            os.chmod(self.root / "state", 0o755)
        self.assertEqual(r.returncode, 2)
        self.assertIn("refused: cannot write state/console.json", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_write_stdout_and_validate(self):
        out = self.root / "state" / "console.json"
        out.parent.mkdir()
        r = self.run_cli("--stdout")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["schema"], "shipkit-console/1")
        self.assertFalse(out.exists())
        r = self.run_cli("--stale-after", "120")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(out.read_text())["stale_after_s"], 120)
        self.assertEqual(out.stat().st_mode & 0o777, 0o644)
        self.assertEqual([p.name for p in out.parent.iterdir()], ["console.json"])
        self.assertEqual(self.run_cli("--validate", str(out)).returncode, 0)
        out.write_text(json.dumps({"schema": "shipkit-console/1"}))
        r = self.run_cli("--validate", str(out))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing generated_at", r.stdout)
        out.write_text("{not json")
        self.assertEqual(self.run_cli("--validate", str(out)).returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
