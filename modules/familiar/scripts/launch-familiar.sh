#!/bin/bash
# launch-familiar.sh — start or inspect the background Familiar seat.
#
#   launch-familiar.sh --check    # list live Familiar sessions and the last launch; launch nothing
#   launch-familiar.sh --ensure   # launch one ONLY if none is live (the default)
#   launch-familiar.sh --force    # launch even though one looks live
#
# Why it refuses: two Familiars send conflicting commands to one Mate. --ensure never launches
# past a live seat; it names it instead. It also refuses when the `claude agents --json` scan
# fails or returns something unparseable, because a scan that did not run is not a scan that
# found nothing. And it will not launch again within SHIP_FAMILIAR_LAUNCH_GRACE seconds
# (default 300) of its own last launch, which covers a seat that is booting but not yet listed.
#
# The scan sees background seats only. An interactive `claude --agent ship-familiar` in another
# terminal is invisible to it. `claude agents` status can be stale (familiar.md §11), so a listed
# session is treated as live unless its state is done: the guard errs toward refusing.
#
# ENFORCEMENT PROBE: before any launch (and in --check) it feeds each Familiar hook a command it
# must refuse and checks for the hook's own deny message, and checks the installed agent def
# names both hooks. A seat whose bright lines are unproven is not launched (exit 4).
#
# PERMISSION MODE: auto by default. SHIP_FAMILIAR_PERMISSION_MODE=bypassPermissions is the
# fallback for accounts without auto mode; the hooks fire in either mode.
#
# SANDBOX: point SHIP_SANDBOX_RUN at a wrapper that runs `claude <args>` sandboxed; absent, bare
# claude. Bash 3.2 compatible. Env seams for tests: SHIP_ROOT, SHIP_CLAUDE_BIN, SHIP_AGENTS_DIR.

set -uo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SHIP="${SHIP_ROOT:-$KIT}"
AGENT_DEF="${SHIP_AGENTS_DIR:-$HOME/.claude/agents}/ship-familiar.md"
PERM_MODE="${SHIP_FAMILIAR_PERMISSION_MODE:-auto}"
CLAUDE_BIN="${SHIP_CLAUDE_BIN:-claude}"
SANDBOX_RUN="${SHIP_SANDBOX_RUN:-$HOME/.config/sandbox-exec/run-sandboxed.sh}"
GRACE="${SHIP_FAMILIAR_LAUNCH_GRACE:-300}"
REC="$SHIP/state/familiar/launch.json"
cd "$SHIP" || { echo "FATAL: no ship root at $SHIP" >&2; exit 1; }
sbx() { if [ -x "$SANDBOX_RUN" ]; then "$SANDBOX_RUN" "$CLAUDE_BIN" "$@"; else "$CLAUDE_BIN" "$@"; fi; }

usage() { echo "usage: launch-familiar.sh [--check|--ensure|--force]" >&2; }

# Prints one "hooks: ..." line; returns non-zero if enforcement is not proven.
probe() {
  local hooks="$KIT/modules/familiar/hooks" q="queue"".md" out bad=""
  out=$(printf '{"tool_input":{"command":"echo x > %s"}}' "$q" | bash "$hooks/validate-familiar-bash.sh" 2>&1)
  [[ "$out" == *"familiar-bash DENY"* ]] || bad="$bad; the bash hook did not refuse a redirect"
  out=$(printf '{"tool_input":{"file_path":"%s/%s"}}' "$KIT" "$q" | bash "$hooks/validate-familiar-write.sh" 2>&1)
  [[ "$out" == *"familiar-write DENY"* ]] || bad="$bad; the write hook did not refuse the queue"
  if [ ! -f "$AGENT_DEF" ]; then
    bad="$bad; agent def not installed at $AGENT_DEF"
  elif ! grep -q 'validate-familiar-bash\.sh' "$AGENT_DEF" || ! grep -q 'validate-familiar-write\.sh' "$AGENT_DEF"; then
    bad="$bad; $AGENT_DEF does not wire both hooks"
  fi
  if [ -z "$bad" ]; then echo "hooks: OK (both refuse a probe; $AGENT_DEF wires both)"; return 0; fi
  echo "hooks: NOT PROVEN${bad#;}"
  return 1
}

# Prints "#SCAN ok" or "#SCAN fail <why>", then one "LIVE<TAB>id<TAB>name<TAB>status" per seat.
scan() {
  local raw rc
  raw=$("$CLAUDE_BIN" agents --json 2>/dev/null)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '#SCAN fail claude agents --json exited %s\n' "$rc"
    return
  fi
  printf '%s' "$raw" | python3 -c '
import json, sys
try:
    rows = json.load(sys.stdin)
    if isinstance(rows, dict):
        rows = rows.get("agents", rows.get("sessions"))
    if not isinstance(rows, list):
        raise ValueError("not a list")
except Exception as exc:
    print("#SCAN fail unparseable output (%s)" % exc.__class__.__name__)
    sys.exit(0)
print("#SCAN ok")
for a in rows:
    if not isinstance(a, dict) or a.get("state") == "done":
        continue
    name = str(a.get("name") or "")
    agent = {str(a.get(k) or "") for k in ("agent", "agentType", "agentSetting", "agent_type")}
    if name.lower().startswith("familiar") or "ship-familiar" in agent:
        print("LIVE\t%s\t%s\t%s" % (a.get("id", "?"), name, a.get("status", "?")))
'
}

# Seconds since the last recorded launch, or -1 when there is no readable record.
since_launch() {
  [ -f "$REC" ] || { echo -1; return; }
  python3 - "$REC" <<'PY' 2>/dev/null || echo -1
import json, sys
from datetime import datetime, timezone
d = json.load(open(sys.argv[1]))
t = datetime.strptime(d["launched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
print(int((datetime.now(timezone.utc) - t).total_seconds()))
PY
}

do_launch() {
  local name stamp
  stamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  name="familiar $(date -u +%m-%d-%H%MZ)"
  echo "launching a background Familiar: $name"
  if ! printf '%s' "/familiar-wake" | sbx --bg --agent ship-familiar --name "$name" \
      --permission-mode "$PERM_MODE"; then
    echo "launch FAILED (claude exited non-zero); no record written" >&2
    return 1
  fi
  mkdir -p "$(dirname "$REC")"
  printf '{"launched_at": "%s", "name": "%s"}\n' "$stamp" "$name" > "$REC"
  echo "launched. Verify: launch-familiar.sh --check, then today's logs/familiar/ file."
}

MODE="${1:---ensure}"
[ $# -le 1 ] || { usage; exit 2; }
case "$MODE" in --check|--ensure|--force) ;; *) usage; exit 2 ;; esac

SCAN=$(scan)
STATUS=$(printf '%s\n' "$SCAN" | sed -n 's/^#SCAN \([a-z]*\).*/\1/p' | head -1)
LIVE=$(printf '%s\n' "$SCAN" | grep '^LIVE' || true)
AGE=$(since_launch)

if [ "$MODE" = "--check" ]; then
  if [ "$STATUS" != "ok" ]; then
    echo "Familiar: UNKNOWN ($(printf '%s\n' "$SCAN" | sed -n 's/^#SCAN fail //p'))"
  elif [ -n "$LIVE" ]; then
    echo "Familiar: LIVE"
    printf '%s\n' "$LIVE" | cut -f2- | sed 's/^/  /'
  else
    echo "Familiar: NONE listed (interactive seats are not visible to this scan)"
  fi
  if [ "$AGE" -ge 0 ] 2>/dev/null; then echo "last launch: ${AGE}s ago"; else echo "last launch: no record"; fi
  probe
  exit 0
fi

if [ "$MODE" = "--ensure" ]; then
  if [ "$STATUS" != "ok" ]; then
    echo "REFUSED: cannot tell whether a Familiar is live ($(printf '%s\n' "$SCAN" | sed -n 's/^#SCAN fail //p')). Re-run with --force if you are sure." >&2
    exit 3
  fi
  if [ -n "$LIVE" ]; then
    echo "A Familiar is already live; not launching another:"
    printf '%s\n' "$LIVE" | cut -f2- | sed 's/^/  /'
    exit 0
  fi
  if [ "$AGE" -ge 0 ] 2>/dev/null && [ "$AGE" -lt "$GRACE" ]; then
    echo "A Familiar was launched ${AGE}s ago and may still be booting; not launching another (grace ${GRACE}s)."
    exit 0
  fi
fi

if ! PROBE=$(probe); then
  echo "REFUSED: $PROBE. A Familiar without proven enforcement is not launched." >&2
  exit 4
fi
echo "$PROBE"
do_launch
