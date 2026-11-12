#!/bin/bash
# Test suite for validate-familiar-bash.sh (the Familiar's positive shell lane).
# Usage: bash modules/familiar/tests/test-familiar-bash.sh
#
# Runs the hook from a copy inside a throwaway ship tree. Helper paths are judged by realpath,
# so the helpers themselves need not exist there except for the symlink case at the end.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)/hooks/validate-familiar-bash.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/familiar-bash.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/ship"
mkdir -p "$ROOT/modules/familiar/hooks" "$ROOT/modules/familiar/scripts"
cp "$SRC" "$ROOT/modules/familiar/hooks/"
HOOK="$ROOT/modules/familiar/hooks/validate-familiar-bash.sh"
ROOT="$(cd "$ROOT" && pwd -P)"

PASS=0; FAIL=0
check() { # check ALLOW|DENY <command> [cwd]
  local want="$1" cmd="$2" cwd="${3:-$ROOT}" json out got
  json=$(python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd")
  out=$(printf '%s' "$json" | bash "$HOOK" 2>&1)
  case $? in 0) got=ALLOW ;; 2) got=DENY ;; *) got="ERROR($?)" ;; esac
  # A crash or a bash parse error also exits 2; only the checker's own verdict counts.
  [ "$got" = DENY ] && [[ "$out" != *"familiar-bash DENY"* ]] && got="CRASH"
  if [ "$got" = "$want" ]; then PASS=$((PASS+1)); else
    FAIL=$((FAIL+1)); printf '  FAIL: want %s got %s: %s\n    %s\n' "$want" "$got" "$cmd" "$out"; fi
}

echo "=== read-only inspection (ALLOW) ==="
check ALLOW 'ls -la'
check ALLOW 'cat queue.md'
check ALLOW "rg -n '^## Note to tomorrow\$' logs/familiar"
check ALLOW 'find . -name "*.md" -newer state/status.json'
check ALLOW 'sort -k2 a.txt | uniq -c | head -5'
check ALLOW 'ls missing 2>/dev/null'
check ALLOW 'git log --oneline -5 2>&1 | tail -3'
check ALLOW 'tail -1 state/bosun-heartbeat.log; date -u'
check ALLOW 'grep -c steer inbox/drops/a.md && echo found'
check ALLOW ''

echo "=== git, gh, claude reads (ALLOW) ==="
check ALLOW 'git status'
check ALLOW 'git -C /some/repo log --oneline -5'
check ALLOW 'git --no-pager diff --stat'
check ALLOW 'git branch --show-current'
check ALLOW 'git branch -a'
check ALLOW 'git worktree list'
check ALLOW 'git remote -v'
check ALLOW 'gh pr view 12 --json state'
check ALLOW 'gh api repos/o/r/pulls'
check ALLOW 'gh api -X GET repos/o/r'
check ALLOW 'claude agents --json'

echo "=== helpers (ALLOW) ==="
check ALLOW "python3 $ROOT/modules/familiar/scripts/familiar_orient.py --open-log"
check ALLOW "python3 $ROOT/modules/familiar/scripts/familiar_drop.py send state/familiar/drafts/x.md"
check ALLOW "$ROOT/modules/familiar/scripts/familiar_drop.py validate inbox/drops/x.md"
check ALLOW "bash $ROOT/modules/familiar/scripts/launch-familiar.sh --check"
check ALLOW "bash $ROOT/modules/autonomous/scripts/launch-bosun.sh --ensure"
check ALLOW "$ROOT/modules/autonomous/scripts/ship-up.sh --launch-mate"
check ALLOW "$ROOT/modules/autonomous/scripts/ship-up.sh"
check ALLOW "python3 $ROOT/modules/autonomous/scripts/mate-lock.py status --json"
check ALLOW "ls && python3 $ROOT/modules/familiar/scripts/familiar_orient.py"

echo "=== writes and executors (DENY) ==="
check DENY 'echo x > queue.md'
check DENY 'echo x >> logs/familiar/a.md'
check DENY 'echo x>projects/p/tickets/T.md'
check DENY 'ls &> out.txt'
check DENY 'cat a | tee b'
check DENY 'cp a b'
check DENY 'mv inbox/familiar/a.md inbox/familiar/read/'
check DENY 'rm x'
check DENY 'touch x'
check DENY 'mkdir x'
check DENY 'sed -i s/a/b/ f'
check DENY "env python3 -c 'print(1)'"
check DENY 'echo a | xargs touch'
check DENY "python3 -c 'print(1)'"
check DENY "bash -c 'ls'"
check DENY 'cat a | bash'
check DENY 'FOO=1 ls'
check DENY 'find . -delete'
check DENY 'find . -exec rm {} +'
check DENY 'sort -o out in'
check DENY 'sort -ro out in'
check DENY 'rg --pre=cat x'
check DENY 'date -s 2020-01-01'
check DENY 'uniq in out'
check DENY 'file -C -m x'
check DENY 'curl -s https://example.com'

echo "=== expansion, operators, quoting (DENY) ==="
check DENY 'echo $(id)'
check DENY 'echo "$HOME"'
check DENY 'echo `id`'
check DENY "echo \"it's \$(id)\""
check DENY 'ls & rm x'
check DENY '(ls)'
check DENY 'cat < /etc/hosts'
check DENY "echo 'unbalanced"
check DENY "$(printf 'ls\nrm x')"
check DENY "$(printf 'git pu\\\nsh')"

echo "=== git, gh, claude writes (DENY) ==="
check DENY 'git commit -m x'
check DENY 'git push'
check DENY 'git -c core.pager=sh log'
check DENY 'git log --output=/tmp/x'
check DENY 'git diff --ext-diff'
check DENY 'git grep -Ovim x'
check DENY 'git branch -D old'
check DENY 'git branch newbranch'
check DENY 'git checkout main'
check DENY 'git worktree add ../x'
check DENY 'git remote add o url'
check DENY 'gh pr merge 1'
check DENY 'gh pr create --draft'
check DENY 'gh api -X POST repos/o/r/issues'
check DENY 'gh api -XPOST repos/o/r/issues'
check DENY 'gh api -iX DELETE repos/o/r'
check DENY 'gh api --method=PATCH repos/o/r'
check DENY 'gh api -f title=x repos/o/r/issues'
check DENY 'gh api -F x=@f repos/o/r'
check DENY 'gh api --input body.json repos/o/r'
check DENY 'claude --bg --agent ship-mate'
check DENY 'claude agents stop abc'

echo "=== helper spellings (DENY) ==="
check DENY 'bash modules/familiar/scripts/launch-familiar.sh --ensure'
check DENY 'bash modules/familiar/scripts/launch-familiar.sh --force'
check DENY 'modules/autonomous/scripts/launch-bosun.sh --force'
check DENY 'modules/autonomous/scripts/ship-up.sh --rotate-mate'
check DENY 'python3 modules/autonomous/scripts/mate-lock.py release s --force'
check DENY 'python3 modules/familiar/scripts/../../autonomous/scripts/bosun_emit.py drop x'
check DENY 'python3 /tmp/elsewhere/familiar_drop.py send x'
check DENY 'bash modules/familiar/scripts/familiar_drop.py send x'
check DENY 'python3 modules/familiar/scripts/launch-familiar.sh --check'
check DENY 'python3 -I modules/familiar/scripts/familiar_drop.py send x'
check DENY 'cd /tmp && python3 modules/familiar/scripts/familiar_drop.py send x'
check DENY 'cd && python3 modules/familiar/scripts/familiar_drop.py send x'
check DENY 'cd - && python3 modules/familiar/scripts/familiar_drop.py send x'
check DENY "bash $ROOT/modules/familiar/scripts/launch-familiar.sh"
check DENY 'python3 modules/familiar/scripts/familiar_orient.py'
check DENY "cd $ROOT && python3 modules/familiar/scripts/familiar_drop.py archive note.md"
check DENY "cd /tmp && python3 $ROOT/modules/familiar/scripts/familiar_orient.py"
check DENY 'cd -P /tmp'

echo "=== gate bypasses (DENY) ==="
check DENY "$(printf 'ls #\ncp state/familiar/q.md queue.md')"
check DENY 'cat x#; cp state/familiar/q.md queue.md'
check DENY "echo \\' \`cp state/familiar/q.md queue.md\` \\'"
check DENY "echo \"\\\" '\" \`cp state/familiar/q.md queue.md\` \"'\""
check DENY "echo 'literal \`backtick\`'"
check DENY "echo \\'\$(id)\\'"
check DENY "find state/familiar/p.md -{true,exec} bash {} ';'"
check DENY 'ls {a..c}'
check DENY 'find . -exe[c] rm'
check DENY 'sort --o=queue.md a'
check DENY 'sort --comp=sh a'
check DENY 'git grep --untracked --op=bash -e . -- state/familiar/p.md'
check DENY 'git grep -iOvim x'
check DENY 'git log --outp=x'
check DENY 'git diff --ext=x'
check DENY 'file --compile -m x'
check DENY 'tree -ao out'
check DENY 'date --se=2020-01-01'
check DENY 'cat a | uniq - queue.md'
check DENY 'uniq -- a b'
check DENY 'ls # a trailing comment'

echo "=== gate 2 bypasses (DENY) ==="
check DENY "$(printf "true #'\nprintf 'source: familiar' > queue.md #'")"
check DENY "$(printf 'true #\\\npython3 -c "open(%squeue.md%s,%sa%s).write(%sx%s)"' "'" "'" "'" "'" "'" "'")"
check DENY 'rg --hostname-bin=/usr/bin/true -l x README.md'
check DENY 'rg --hostname-b=/usr/bin/true x'
check DENY 'rg --host /usr/bin/true x'
check DENY 'uniq a.md -out.md'
check DENY 'uniq -c a.md -out.md'
check DENY 'gh api --hostname example.com /x'
check DENY 'gh api --hostname=example.com /x'
check DENY 'tree -R'
check DENY 'tree -H . -R'
check DENY 'sort *.md'
check DENY 'uniq ?.md'
check DENY 'file [a].md'
check DENY 'tree d*'
check ALLOW "grep -c '#' a.md"
check ALLOW 'uniq a.md'
check ALLOW 'ls *.md'

echo "=== re-gate: printf, ugrep config, glob markers ==="
check DENY "printf -v 'functions[cat]' 'touch /tmp/l4-pwn' && cat /dev/null"
check DENY "printf %d 'path[1]'"
check DENY 'printf x'
check DENY 'grep --config=x y'
check DENY 'grep --config y'
check DENY 'grep ---x y'
check DENY "rg x '*'*"
check DENY "$(printf 'rg x a\001b')"
check ALLOW 'rg x \*'
check ALLOW 'rg x "*"'
check ALLOW 'echo hello'

echo "=== gate 3 (DENY) ==="
check DENY 'find . -name x -rm'
check DENY 'find . "-rm"'
check DENY 'find /tmp/nonexistent-l4 -name x -rm'
check DENY 'rg x *'
check DENY 'find * -name x'
check DENY 'git log -- *'
check DENY 'grep -r x *'
check DENY 'gh api *'
check DENY 'git branch -l foo'
check DENY 'grep --filter=sh x a.md'
check DENY 'grep --filt=sh x a.md'
check DENY 'grep --pager=sh x a.md'
check DENY 'grep --view=sh x a.md'
check DENY 'grep --save-config'
check DENY 'grep -Q x'
check DENY 'egrep --query x'
check DENY 'fgrep -rQ x'
check ALLOW "find . -name '*.md'"
check ALLOW "rg -g '*.md' x"
check ALLOW "git diff -- '*.md'"
check ALLOW 'git branch --list "v3*"'
check ALLOW 'grep -rn --include=x x .'
check ALLOW "echo '\$HOME'"
check ALLOW 'echo "\$"'
check ALLOW 'find . -name x -print'
check ALLOW 'sort --reverse a'
check ALLOW 'uniq -c a'

echo "=== symlinked helper pointing outside the ship (DENY) ==="
printf 'print("not the helper")\n' > "$TMP/evil.py"
ln -s "$TMP/evil.py" "$ROOT/modules/familiar/scripts/familiar_drop.py"
check DENY "python3 $ROOT/modules/familiar/scripts/familiar_drop.py send x"

echo "=== a json.py in the session cwd cannot shadow the stdlib (DENY) ==="
mkdir -p "$TMP/evilcwd" && printf 'import sys\nsys.exit(0)\n' > "$TMP/evilcwd/json.py"
out=$(cd "$TMP/evilcwd" && printf '{"tool_input":{"command":"cp a b"}}' | bash "$HOOK" 2>&1); rc=$?
if [ "$rc" -eq 2 ] && [[ "$out" == *"familiar-bash DENY"* ]]; then PASS=$((PASS+1)); else
  FAIL=$((FAIL+1)); echo "  FAIL: cwd json.py shadowed the stdlib (rc=$rc)"; fi

echo "=== malformed payloads (DENY, fail closed) ==="
for p in 'not json' '["x"]' '{"tool_input":{"command":7}}'; do
  if printf '%s' "$p" | bash "$HOOK" >/dev/null 2>&1; then
    FAIL=$((FAIL+1)); echo "  FAIL: malformed payload allowed: $p"
  else PASS=$((PASS+1)); fi
done

echo
echo "validate-familiar-bash: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
