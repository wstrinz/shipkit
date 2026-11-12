#!/bin/bash
# validate-familiar-bash.sh — PreToolUse hook (matcher Bash) for the ship-familiar agent.
#
# The Familiar's shell is a POSITIVE allow-list: read-only inspection commands, git and gh
# reads, `claude agents`, and a short list of lifecycle helpers with pinned arguments. Default
# is DENY. Without this lane the Write/Edit allow-list would be decoration: `echo … > queue.md`
# reaches the same file.
#
# Deliberately NOT a delegation to core's validate-readonly-bash.sh: that lane allows `env CMD`,
# `xargs CMD` and `> file` redirects, each of which runs or writes anything.
#
# The checker between the SHIP-POSITIVE-LANE markers is shared verbatim with
# modules/navigator/hooks/validate-navigator-bash.sh (hooks stay self-contained single files);
# a test diffs the two blocks. Only the config above the markers differs.
#
# Fails CLOSED: missing python3, an unreadable payload, unbalanced quotes, or the checker
# crashing all exit 2.
set -u
SHIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "familiar-bash DENY: python3 not on PATH (fail closed)" >&2
  exit 2
fi

# read -d '' rather than $(cat <<EOF): bash 3.2 parses quotes and backticks inside a heredoc
# that sits in a command substitution, and the checker below contains both.
read -r -d '' PY <<'EOF'
SEAT = "familiar"
# Lifecycle helpers, by ship-relative path. None = any arguments (the helper path-locks its
# own writes); a set = the only argument lists accepted.
HELPERS = {
    "modules/familiar/scripts/familiar_drop.py": None,
    "modules/familiar/scripts/familiar_orient.py": None,
    "modules/familiar/scripts/launch-familiar.sh": {("--check",)},
    "modules/autonomous/scripts/ship-up.sh": {(), ("--check",), ("--launch-mate",)},
    "modules/autonomous/scripts/launch-bosun.sh": {("--check",), ("--ensure",)},
    "modules/autonomous/scripts/mate-lock.py": {("status",), ("status", "--json")},
}
HELPER_HINT = ("familiar_drop.py, familiar_orient.py, launch-familiar.sh --check, ship-up.sh "
               "[--check|--launch-mate], launch-bosun.sh --check|--ensure, mate-lock.py status")

# ==== SHIP-POSITIVE-LANE v1 ====
# Rules, in order:
#   - no backtick anywhere; no `$` outside single quotes (escape-aware); no unquoted `{`
#     other than a bare `{}` (brace expansion would rebuild option names the checks compare);
#   - redirects only to /dev/null or between fds 0-2; no `<`, `>`, `&`, `(` otherwise;
#   - no unquoted `#`: a shell comment would make the shell skip text these checks read, or
#     run text they think is quoted (`true #'` newline `cmd #'`);
#   - no glob characters in an option-shaped word, and no UNQUOTED glob in any argument to
#     the commands in GLOB_SHY (a hostile filename such as `--pre=sh` or `-rm` would expand
#     into an option the checks never saw); a quoted pattern (`-name '*.md'`) is fine;
#   - helpers only by absolute path, never after a `cd`, and no `cd` with options;
#   - the command splits on | || && ; and newline, and EVERY segment must pass `allowed()`.
# Nothing on the list writes a file except the helpers, and each helper path-locks its own
# writes. Quoted operators are read as operators (shlex cannot tell them apart): that only
# splits a command into more segments, so it over-blocks, never under-blocks.
import json, os, re, shlex, sys

root = os.path.realpath(sys.argv[1])


def deny(msg):
    sys.stderr.write("%s-bash DENY: %s\n" % (SEAT, msg))
    sys.exit(2)


try:
    payload = json.loads(sys.stdin.read())
except Exception:
    deny("malformed PreToolUse payload (fail closed)")
if not isinstance(payload, dict):
    deny("malformed PreToolUse payload (fail closed)")
cmd = (payload.get("tool_input") or {}).get("command")
if cmd is None or (isinstance(cmd, str) and not cmd.strip()):
    sys.exit(0)
if not isinstance(cmd, str):
    deny("malformed command (fail closed)")

cmd = re.sub(r"(?<!\\)((?:\\\\)*)\\\n", r"\1", cmd)


def unsafe(text):
    """The first shell feature the checks below cannot see through, or None."""
    if "`" in text:
        return "backtick (command substitution)"
    if re.search(r"[\x01-\x03]", text):
        return "control characters \\x01-\\x03 (reserved as glob markers)"
    quote, i = None, 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            i += 1
        elif c == "$":
            return "$-expansion (single-quote a literal $ in a search pattern)"
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif quote is None and c == "'":
            quote = "'"
        elif quote is None and c == "{" and text[i + 1:i + 2] != "}":
            return "unquoted { (brace expansion)"
        elif quote is None and c == "#":
            return "unquoted # (quote it, e.g. grep '#')"
        i += 1
    return None


why = unsafe(cmd)
if why:
    deny("no %s in the %s's shell" % (why, SEAT))

cmd = re.sub(r"(?:(?<=\s)|^)(?:[0-2]?>&[0-2]|(?:[0-2]|&)?>\s*/dev/null)(?=\s|;|\||&&|$)", " ", cmd)

# Unquoted glob characters become sentinels before lexing, so a token still says whether the
# shell would expand it after shlex has dropped the quotes. Only `* ? [` are modelled: zsh's
# EXTENDED_GLOB (`^ ~ #`) or KSH_GLOB (`@( )` etc.) would widen the set.
GLOB_MARK = {"*": "\x01", "?": "\x02", "[": "\x03"}


def mark_globs(text):
    out, quote, i = [], None, 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif quote is None and c == "'":
            quote = "'"
        elif quote is None and c in GLOB_MARK:
            c = GLOB_MARK[c]
        out.append(c)
        i += 1
    return "".join(out)


cmd = mark_globs(cmd)

SEPS = {"|", "||", "&&", ";", ";;"}
try:
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)
except ValueError:
    deny("unbalanced quotes (fail closed)")

segments, cur = [], []
for t in tokens:
    if t in SEPS:
        segments.append(cur)
        cur = []
    elif t and set(t) <= set(";&|<>()"):
        deny("operator %r is not allowed: no file redirects, background jobs or subshells. "
             "Write with the Write tool on an allowed path." % t)
    elif t.startswith("-") and re.search(r"[*?\[\]\x01-\x03]", t):
        deny("a glob in an option (%r) could expand to an option the checks never saw"
             % t.translate({1: "*", 2: "?", 3: "["}))
    else:
        cur.append(t)
segments.append(cur)
segments = [s for s in segments if s]
if not segments:
    deny("no command found (fail closed)")

READ_ONLY = {
    # no printf: zsh's builtin `printf -v NAME` assigns any parameter (functions[cat], PATH)
    "cat", "head", "tail", "wc", "ls", "stat", "file", "du", "df", "pwd", "echo",
    "grep", "egrep", "fgrep", "cut", "tr", "column", "basename", "dirname", "realpath",
    "diff", "true", "false", "which", "jq", "sort", "uniq", "tree", "rg", "find", "date", "cd",
}
FIND_ACTIONS = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0",
                "-fprintf", "-fls", "-rm"}
# Commands whose arguments include option names that run or write something; an unquoted
# glob could manufacture one from a hostile filename.
GLOB_SHY = {"sort", "tree", "file", "date", "uniq", "rg", "find", "git", "gh", "grep", "egrep",
            "fgrep"}
# grep here may be ugrep behind a shell wrapper: these run a command, write, load a config
# whose filter=/pager= lines run commands (also `---FILE`), or open a TUI.
UGREP_EXEC = ("filter", "pager", "view", "save-config", "query", "config")
GIT_READ = {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe",
            "shortlog", "grep", "ls-tree", "cat-file", "branch", "remote", "worktree"}
GH_READ = {("pr", "view"), ("pr", "list"), ("pr", "checks"), ("pr", "diff"), ("pr", "status"),
           ("run", "view"), ("run", "list"), ("issue", "view"), ("issue", "list"),
           ("repo", "view")}


def is_abbrev(arg, longname):
    """GNU-style tools accept any unambiguous prefix of a long option (`--o` for --output)."""
    if not arg.startswith("--"):
        return False
    name = arg[2:].split("=", 1)[0]
    return bool(name) and longname.startswith(name)


def short_has(arg, letters):
    """A short-option cluster (`-ao`) that contains any of `letters`."""
    return bool(re.match(r"^-[A-Za-z0-9]", arg)) and any(c in arg[1:] for c in letters)


def helper_ok(argv):
    if argv[0] in ("python3", "python", "bash", "sh"):
        if len(argv) < 2:
            return False
        script, args = argv[1], argv[2:]
    else:
        script, args = argv[0], argv[1:]
    if not os.path.isabs(script):
        return False
    rp = os.path.realpath(script)
    if not rp.startswith(root + os.sep):
        return False
    rel = os.path.relpath(rp, root).replace(os.sep, "/")
    if rel not in HELPERS:
        return False
    is_py = rel.endswith(".py")
    if argv[0] in ("python3", "python") and not is_py:
        return False
    if argv[0] in ("bash", "sh") and is_py:
        return False
    pinned = HELPERS[rel]
    return pinned is None or tuple(args) in pinned


def git_ok(args):
    while args and args[0].startswith("-"):
        if args[0] == "--no-pager":
            args = args[1:]
        elif args[0] == "-C" and len(args) > 1:
            args = args[2:]
        else:
            return False
    if not args or args[0] not in GIT_READ:
        return False
    sub, rest = args[0], args[1:]
    for a in rest:
        if is_abbrev(a, "output") or is_abbrev(a, "ext-diff"):
            return False
        if sub == "grep" and (is_abbrev(a, "open-files-in-pager") or short_has(a, "O")):
            return False
    if sub == "branch":
        listing = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--verbose", "--list", "-l",
                   "--show-current", "--contains", "--merged", "--no-merged"}
        if any(a.startswith("-") and a not in listing for a in rest):
            return False
        # not `-l`: on git < 2.19 it means --create-reflog, so `git branch -l foo` creates foo
        if any(not a.startswith("-") for a in rest) and not ({"--list", "--contains",
                                                                "--merged", "--no-merged"} & set(rest)):
            return False
    if sub == "remote" and rest not in ([], ["-v"]) and (not rest or rest[0] not in ("show", "get-url")):
        return False
    if sub == "worktree" and rest[:1] != ["list"]:
        return False
    return True


def gh_ok(args):
    if len(args) >= 2 and (args[0], args[1]) in GH_READ:
        return True
    if not args or args[0] != "api":
        return False
    for i, a in enumerate(args):
        if re.match(r"^-[a-zA-Z]*[fF]|^--(field|raw-field|input)(=|$)|^--hostname", a):
            return False
        m = re.match(r"^(?:-[a-zA-Z]*X|--method)=?(.*)$", a)
        if m:
            method = m.group(1) or (args[i + 1] if i + 1 < len(args) else "")
            if method.upper() != "GET":
                return False
    return True


def uniq_ok(rest):
    # Any word after the input operand is an OUTPUT file to uniq, including a `-word`
    # (macOS reads `uniq IN -OUT` that way). So nothing may follow the first operand.
    opts = True
    for i, a in enumerate(rest):
        if opts and a == "--":
            opts = False
        elif not opts or a == "-" or not a.startswith("-"):
            return i == len(rest) - 1
    return True


def allowed(argv, seen_cd):
    w = argv[0]
    if not seen_cd and helper_ok(argv):
        return True
    if w in GLOB_SHY and any(re.search(r"[\x01-\x03]", a) for a in argv[1:]):
        return False
    if w in READ_ONLY:
        rest = argv[1:]
        if w == "cd" and any(a.startswith("-") for a in rest):
            return False
        if w == "find" and FIND_ACTIONS & set(rest):
            return False
        if w in ("grep", "egrep", "fgrep") and any(
                short_has(a, "Q") or a.startswith("---")
                or any(is_abbrev(a, n) for n in UGREP_EXEC) for a in rest):
            return False
        if w == "sort" and any(is_abbrev(a, "output") or is_abbrev(a, "compress-program")
                               or short_has(a, "o") for a in rest):
            return False
        if w == "rg" and any(a.startswith("--pre") or is_abbrev(a, "hostname-bin") for a in rest):
            return False
        if w == "tree" and any(short_has(a, "oR") for a in rest):
            return False
        if w == "file" and any(short_has(a, "C") or is_abbrev(a, "compile") for a in rest):
            return False
        if w == "date" and any(is_abbrev(a, "set") or (short_has(a, "s") and not a.startswith("-I"))
                               for a in rest):
            return False
        if w == "uniq" and not uniq_ok(rest):
            return False
        return True
    if w == "git":
        return git_ok(argv[1:])
    if w == "gh":
        return gh_ok(argv[1:])
    if w == "claude":
        return argv[1:] in (["agents"], ["agents", "--json"])
    return False


seen_cd = False
for seg in segments:
    if not allowed(seg, seen_cd):
        deny("%r is not on the %s's shell allow-list. Allowed: file inspection and search, git "
             "and gh reads, `claude agents`%s. Anything else is a command to the Mate."
             % (" ".join(seg)[:120], SEAT, (", " + HELPER_HINT + " (absolute paths, no cd "
                                                 "first)") if HELPERS else ""))
    seen_cd = seen_cd or seg[0] == "cd"
sys.exit(0)
# ==== end SHIP-POSITIVE-LANE ====
EOF

# -I: isolated mode, so a json.py or re.py in the session's cwd cannot shadow the stdlib.
python3 -I -c "$PY" "$SHIP_DIR"
rc=$?
[ "$rc" -eq 0 ] && exit 0
exit 2
