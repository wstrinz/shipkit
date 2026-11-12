#!/bin/bash
# Test suite for validate-crew-write.sh (the crew Write/Edit path guard)
# Usage: ./core/tests/test-crew-write.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../hooks/validate-crew-write.sh"
SHIP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PASS=0
FAIL=0

# jq is required — this suite builds the hook's stdin JSON with `jq -n`. Fail fast with a
# clear message instead of cascading per-case failures if jq is absent.
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required to run this suite. Install jq (brew install jq / apt-get install jq) and re-run." >&2
  exit 2
fi

check() {
  local expected="$1" path="$2" cwd="${3:-}"
  local json
  json=$(jq -n --arg fp "$path" --arg cwd "$cwd" \
    '{"tool_input":{"file_path":$fp}} + (if $cwd != "" then {"cwd":$cwd} else {} end)')
  local result
  if echo "$json" | bash "$HOOK" >/dev/null 2>&1; then
    result="ALLOW"
  else
    result="BLOCK"
  fi
  if [ "$result" = "$expected" ]; then
    PASS=$((PASS + 1))
  else
    printf "  FAIL: expected %-5s got %-5s  %s (cwd=%s)\n" "$expected" "$result" "$path" "${cwd:-—}"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Ship-state boundaries (BLOCK) ==="
check BLOCK "$SHIP_DIR/queue.md"
check BLOCK "$SHIP_DIR/queue-archive.md"
check BLOCK "$SHIP_DIR/captain.md"
check BLOCK "$SHIP_DIR/inbox/captain.md"
check BLOCK "$SHIP_DIR/inbox/drops/ci-2026-07-13-0900-note.md"

echo "=== Relative + traversal forms (BLOCK) ==="
check BLOCK "queue.md" "$SHIP_DIR"
check BLOCK "./queue.md" "$SHIP_DIR"
check BLOCK "../queue.md" "$SHIP_DIR/logs"
check BLOCK "$SHIP_DIR/logs/../queue.md"
check BLOCK "../queue-archive.md" "$SHIP_DIR/logs"
check BLOCK "inbox/captain.md" "$SHIP_DIR"

echo "=== Legitimate crew writes (ALLOW) ==="
check ALLOW "$SHIP_DIR/logs/proj/TICKET-1/2026-07-13-1200.md"
check ALLOW "$SHIP_DIR/projects/proj/tickets/TICKET-1.md"
check ALLOW "$SHIP_DIR/docs/knowledge/env-config.md"
check ALLOW "/home/user/some-target-repo/src/main.py"
check ALLOW "/home/user/some-target-repo/queue.md"          # same basename, different tree
check ALLOW "$SHIP_DIR/modules/queue-split/templates/queue-archive.md"  # the template, not the archive
check ALLOW "/home/user/some-target-repo/inbox/handler.py"  # 'inbox' outside the ship
check ALLOW "src/lib/util.ts" "/home/user/some-target-repo"

echo "=== Data root: dirs linked, root files in the data root, stubs left (BLOCK all) ==="
TMP=$(mktemp -d -t crew-write-test.XXXXXX)
mkdir -p "$TMP/ship/core/hooks" "$TMP/ship/lib" "$TMP/data/inbox/drops" "$TMP/data/logs" \
  "$TMP/data/state"
cp "$HOOK" "$TMP/ship/core/hooks/"
cp "$SHIP_DIR/lib/ship_data.py" "$TMP/ship/lib/"
touch "$TMP/data/queue.md" "$TMP/data/captain.md" "$TMP/ship/queue.md" "$TMP/ship/captain.md"
ln -s ../data/inbox "$TMP/ship/inbox"
ln -s ../data/logs "$TMP/ship/logs"
ln -s ../data/state "$TMP/ship/state"
REAL_HOOK="$HOOK"
HOOK="$TMP/ship/core/hooks/validate-crew-write.sh"
check BLOCK "$TMP/ship/queue.md"
check BLOCK "$TMP/data/queue.md"
check BLOCK "$TMP/data/captain.md"
check BLOCK "$TMP/data/queue-archive.md"
check BLOCK "$TMP/ship/queue-archive.md"
check BLOCK "$TMP/ship/inbox/drops/x.md"
check BLOCK "$TMP/data/inbox/drops/x.md"
check BLOCK "../data/queue.md" "$TMP/ship"
check BLOCK "$TMP/DATA/Queue.md"
check BLOCK "$TMP/ship/INBOX/drops/x.md"
check ALLOW "$TMP/ship/logs/proj/T-1/2026-07-13-1200.md"
check ALLOW "$TMP/data/logs/proj/T-1/2026-07-13-1200.md"
check ALLOW "$TMP/data/state/status.json"
# A Unicode fold `tr` misses: U+017F LONG S, which APFS treats as "s".
if [ -e "$TMP/data/ſtate" ]; then
  check BLOCK "$TMP/ſhip/queue.md"
  check BLOCK "$TMP/data/queue-archive.md" "$TMP/ſhip"
  check BLOCK "$TMP/ſhip/inbox/drops/x.md"
else
  echo "  (skip: this filesystem doesn't fold ſ to s)"
fi
HOOK="$REAL_HOOK"
rm -rf "$TMP"

echo "=== A state/ link alone is not a data root (no stub, no queue.md beside it) ==="
TMP=$(mktemp -d -t crew-write-test.XXXXXX)
mkdir -p "$TMP/ship/core/hooks" "$TMP/ship/lib" "$TMP/elsewhere/state"
cp "$REAL_HOOK" "$TMP/ship/core/hooks/"
cp "$SHIP_DIR/lib/ship_data.py" "$TMP/ship/lib/"
touch "$TMP/ship/queue.md"
ln -s ../elsewhere/state "$TMP/ship/state"
HOOK="$TMP/ship/core/hooks/validate-crew-write.sh"
check BLOCK "$TMP/ship/queue.md"
check ALLOW "$TMP/elsewhere/queue.md"
rm "$TMP/ship/state"
ln -s ../gone/state "$TMP/ship/state"
check BLOCK "$TMP/ship/queue.md"
check ALLOW "$TMP/gone/queue.md"
HOOK="$REAL_HOOK"
rm -rf "$TMP"

echo "=== Non-file payloads (ALLOW — nothing to guard) ==="
json='{"tool_input":{"command":"git status"}}'
if echo "$json" | bash "$HOOK" >/dev/null 2>&1; then PASS=$((PASS + 1)); else
  echo "  FAIL: expected ALLOW for non-file payload"; FAIL=$((FAIL + 1)); fi
json='{"tool_input":{}}'
if echo "$json" | bash "$HOOK" >/dev/null 2>&1; then PASS=$((PASS + 1)); else
  echo "  FAIL: expected ALLOW for empty tool_input"; FAIL=$((FAIL + 1)); fi

echo
echo "Passed: $PASS  Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo "All crew-write tests passed."
