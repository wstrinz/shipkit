#!/bin/bash
# Test suite for launch-familiar.sh — the double-boot guard and the launch call.
# Usage: bash modules/familiar/tests/test-launch-familiar.sh
#
# A stub `claude` (SHIP_CLAUDE_BIN) answers `agents --json` from a fixture and records any
# launch instead of starting a model, so this suite never spends money.
set -uo pipefail

LAUNCHER="$(cd "$(dirname "$0")/.." && pwd)/scripts/launch-familiar.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/launch-familiar.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
STUB="$TMP/claude"
cat > "$STUB" <<'EOF'
#!/bin/bash
if [ "${1:-}" = "agents" ]; then
  [ -n "${STUB_AGENTS_RC:-}" ] && exit "$STUB_AGENTS_RC"
  cat "$STUB_AGENTS"
  exit 0
fi
{ printf 'ARGS:'; printf ' %s' "$@"; printf '\nSTDIN:'; cat; printf '\n'; } >> "$STUB_LAUNCHES"
exit "${STUB_LAUNCH_RC:-0}"
EOF
chmod +x "$STUB"

PASS=0; FAIL=0
# run <mode> <agents-json> [env assignments...] -> OUT, CODE, LAUNCHES (count), ROOT
run() {
  local mode="$1" agents="$2"; shift 2
  ROOT="$TMP/ship-$PASS-$FAIL-$RANDOM"
  mkdir -p "$ROOT/agents"
  printf '%s' "$agents" > "$ROOT/agents.json"
  : > "$ROOT/launches"
  printf 'command: "bash /k/modules/familiar/hooks/validate-familiar-bash.sh"\ncommand: "bash /k/modules/familiar/hooks/validate-familiar-write.sh"\n' \
    > "$ROOT/agents/ship-familiar.md"
  OUT=$(env SHIP_ROOT="$ROOT" SHIP_CLAUDE_BIN="$STUB" SHIP_SANDBOX_RUN="$TMP/none" \
        SHIP_AGENTS_DIR="$ROOT/agents" STUB_AGENTS="$ROOT/agents.json" STUB_LAUNCHES="$ROOT/launches" "$@" \
        bash "$LAUNCHER" $mode 2>&1)
  CODE=$?
  LAUNCHES=$(grep -c '^ARGS:' "$ROOT/launches")
}
expect() { # expect <name> <code> <launches> <substring>
  if [ "$CODE" -eq "$2" ] && [ "$LAUNCHES" -eq "$3" ] && [[ "$OUT" == *"$4"* ]]; then
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1)); echo "  FAIL: $1 (rc=$CODE launches=$LAUNCHES)"; echo "$OUT" | sed 's/^/    | /'
  fi
}
record() { mkdir -p "$ROOT/state/familiar"; printf '{"launched_at": "%s", "name": "x"}\n' "$1" > "$ROOT/state/familiar/launch.json"; }

NONE='[]'
LIVE='[{"id":"a1","name":"familiar 11-12-2000Z","state":"running","status":"idle"}]'
DONE='[{"id":"a1","name":"familiar 11-12-2000Z","state":"done","status":"idle"}]'
BY_AGENT='[{"id":"b2","name":"seat","agent":"ship-familiar","state":"running"}]'
OTHER='[{"id":"c3","name":"mate 11-12","agent":"ship-mate","state":"running"}]'

echo "=== --check never launches ==="
run --check "$NONE";      expect "check none"            0 0 "Familiar: NONE"
run --check "$LIVE";      expect "check live"            0 0 "Familiar: LIVE"
run --check "$NONE" STUB_AGENTS_RC=1; expect "check scan fail" 0 0 "Familiar: UNKNOWN"

echo "=== --ensure launches only when nothing is live ==="
run --ensure "$NONE";     expect "ensure none launches"  0 1 "launching a background Familiar"
grep -q 'ARGS: --bg --agent ship-familiar --name familiar .* --permission-mode auto' "$ROOT/launches" && grep -q 'STDIN:/familiar-wake' "$ROOT/launches" \
  && [ -f "$ROOT/state/familiar/launch.json" ] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "  FAIL: launch args/record"; cat "$ROOT/launches"; }
run --ensure "$LIVE";     expect "ensure live refuses"   0 0 "already live"
run --ensure "$BY_AGENT"; expect "live by agent field"   0 0 "already live"
run --ensure "$DONE";     expect "done seat is not live" 0 1 "launching"
run --ensure "$OTHER";    expect "other agents ignored"  0 1 "launching"
run "" "$LIVE";           expect "default mode is ensure" 0 0 "already live"

echo "=== --ensure refuses when it cannot tell ==="
run --ensure "$NONE" STUB_AGENTS_RC=1; expect "scan exit fail" 3 0 "REFUSED"
run --ensure "not json";  expect "scan unparseable"      3 0 "unparseable"
run --ensure '{"x":1}';   expect "scan wrong shape"      3 0 "REFUSED"

echo "=== launch grace ==="
run --check "$NONE"; record "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT=$(env SHIP_ROOT="$ROOT" SHIP_CLAUDE_BIN="$STUB" SHIP_SANDBOX_RUN="$TMP/none" STUB_AGENTS="$ROOT/agents.json" \
      SHIP_AGENTS_DIR="$ROOT/agents" STUB_LAUNCHES="$ROOT/launches" bash "$LAUNCHER" --ensure 2>&1); CODE=$?
LAUNCHES=$(grep -c '^ARGS:' "$ROOT/launches");     expect "fresh record holds"    0 0 "may still be booting"
record "2020-01-01T00:00:00Z"
OUT=$(env SHIP_ROOT="$ROOT" SHIP_CLAUDE_BIN="$STUB" SHIP_SANDBOX_RUN="$TMP/none" STUB_AGENTS="$ROOT/agents.json" \
      SHIP_AGENTS_DIR="$ROOT/agents" STUB_LAUNCHES="$ROOT/launches" bash "$LAUNCHER" --ensure 2>&1); CODE=$?
LAUNCHES=$(grep -c '^ARGS:' "$ROOT/launches");     expect "stale record launches" 0 1 "launching"

echo "=== enforcement probe ==="
run --check "$NONE";      expect "check probes the hooks"  0 0 "hooks: OK"
run --ensure "$NONE" SHIP_AGENTS_DIR="$TMP/no-such-dir"
expect "no installed def: refuse" 4 0 "not installed"
run --check "$NONE" SHIP_AGENTS_DIR="$TMP/no-such-dir"
expect "no installed def: check says so" 0 0 "not installed"
run --ensure "$NONE" SHIP_FAMILIAR_PERMISSION_MODE=bypassPermissions
expect "permission fallback" 0 1 "launching"
grep -q -- '--permission-mode bypassPermissions' "$ROOT/launches" && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "  FAIL: permission fallback not passed"; }

echo "=== --force, failures, usage ==="
run --force "$LIVE";      expect "force past live"       0 1 "launching"
run --ensure "$NONE" STUB_LAUNCH_RC=1; expect "failed launch" 1 1 "launch FAILED"
[ ! -f "$ROOT/state/familiar/launch.json" ] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "  FAIL: record after failed launch"; }
run --bogus "$NONE";      expect "bad mode"              2 0 "usage"
run "--check --force" "$NONE"; expect "two modes"        2 0 "usage"

echo
echo "launch-familiar: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
