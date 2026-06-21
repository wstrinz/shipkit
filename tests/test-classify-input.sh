#!/bin/bash
# Test suite for classify_input.sh — the 3-step declared-input ladder.
# Usage: ./tests/test-classify-input.sh   (or: scripts/classify_input.sh --test)
#
# bash-3.2-safe: no `declare -A`, no empty-array subscripts. Fixtures are
# written to a temp dir and cleaned up on exit.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLASSIFY="$SCRIPT_DIR/../scripts/classify_input.sh"
PASS=0
FAIL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/classify-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# write_fixture <name> with heredoc on stdin -> sets global FIXTURE to the path.
# (Sets a global rather than echoing via $(...) so a heredoc body can contain
# apostrophes/parens without confusing bash-3.2's command-substitution parser.)
FIXTURE=""
write_fixture() {
  FIXTURE="$TMP/$1"
  cat > "$FIXTURE"
}

# expect_class <expected> <fixture-path> <label>
# Asserts stdout class only (stderr ignored).
expect_class() {
  local expected="$1" path="$2" label="$3"
  local got
  got="$("$CLASSIFY" "$path" 2>/dev/null || true)"
  if [ "$got" = "$expected" ]; then
    PASS=$((PASS + 1))
  else
    printf "  FAIL: expected class %-7s got %-7s  [%s]\n" "$expected" "$got" "$label"
    FAIL=$((FAIL + 1))
  fi
}

# expect_warn <yes|no> <fixture-path> <label>
# Asserts whether a stderr warning was emitted (undeclared heuristic path).
expect_warn() {
  local want="$1" path="$2" label="$3"
  local err
  err="$("$CLASSIFY" "$path" 2>&1 >/dev/null || true)"
  local got="no"
  case "$err" in *"heuristically classified"*) got="yes" ;; esac
  if [ "$got" = "$want" ]; then
    PASS=$((PASS + 1))
  else
    printf "  FAIL: expected warn=%-3s got warn=%-3s  [%s]\n" "$want" "$got" "$label"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Step 1: declared wake_class is authoritative ==="

write_fixture wake.md <<'EOF'
---
shipkit_input: v1
source: status-surface
kind: steer
wake_class: wake
---
do the thing
EOF
expect_class wake "$FIXTURE" "wake_class: wake -> wake"
expect_warn no "$FIXTURE" "declared wake_class -> no warning"

write_fixture batch.md <<'EOF'
---
shipkit_input: v1
source: pr-buddy
kind: sensor-redrop
wake_class: batch
---
PR 6 unchanged
EOF
expect_class batch "$FIXTURE" "wake_class: batch -> batch"
expect_warn no "$FIXTURE" "declared wake_class -> no warning"

write_fixture silent.md <<'EOF'
---
shipkit_input: v1
source: noisy-sensor
kind: notification
wake_class: silent
---
heartbeat ping (pure noise)
EOF
expect_class silent "$FIXTURE" "wake_class: silent -> silent"
expect_warn no "$FIXTURE" "declared wake_class -> no warning"

# wake_class overrides a kind that would otherwise default the other way.
write_fixture override.md <<'EOF'
---
shipkit_input: v1
kind: steer
wake_class: batch
---
declared steer but author wants it batched
EOF
expect_class batch "$FIXTURE" "wake_class beats kind table"

# JSON-shaped declaration (thread/signal event).
write_fixture event.json <<'EOF'
{"shipkit_input":"v1","source":"thread","kind":"comment","wake_class":"wake","body":"hi"}
EOF
expect_class wake "$FIXTURE" "JSON wake_class: wake -> wake"
expect_warn no "$FIXTURE" "JSON declared -> no warning"

echo "=== Step 2: kind-only (no wake_class) -> kind->class table ==="

write_fixture kind-steer.md <<'EOF'
---
shipkit_input: v1
source: captain-ui
kind: steer
---
a directive
EOF
expect_class wake "$FIXTURE" "kind: steer -> wake"
expect_warn no "$FIXTURE" "kind declared -> no warning"

write_fixture kind-statusreq.md <<'EOF'
---
kind: status-request
---
status please
EOF
expect_class wake "$FIXTURE" "kind: status-request -> wake"

write_fixture kind-redrop.md <<'EOF'
---
shipkit_input: v1
source: pr-buddy
kind: sensor-redrop
---
unchanged PR state
EOF
expect_class batch "$FIXTURE" "kind: sensor-redrop -> batch"
expect_warn no "$FIXTURE" "kind declared -> no warning"

write_fixture kind-notif.md <<'EOF'
---
kind: notification
---
fyi
EOF
expect_class batch "$FIXTURE" "kind: notification -> batch"

write_fixture kind-unknown.md <<'EOF'
---
kind: some-future-kind
---
unrecognized but declared
EOF
expect_class wake "$FIXTURE" "kind: unknown -> wake (directive floor)"

echo "=== Step 3: undeclared -> heuristic + stderr warning ==="

write_fixture legacy-steer.md <<'EOF'
---
type: steer
title: "legacy steer, no envelope"
---
old-style directive
EOF
expect_class wake "$FIXTURE" "legacy type: steer -> wake (heuristic)"
expect_warn yes "$FIXTURE" "undeclared -> warning emitted"

write_fixture legacy-bookkeeping.md <<'EOF'
---
type: status-applied
---
bookkeeping
EOF
expect_class batch "$FIXTURE" "legacy type: status-applied -> batch (heuristic)"
expect_warn yes "$FIXTURE" "undeclared bookkeeping -> warning emitted"

write_fixture bare.md <<'EOF'
just a plain chat message with no frontmatter at all
EOF
expect_class wake "$FIXTURE" "bare undeclared -> wake (heuristic floor)"
expect_warn yes "$FIXTURE" "bare undeclared -> warning emitted"

echo "=== Always-on guards ==="

# Self-authored wins even over a (mistaken) wake_class: wake declaration.
write_fixture self.md <<'EOF'
---
shipkit_input: v1
source: mate
kind: steer
wake_class: wake
---
the loop's own surface
EOF
expect_class batch "$FIXTURE" "source: mate -> batch (self-author guard)"

# Unknown wake_class value -> ignored, falls through to kind table.
write_fixture badclass.md <<'EOF'
---
kind: steer
wake_class: bogus
---
mistyped wake_class
EOF
expect_class wake "$FIXTURE" "unknown wake_class -> ignored, kind: steer -> wake"

echo ""
echo "---"
echo "Passed: $PASS  Failed: $FAIL"
[ "$FAIL" -eq 0 ] && echo "All tests passed." || exit 1
