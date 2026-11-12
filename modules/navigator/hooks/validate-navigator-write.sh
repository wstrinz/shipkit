#!/bin/bash
# validate-navigator-write.sh — PreToolUse hook (matcher Write|Edit|MultiEdit|NotebookEdit) for the
# ship-navigator agent. A POSITIVE allow-list of what the Navigator may write: tickets, project
# docs, drafts, memory, and its reports. Reports go to inbox/drops/ for the Mate, or, when the
# familiar module is enabled (per state/install.json), to inbox/familiar/ INSTEAD: one
# commander. Everything else is DENY, queue.md included.
#
# Positive, not a deny-list: a deny-list turns every spelling it did not anticipate into an ALLOW.
# BOTH sides are canonicalized (target and each anchor directory, with realpath), so `..`, `./`,
# doubled slashes and symlinks are judged by where they land, and a data root (data dirs
# symlinked out of the kit) keeps working.
#
# A drop the Navigator writes may not pose as a Familiar command: no `familiar-*` filename and no
# `source: familiar` line in the written text.
#
# Fails CLOSED: missing python3, an unreadable payload, a missing path, or the checker crashing
# all exit 2.
set -u
SHIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "navigator-write DENY: python3 not on PATH (fail closed)" >&2
  exit 2
fi

# read -d '' rather than $(cat <<EOF): bash 3.2 parses quotes inside a heredoc that sits in a
# command substitution.
read -r -d '' PY <<'EOF'
import json, os, re, sys

root = sys.argv[1]


def deny(msg):
    sys.stderr.write("navigator-write DENY: " + msg + "\n")
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


def familiar_enabled():
    try:
        with open(canon("state/install.json"), encoding="utf-8") as fh:
            mods = json.load(fh).get("modules")
        return isinstance(mods, list) and "familiar" in mods
    except Exception:
        return False


def resulting_texts():
    """The file text after this call, plus every new fragment (belt and braces)."""
    if isinstance(ti.get("content"), str):
        return [ti["content"]]
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        text = ""
    edits = ti.get("edits") if isinstance(ti.get("edits"), list) else [ti]
    out = []
    for e in edits:
        if not isinstance(e, dict):
            continue
        old, new = e.get("old_string"), e.get("new_string")
        if isinstance(new, str):
            out.append(new)
            if isinstance(old, str) and old:
                text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return [text] + out


# Same shape as classify_input's claim test; splitlines() breaks on \r, \v, \f, U+2028 and the
# other separators a reader might treat as a line end, not only \n.
CLAIM = re.compile(r'(?:^|[\s,{])"?source"?[ \t]*:[ \t]*["\']?familiar(?![A-Za-z0-9_.-])')


def claims_familiar():
    return any(CLAIM.search(ln) for t in resulting_texts() for ln in t.splitlines())


NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
PATH = r"%s(/%s)*" % (NAME, NAME)
# Every allowed name ends in .md, and the Navigator's shell lane runs no file it did not pin.
ALLOW = [
    ("projects", r"%s/tickets/%s\.md" % (NAME, NAME)),
    ("projects", r"%s/docs/%s\.md" % (NAME, PATH)),
    ("docs/drafts", r"%s\.md" % PATH),
    ("memory", r"%s\.md" % PATH),
]
PROTECTED = ("queue.md", "queue-archive.md", "captain.md", "inbox/captain.md")

if os.path.basename(target).lower() in {os.path.basename(x) for x in PROTECTED} or \
        target in {canon(x) for x in PROTECTED}:
    deny("%s is a protected surface. The Mate is the only queue writer: send the change as a "
         "drop in inbox/drops/." % shown)
rest = under(target, "inbox/drops")
if rest is not None:
    if familiar_enabled():
        deny("%s: with the familiar module enabled the Navigator reports to inbox/familiar/ "
             "and the Familiar commands the Mate (one commander)." % shown)
    if rest.lower().startswith("familiar-"):
        deny("%s: familiar-* drops are Familiar commands; the Navigator advises, it does not "
             "command the Mate." % shown)
    if claims_familiar():
        deny("%s: a Navigator drop may not declare source: familiar." % shown)
    if re.fullmatch(r"%s\.md" % NAME, rest):
        sys.exit(0)
rest = under(target, "inbox/familiar")
if rest is not None:
    if not familiar_enabled():
        deny("%s: the familiar module is not enabled on this ship; report in your drop or "
             "to the Captain instead." % shown)
    if re.fullmatch(r"%s\.md" % NAME, rest):
        sys.exit(0)
for anchor, pattern in ALLOW:
    rest = under(target, anchor)
    if rest is not None and re.fullmatch(pattern, rest):
        sys.exit(0)
deny("%s is not on the Navigator write allow-list (tickets, projects/*/docs, docs/drafts, "
     "memory, inbox/drops, and inbox/familiar when the familiar module is enabled). Code, "
     "state, logs and role docs are not yours; queue changes go as a drop." % shown)
EOF

# -I: isolated mode, so a json.py or re.py in the session's cwd cannot shadow the stdlib.
python3 -I -c "$PY" "$SHIP_DIR"
rc=$?
[ "$rc" -eq 0 ] && exit 0
exit 2
