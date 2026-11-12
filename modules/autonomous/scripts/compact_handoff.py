#!/usr/bin/env python3
"""compact_handoff.py — the Mate's compaction hook pair (one script, two events).

Reads the hook JSON on stdin and acts on `hook_event_name`:

  PreCompact               write state/precompact-handoff.md (atomic) and print summary
                           instructions to stdout (the harness feeds them to the compactor).
  SessionStart (compact)   print {"hookSpecificOutput": {..., "additionalContext": ...}}
                           telling the resumed session to re-anchor and run /ship-watch-start.

ship-watch-start step 1 reads the snapshot's first line,
`# PRE-COMPACTION SNAPSHOT <YYYY-MM-DDTHH:MM:SSZ>`, to tell RESUME from FRESH.

Seat guard: only a payload with agent_type == "ship-mate" acts; anything else is a silent
no-op. The kit's mate-lock stores a synthetic label, not the Claude session id, so it can't
identify the firing session; agent_type is what the harness sets for `--agent ship-mate`.

Exits 0 (only exit 2 blocks compaction; the hook shim also forces 0).
Env: SHIP_ROOT (default: the kit root, three levels up from this file).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MATE_AGENT = "ship-mate"
HANDOFF_REL = "state/precompact-handoff.md"
HEADER = "# PRE-COMPACTION SNAPSHOT"
LOG_TAIL_LINES = 15

KIT_ROOT = Path(__file__).resolve().parents[3]
SHIP_ROOT = Path(os.environ.get("SHIP_ROOT") or KIT_ROOT)
sys.path.insert(0, str(KIT_ROOT / "lib"))
from ship_data import data_root  # noqa: E402


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _today_log():
    return SHIP_ROOT / "logs" / "mate" / f"{datetime.now().strftime('%Y-%m-%d')}.md"


def _rel(path):
    try:
        return str(Path(path).relative_to(SHIP_ROOT))
    except ValueError:
        return str(path)


def queue_summary(queue_path):
    try:
        lines = Path(queue_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(no queue file)"
    counts, section = {}, None
    for ln in lines:
        if ln.startswith("## "):
            section = ln[3:].strip()
            counts.setdefault(section, 0)
        elif section and re.match(r"\d+\. ", ln):
            counts[section] += 1
    return " · ".join(f"{k}={v}" for k, v in counts.items()) or "(no sections)"


def _bullets(items):
    out = []
    for it in items or []:
        if isinstance(it, dict):
            label = it.get("name") or it.get("id") or "?"
            task = it.get("task") or it.get("doing")
            out.append(f"- {label}: {task}" if task else f"- {label}")
        else:
            out.append(f"- {it}")
    return "\n".join(out) or "(none recorded)"


def build_snapshot(payload, stamp):
    status = _read_json(SHIP_ROOT / "state" / "status.json") or {}
    lock = _read_json(SHIP_ROOT / "state" / "mate-lock.json") or {}
    queue = data_root(SHIP_ROOT) / "queue.md"
    log = _today_log()
    try:
        tail = "\n".join(log.read_text(encoding="utf-8").splitlines()[-LOG_TAIL_LINES:])
    except OSError:
        tail = f"(no {_rel(log)})"
    now = status.get("now") if isinstance(status.get("now"), dict) else {}
    return "\n".join([
        f"{HEADER} {stamp}",
        "",
        f"trigger: {payload.get('trigger') or '?'} · session: {payload.get('session_id') or '?'}",
        f"mate-lock: {lock.get('session_id') or '(none)'} (heartbeat {lock.get('heartbeat_at') or '?'})",
        "",
        "## Loop state (state/status.json)",
        f"- tick: {status.get('tick', '?')}",
        f"- wake_reason: {status.get('wake_reason', '?')}",
        f"- doing: {now.get('doing', '?')}",
        "",
        "## Crew in flight",
        _bullets(status.get("crew")),
        "",
        "## Last actions",
        _bullets(status.get("last_actions")),
        "",
        f"## Queue summary ({_rel(queue)})",
        queue_summary(queue),
        "",
        f"## Tail of {_rel(log)} (last {LOG_TAIL_LINES} lines)",
        "```",
        tail,
        "```",
        "",
    ])


def precompact(payload):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = SHIP_ROOT / HANDOFF_REL
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(build_snapshot(payload, stamp), encoding="utf-8")
        os.replace(tmp, out)
    except OSError as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        sys.stderr.write(f"compact_handoff: snapshot not written: {e}\n")
        return
    print(f"Ship First Mate session. Preserve in the summary: crew in flight (ids and tickets), "
          f"the mate-lock label, open Awaiting-Captain items and the current tick. "
          f"The full snapshot is {HANDOFF_REL} ({stamp}).")


def reanchor(payload):
    if payload.get("source") != "compact":
        return
    droot = data_root(SHIP_ROOT)
    handoff = HANDOFF_REL if (SHIP_ROOT / HANDOFF_REL).is_file() else f"{HANDOFF_REL} (MISSING: re-anchor from the other files)"
    ctx = (
        "You are the Ship First Mate resuming after a compaction, mid-watch: NOT a fresh launch. "
        "Re-anchor on the files, not the summary: core/mate.md, mate.local.md and "
        "modules/autonomous/mate-event-driven.md (role), "
        f"{handoff} (the pre-compaction snapshot), {_rel(droot / 'queue.md')}, "
        f"{_rel(droot / 'captain.md')} and today's {_rel(_today_log())}. "
        "Then run /ship-watch-start: it detects RESUME, re-arms the wake-monitor and checks the Bosun. "
        "Do not re-run the fresh-day ceremony, do not open a new watch section, and keep the tick "
        "numbering unbroken."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": ctx}}))


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("agent_type") != MATE_AGENT:
        return 0
    event = payload.get("hook_event_name")
    if event == "PreCompact":
        precompact(payload)
    elif event == "SessionStart":
        reanchor(payload)
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never block compaction or session start
        sys.stderr.write(f"compact_handoff: {e}\n")
    sys.exit(0)
