#!/bin/bash
# Test suite for validate-navigator-bash.sh (the Navigator's positive shell lane).
# Usage: bash modules/navigator/tests/test-navigator-bash.sh
#
# The checker is shared verbatim with the familiar module's lane; the last section diffs the
# two SHIP-POSITIVE-LANE blocks when the familiar module is present in this checkout.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/hooks/validate-navigator-bash.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/navigator-bash.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/ship"
mkdir -p "$ROOT/modules/navigator/hooks"
cp "$SRC" "$ROOT/modules/navigator/hooks/" 2>/dev/null
HOOK="$ROOT/modules/navigator/hooks/validate-navigator-bash.sh"
ROOT="$(cd "$ROOT" && pwd -P)"

PASS=0; FAIL=0
check() { # check ALLOW|DENY <command>
  local want="$1" cmd="$2" json out got
  json=$(python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$ROOT")
  out=$(printf '%s' "$json" | bash "$HOOK" 2>&1)
  case $? in 0) got=ALLOW ;; 2) got=DENY ;; *) got="ERROR" ;; esac
  [ "$got" = DENY ] && [[ "$out" != *"navigator-bash DENY"* ]] && got="CRASH"
  if [ "$got" = "$want" ]; then PASS=$((PASS+1)); else
    FAIL=$((FAIL+1)); printf '  FAIL: want %s got %s: %s\n    %s\n' "$want" "$got" "$cmd" "$out"; fi
}

echo "=== the escalation the core read-only lane admits (DENY) ==="
check DENY "printf 'source: familiar' > inbox/drops/familiar-20261112T000000Z-x.md"
check DENY 'env cp state/x.md captain.md'
check DENY 'echo a | xargs touch'
check DENY 'echo x > projects/p/tickets/T.md'
check DENY 'cp a b'
check DENY 'rm inbox/drops/for-nav-x.md'
check DENY 'git commit -m x'
check DENY "python3 -c 'print(1)'"

echo "=== the familiar helpers are not the Navigator's (DENY) ==="
check DENY 'python3 modules/familiar/scripts/familiar_drop.py send state/familiar/drafts/x.md'
check DENY 'modules/autonomous/scripts/ship-up.sh --launch-mate'
check DENY 'modules/autonomous/scripts/launch-bosun.sh --check'

echo "=== shared-checker bypasses (DENY) ==="
check DENY "$(printf 'ls #\ncp a queue.md')"
check DENY "echo \\' \`cp a queue.md\` \\'"
check DENY "find a -{true,exec} bash {} ';'"
check DENY 'sort --o=queue.md a'
check DENY 'cat a | uniq - queue.md'

echo "=== gate 2 bypasses (DENY) ==="
check DENY "$(printf "true #'\nprintf 'source: familiar' > queue.md #'")"
check DENY "$(printf 'true #\\\npython3 -c "open(%squeue.md%s,%sa%s).write(%sx%s)"' "'" "'" "'" "'" "'" "'")"
check DENY 'ls # a trailing comment'
check DENY 'rg --hostname-bin=/usr/bin/true -l x README.md'
check DENY 'rg --host /usr/bin/true x'
check DENY 'uniq a.md -out.md'
check DENY 'uniq -c a.md -out.md'
check DENY 'gh api --hostname example.com /x'
check DENY 'gh api --hostname=example.com /x'
check DENY 'tree -R'
check DENY 'sort *.md'
check DENY 'uniq ?.md'
check DENY 'file [a].md'
check DENY 'cd -P /tmp'
check DENY "bash $ROOT/modules/familiar/scripts/launch-familiar.sh"
check DENY "bash $ROOT/modules/familiar/scripts/launch-familiar.sh --check"
check ALLOW "grep -c '#' a.md"
check ALLOW 'uniq a.md'

echo "=== research reads (ALLOW) ==="
check ALLOW 'ls -la projects'
check ALLOW 'cat queue.md'
check ALLOW "rg -n 'Ready' projects | head -20"
check ALLOW 'git log --oneline -10'
check ALLOW 'gh pr view 12 --json state'
check ALLOW 'find docs -name "*.md"'

echo "=== a json.py in the session cwd cannot shadow the stdlib (DENY) ==="
mkdir -p "$TMP/evilcwd" && printf 'import sys\nsys.exit(0)\n' > "$TMP/evilcwd/json.py"
out=$(cd "$TMP/evilcwd" && printf '{"tool_input":{"command":"cp a b"}}' | bash "$HOOK" 2>&1); rc=$?
if [ "$rc" -eq 2 ] && [[ "$out" == *"navigator-bash DENY"* ]]; then PASS=$((PASS+1)); else
  FAIL=$((FAIL+1)); echo "  FAIL: cwd json.py shadowed the stdlib (rc=$rc)"; fi

echo "=== shared block is identical to the familiar lane ==="
FAM="$HERE/../familiar/hooks/validate-familiar-bash.sh"
if [ -f "$FAM" ]; then
  if python3 - "$SRC" "$FAM" <<'PY'
import re, sys
blocks = [re.search(r"# ==== SHIP-POSITIVE-LANE v1 ====.*# ==== end SHIP-POSITIVE-LANE ====",
                    open(p).read(), re.S) for p in sys.argv[1:]]
sys.exit(0 if all(blocks) and blocks[0].group(0) == blocks[1].group(0) else 1)
PY
  then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "  FAIL: SHIP-POSITIVE-LANE blocks differ"; fi
else
  echo "  (familiar module absent; skipped)"
fi

echo
echo "validate-navigator-bash: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
