#!/usr/bin/env python3
"""familiar_orient.py — the Familiar's one-screen wake.

Reads only kit-native state, all relative to the ship root:
  state/mate-lock.json, state/status.json, state/bosun-heartbeat.log,
  inbox/familiar/*.md (unread mail), inbox/drops/familiar-*.md (commands not yet processed),
  logs/mate/<today>.md, logs/familiar/*.md (the last "## Note to tomorrow").

Read-only, except --open-log, which starts today's logs/familiar/<date>.md if it does not exist.
Log files are named by the local calendar date, as the Mate's are; times are shown as ages or
in UTC. A missing or unreadable source is printed as such, never skipped: an absent signal must
not read as a quiet one. Stdlib only.

    familiar_orient.py              # print the screen
    familiar_orient.py --open-log   # also start today's Familiar log
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SHIP_ROOT = Path(os.environ.get("SHIP_ROOT", Path(__file__).resolve().parents[3])).resolve()
MAIL_SHOWN = 12


def parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    m = re.match(r"^(\d{8})T(\d{6})\+00:00$", v)
    try:
        if m:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc)
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def age(dt, now):
    if dt is None:
        return "?"
    mins = int((now - dt).total_seconds() // 60)
    if mins < 0:
        return "in the future (clock skew?)"
    if mins < 120:
        return "%dm" % mins
    if mins < 72 * 60:
        return "%dh%02dm" % (mins // 60, mins % 60)
    return "%dd" % (mins // 1440)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "absent"
    except (OSError, ValueError) as exc:
        return None, "unreadable (%s)" % exc.__class__.__name__


def subject(path):
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return "(unreadable)"
    for key in ("summary", "re", "title", "command"):
        m = re.search(r"^%s:\s*[\"']?(.+?)[\"']?\s*$" % key, head, re.M)
        if m:
            return m.group(1)
    m = re.search(r"^#+ (.+)$", head, re.M)
    return m.group(1) if m else ""


def deck(root, now):
    out = ["deck"]
    lock, err = read_json(root / "state" / "mate-lock.json")
    if lock is None:
        out.append("  mate-lock  %s" % err)
    else:
        sid = str(lock.get("session_id") or "?")[:12]
        out.append("  mate-lock  held by %s, heartbeat %s ago (a mutex, not a liveness signal)"
                   % (sid, age(parse_ts(lock.get("heartbeat_at")), now)))
    status, err = read_json(root / "state" / "status.json")
    if status is None:
        out.append("  status     %s" % err)
    else:
        doing = (status.get("now") or {}).get("doing") if isinstance(status.get("now"), dict) else None
        out.append("  status     written %s ago, tick %s, doing: %s"
                   % (age(parse_ts(status.get("generated_at")), now), status.get("tick", "?"),
                      (doing or "-")[:100]))
    hb = root / "state" / "bosun-heartbeat.log"
    try:
        lines = [ln for ln in hb.read_text(encoding="utf-8", errors="replace").splitlines() if ln]
    except FileNotFoundError:
        lines = None
    if lines is None:
        out.append("  bosun      no heartbeat log")
    elif not lines:
        out.append("  bosun      heartbeat log empty")
    else:
        stamp, _, text = lines[-1].partition("\t")
        out.append("  bosun      last beat %s ago: %s" % (age(parse_ts(stamp), now), text[:100]))
    return out


def mail(root):
    box = root / "inbox" / "familiar"
    files = sorted(box.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) \
        if box.is_dir() else []
    out = ["", "mail       %d unread in inbox/familiar/ (archive with familiar_drop.py archive "
           "<name>)" % len(files)]
    for p in files[:MAIL_SHOWN]:
        out.append("  %-34s %s" % (p.name[:34], subject(p)[:90]))
    if len(files) > MAIL_SHOWN:
        out.append("  ... %d older" % (len(files) - MAIL_SHOWN))
    return out


def pending(root, now):
    drops = root / "inbox" / "drops"
    files = sorted(drops.glob("familiar-*.md")) if drops.is_dir() else []
    out = ["", "commands   %d of yours not yet processed by the Mate" % len(files)]
    for p in files:
        m = re.match(r"^familiar-(\d{8}T\d{6}Z)", p.name)
        out.append("  %s ago  %s" % (age(parse_ts(m.group(1)) if m else None, now), p.name))
    return out


def continuity(root, today):
    out = [""]
    mate = root / "logs" / "mate" / ("%s.md" % today)
    if mate.is_file():
        heads = re.findall(r"^# (.+)$", mate.read_text(encoding="utf-8", errors="replace"), re.M)
        out.append("mate log   today: %d section(s), last: %s"
                   % (len(heads), heads[-1][:80] if heads else "-"))
    else:
        out.append("mate log   none for %s" % today)
    logs = sorted((root / "logs" / "familiar").glob("*.md")) \
        if (root / "logs" / "familiar").is_dir() else []
    earlier = [p for p in logs if p.stem < today]
    started = any(p.stem == today for p in logs)
    out.append("own log    %s" % ("today started" if started else
                                  "today not started; last = %s"
                                  % (earlier[-1].stem if earlier else "none")))
    if earlier:
        text = earlier[-1].read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^## Note to tomorrow[ \t]*\n(.+?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            out += ["", "note to tomorrow (%s):" % earlier[-1].stem,
                    "  " + " ".join(m.group(1).split())[:700]]
        else:
            out += ["", "note to tomorrow: none in %s (the last close skipped it)"
                    % earlier[-1].stem]
    return out


def open_log(root, today, now):
    path = root / "logs" / "familiar" / ("%s.md" % today)
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Familiar log — %s\n\n## Seat opened %s\n\n"
                    % (today, now.strftime("%H:%MZ")), encoding="utf-8")
    return path


def screen(root, now, today):
    lines = ["familiar orient · %s" % now.strftime("%Y-%m-%d %H:%MZ"), ""]
    lines += deck(root, now)
    lines += mail(root)
    lines += pending(root, now)
    lines += continuity(root, today)
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--open-log", action="store_true", help="start today's Familiar log")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    today = datetime.now().strftime("%Y-%m-%d")
    print("\n".join(screen(SHIP_ROOT, now, today)))
    if args.open_log:
        made = open_log(SHIP_ROOT, today, now)
        if made:
            print("\nopened     %s" % made.relative_to(SHIP_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
