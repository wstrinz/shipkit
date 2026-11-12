#!/bin/bash
# Ship crew Write/Edit path guard (PreToolUse, matcher "Write|Edit").
# Companion to validate-crew-bash.sh.
#
# WHY THIS EXISTS: crew agents carry the Write/Edit tools, and the bash hook only
# matches the Bash tool — so a direct Write/Edit call to queue.md never passed through
# any guard. This hook closes that gap for the indisputable shared-state boundaries:
#
#   BLOCKED (ship-root-relative, and data-root-relative too when there is one — DATA.md):
#     - queue.md            (Mate-owned index; crew are read-only on it)
#     - queue-archive.md    (its archive, queue-split module; same owner)
#     - captain.md          (the Captain's orders; crew read-only)
#     - inbox/**            (crew note blockers in their LOG, not the inbox)
#
#   ALLOWED: everything else — crew legitimately write code in target repos, watch
#   logs under logs/, and their assigned ticket's "Current state" / "Watch history".
#   Ticket single-ticket scope stays prompt-governed (the hook can't know the
#   assignment).
#
# Like all Ship hooks this is a fail-loud guardrail against accidental violations,
# not a sandbox. Invoked as `bash <abs-path>` by the installed def, so the exec bit
# is POSIX belt-and-suspenders, not load-bearing. Ship root is resolved from this
# script's own location (core/hooks/ → two up).

# jq DEPENDENCY GUARD (fail CLOSED): the path parse below uses jq. Without jq the
# parse yields empty and the hook exits 0 — SILENT ZERO ENFORCEMENT. Refuse to run
# instead: exit 2 with a loud message. shipkit_init.py's preflight asserts jq is on
# PATH at install, so a correctly-installed ship never reaches this.
if ! command -v jq >/dev/null 2>&1; then
  echo "Blocked: ${0##*/} requires jq, which is not on PATH. Install jq (brew install jq / apt-get install jq / winget install jqlang.jq) — failing CLOSED to avoid silent zero enforcement of the Ship hooks." >&2
  exit 2
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')

# No path in the payload (not a file-writing call) — nothing to guard.
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

SHIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Resolve a relative path against the tool call's cwd (Claude Code passes absolute
# paths for Write/Edit, but don't rely on it — a relative path must not dodge the
# guard).
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
case "$FILE_PATH" in
  /*) CANDIDATE="$FILE_PATH" ;;
  *)  CANDIDATE="${CWD:-$PWD}/$FILE_PATH" ;;
esac

block() {
  echo "Blocked: crew don't write $1 — $2" >&2
  exit 2
}

# python3 (a kit dependency) compares by FILE IDENTITY: the candidate, or its nearest
# existing ancestor, against each protected path, with symlinks resolved. That catches
# a data root, ../ segments, and every spelling the filesystem folds together (case,
# and Unicode folds like `ſ` that APFS honours but `tr` doesn't). The data root comes
# from lib/ship_data.py; an import failure fails CLOSED.
read -r -d '' PY <<'PY'
import os, sys
cand, ship = os.path.realpath(sys.argv[1]), sys.argv[2]
sys.path.insert(0, os.path.join(ship, "lib"))
from ship_data import data_root
roots = {ship, str(data_root(ship))}

def same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a).casefold() == os.path.realpath(b).casefold()

def at(path, prot):
    if os.path.exists(path) and os.path.exists(prot):
        return same(path, prot)
    return (same(os.path.dirname(path), os.path.dirname(prot))
            and os.path.basename(path).casefold() == os.path.basename(prot).casefold())

def under(path, d):
    p = path
    while True:
        if os.path.exists(p) and same(p, d):
            return True
        if os.path.dirname(p) == p:
            break
        p = os.path.dirname(p)
    rp, rd = path.casefold(), os.path.realpath(d).casefold().rstrip(os.sep)
    return rp == rd or rp.startswith(rd + os.sep)

for name, label in (("queue.md", "queue"), ("queue-archive.md", "archive"),
                    ("captain.md", "captain")):
    if any(at(cand, os.path.join(r, name)) for r in roots):
        print(label)
        sys.exit(0)
if any(under(cand, os.path.join(r, "inbox")) for r in roots):
    print("inbox")
PY

if command -v python3 >/dev/null 2>&1; then
  LABEL=$(python3 -c "$PY" "$CANDIDATE" "$SHIP_DIR") \
    || { echo "Blocked: ${0##*/} could not check the path (python3 failed) — failing CLOSED." >&2; exit 2; }
else
  # No python3: string compare of GNU `realpath -m` (Git-Bash/Linux) or raw paths,
  # lowercased. Weaker: a raw fallback lets dotted paths (./queue.md) through.
  DATA_DIR="$SHIP_DIR"
  if [ -L "$SHIP_DIR/state" ] && PARENT=$(cd -P "$SHIP_DIR/state/.." 2>/dev/null && pwd); then
    if head -n 1 "$SHIP_DIR/queue.md" 2>/dev/null | grep -qF '<!-- shipkit: data-root pointer -->' \
        || [ -f "$PARENT/queue.md" ]; then
      DATA_DIR="$PARENT"
    fi
  fi
  set -- "$CANDIDATE" "$SHIP_DIR/queue.md" "$SHIP_DIR/queue-archive.md" "$SHIP_DIR/captain.md" \
    "$SHIP_DIR/inbox" "$DATA_DIR/queue.md" "$DATA_DIR/queue-archive.md" "$DATA_DIR/captain.md"
  CANON=$(realpath -m -- "$@" 2>/dev/null) && [ -n "$CANON" ] || CANON=$(printf '%s\n' "$@")
  CANON=$(printf '%s\n' "$CANON" | tr '[:upper:]' '[:lower:]')
  { read -r NORM; read -r Q; read -r A; read -r C; read -r I; read -r DQ; read -r DA; read -r DC; } <<EOF
$CANON
EOF
  case "$NORM" in
    "$Q"|"$DQ") LABEL=queue ;;
    "$A"|"$DA") LABEL=archive ;;
    "$C"|"$DC") LABEL=captain ;;
    "$I/"*|"$I") LABEL=inbox ;;
    *) LABEL="" ;;
  esac
fi

case "$LABEL" in
  queue)
    block "queue.md" "the Mate owns the queue. Note needed changes in your watch log; the Mate applies them." ;;
  archive)
    block "queue-archive.md" "the Mate owns the queue archive. Note needed changes in your watch log; the Mate applies them." ;;
  captain)
    block "captain.md" "the Captain's orders are read-only for crew." ;;
  inbox)
    block "inbox/" "note blockers in your watch log, not the inbox; the Mate processes the inbox." ;;
esac

exit 0
