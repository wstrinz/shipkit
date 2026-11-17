#!/usr/bin/env python3
"""Tests for the Mate's compaction hook pair (hooks/compact-handoff.sh -> scripts/compact_handoff.py).

Every case pipes a stub hook payload into the real script against a temp SHIP_ROOT.
Stand-down cases carry a positive control: the same fixture with agent_type ship-mate writes.

Usage: python3 modules/autonomous/tests/test_compact_handoff.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
SCRIPT = MODULE / "scripts" / "compact_handoff.py"
SHIM = MODULE / "hooks" / "compact-handoff.sh"
SKILL = MODULE / "skills" / "ship-watch-start" / "SKILL.md"
KIT = MODULE.parents[1]
sys.path.insert(0, str(KIT / "lib"))
from ship_data import STUB_MARKER  # noqa: E402

HEADER_RE = re.compile(r"^# PRE-COMPACTION SNAPSHOT (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)$")
QUEUE = """# Queue

## Ready
1. [A-1](x) - one
2. [A-2](x) - two

## Active
1. [B-1](x) - busy

## Awaiting Captain
<!-- empty -->
"""


def precompact(**extra):
    return dict({"session_id": "abc", "hook_event_name": "PreCompact", "trigger": "auto",
                 "cwd": "/tmp", "custom_instructions": None}, **extra)


def session_start(source="compact", **extra):
    return dict({"session_id": "abc", "hook_event_name": "SessionStart", "source": source,
                 "cwd": "/tmp"}, **extra)


class CompactHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ship = Path(self.tmp.name) / "ship"
        (self.ship / "state").mkdir(parents=True)
        (self.ship / "logs" / "mate").mkdir(parents=True)
        (self.ship / "queue.md").write_text(QUEUE, encoding="utf-8")
        (self.ship / "state" / "status.json").write_text(json.dumps({
            "tick": 41, "wake_reason": "crew-done", "now": {"doing": "reviewing A-1"},
            "last_actions": ["dispatched A-1", "merged nothing"],
            "crew": [{"name": "crew-A-1", "task": "build the thing"}],
        }), encoding="utf-8")
        (self.ship / "state" / "mate-lock.json").write_text(json.dumps({
            "session_id": "bg-mate-1700000000", "heartbeat_at": "2026-11-12T20:00:00Z"}),
            encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")
        (self.ship / "logs" / "mate" / f"{today}.md").write_text(
            "\n".join(f"line {i}" for i in range(30)) + "\nLAST-LOG-LINE\n", encoding="utf-8")
        self.handoff = self.ship / "state" / "precompact-handoff.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload, via_shim=False, ship=None):
        env = dict(os.environ, SHIP_ROOT=str(ship or self.ship))
        cmd = ["bash", str(SHIM)] if via_shim else [sys.executable, str(SCRIPT)]
        data = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(cmd, input=data, capture_output=True, text=True, env=env)

    # --- PreCompact ------------------------------------------------------------------

    def test_mate_precompact_writes_snapshot_skill_can_read(self):
        r = self.run_hook(precompact(agent_type="ship-mate"))
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.handoff.read_text(encoding="utf-8")
        m = HEADER_RE.match(text.splitlines()[0])
        self.assertIsNotNone(m, text.splitlines()[0])
        age = datetime.now(timezone.utc) - datetime.strptime(
            m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertLess(abs(age.total_seconds()), 120)
        for want in ("trigger: auto", "bg-mate-1700000000", "- tick: 41", "reviewing A-1",
                     "- crew-A-1: build the thing", "- dispatched A-1",
                     "Ready=2 · Active=1 · Awaiting Captain=0", "LAST-LOG-LINE"):
            self.assertIn(want, text)
        self.assertNotIn("line 0\n", text)
        self.assertIn("Ship First Mate session. Preserve in the summary", r.stdout)
        self.assertIn("state/precompact-handoff.md", r.stdout)

    def test_skill_documents_the_header_the_writer_emits(self):
        self.assertIn("`# PRE-COMPACTION SNAPSHOT <UTC timestamp, YYYY-MM-DDTHH:MM:SSZ>`",
                      SKILL.read_text(encoding="utf-8"))

    def test_non_mate_sessions_stand_down(self):
        for payload in (precompact(), precompact(agent_type="ship-crew"),
                        precompact(agent_type="ship-bosun")):
            r = self.run_hook(payload)
            self.assertEqual((r.returncode, r.stdout), (0, ""), payload)
            self.assertFalse(self.handoff.exists(), payload)
        self.run_hook(precompact(agent_type="ship-mate"))
        self.assertTrue(self.handoff.exists())

    def test_foreign_compaction_does_not_clobber_mate_snapshot(self):
        self.handoff.write_text("MATE SNAPSHOT\n", encoding="utf-8")
        self.run_hook(precompact(agent_type="some-other-agent"))
        self.assertEqual(self.handoff.read_text(encoding="utf-8"), "MATE SNAPSHOT\n")
        self.run_hook(precompact(agent_type="ship-mate"))
        self.assertNotEqual(self.handoff.read_text(encoding="utf-8"), "MATE SNAPSHOT\n")

    def test_missing_state_still_writes_and_exits_zero(self):
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        r = self.run_hook(precompact(agent_type="ship-mate"), ship=bare)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (bare / "state" / "precompact-handoff.md").read_text(encoding="utf-8")
        self.assertRegex(text.splitlines()[0], HEADER_RE)
        self.assertIn("(no queue file)", text)
        self.assertIn("mate-lock: (none)", text)

    def test_queue_read_from_data_root(self):
        data = Path(self.tmp.name) / "data"
        (data / "state").mkdir(parents=True)
        (data / "queue.md").write_text(QUEUE.replace("2. [A-2](x) - two\n", ""), encoding="utf-8")
        ship = Path(self.tmp.name) / "linked"
        ship.mkdir()
        (ship / "state").symlink_to(data / "state")
        (ship / "queue.md").write_text(STUB_MARKER + "\nsee data root\n", encoding="utf-8")
        self.run_hook(precompact(agent_type="ship-mate"), ship=ship)
        text = (data / "state" / "precompact-handoff.md").read_text(encoding="utf-8")
        self.assertIn("Ready=1 · Active=1", text)

    # --- SessionStart ------------------------------------------------------------------

    def context(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        return out["additionalContext"]

    def test_mate_compact_restart_gets_reanchor(self):
        self.run_hook(precompact(agent_type="ship-mate"))
        ctx = self.context(self.run_hook(session_start(agent_type="ship-mate")))
        self.assertIn("You are the Ship First Mate resuming after a compaction", ctx)
        self.assertIn("state/precompact-handoff.md (the pre-compaction snapshot)", ctx)
        self.assertIn("/ship-watch-start", ctx)
        self.assertNotIn("MISSING", ctx)

    def test_reanchor_flags_missing_snapshot(self):
        ctx = self.context(self.run_hook(session_start(agent_type="ship-mate")))
        self.assertIn("MISSING", ctx)

    def test_reanchor_only_for_mate_after_compaction(self):
        for payload in (session_start(), session_start(agent_type="ship-crew"),
                        session_start(source="startup", agent_type="ship-mate"),
                        session_start(source="resume", agent_type="ship-mate")):
            r = self.run_hook(payload)
            self.assertEqual((r.returncode, r.stdout), (0, ""), payload)
        self.assertTrue(self.context(self.run_hook(session_start(agent_type="ship-mate"))))

    # --- robustness + the shim -----------------------------------------------------------

    def test_garbage_stdin_is_a_silent_zero(self):
        for raw in ("", "not json", "[1,2]"):
            r = self.run_hook(raw)
            self.assertEqual((r.returncode, r.stdout), (0, ""), raw)

    def test_shim_runs_the_script_and_exits_zero(self):
        r = self.run_hook(precompact(agent_type="ship-mate"), via_shim=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Ship First Mate session. Preserve in the summary", r.stdout)
        self.assertTrue(self.handoff.exists())
        self.assertEqual(self.run_hook("not json", via_shim=True).returncode, 0)

    def test_unwritable_state_exits_zero_with_message(self):
        blocked = Path(self.tmp.name) / "blocked"
        blocked.mkdir()
        (blocked / "state").write_text("a file, not a dir", encoding="utf-8")
        r = self.run_hook(precompact(agent_type="ship-mate"), via_shim=True, ship=blocked)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("compact_handoff: snapshot not written", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
