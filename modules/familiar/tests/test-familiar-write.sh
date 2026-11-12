#!/bin/bash
# Test suite for validate-familiar-write.sh (the Familiar's Write/Edit allow-list).
# Usage: bash modules/familiar/tests/test-familiar-write.sh
#
# Runs the hook from a copy inside a throwaway ship tree, so symlink cases can be built without
# touching the repo. Every deny asserts its message, so a deny for the wrong reason fails.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)/hooks/validate-familiar-write.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/familiar-write.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/ship"
mkdir -p "$ROOT/modules/familiar/hooks" "$ROOT/logs/familiar" "$ROOT/projects/p/tickets" "$ROOT/docs"
cp "$SRC" "$ROOT/modules/familiar/hooks/"
HOOK="$ROOT/modules/familiar/hooks/validate-familiar-write.sh"
ROOT="$(cd "$ROOT" && pwd -P)"
ln -s ../../queue.md "$ROOT/logs/familiar/link.md"

PASS=0; FAIL=0
run_json() { OUT=$(printf '%s' "$1" | bash "$HOOK" 2>&1); CODE=$?; }
run_path() { # run_path <file_path> [cwd]
  local cwd="${2:-}"
  if [ -n "$cwd" ]; then
    run_json "$(printf '{"tool_input":{"file_path":"%s"},"cwd":"%s"}' "$1" "$cwd")"
  else
    run_json "$(printf '{"tool_input":{"file_path":"%s"}}' "$1")"
  fi
}
ok()  { PASS=$((PASS+1)); }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $1 (rc=$CODE: $OUT)"; }
allow() { run_path "$2" "${3:-}"; if [ "$CODE" -eq 0 ]; then ok; else bad "allow: $1"; fi; }
deny()  { run_path "$2" "${4:-}"; if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"$3"* ]]; then ok; else bad "deny: $1"; fi; }

echo "=== allow-list (ALLOW) ==="
allow "own log"                       "$ROOT/logs/familiar/2026-11-12.md"
allow "own state json"                "$ROOT/state/familiar/launch.json"
allow "draft command"                 "$ROOT/state/familiar/drafts/steer-1.md"
allow "own runbook"                   "$ROOT/docs/familiar/ops.local.md"
allow "shared draft doc"              "$ROOT/docs/drafts/plan.md"
allow "brief to the Navigator"        "$ROOT/inbox/navigator/brief.md"
allow "relative path from the root"   "logs/familiar/x.md" "$ROOT"
allow "near-miss name queue-notes"    "$ROOT/docs/drafts/queue-notes.md"

echo "=== queue, tickets, captain (DENY by mechanism) ==="
deny "queue.md"                       "$ROOT/queue.md" "protected surface"
deny "queue-archive.md"               "$ROOT/queue-archive.md" "protected surface"
deny "captain.md"                     "$ROOT/captain.md" "protected surface"
deny "queue.md spelled under drafts"  "$ROOT/docs/drafts/queue.md" "protected surface"
deny "queue.md, other case"           "$ROOT/docs/drafts/Queue.MD" "protected surface"
deny "a ticket"                       "$ROOT/projects/p/tickets/T-1.md" "is a ticket"
deny "a new ticket in a new project"  "$ROOT/projects/new/tickets/T-2.md" "is a ticket"
deny "captain inbox"                  "$ROOT/inbox/captain.md" "protected surface"
deny "a raw drop"                     "$ROOT/inbox/drops/familiar-20261112T000000Z.md" "only through familiar_drop.py"
deny "own mailbox"                    "$ROOT/inbox/familiar/note.md" "your mailbox"

echo "=== everything else (DENY) ==="
deny "status.json"                    "$ROOT/state/status.json" "not on the Familiar write allow-list"
deny "mate log"                       "$ROOT/logs/mate/2026-11-12.md" "not on the Familiar write allow-list"
deny "role doc"                       "$ROOT/core/mate.md" "not on the Familiar write allow-list"
deny "its own hook"                   "$HOOK" "not on the Familiar write allow-list"
deny "executable under drafts"        "$ROOT/docs/drafts/x.py" "not on the Familiar write allow-list"
deny "shell script in own state"      "$ROOT/state/familiar/run.sh" "not on the Familiar write allow-list"
deny "dotfile in own log dir"         "$ROOT/logs/familiar/.hidden.md" "not on the Familiar write allow-list"
deny "nested dir under own log"       "$ROOT/logs/familiar/sub/x.md" "not on the Familiar write allow-list"
deny "case-shifted allowed dir"       "$ROOT/LOGS/familiar/x.md" "not on the Familiar write allow-list"
deny "outside the ship root"          "/etc/familiar.md" "not on the Familiar write allow-list"

echo "=== traversal and symlink spellings (DENY) ==="
ln -s ../projects/p/tickets "$ROOT/docs/familiar"
deny "dot-dot out of own log"         "$ROOT/logs/familiar/../../queue.md" "protected surface"
deny "dot-dot into tickets"           "$ROOT/docs/drafts/../../projects/p/tickets/T.md" "is a ticket"
deny "doubled slashes"                "$ROOT//logs//familiar//..//..//queue.md" "protected surface"
deny "relative ./queue.md"            "./queue.md" "protected surface" "$ROOT"
deny "relative ../queue.md"           "../../queue.md" "protected surface" "$ROOT/logs/familiar"
deny "symlinked file -> queue.md"     "$ROOT/logs/familiar/link.md" "protected surface"
deny "symlinked dir -> tickets"       "$ROOT/docs/familiar/T-1.md" "is a ticket"
deny "dot-dot out of the root"        "$ROOT/../outside.md" "not on the Familiar write allow-list"

echo "=== data root: data dirs symlinked out of the kit (nested and external) ==="
for layout in nested external; do
  K="$TMP/kit-$layout"
  if [ "$layout" = nested ]; then D="$K/ship-data"; else D="$TMP/data-$layout"; fi
  mkdir -p "$K/modules/familiar/hooks" "$D/logs/familiar" "$D/projects/p/tickets" "$D/state" "$D/docs" "$D/inbox/drops"
  cp "$SRC" "$K/modules/familiar/hooks/"
  : > "$D/queue.md"
  for e in logs projects state docs inbox queue.md; do ln -s "$D/$e" "$K/$e"; done
  HOOK="$K/modules/familiar/hooks/validate-familiar-write.sh"
  allow "$layout: own log via kit path"     "$K/logs/familiar/2026-11-12.md"
  allow "$layout: own log via data path"    "$D/logs/familiar/2026-11-12.md"
  allow "$layout: draft"                    "$K/state/familiar/drafts/x.md"
  deny  "$layout: queue via kit path"       "$K/queue.md" "protected surface"
  deny  "$layout: queue via data path"      "$D/queue.md" "protected surface"
  deny  "$layout: ticket via kit path"      "$K/projects/p/tickets/T.md" "is a ticket"
  deny  "$layout: ticket via data path"     "$D/projects/p/tickets/T.md" "is a ticket"
  deny  "$layout: raw drop via data path"   "$D/inbox/drops/familiar-x.md" "only through familiar_drop.py"
  deny  "$layout: data-root state file"     "$D/state/status.json" "not on the Familiar write allow-list"
done
HOOK="$ROOT/modules/familiar/hooks/validate-familiar-write.sh"

echo "=== names are matched whole (DENY) ==="
run_json "$(python3 -c 'import json,sys; print(json.dumps({"tool_input":{"file_path":sys.argv[1]+"/logs/familiar/x.md\n"}}))' "$ROOT")"
if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"not on the Familiar write allow-list"* ]]; then ok; else bad "deny: trailing newline in an allowed name"; fi

echo "=== a json.py in the session cwd cannot shadow the stdlib (DENY) ==="
mkdir -p "$TMP/evilcwd" && printf 'import sys\nsys.exit(0)\n' > "$TMP/evilcwd/json.py"
OUT=$(cd "$TMP/evilcwd" && printf '{"tool_input":{"file_path":"%s/state/status.json"}}' "$ROOT" | bash "$HOOK" 2>&1); CODE=$?
if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"familiar-write DENY"* ]]; then ok; else bad "cwd json.py shadowed the stdlib"; fi

echo "=== malformed payloads (DENY, fail closed) ==="
run_json '{"tool_input":{}}';             if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"no file_path"* ]]; then ok; else bad "no file_path"; fi
run_json 'not json';                      if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"malformed"* ]]; then ok; else bad "malformed"; fi
run_json '';                              if [ "$CODE" -eq 2 ]; then ok; else bad "empty payload"; fi
run_json '["a list"]';                    if [ "$CODE" -eq 2 ]; then ok; else bad "non-object payload"; fi
run_json '{"tool_input":{"file_path":7}}'; if [ "$CODE" -eq 2 ]; then ok; else bad "non-string path"; fi

echo
echo "validate-familiar-write: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
