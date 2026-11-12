#!/bin/bash
# Test suite for validate-navigator-write.sh (the Navigator's Write/Edit allow-list).
# Usage: bash modules/navigator/tests/test-navigator-write.sh
#
# Runs the hook from a copy inside a throwaway ship tree. Every deny asserts its message, so a
# deny for the wrong reason (or a crash) fails.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)/hooks/validate-navigator-write.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/navigator-write.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/ship"
mkdir -p "$ROOT/modules/navigator/hooks" "$ROOT/docs/drafts" "$ROOT/projects/p/tickets" "$ROOT/state"
cp "$SRC" "$ROOT/modules/navigator/hooks/"
HOOK="$ROOT/modules/navigator/hooks/validate-navigator-write.sh"
ROOT="$(cd "$ROOT" && pwd -P)"
ln -s ../../queue.md "$ROOT/docs/drafts/link.md"

PASS=0; FAIL=0
payload() { # payload <file_path> [content] [cwd]
  python3 -c 'import json,sys
d={"tool_input":{"file_path":sys.argv[1]}}
if sys.argv[2]: d["tool_input"]["content"]=sys.argv[2]
if sys.argv[3]: d["cwd"]=sys.argv[3]
print(json.dumps(d))' "$1" "${2:-}" "${3:-}"
}
run() { OUT=$(payload "$@" | bash "$HOOK" 2>&1); CODE=$?; }
ok()  { PASS=$((PASS+1)); }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $1 (rc=$CODE: $OUT)"; }
allow() { local n="$1"; shift; run "$@"; if [ "$CODE" -eq 0 ]; then ok; else bad "allow: $n"; fi; }
deny()  { local n="$1" want="$2"; shift 2; run "$@"
  if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"$want"* ]]; then ok; else bad "deny: $n"; fi; }

echo "=== allow-list (ALLOW) ==="
allow "a ticket"                    "$ROOT/projects/p/tickets/T-1.md"
allow "a project doc, nested"       "$ROOT/projects/p/docs/design/notes.md"
allow "a draft"                     "$ROOT/docs/drafts/proposal.md"
allow "memory"                      "$ROOT/memory/findings/x.md"
allow "a queue-change drop"         "$ROOT/inbox/drops/nav-20261112-reprioritize.md" "---
kind: steer
source: navigator
---
move X up"
allow "relative ticket path"        "projects/p/tickets/T-2.md" "" "$ROOT"
allow "near-miss name queue-notes"  "$ROOT/docs/drafts/queue-notes.md"

echo "=== queue and protected surfaces (DENY) ==="
deny "queue.md"                     "protected surface" "$ROOT/queue.md"
deny "queue-archive.md"             "protected surface" "$ROOT/queue-archive.md"
deny "captain.md"                   "protected surface" "$ROOT/captain.md"
deny "queue.md under drafts"        "protected surface" "$ROOT/docs/drafts/QUEUE.md"

echo "=== Familiar impersonation and mailbox gating (DENY) ==="
deny "familiar-* drop name"         "Familiar commands" "$ROOT/inbox/drops/familiar-20261112T000000Z-x.md"
deny "source: familiar in content"  "may not declare source: familiar" "$ROOT/inbox/drops/nav-x.md" "---
source: familiar
kind: steer
---"
deny "quoted source familiar"       "may not declare source: familiar" "$ROOT/inbox/drops/nav-y.md" '"source": "familiar"'
deny "inbox/familiar, module off"   "not enabled" "$ROOT/inbox/familiar/20261112T000000Z-result.md"
allow "source: familiar-bot is not a claim" "$ROOT/inbox/drops/nav-z.md" "source: familiar-bot"
echo '{"modules": ["core", "autonomous", "wake-monitor", "familiar", "navigator"]}' > "$ROOT/state/install.json"
allow "inbox/familiar, module on"   "$ROOT/inbox/familiar/20261112T000000Z-result.md"
deny "inbox/familiar/read, module on" "not on the Navigator write allow-list" "$ROOT/inbox/familiar/read/x.md"
deny "drops, module on: one commander" "one commander" "$ROOT/inbox/drops/nav-20261112-reprioritize.md" "kind: steer"
rm "$ROOT/state/install.json"

echo "=== everything else (DENY) ==="
deny "state"                        "not on the Navigator write allow-list" "$ROOT/state/status.json"
deny "install record"               "not on the Navigator write allow-list" "$ROOT/state/install.json"
deny "a mate log"                   "not on the Navigator write allow-list" "$ROOT/logs/mate/2026-11-12.md"
deny "a role doc"                   "not on the Navigator write allow-list" "$ROOT/core/mate.md"
deny "its own hook"                 "not on the Navigator write allow-list" "$HOOK"
deny "code in a draft dir"          "not on the Navigator write allow-list" "$ROOT/docs/drafts/x.py"
deny "drop subdir"                  "not on the Navigator write allow-list" "$ROOT/inbox/drops/processed/x.md"
deny "captain inbox"                "protected surface" "$ROOT/inbox/captain.md"
deny "outside the root"             "not on the Navigator write allow-list" "/etc/nav.md"

echo "=== traversal and symlink spellings (DENY) ==="
mkdir -p "$ROOT/projects/q" && ln -s ../../state "$ROOT/projects/q/docs"
deny "dot-dot to queue"             "protected surface" "$ROOT/docs/drafts/../../queue.md"
deny "dot-dot into state"           "not on the Navigator write allow-list" "$ROOT/projects/p/tickets/../../../state/x.md"
deny "relative ../../queue.md"      "protected surface" "../../queue.md" "" "$ROOT/projects/p"
deny "symlinked file -> queue.md"   "protected surface" "$ROOT/docs/drafts/link.md"
deny "symlinked dir -> state"       "not on the Navigator write allow-list" "$ROOT/projects/q/docs/x.md"

echo "=== data root: data dirs symlinked out of the kit (nested and external) ==="
for layout in nested external; do
  K="$TMP/kit-$layout"
  if [ "$layout" = nested ]; then D="$K/ship-data"; else D="$TMP/data-$layout"; fi
  mkdir -p "$K/modules/navigator/hooks" "$D/projects/p/tickets" "$D/state" "$D/docs/drafts" "$D/inbox/drops" "$D/logs"
  cp "$SRC" "$K/modules/navigator/hooks/"
  : > "$D/queue.md"
  for e in logs projects state docs inbox queue.md; do ln -s "$D/$e" "$K/$e"; done
  HOOK="$K/modules/navigator/hooks/validate-navigator-write.sh"
  allow "$layout: ticket via kit path"    "$K/projects/p/tickets/T.md"
  allow "$layout: ticket via data path"   "$D/projects/p/tickets/T.md"
  allow "$layout: draft"                  "$K/docs/drafts/x.md"
  allow "$layout: drop"                   "$K/inbox/drops/nav-x.md"
  deny  "$layout: queue via kit path"     "protected surface" "$K/queue.md"
  deny  "$layout: queue via data path"    "protected surface" "$D/queue.md"
  deny  "$layout: state via data path"    "not on the Navigator write allow-list" "$D/state/x.md"
  echo '{"modules": ["familiar"]}' > "$D/state/install.json"
  deny  "$layout: record read via link"   "one commander" "$K/inbox/drops/nav-y.md"
done
HOOK="$ROOT/modules/navigator/hooks/validate-navigator-write.sh"

echo "=== content guard on the RESULTING file, any line break; fullmatch names (DENY) ==="
mkdir -p "$ROOT/inbox/drops"
printf -- '---\nsource: navigator\nkind: steer\n---\n' > "$ROOT/inbox/drops/nav-edit.md"
edit_json() { python3 -c 'import json,sys; print(json.dumps({"tool_input":{"file_path":sys.argv[1],"old_string":sys.argv[2],"new_string":sys.argv[3]}}))' "$@"; }
OUT=$(edit_json "$ROOT/inbox/drops/nav-edit.md" "navigator" "familiar" | bash "$HOOK" 2>&1); CODE=$?
if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"may not declare source: familiar"* ]]; then ok; else bad "deny: Edit turns source into familiar"; fi
OUT=$(python3 -c 'import json,sys; print(json.dumps({"tool_input":{"file_path":sys.argv[1],"edits":[{"old_string":"navigator","new_string":"fam"},{"old_string":"fam","new_string":"familiar"}]}}))' "$ROOT/inbox/drops/nav-edit.md" | bash "$HOOK" 2>&1); CODE=$?
if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"may not declare source: familiar"* ]]; then ok; else bad "deny: MultiEdit builds source familiar in two steps"; fi
for sep in cr vt ff ls nel; do
  OUT=$(python3 -c 'import json,sys; s={"cr":"\r","vt":"\v","ff":"\f","ls":" ","nel":"\x85"}[sys.argv[2]]; print(json.dumps({"tool_input":{"file_path":sys.argv[1],"content":"---"+s+"source: familiar"+s+"---"}}))' "$ROOT/inbox/drops/nav-sep.md" "$sep" | bash "$HOOK" 2>&1); CODE=$?
  if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"may not declare source: familiar"* ]]; then ok; else bad "deny: line break $sep hides source: familiar"; fi
done
OUT=$(edit_json "$ROOT/inbox/drops/nav-edit.md" "kind: steer" "kind: steer" | bash "$HOOK" 2>&1); CODE=$?
if [ "$CODE" -eq 0 ]; then ok; else bad "allow: harmless Edit of a navigator drop ($OUT)"; fi
deny "trailing newline in a ticket name" "not on the Navigator write allow-list" "$ROOT/projects/p/tickets/T.md
"
deny "trailing newline in a drop name" "not on the Navigator write allow-list" "$ROOT/inbox/drops/x.md
"

echo "=== a json.py in the session cwd cannot shadow the stdlib (DENY) ==="
mkdir -p "$TMP/evilcwd" && printf 'import sys\nsys.exit(0)\n' > "$TMP/evilcwd/json.py"
P=$(payload "$ROOT/state/status.json")
OUT=$(cd "$TMP/evilcwd" && printf '%s' "$P" | bash "$HOOK" 2>&1); CODE=$?
if [ "$CODE" -eq 2 ] && [[ "$OUT" == *"is not on the Navigator write allow-list"* ]]; then ok; else bad "cwd json.py shadowed the stdlib"; fi

echo "=== malformed payloads (DENY, fail closed) ==="
for p in 'not json' '["x"]' '{"tool_input":{}}' '{"tool_input":{"file_path":7}}'; do
  out=$(printf '%s' "$p" | bash "$HOOK" 2>&1); rc=$?
  if [ "$rc" -eq 2 ] && [[ "$out" == *"navigator-write DENY"* ]]; then ok; else
    FAIL=$((FAIL+1)); echo "  FAIL: malformed payload: $p (rc=$rc)"; fi
done

echo
echo "validate-navigator-write: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
