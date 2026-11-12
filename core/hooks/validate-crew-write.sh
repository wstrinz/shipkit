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
# guard). The candidate AND the protected paths are canonicalized the same way
# (../ segments and symlinks resolved, file need not exist) and lowercased (macOS and
# Windows filesystems are case-insensitive), so neither a data root nor a case variant
# gets around the guard. `realpath -m` is GNU/Git-Bash only (macOS/BSD realpath has no
# -m and errors), so fall back to python3's os.path.realpath (already a kit dependency),
# then to the raw paths — a raw fallback lets dotted paths (./queue.md, logs/../queue.md)
# dodge the checks, which is why the python3 rung exists.
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
case "$FILE_PATH" in
  /*) CANDIDATE="$FILE_PATH" ;;
  *)  CANDIDATE="${CWD:-$PWD}/$FILE_PATH" ;;
esac
# With a data root, state/ is a symlink into it and the root data files live beside it.
DATA_DIR="$SHIP_DIR"
if [ -L "$SHIP_DIR/state" ]; then
  DATA_DIR=$(cd -P "$SHIP_DIR/state/.." 2>/dev/null && pwd) || DATA_DIR="$SHIP_DIR"
fi
set -- "$CANDIDATE" "$SHIP_DIR/queue.md" "$SHIP_DIR/captain.md" "$SHIP_DIR/inbox" \
  "$DATA_DIR/queue.md" "$DATA_DIR/captain.md"
if CANON=$(realpath -m -- "$@" 2>/dev/null) && [ -n "$CANON" ]; then
  :
elif command -v python3 >/dev/null 2>&1; then
  CANON=$(python3 -c 'import os, sys; print("\n".join(os.path.realpath(p) for p in sys.argv[1:]))' "$@") \
    || { echo "Blocked: ${0##*/} could not canonicalize the path (python3 failed) — failing CLOSED." >&2; exit 2; }
else
  CANON=$(printf '%s\n' "$@")
fi
CANON=$(printf '%s\n' "$CANON" | tr '[:upper:]' '[:lower:]')
{ read -r NORM; read -r QUEUE; read -r CAPTAIN; read -r INBOX; read -r DQUEUE; read -r DCAPTAIN; } <<EOF
$CANON
EOF

block() {
  echo "Blocked: crew don't write $1 — $2" >&2
  exit 2
}

case "$NORM" in
  "$QUEUE"|"$DQUEUE")
    block "queue.md" "the Mate owns the queue. Note needed changes in your watch log; the Mate applies them." ;;
  "$CAPTAIN"|"$DCAPTAIN")
    block "captain.md" "the Captain's orders are read-only for crew." ;;
  "$INBOX/"*|"$INBOX")
    block "inbox/" "note blockers in your watch log, not the inbox; the Mate processes the inbox." ;;
esac

exit 0
