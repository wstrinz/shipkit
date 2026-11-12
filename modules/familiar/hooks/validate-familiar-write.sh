#!/bin/bash
# validate-familiar-write.sh — PreToolUse hook (matcher Write|Edit|MultiEdit|NotebookEdit) for the
# ship-familiar agent. A POSITIVE allow-list: the Familiar may write its own log, its own state,
# its own docs, drafts, and briefs to the Navigator. Everything else is DENY — queue.md, every
# ticket, inbox/drops/ (commands go through familiar_drop.py, which validates them), captain.md,
# code, role docs.
#
# Positive, not a deny-list: a deny-list turns every spelling it did not anticipate into an ALLOW.
# BOTH sides are canonicalized: the target with realpath, and each anchor directory with realpath
# too. So `..`, `./`, doubled slashes and symlinks are judged by where they land, and a data root
# (inbox/, logs/, projects/, state/, docs/ symlinked out of the kit) keeps working. Denies run
# before allows, so a symlinked allowed directory that lands on tickets is still refused.
#
# Fails CLOSED: missing python3, an unreadable payload, a missing path, or the checker crashing
# all exit 2 (the PreToolUse "block" contract). Any other non-zero exit would let the write
# through, so the python exit code is normalised below.
set -u
SHIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "familiar-write DENY: python3 not on PATH (fail closed)" >&2
  exit 2
fi

# read -d '' rather than $(cat <<EOF): bash 3.2 parses quotes inside a heredoc that sits in a
# command substitution.
read -r -d '' PY <<'EOF'
import json, os, re, sys

root = sys.argv[1]


def deny(msg):
    sys.stderr.write("familiar-write DENY: " + msg + "\n")
    sys.exit(2)


def canon(rel):
    return os.path.realpath(os.path.join(root, rel))


def under(path, anchor_rel):
    """path's remainder below the canonical anchor, or None."""
    a = canon(anchor_rel)
    return os.path.relpath(path, a).replace(os.sep, "/") if path.startswith(a + os.sep) else None


try:
    payload = json.loads(sys.stdin.read())
except Exception:
    deny("malformed PreToolUse payload (fail closed)")
if not isinstance(payload, dict):
    deny("malformed PreToolUse payload (fail closed)")
ti = payload.get("tool_input") or {}
p = ti.get("file_path") or ti.get("notebook_path") or ""
if not isinstance(p, str) or not p:
    deny("no file_path in payload (fail closed)")

target = os.path.realpath(os.path.join(payload.get("cwd") or os.getcwd(), p))
shown = p

NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
PROTECTED = ("queue.md", "queue-archive.md", "captain.md", "inbox/captain.md")
# Allowed names end in .md or .json, and the Familiar's shell lane runs only pinned helper
# paths, never a file by an arbitrary name. Together that keeps a write from becoming a run.
ALLOW = [
    ("logs/familiar", r"%s\.md" % NAME),
    ("state/familiar", r"(drafts/)?%s\.(md|json)" % NAME),
    ("docs/familiar", r"%s\.md" % NAME),
    ("docs/drafts", r"%s\.md" % NAME),
    ("inbox/navigator", r"%s\.md" % NAME),
]

if os.path.basename(target).lower() in {os.path.basename(x) for x in PROTECTED} or \
        target in {canon(x) for x in PROTECTED}:
    deny("%s is a protected surface. The Mate is the only queue writer; captain.md is the "
         "Captain's. Send the change as a command: familiar_drop.py send <draft>." % shown)
rest = under(target, "projects")
if rest is not None and re.match(r"^[^/]+/tickets/", rest):
    deny("%s is a ticket. Tickets belong to the Mate (and the Navigator, if you run one). "
         "Command the change with familiar_drop.py send <draft>." % shown)
if under(target, "inbox/drops") is not None:
    deny("%s: commands reach inbox/drops/ only through familiar_drop.py, which stamps the "
         "name and validates the frontmatter. Write the draft under state/familiar/drafts/ "
         "and run familiar_drop.py send <draft>." % shown)
if under(target, "inbox/familiar") is not None:
    deny("%s: inbox/familiar/ is your mailbox, written by others. Archive read mail with "
         "familiar_drop.py archive <name>." % shown)
for anchor, pattern in ALLOW:
    rest = under(target, anchor)
    if rest is not None and re.fullmatch(pattern, rest):
        sys.exit(0)
deny("%s is not on the Familiar write allow-list (logs/familiar/, state/familiar/, "
     "docs/familiar/, docs/drafts/, inbox/navigator/). Work on anything else is a command "
     "to the Mate." % shown)
EOF

# -I: isolated mode, so a json.py or re.py in the session's cwd cannot shadow the stdlib.
python3 -I -c "$PY" "$SHIP_DIR"
rc=$?
[ "$rc" -eq 0 ] && exit 0
exit 2
