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
# ENFORCEMENT PROBE: before any launch (and in --check) it reads the installed def's frontmatter
# hooks.PreToolUse, requires matcher `Bash` -> exactly the Familiar bash hook and matcher
# `Write|Edit|MultiEdit|NotebookEdit` -> exactly the write hook, and runs THOSE command strings
# with a payload each must refuse (a hook that is missing exits 127, which fails OPEN in Claude
# Code, so only rc 2 plus the hook's own message counts). It refuses a project-level
# .claude/agents/ship-familiar.md (that one would win) and any settings file that sets
# disableAllHooks. A seat whose bright lines are unproven is not launched (exit 4). The user
# config dir is $CLAUDE_CONFIG_DIR, else ~/.claude, as Claude Code resolves it.
#
# PERMISSION MODE: auto by default. SHIP_FAMILIAR_PERMISSION_MODE=bypassPermissions is the
# fallback for accounts without auto mode; the hooks fire in either mode.
#
# SANDBOX: point SHIP_SANDBOX_RUN at a wrapper that runs `claude <args>` sandboxed; absent, bare
# claude. Bash 3.2 compatible. Env seams for tests: SHIP_ROOT, SHIP_CLAUDE_BIN.

set -uo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SHIP="${SHIP_ROOT:-$KIT}"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
AGENT_DEF="$CLAUDE_HOME/agents/ship-familiar.md"
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
  local plan bad="" kind cmd payload want out rc
  plan=$(python3 -I - "$AGENT_DEF" "$SHIP" "$CLAUDE_HOME" <<'PY'
import json, os, re, sys
agent_def, ship, home = sys.argv[1:4]
bad = []
for f in (os.path.join(home, "settings.json"), os.path.join(home, "settings.local.json"),
          os.path.join(ship, ".claude", "settings.json"),
          os.path.join(ship, ".claude", "settings.local.json")):
    if os.path.exists(f):
        try:
            if json.load(open(f, encoding="utf-8")).get("disableAllHooks"):
                bad.append("%s sets disableAllHooks" % f)
        except Exception:
            bad.append("%s is unreadable, so disableAllHooks cannot be ruled out" % f)
if os.path.exists(os.path.join(ship, ".claude", "agents", "ship-familiar.md")):
    bad.append("a project-level .claude/agents/ship-familiar.md would win over the installed def")


def unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v


entries = []
if not os.path.isfile(agent_def):
    bad.append("agent def not installed at %s" % agent_def)
else:
    lines = open(agent_def, encoding="utf-8").read().splitlines()
    fm = lines[1:lines.index("---", 1)] if lines[:1] == ["---"] and "---" in lines[1:] else []
    in_hooks = in_pre = False
    matcher = kind = None
    for ln in fm:
        if re.match(r"^\S", ln):
            in_hooks, in_pre = ln.rstrip() == "hooks:", False
            continue
        if in_hooks and re.match(r"^\s+PreToolUse:\s*$", ln):
            in_pre = True
            continue
        if not in_pre:
            continue
        m = re.match(r"^\s*(?:-\s*)?(matcher|type|command):\s*(.*)$", ln)
        if m:
            key, val = m.group(1), unquote(m.group(2))
            if key == "matcher":
                matcher, kind = val, None
            elif key == "type":
                kind = val
            else:
                entries.append((matcher, kind, val))
want = {"Bash": "/modules/familiar/hooks/validate-familiar-bash.sh",
        "Write|Edit|MultiEdit|NotebookEdit": "/modules/familiar/hooks/validate-familiar-write.sh"}
if os.path.isfile(agent_def):
    if sorted(m for m, _, _ in entries) != sorted(want) or \
            any(k != "command" or not c.endswith(want.get(m, "\0")) for m, k, c in entries):
        bad.append("%s's frontmatter does not wire exactly Bash -> validate-familiar-bash.sh "
                   "and Write|Edit|MultiEdit|NotebookEdit -> validate-familiar-write.sh" % agent_def)
for b in bad:
    print("BAD\t" + b)
if not bad:
    for m, _, c in entries:
        print("CMD\t%s\t%s" % ("bash" if m == "Bash" else "write", c))
PY
  ) || bad="; the frontmatter parser failed"
  while IFS="$(printf '\t')" read -r kind cmd payload; do
    case "$kind" in
      BAD) bad="$bad; $cmd" ;;
      CMD)
        if [ "$cmd" = bash ]; then
          out=$(printf '{"tool_input":{"command":"echo x > /tmp/ship-probe"}}' | bash -c "$payload" 2>&1); rc=$?
          want="familiar-bash DENY"
        else
          out=$(printf '{"tool_input":{"file_path":"/etc/ship-probe.md"}}' | bash -c "$payload" 2>&1); rc=$?
          want="familiar-write DENY"
        fi
        if [ "$rc" -ne 2 ] || [[ "$out" != *"$want"* ]]; then
          bad="$bad; the wired $cmd hook did not refuse its probe (rc=$rc): $payload"
        fi
        ;;
    esac
  done <<EOF
$plan
EOF
  if [ -z "$bad" ]; then echo "hooks: OK (the hooks $AGENT_DEF wires both refused their probes)"; return 0; fi
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
